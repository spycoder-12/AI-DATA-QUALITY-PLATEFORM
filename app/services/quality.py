"""Data-quality analysis and the ONE canonical quality score.

CANONICAL QUALITY SCORE (0-100, higher is better)
=================================================
    score = 0.30 * completeness
          + 0.20 * uniqueness
          + 0.20 * validity
          + 0.15 * consistency
          + 0.15 * structure

    completeness = 100 * (1 - missing_cells / total_cells)
    uniqueness   = 100 * (1 - duplicate_rows / rows)
    validity     = 100 * (1 - rows_with_invalid_values / rows)
    consistency  = 100 * (1 - rows_with_inconsistent_values / rows)
    structure    = 100 * (1 - constant_columns / columns)

Grade: >= 90 Excellent, >= 75 Good, >= 50 Moderate, otherwise Poor - but capped at
"Good" if any dimension is below 80 and at "Moderate" if any is below 60.

Anomalies are deliberately NOT part of this score - statistical / ML
anomalies describe *unusual* rather than *defective* data and are weighed in
the risk score by the decision engine. This avoids double counting and gives
the application a single, stable, explainable quality number.

"Invalid" = value violates a domain range rule, is infinite, is text inside a
numeric column (datatype problem) or is outside a user-supplied allowed list.
"Inconsistent" = the same category written several ways (case / whitespace).
Rare categories are reported as *suspicious* but do not affect the score.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from app.config import AnalysisConfig
from app.services.profiler import infer_kind
from app.services.severity import severity_from_rate
from app.utils.helpers import (is_numeric_series, is_text_series, json_safe, rnd,
                               row_number)

WEIGHTS = {"completeness": 0.30, "uniqueness": 0.20, "validity": 0.20,
           "consistency": 0.15, "structure": 0.15}
FORMULA = ("quality = 0.30*completeness + 0.20*uniqueness + 0.20*validity + "
           "0.15*consistency + 0.15*structure (each dimension 0-100)")

_RANGE_IN_NAME = re.compile(r"(?:^|_)(-?\d+(?:\.\d+)?)to(-?\d+(?:\.\d+)?)(?:$|_)")
_NON_NEGATIVE_TOKENS = {
    "income", "salary", "wage", "price", "cost", "revenue", "amount", "quantity", "qty",
    "count", "hours", "minutes", "seconds", "weight", "height", "distance", "duration",
    "population", "sales", "age",
}
_PERCENT_TOKENS = {"percent", "percentage", "pct"}
_MIN_ROWS_FOR_CATEGORY_CHECKS = 10


# --------------------------------------------------------------------------
# Validity rules
# --------------------------------------------------------------------------
def derive_rules(numeric_columns: List[str],
                 overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    """Domain range rules inferred from column names (+ explicit user overrides).

    Returns {column: {"min": x|None, "max": y|None, "source": str}}.
    """
    rules: Dict[str, Dict[str, Any]] = {}
    for column in numeric_columns:
        tokens = set(column.lower().split("_"))
        match = _RANGE_IN_NAME.search(column.lower())
        if match:
            lo, hi = float(match.group(1)), float(match.group(2))
            rules[column] = {"min": lo, "max": hi, "source": "range in column name"}
        elif "age" in tokens:
            rules[column] = {"min": 0.0, "max": 120.0, "source": "plausible human age (0-120)"}
        elif tokens & _PERCENT_TOKENS or column.lower() == "score":
            rules[column] = {"min": 0.0, "max": 100.0, "source": "percentage / score (0-100)"}
        elif tokens & _NON_NEGATIVE_TOKENS:
            rules[column] = {"min": 0.0, "max": None, "source": "non-negative measure"}
    for column, spec in (overrides or {}).items():
        if column not in numeric_columns:
            continue
        try:
            lo, hi = spec if isinstance(spec, (list, tuple)) else (spec.get("min"), spec.get("max"))
        except (TypeError, ValueError, AttributeError):
            continue
        rules[column] = {"min": None if lo is None else float(lo),
                         "max": None if hi is None else float(hi), "source": "user-defined rule"}
    return rules


def _rule_violations(series: pd.Series, rule: Dict[str, Any]) -> Tuple[List[Any], Dict[Any, Optional[float]]]:
    values = pd.to_numeric(series, errors="coerce")
    lo, hi = rule.get("min"), rule.get("max")
    mask = pd.Series(False, index=series.index)
    if lo is not None:
        mask |= values < lo
    if hi is not None:
        mask |= values > hi
    mask &= values.notna()
    width = (hi - lo) if (lo is not None and hi is not None and hi > lo) else None
    excess: Dict[Any, Optional[float]] = {}
    for idx in series.index[mask.values]:
        v = float(values.loc[idx])
        over = (lo - v) if (lo is not None and v < lo) else (v - hi)
        excess[idx] = (over / width) if width else None
    return list(excess.keys()), excess


# --------------------------------------------------------------------------
# Main assessment
# --------------------------------------------------------------------------
def _grade(score: float, weakest_dimension: float = 100.0) -> str:
    """Grade from the score, capped by the weakest dimension so that a high average
    cannot hide a badly failing dimension (e.g. 27% invalid rows is never 'Excellent')."""
    if score >= 90:
        grade = "Excellent"
    elif score >= 75:
        grade = "Good"
    elif score >= 50:
        grade = "Moderate"
    else:
        grade = "Poor"
    order = ["Poor", "Moderate", "Good", "Excellent"]
    cap = "Moderate" if weakest_dimension < 60 else "Good" if weakest_dimension < 80 else "Excellent"
    return order[min(order.index(grade), order.index(cap))]


def _finding(ftype: str, severity: Optional[str], message: str, **extra) -> Optional[dict]:
    if severity is None:
        return None
    return {"type": ftype, "severity": severity, "message": message, **extra}


def assess_quality(df: pd.DataFrame, cfg: AnalysisConfig, coerced: Optional[dict] = None,
                   options: Optional[dict] = None) -> Tuple[dict, dict]:
    """Return (public_result, internal_result).

    ``internal_result`` carries row-level detail (rule breaches with row
    indexes) that other services need but that is too bulky for the API.
    """
    options = options or {}
    coerced = coerced or {}
    rows, cols = df.shape
    total_cells = max(rows * cols, 1)
    findings: List[dict] = []
    notes: List[str] = []
    if rows < 10:
        notes.append(f"The dataset has only {rows} row(s); quality and anomaly conclusions are limited.")

    kinds = {c: infer_kind(df[c]) for c in df.columns}
    numeric_columns = [c for c in df.columns if is_numeric_series(df[c])]

    # ------------------------------------------------------------ missing
    missing_cols: Dict[str, dict] = {}
    total_missing = 0
    for column in df.columns:
        coerced_count = len(coerced.get(column, {}).get("index", []))
        missing = max(int(df[column].isna().sum()) - coerced_count, 0)  # coerced tokens are "invalid", not "missing"
        pct = missing / rows * 100 if rows else 0.0
        total_missing += missing
        sev = severity_from_rate("missing", pct)
        missing_cols[column] = {"count": missing, "pct": rnd(pct, 2), "severity": sev or "GOOD"}
        f = _finding("missing_values", sev,
                     f"{missing} missing value(s) ({pct:.1f}%) in '{column}'.",
                     column=column, count=missing, pct=rnd(pct, 2))
        if f:
            findings.append(f)
    missing_pct_total = total_missing / total_cells * 100

    # --------------------------------------------------------- duplicates
    dup_mask = df.duplicated(keep="first")
    dup_count = int(dup_mask.sum())
    dup_pct = dup_count / rows * 100 if rows else 0.0
    dup_sev = severity_from_rate("duplicates", dup_pct)
    duplicates = {"count": dup_count, "pct": rnd(dup_pct, 2), "severity": dup_sev or "GOOD",
                  "sample_rows": [row_number(i) for i in df.index[dup_mask.values][:20]]}
    f = _finding("duplicate_rows", dup_sev,
                 f"{dup_count} exact duplicate row(s) ({dup_pct:.1f}% of rows).",
                 column=None, count=dup_count, pct=rnd(dup_pct, 2))
    if f:
        findings.append(f)

    # ---------------------------------------------------------- constants
    constant_cols = [c for c in df.columns if df[c].nunique(dropna=True) <= 1]
    if constant_cols and rows > 1:
        findings.append(_finding(
            "constant_columns", "LOW" if len(constant_cols) < max(cols / 2, 1) else "MEDIUM",
            f"{len(constant_cols)} constant column(s) carry no information: "
            f"{', '.join(constant_cols[:8])}.", column=None, count=len(constant_cols), pct=None))
    else:
        constant_cols = constant_cols if rows > 1 else []

    # ----------------------------------------------------------- validity
    rules = derive_rules(numeric_columns, options.get("validity_rules"))
    allowed = {str(k): set(map(str, v)) for k, v in (options.get("allowed_values") or {}).items()}
    invalid_index: Set[Any] = set()
    validity_cols: Dict[str, dict] = {}
    rule_rows: Dict[str, dict] = {}
    invalid_cells = 0

    for column in df.columns:
        detail: Dict[str, Any] = {"rule_violations": 0, "datatype_problems": 0,
                                  "infinite": 0, "not_allowed": 0}
        col_idx: Set[Any] = set()
        if column in rules:
            idx, excess = _rule_violations(df[column], rules[column])
            if idx:
                detail["rule_violations"] = len(idx)
                col_idx.update(idx)
                rule_rows[column] = {"rule": rules[column], "indices": idx, "excess": excess}
                vals = pd.to_numeric(df.loc[idx[:5], column], errors="coerce").tolist()
                detail["rule"] = rules[column]
                detail["examples"] = [{"row": row_number(i), "value": json_safe(v)}
                                      for i, v in zip(idx[:5], vals)]
        if column in coerced:
            n = len(coerced[column]["index"])
            detail["datatype_problems"] = n
            detail["datatype_examples"] = coerced[column]["examples"]
            col_idx.update(coerced[column]["index"])
        if column in numeric_columns:
            inf = np.isinf(pd.to_numeric(df[column], errors="coerce").to_numpy(dtype=float, na_value=np.nan))
            if inf.any():
                detail["infinite"] = int(inf.sum())
                col_idx.update(df.index[inf])
        if column in allowed and is_text_series(df[column]):
            bad = df[column].notna() & ~df[column].astype(str).isin(allowed[column])
            if bad.any():
                detail["not_allowed"] = int(bad.sum())
                detail["allowed_values"] = sorted(allowed[column])[:20]
                detail["examples_not_allowed"] = [str(v) for v in df.loc[bad, column].unique()[:5]]
                col_idx.update(df.index[bad.values])
        count = len(col_idx)
        detail["invalid_count"] = count
        detail["invalid_pct"] = rnd(count / rows * 100 if rows else 0, 2)
        validity_cols[column] = detail
        invalid_cells += (detail["rule_violations"] + detail["datatype_problems"]
                          + detail["infinite"] + detail["not_allowed"])
        invalid_index |= col_idx
        if count:
            sev = severity_from_rate("invalid", count / rows * 100)
            parts = []
            if detail["rule_violations"]:
                parts.append(f"{detail['rule_violations']} outside the valid range ({rules[column]['source']})")
            if detail["datatype_problems"]:
                parts.append(f"{detail['datatype_problems']} non-numeric text value(s)")
            if detail["infinite"]:
                parts.append(f"{detail['infinite']} infinite value(s)")
            if detail["not_allowed"]:
                parts.append(f"{detail['not_allowed']} value(s) outside the approved list")
            findings.append(_finding("invalid_values", sev,
                                     f"'{column}': " + "; ".join(parts) + ".",
                                     column=column, count=count, pct=detail["invalid_pct"]))
    invalid_rows = len(invalid_index)
    invalid_pct = invalid_rows / rows * 100 if rows else 0.0

    # -------------------------------------------------------- consistency
    inconsistent_index: Set[Any] = set()
    consistency_cols: Dict[str, dict] = {}
    suspicious: Dict[str, List[dict]] = {}
    for column in df.columns:
        if not is_text_series(df[column]) or kinds[column] not in ("categorical", "boolean", "text"):
            continue
        series = df[column].dropna().astype(str)
        if series.empty:
            continue
        detail = {"variant_groups": [], "whitespace_issues": 0, "inconsistent_count": 0}
        col_idx: Set[Any] = set()
        # whitespace problems
        ws = series != series.str.strip()
        if ws.any():
            detail["whitespace_issues"] = int(ws.sum())
            col_idx.update(series.index[ws.values])
        # spelling / case variants (skip free text such as names)
        if kinds[column] != "text" and series.nunique() / max(len(series), 1) <= 0.5:
            key = series.str.strip().str.lower().str.replace(r"\s+", " ", regex=True)
            for k, group in series.groupby(key):
                counts = group.value_counts()
                if len(counts) > 1:
                    dominant = counts.index[0]
                    minority = group[group != dominant]
                    col_idx.update(minority.index)
                    detail["variant_groups"].append({
                        "canonical": dominant, "variants": {str(v): int(c) for v, c in counts.items()}})
        detail["inconsistent_count"] = len(col_idx)
        if col_idx:
            inconsistent_index |= col_idx
            consistency_cols[column] = detail
            sev = severity_from_rate("inconsistent", len(col_idx) / rows * 100)
            what = []
            if detail["variant_groups"]:
                what.append(f"{len(detail['variant_groups'])} category value(s) written inconsistently "
                            f"(case/spelling)")
            if detail["whitespace_issues"]:
                what.append(f"{detail['whitespace_issues']} value(s) with leading/trailing spaces")
            findings.append(_finding("inconsistent_values", sev, f"'{column}': " + "; ".join(what) + ".",
                                     column=column, count=len(col_idx),
                                     pct=rnd(len(col_idx) / rows * 100, 2)))
        # rare (suspicious) categories - reported, not scored
        if rows >= _MIN_ROWS_FOR_CATEGORY_CHECKS and kinds[column] == "categorical":
            norm = series.str.strip().str.lower()
            counts = norm.value_counts()
            if 2 <= len(counts) <= 20:
                threshold = max(1, int(rows * 0.005))
                regular = counts[counts > threshold]
                rare = counts[counts <= threshold]
                if len(regular) >= 2 and regular.sum() / len(norm) >= 0.90 and len(rare):
                    suspicious[column] = [
                        {"value": str(v), "count": int(c),
                         "rows": [row_number(i) for i in norm.index[norm == v][:5]]}
                        for v, c in rare.items()]
    inconsistent_rows = len(inconsistent_index)
    inconsistent_pct = inconsistent_rows / rows * 100 if rows else 0.0
    for column, items in suspicious.items():
        findings.append(_finding(
            "suspicious_categories", "LOW",
            f"'{column}' contains rare value(s) that may be data-entry errors: "
            f"{', '.join(repr(i['value']) for i in items[:5])}.",
            column=column, count=int(sum(i["count"] for i in items)), pct=None))

    # ------------------------------------------------------------- scores
    dims = {
        "completeness": 100 * (1 - total_missing / total_cells),
        "uniqueness": 100 * (1 - dup_count / rows) if rows else 0.0,
        "validity": 100 * (1 - invalid_rows / rows) if rows else 0.0,
        "consistency": 100 * (1 - inconsistent_rows / rows) if rows else 0.0,
        "structure": 100 * (1 - len(constant_cols) / cols) if cols else 0.0,
    }
    dims = {k: max(0.0, min(100.0, v)) for k, v in dims.items()}
    overall = round(sum(dims[k] * w for k, w in WEIGHTS.items()), 2)
    details = {
        "completeness": f"{total_missing} missing of {total_cells} cells ({missing_pct_total:.2f}%)",
        "uniqueness": f"{dup_count} duplicate rows ({dup_pct:.2f}%)",
        "validity": f"{invalid_rows} rows with invalid values ({invalid_pct:.2f}%)",
        "consistency": f"{inconsistent_rows} rows with inconsistent values ({inconsistent_pct:.2f}%)",
        "structure": f"{len(constant_cols)} constant column(s) of {cols}",
    }
    dimensions = {k: {"score": rnd(v, 2), "weight": WEIGHTS[k], "detail": details[k]}
                  for k, v in dims.items()}

    # ------------------------------------------------- per-column quality
    column_quality = []
    for column in df.columns:
        m = missing_cols[column]["pct"] or 0
        iv = validity_cols[column]["invalid_pct"] or 0
        ic = (consistency_cols.get(column, {}).get("inconsistent_count", 0) / rows * 100) if rows else 0
        issues = []
        if m > 0:
            issues.append(f"{m}% missing")
        if iv > 0:
            issues.append(f"{iv}% invalid")
        if ic > 0:
            issues.append(f"{ic:.1f}% inconsistent")
        if column in constant_cols and rows > 1:
            issues.append("constant")
        column_quality.append({
            "column": column, "kind": kinds[column],
            "score": rnd(max(0.0, 100 - m - iv - ic - (25 if (column in constant_cols and rows > 1) else 0)), 2),
            "missing_pct": m, "invalid_pct": iv, "inconsistent_pct": rnd(ic, 2), "issues": issues})

    findings = [f for f in findings if f]
    public = {
        "overall_score": overall, "grade": _grade(overall, min(dims.values())), "formula": FORMULA,
        "dimensions": dimensions,
        "summary": {
            "rows": int(rows), "columns": int(cols), "missing_values": int(total_missing),
            "missing_pct": rnd(missing_pct_total, 2), "duplicate_rows": dup_count,
            "duplicate_pct": rnd(dup_pct, 2), "constant_columns": constant_cols,
            "invalid_rows": invalid_rows, "invalid_pct": rnd(invalid_pct, 2),
            "invalid_cells": int(invalid_cells),
            "inconsistent_rows": inconsistent_rows, "inconsistent_pct": rnd(inconsistent_pct, 2),
            "columns_with_missing": int(sum(1 for m in missing_cols.values() if m["count"] > 0)),
        },
        "missing": {"total": int(total_missing), "columns": missing_cols},
        "duplicates": duplicates,
        "validity": {"rules_applied": {c: r for c, r in rules.items()}, "columns": {
            c: d for c, d in validity_cols.items() if d["invalid_count"]}},
        "consistency": {"columns": consistency_cols, "suspicious_categories": suspicious},
        "column_quality": column_quality,
        "findings": findings, "notes": notes,
    }
    internal = {"rule_rows": rule_rows, "rules": rules, "invalid_index": invalid_index,
                "kinds": kinds, "numeric_columns": numeric_columns}
    return json_safe(public), internal
