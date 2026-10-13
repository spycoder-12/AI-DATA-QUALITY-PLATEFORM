"""Forecasting of quality, risk and anomaly indicators.

A simple, transparent linear-regression forecast over the monitoring history.
It is only produced with at least ``forecast_min_points`` historical analyses
(default 5). Below that we say so - we never invent predictions.
"""
from __future__ import annotations

from typing import List

import numpy as np

from app.config import AnalysisConfig
from app.services.severity import risk_level_from_score
from app.services.trends import WINDOW, classify_slope, linear_fit, tolerance_for
from app.utils.helpers import json_safe, rnd

INSUFFICIENT = "Insufficient historical data for reliable forecasting."


def _project(values: List[float], horizon: int, low: float, high: float) -> List[dict]:
    fit = linear_fit(values)
    n = len(values)
    out = []
    for k in range(1, horizon + 1):
        pred = fit["slope"] * (n - 1 + k) + fit["intercept"]
        margin = 1.96 * fit["resid_std"]
        out.append({"period": k, "value": rnd(min(max(pred, low), high), 2),
                    "lower": rnd(min(max(pred - margin, low), high), 2),
                    "upper": rnd(min(max(pred + margin, low), high), 2)})
    return out


def forecast(points: List[dict], cfg: AnalysisConfig) -> dict:
    points = points[-WINDOW:]
    quality = [p["quality_score"] for p in points if p.get("quality_score") is not None]
    if len(quality) < cfg.forecast_min_points:
        return {"available": False, "history_points": len(quality),
                "required_points": cfg.forecast_min_points, "message": INSUFFICIENT}
    horizon = cfg.forecast_horizon
    result = {"available": True, "history_points": len(quality), "horizon": horizon,
              "method": "Linear regression on the monitoring history (approximate 95% band from residuals).",
              "unit": "future analysis runs", "forecast": {}}
    result["forecast"]["quality_score"] = _project(quality, horizon, 0.0, 100.0)
    fit = linear_fit(quality)
    result["forecast_trend"] = classify_slope(fit["slope"], tolerance_for("quality_score", quality), True)["trend"]
    result["r_squared"] = rnd(fit["r2"], 3) if fit["r2"] is not None else None
    risk = [p["risk_score"] for p in points if p.get("risk_score") is not None]
    if len(risk) >= cfg.forecast_min_points:
        result["forecast"]["risk_score"] = _project(risk, horizon, 0.0, 100.0)
        end = result["forecast"]["risk_score"][-1]["value"]
        result["forecast_risk_level"] = risk_level_from_score(end, cfg.risk_medium, cfg.risk_high, cfg.risk_critical)
    anomalies = [p["anomaly_count"] for p in points if p.get("anomaly_count") is not None]
    if len(anomalies) >= cfg.forecast_min_points:
        result["forecast"]["anomaly_count"] = _project(anomalies, horizon, 0.0, float("inf"))
    result["latest"] = {"quality_score": quality[-1], "risk_score": risk[-1] if risk else None}
    result["reliability_note"] = ("Low R² means the history is noisy; treat the forecast as indicative."
                                  if (result["r_squared"] is not None and result["r_squared"] < 0.3) else "")
    return json_safe(result)
