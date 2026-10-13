"""Trend analysis from real monitoring history.

Direction semantics are handled explicitly: for quality a rising slope is
IMPROVING, but for anomalies, drift, risk and alerts a rising slope is
DECLINING (the original prototype mislabelled these). Each metric therefore
reports both the raw direction (UP/DOWN/FLAT) and the health interpretation.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from app.utils.helpers import json_safe, rnd

WINDOW = 30
# metric: (higher_is_better, absolute slope tolerance per run, weight in overall vote)
METRICS = {
    "quality_score": (True, 0.5, 2),
    "risk_score": (False, 0.5, 2),
    "anomaly_count": (False, None, 1),        # tolerance = max(0.5, 2 % of mean)
    "drifted_features": (False, 0.1, 1),
    "alert_count": (False, 0.2, 1),
}


def linear_fit(values: List[float]) -> Optional[dict]:
    if len(values) < 2:
        return None
    y = np.asarray(values, dtype=float)
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    ss_res = float(((y - fitted) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return {"slope": float(slope), "intercept": float(intercept),
            "r2": (1 - ss_res / ss_tot) if ss_tot > 0 else None,
            "resid_std": float(np.sqrt(ss_res / (len(y) - 2))) if len(y) > 2 else 0.0}


def classify_slope(slope: float, tolerance: float, higher_is_better: bool) -> dict:
    if abs(slope) <= tolerance:
        return {"direction": "FLAT", "trend": "STABLE"}
    up = slope > 0
    improving = up == higher_is_better
    return {"direction": "UP" if up else "DOWN", "trend": "IMPROVING" if improving else "DECLINING"}


def tolerance_for(metric: str, values: List[float]) -> float:
    fixed = METRICS[metric][1]
    return fixed if fixed is not None else max(0.5, 0.02 * float(np.mean(values)))


def analyze_trends(points: List[dict]) -> dict:
    points = points[-WINDOW:]
    series = [{k: p.get(k) for k in ("timestamp", "analysis_id", "quality_score", "anomaly_count",
                                     "drifted_features", "risk_score", "alert_count")} for p in points]
    if len(points) < 2:
        return {"available": False, "points": len(points), "series": series,
                "message": "Not available — insufficient data. Trends need at least two analyses of "
                           "the same dataset series.", "overall_trend": "INSUFFICIENT DATA", "metrics": {}}
    metrics: Dict[str, dict] = {}
    vote = 0
    for name, (hib, _tol, weight) in METRICS.items():
        vals = [p[name] for p in points if p.get(name) is not None]
        if len(vals) < 2:
            metrics[name] = {"trend": "INSUFFICIENT DATA", "direction": None, "points": len(vals)}
            continue
        fit = linear_fit(vals)
        verdict = classify_slope(fit["slope"], tolerance_for(name, vals), hib)
        metrics[name] = {**verdict, "slope": rnd(fit["slope"], 4), "first": vals[0], "latest": vals[-1],
                         "previous": vals[-2], "change": rnd(vals[-1] - vals[-2], 2),
                         "higher_is_better": hib, "points": len(vals)}
        vote += weight * {"IMPROVING": 1, "DECLINING": -1, "STABLE": 0}[verdict["trend"]]
    overall = "IMPROVING" if vote >= 2 else "DECLINING" if vote <= -2 else "STABLE"
    return json_safe({"available": True, "points": len(points), "series": series, "metrics": metrics,
                      "overall_trend": overall, "vote_score": vote,
                      "method": "Linear-regression slope over the last "
                                f"{min(len(points), WINDOW)} analyses; weighted vote "
                                "(quality 2, risk 2, anomalies 1, drift 1, alerts 1; |vote| >= 2 decides)."})
