"""Data drift detection: reference dataset vs current dataset.

Numerical features   PSI (bins from the reference quantiles) + two-sample
                     Kolmogorov-Smirnov test.
Categorical features PSI on category proportions + chi-square test.

Decision rule (documented and deterministic)
--------------------------------------------
A feature is *drifted* only when the PSI passes a threshold AND the
statistical test is significant (p < alpha, default 0.05):

    PSI >= 0.25 and p < alpha  ->  SIGNIFICANT DRIFT  (risk HIGH)
    PSI >= 0.10 and p < alpha  ->  MODERATE DRIFT     (risk MEDIUM)
    otherwise                  ->  NO DRIFT           (risk LOW)

Requiring both guards against PSI noise on small samples and against
"significant" but practically meaningless p-values on huge samples.
Features with fewer than ``drift_min_samples`` values on either side are
reported as INSUFFICIENT DATA and never counted as drifted.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from app.config import AnalysisConfig
from app.services.profiler import infer_kind
from app.utils.helpers import (is_ground_truth_name, is_numeric_series, json_safe,
                               looks_like_id, rnd)

_EPS = 1e-4


def _psi(ref_pct: np.ndarray, cur_pct: np.ndarray) -> float:
    ref_pct = np.where(ref_pct == 0, _EPS, ref_pct)
    cur_pct = np.where(cur_pct == 0, _EPS, cur_pct)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def _numeric_drift(ref: pd.Series, cur: pd.Series, cfg: AnalysisConfig) -> dict:
    bins = int(min(10, max(3, len(ref) // 30)))
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:                                    # (almost) discrete -> compare values as categories
        cats = sorted(set(ref.unique()) | set(cur.unique()))
        rc = ref.value_counts().reindex(cats, fill_value=0).to_numpy(dtype=float)
        cc = cur.value_counts().reindex(cats, fill_value=0).to_numpy(dtype=float)
        psi = _psi(rc / rc.sum(), cc / cc.sum())
    else:
        edges = edges.copy()
        edges[0], edges[-1] = -np.inf, np.inf
        rc = np.histogram(ref, bins=edges)[0].astype(float)
        cc = np.histogram(cur, bins=edges)[0].astype(float)
        psi = _psi(rc / rc.sum(), cc / cc.sum())
    ks_stat, p_value = scipy_stats.ks_2samp(ref, cur)

    # distribution for charts: 10 equal-width bins over the combined range
    lo, hi = float(min(ref.min(), cur.min())), float(max(ref.max(), cur.max()))
    if hi > lo:
        chart_edges = np.linspace(lo, hi, 11)
        r = np.histogram(ref, bins=chart_edges)[0] / len(ref)
        c = np.histogram(cur, bins=chart_edges)[0] / len(cur)
        distribution = {"type": "numeric", "edges": [rnd(e, 4) for e in chart_edges],
                        "reference": [rnd(v, 4) for v in r], "current": [rnd(v, 4) for v in c]}
    else:
        distribution = {"type": "numeric", "edges": [lo, hi], "reference": [1.0], "current": [1.0]}
    ref_mean, cur_mean = float(ref.mean()), float(cur.mean())
    return {
        "psi": psi, "test": "Kolmogorov-Smirnov", "statistic": float(ks_stat), "p_value": float(p_value),
        "reference_summary": {"mean": rnd(ref_mean), "median": rnd(ref.median()), "std": rnd(ref.std()),
                              "min": rnd(ref.min()), "max": rnd(ref.max())},
        "current_summary": {"mean": rnd(cur_mean), "median": rnd(cur.median()), "std": rnd(cur.std()),
                            "min": rnd(cur.min()), "max": rnd(cur.max())},
        "mean_change_pct": rnd((cur_mean - ref_mean) / abs(ref_mean) * 100, 2) if ref_mean else None,
        "distribution": distribution,
    }


def _categorical_drift(ref: pd.Series, cur: pd.Series) -> dict:
    ref, cur = ref.astype(str).str.strip(), cur.astype(str).str.strip()
    cats = sorted(set(ref.unique()) | set(cur.unique()))
    rc = ref.value_counts().reindex(cats, fill_value=0).to_numpy(dtype=float)
    cc = cur.value_counts().reindex(cats, fill_value=0).to_numpy(dtype=float)
    psi = _psi(rc / rc.sum(), cc / cc.sum())
    try:
        table = np.vstack([rc, cc])[:, (rc + cc) > 0]
        if table.shape[1] > 1:
            chi2, p_value, _dof, _expected = scipy_stats.chi2_contingency(table)
        else:
            chi2, p_value = 0.0, 1.0
        statistic = float(chi2)
    except ValueError:
        p_value, statistic = 1.0, 0.0
    order = np.argsort(-(rc + cc))[:8]
    top = [cats[i] for i in order]
    other_r, other_c = 1 - sum(rc[i] for i in order) / rc.sum(), 1 - sum(cc[i] for i in order) / cc.sum()
    labels = top + (["(other)"] if other_r > 1e-9 or other_c > 1e-9 else [])
    ref_pct = [rnd(rc[i] / rc.sum(), 4) for i in order] + ([rnd(max(other_r, 0), 4)] if len(labels) > len(top) else [])
    cur_pct = [rnd(cc[i] / cc.sum(), 4) for i in order] + ([rnd(max(other_c, 0), 4)] if len(labels) > len(top) else [])
    new_cats = [c for c, r, k in zip(cats, rc, cc) if r == 0 and k > 0]
    gone = [c for c, r, k in zip(cats, rc, cc) if r > 0 and k == 0]
    return {
        "psi": psi, "test": "Chi-square", "statistic": statistic, "p_value": float(p_value),
        "new_categories": new_cats[:10], "disappeared_categories": gone[:10],
        "reference_summary": {"categories": len(set(ref)), "top": ref.value_counts().index[0]},
        "current_summary": {"categories": len(set(cur)), "top": cur.value_counts().index[0]},
        "mean_change_pct": None,
        "distribution": {"type": "categorical", "labels": labels, "reference": ref_pct, "current": cur_pct},
    }


def _classify(psi: float, p_value: float, cfg: AnalysisConfig) -> dict:
    significant = p_value < cfg.drift_alpha
    if psi >= cfg.psi_significant and significant:
        return {"status": "SIGNIFICANT DRIFT", "risk": "HIGH", "drifted": True}
    if psi >= cfg.psi_moderate and significant:
        return {"status": "MODERATE DRIFT", "risk": "MEDIUM", "drifted": True}
    note = (" PSI is elevated but the change is not statistically significant."
            if psi >= cfg.psi_moderate else "")
    return {"status": "NO DRIFT", "risk": "LOW", "drifted": False, "note": note.strip()}


def detect_drift(reference_df: pd.DataFrame, current_df: pd.DataFrame, cfg: AnalysisConfig,
                 reference_info: Optional[dict] = None) -> dict:
    ref_cols, cur_cols = set(reference_df.columns), set(current_df.columns)
    common = [c for c in current_df.columns if c in ref_cols]
    schema = {"columns_added": sorted(cur_cols - ref_cols), "columns_removed": sorted(ref_cols - cur_cols)}
    if not common:
        return {"available": False, "reference": reference_info, "schema": schema,
                "message": "The reference and current datasets share no column names, "
                           "so drift cannot be assessed."}

    features: List[dict] = []
    skipped: List[dict] = []
    for column in common:
        if looks_like_id(column) or is_ground_truth_name(column):
            continue
        r, c = reference_df[column], current_df[column]
        kr, kc = infer_kind(r), infer_kind(c)
        if kr in ("text", "datetime") or kc in ("text", "datetime"):
            skipped.append({"feature": column, "reason": "free text / date column"})
            continue
        if r.dropna().nunique() <= 1 and c.dropna().nunique() <= 1 and \
                (r.dropna().unique().tolist() == c.dropna().unique().tolist()):
            continue                                        # identical constants: nothing to compare
        numeric = is_numeric_series(r) and is_numeric_series(c) and kr == "numeric" and kc == "numeric"
        categorical = kr in ("categorical", "boolean") and kc in ("categorical", "boolean") or \
            (is_numeric_series(r) and is_numeric_series(c) and (kr == "boolean" or kc == "boolean"))
        if not numeric and not categorical:
            skipped.append({"feature": column,
                            "reason": f"data type changed ({kr} → {kc}); compare manually"})
            continue
        if numeric:
            rv = pd.to_numeric(r, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
            cv = pd.to_numeric(c, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        else:
            rv, cv = r.dropna(), c.dropna()
        base = {"feature": column, "type": "numeric" if numeric else "categorical",
                "reference_n": int(len(rv)), "current_n": int(len(cv))}
        if len(rv) < cfg.drift_min_samples or len(cv) < cfg.drift_min_samples:
            features.append({**base, "psi": None, "statistic": None, "p_value": None, "test": None,
                             "status": "INSUFFICIENT DATA", "risk": "UNKNOWN", "drifted": False,
                             "note": f"Fewer than {cfg.drift_min_samples} values on one side; "
                                     f"drift cannot be assessed reliably."})
            continue
        detail = _numeric_drift(rv, cv, cfg) if numeric else _categorical_drift(rv, cv)
        verdict = _classify(detail["psi"], detail["p_value"], cfg)
        features.append({**base, **detail, **verdict,
                         "psi": rnd(detail["psi"], 4), "statistic": rnd(detail["statistic"], 4),
                         "p_value": rnd(detail["p_value"], 6)})

    evaluated = [f for f in features if f["status"] != "INSUFFICIENT DATA"]
    if not evaluated:
        return json_safe({
            "available": False, "reference": reference_info, "schema": schema, "features": features,
            "skipped": skipped, "overall_status": "INSUFFICIENT DATA",
            "message": "Insufficient data to assess drift (no feature has enough values in both datasets)."})

    drifted = [f for f in evaluated if f["drifted"]]
    significant = [f for f in drifted if f["status"] == "SIGNIFICANT DRIFT"]
    avg_psi = float(np.mean([f["psi"] for f in evaluated]))
    if significant or len(drifted) / len(evaluated) >= 0.30:
        overall, risk = "SIGNIFICANT DRIFT", "HIGH"
    elif drifted:
        overall, risk = "MODERATE DRIFT", "MEDIUM"
    else:
        overall, risk = "NO DRIFT", "LOW"
    features.sort(key=lambda f: -(f["psi"] or -1))
    return json_safe({
        "available": True, "reference": reference_info, "schema": schema,
        "overall_status": overall, "overall_risk": risk, "drift_detected": bool(drifted),
        "drifted_features": len(drifted), "significant_features": len(significant),
        "features_evaluated": len(evaluated), "average_psi": rnd(avg_psi, 4),
        "drift_score": rnd(min(100.0, avg_psi * 100), 2),
        "affected_features": [f["feature"] for f in drifted],
        "features": features, "skipped": skipped,
        "method": {"psi_moderate": cfg.psi_moderate, "psi_significant": cfg.psi_significant,
                   "alpha": cfg.drift_alpha, "min_samples": cfg.drift_min_samples},
    })
