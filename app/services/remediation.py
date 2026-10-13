"""Automated remediation.

* ``build_plan``  - what *could* be fixed, how many cells/rows it would touch
  and whether the fix is "safe" (mechanical, loses no information a human
  would need) or opt-in (changes values and needs review).
* ``apply_remediation`` - runs the chosen operations on a COPY of the data and
  returns the cleaned frame, an exact change log and before/after statistics.

The user's original file and the working DataFrame are never modified. Order
matters: duplicates are removed *before* imputation (imputing first can turn
distinct rows into false duplicates).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.config import AnalysisConfig
from app.services.anomaly import run_statistical_detection, select_features
from app.services.quality import assess_quality
from app.utils.helpers import is_numeric_series, is_text_series, json_safe, rnd

SAFE_OPERATIONS = ["standardize_column_names", "trim_whitespace", "normalize_categories", "remove_duplicates"]
OPT_IN_OPERATIONS = ["impute_missing", "invalid_to_missing", "winsorize"]
ALL_OPERATIONS = SAFE_OPERATIONS + OPT_IN_OPERATIONS
ORDER = ["standardize_column_names", "trim_whitespace", "normalize_categories", "invalid_to_missing",
         "remove_duplicates", "winsorize", "impute_missing"]
DEFAULT_OPTIONS = {"numeric_strategy": "median", "categorical_strategy": "mode", "winsorize_multiplier": 3.0}
_NUMERIC_STRATEGIES = {"median", "mean", "zero", "drop_rows", "none"}
_CATEGORICAL_STRATEGIES = {"mode", "unknown", "drop_rows", "none"}


# --------------------------------------------------------------------------
# Plan
# --------------------------------------------------------------------------
def build_plan(df: pd.DataFrame, quality: dict, quality_internal: dict, features: List[str],
               cfg: AnalysisConfig, load_meta: Optional[dict] = None) -> List[dict]:
    rows = len(df)
    plan: List[dict] = []
    load_meta = load_meta or {}

    renamed = int(load_meta.get("columns_renamed", 0) or 0)
    plan.append({"operation": "standardize_column_names", "label": "Standardize column names",
                 "description": "Column names are converted to lowercase snake_case. Already applied to the "
                                "working copy; the original file keeps its original headers.",
                 "affected": renamed, "unit": "columns", "safe": True, "default": True})
    ws = sum(d["whitespace_issues"] for d in quality["consistency"]["columns"].values())
    if ws:
        plan.append({"operation": "trim_whitespace", "label": "Trim leading/trailing spaces",
                     "description": "Remove stray spaces around text values.", "affected": ws,
                     "unit": "cells", "safe": True, "default": True})
    variants = 0
    for d in quality["consistency"]["columns"].values():
        for g in d["variant_groups"]:
            variants += sum(g["variants"].values()) - max(g["variants"].values())
    if variants:
        plan.append({"operation": "normalize_categories", "label": "Unify category spelling / case",
                     "description": "Rewrite variants such as 'delhi' / 'DELHI' to the most common spelling.",
                     "affected": variants, "unit": "cells", "safe": True, "default": True})
    if quality["duplicates"]["count"]:
        plan.append({"operation": "remove_duplicates", "label": "Remove exact duplicate rows",
                     "description": "Keep the first occurrence of every fully identical row.",
                     "affected": quality["duplicates"]["count"], "unit": "rows", "safe": True, "default": True})

    imputable = sum(v["count"] for c, v in quality["missing"]["columns"].items()
                    if 0 < v["pct"] <= cfg.max_missing_col_pct_for_impute)
    if imputable:
        plan.append({"operation": "impute_missing", "label": "Fill missing values",
                     "description": "Numeric columns: median (configurable). Categorical: most frequent "
                                    f"value (configurable). Columns over {cfg.max_missing_col_pct_for_impute:.0f}% "
                                    "missing are skipped.",
                     "affected": imputable, "unit": "cells", "safe": False, "default": False,
                     "options": {"numeric_strategy": sorted(_NUMERIC_STRATEGIES),
                                 "categorical_strategy": sorted(_CATEGORICAL_STRATEGIES)}})
    bad = sum(len(i["indices"]) for i in quality_internal["rule_rows"].values())
    if bad:
        plan.append({"operation": "invalid_to_missing", "label": "Blank out out-of-range values",
                     "description": "Set values that break validity rules (e.g. age 185) to missing so they "
                                    "can be reviewed or imputed. Never applied automatically.",
                     "affected": bad, "unit": "cells", "safe": False, "default": False})
    cap = 0
    m = DEFAULT_OPTIONS["winsorize_multiplier"]
    for f in features:
        v = pd.to_numeric(df[f], errors="coerce")
        q1, q3 = v.quantile(0.25), v.quantile(0.75)
        iqr = q3 - q1
        if iqr > 0:
            cap += int(((v < q1 - m * iqr) | (v > q3 + m * iqr)).sum())
    if cap:
        plan.append({"operation": "winsorize", "label": "Cap extreme values",
                     "description": f"Clip values beyond {m:g}×IQR outside the quartiles to that boundary. "
                                    "Opt-in only: it changes real values.",
                     "affected": cap, "unit": "cells", "safe": False, "default": False})
    return plan


# --------------------------------------------------------------------------
# Snapshot (same canonical quality function as the analysis)
# --------------------------------------------------------------------------
def snapshot(df: pd.DataFrame, cfg: AnalysisConfig, coerced: Optional[dict] = None) -> dict:
    quality, internal = assess_quality(df, cfg, coerced)
    features, excluded = select_features(df, cfg)
    stat_records = 0
    if features:
        _, _, public = run_statistical_detection(df, features, excluded, cfg)
        stat_records = public["records_flagged"]
    s = quality["summary"]
    return {"rows": s["rows"], "columns": s["columns"], "missing_values": s["missing_values"],
            "duplicate_rows": s["duplicate_rows"], "invalid_rows": s["invalid_rows"],
            "inconsistent_rows": s["inconsistent_rows"], "quality_score": quality["overall_score"],
            "statistical_anomaly_records": stat_records}


# --------------------------------------------------------------------------
# Apply
# --------------------------------------------------------------------------
def _text_columns(df: pd.DataFrame) -> List[str]:
    return [c for c in df.columns if is_text_series(df[c])]


def apply_remediation(df: pd.DataFrame, operations: Optional[List[str]], options: Optional[dict],
                      quality: dict, quality_internal: dict, features: List[str], cfg: AnalysisConfig,
                      coerced: Optional[dict] = None) -> Tuple[pd.DataFrame, dict]:
    opts = {**DEFAULT_OPTIONS, **{k: v for k, v in (options or {}).items() if v is not None}}
    if opts["numeric_strategy"] not in _NUMERIC_STRATEGIES:
        raise ValueError(f"numeric_strategy must be one of {sorted(_NUMERIC_STRATEGIES)}")
    if opts["categorical_strategy"] not in _CATEGORICAL_STRATEGIES:
        raise ValueError(f"categorical_strategy must be one of {sorted(_CATEGORICAL_STRATEGIES)}")
    selected = SAFE_OPERATIONS if not operations else operations
    unknown = [o for o in selected if o not in ALL_OPERATIONS]
    if unknown:
        raise ValueError(f"Unknown remediation operation(s): {', '.join(unknown)}")

    before = snapshot(df, cfg, coerced)
    work = df.copy()                                     # the original frame is never touched
    changes: List[dict] = []

    for column, info in (coerced or {}).items():
        changes.append({"operation": "coerce_numeric", "column": column, "cells_changed": info["count"],
                        "detail": "Non-numeric text in a numeric column was cleared (values: "
                                  + ", ".join(repr(e) for e in info["examples"][:3]) + ").", "examples": []})

    for op in [o for o in ORDER if o in selected]:
        if op == "standardize_column_names":
            changes.append({"operation": op, "column": None, "cells_changed": 0,
                            "detail": "Column names are lowercase snake_case in the cleaned copy.",
                            "examples": []})

        elif op == "trim_whitespace":
            for column in _text_columns(work):
                s = work[column]
                mask = s.notna() & (s.astype(str) != s.astype(str).str.strip())
                if mask.any():
                    ex = [{"before": repr(a), "after": repr(str(a).strip())} for a in s[mask].head(3)]
                    work[column] = s.where(~mask, s.astype(str).str.strip())
                    changes.append({"operation": op, "column": column, "cells_changed": int(mask.sum()),
                                    "detail": "Removed leading/trailing spaces.", "examples": ex})

        elif op == "normalize_categories":
            for column in list(quality["consistency"]["columns"]):
                if column not in work.columns or not is_text_series(work[column]):
                    continue
                s = work[column]
                present = s.notna()
                text = s[present].astype(str).str.strip()
                key = text.str.lower().str.replace(r"\s+", " ", regex=True)
                dominant = text.groupby(key).agg(lambda x: x.value_counts().index[0])
                new = key.map(dominant)
                changed = new != text
                if changed.any():
                    ex = [{"before": repr(a), "after": repr(b)}
                          for a, b in zip(text[changed].head(3), new[changed].head(3))]
                    work.loc[new.index, column] = new
                    changes.append({"operation": op, "column": column, "cells_changed": int(changed.sum()),
                                    "detail": "Unified spelling/case to the most common variant.", "examples": ex})

        elif op == "invalid_to_missing":
            for column, info in quality_internal["rule_rows"].items():
                idx = [i for i in info["indices"] if i in work.index]
                if idx:
                    ex = [{"before": str(work.at[i, column]), "after": "missing"} for i in idx[:3]]
                    work.loc[idx, column] = np.nan
                    changes.append({"operation": op, "column": column, "cells_changed": len(idx),
                                    "detail": f"Set values outside the valid range ({info['rule']['source']}) "
                                              f"to missing.", "examples": ex})

        elif op == "remove_duplicates":
            dup = work.duplicated(keep="first")
            if dup.any():
                changes.append({"operation": op, "column": None, "rows_removed": int(dup.sum()),
                                "cells_changed": 0,
                                "detail": f"Removed {int(dup.sum())} exact duplicate row(s), keeping the first occurrence.",
                                "examples": [{"before": f"row {int(i) + 2}", "after": "removed"}
                                             for i in work.index[dup.values][:3]]})
                work = work[~dup]

        elif op == "winsorize":
            m = float(opts["winsorize_multiplier"])
            for f in [f for f in features if f in work.columns]:
                v = pd.to_numeric(work[f], errors="coerce")
                p = v.dropna()
                if p.empty:
                    continue
                q1, q3 = p.quantile(0.25), p.quantile(0.75)
                iqr = q3 - q1
                if iqr <= 0:
                    continue
                lo, hi = q1 - m * iqr, q3 + m * iqr
                mask = (v < lo) | (v > hi)
                if mask.any():
                    ex = [{"before": f"{a:g}", "after": f"{min(max(a, lo), hi):g}"} for a in v[mask].head(3)]
                    work.loc[mask.index[mask], f] = v[mask].clip(lo, hi)
                    changes.append({"operation": op, "column": f, "cells_changed": int(mask.sum()),
                                    "detail": f"Capped values outside [{lo:g}, {hi:g}] (±{m:g}×IQR).",
                                    "examples": ex})

        elif op == "impute_missing":
            drop_mask = pd.Series(False, index=work.index)
            for column in work.columns:
                s = work[column]
                miss = s.isna()
                if not miss.any():
                    continue
                pct = miss.mean() * 100
                if pct > cfg.max_missing_col_pct_for_impute:
                    changes.append({"operation": op, "column": column, "cells_changed": 0,
                                    "detail": f"Skipped: {pct:.0f}% missing is too much to impute reliably.",
                                    "examples": []})
                    continue
                if is_numeric_series(s):
                    strat = opts["numeric_strategy"]
                    if strat == "none":
                        continue
                    if strat == "drop_rows":
                        drop_mask |= miss
                        continue
                    fill = {"median": s.median(), "mean": s.mean(), "zero": 0.0}[strat]
                    if pd.isna(fill):
                        continue
                    work[column] = s.fillna(fill)
                    changes.append({"operation": op, "column": column, "cells_changed": int(miss.sum()),
                                    "detail": f"Filled missing values with the {strat}"
                                              f"{'' if strat == 'zero' else f' ({fill:.4g})'}.",
                                    "examples": []})
                elif is_text_series(s):
                    strat = opts["categorical_strategy"]
                    if strat == "none":
                        continue
                    if strat == "drop_rows":
                        drop_mask |= miss
                        continue
                    mode = s.mode(dropna=True)
                    fill = "Unknown" if strat == "unknown" or mode.empty else str(mode.iloc[0])
                    work[column] = s.fillna(fill)
                    changes.append({"operation": op, "column": column, "cells_changed": int(miss.sum()),
                                    "detail": f"Filled missing values with '{fill}'.", "examples": []})
            if drop_mask.any():
                changes.append({"operation": op, "column": None, "rows_removed": int(drop_mask.sum()),
                                "cells_changed": 0,
                                "detail": f"Dropped {int(drop_mask.sum())} row(s) containing missing values.",
                                "examples": []})
                work = work[~drop_mask]

    work = work.reset_index(drop=True)
    after = snapshot(work, cfg)
    summary = {
        "operations_applied": [o for o in ORDER if o in selected],
        "options": opts, "rows_before": before["rows"], "rows_after": after["rows"],
        "cells_changed": int(sum(c.get("cells_changed", 0) for c in changes)),
        "rows_removed": int(sum(c.get("rows_removed", 0) for c in changes)),
        "changes": changes, "before": before, "after": after,
        "improvement": {k: rnd(after[k] - before[k], 2) for k in
                        ("quality_score", "missing_values", "duplicate_rows", "invalid_rows",
                         "inconsistent_rows", "statistical_anomaly_records")},
        "note": "The original dataset is unchanged; this is a cleaned copy. Anomaly counts here are "
                "statistical (IQR/Z-score) records only, measured the same way before and after.",
    }
    return work, json_safe(summary)
