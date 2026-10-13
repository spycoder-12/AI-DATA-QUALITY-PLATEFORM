"""Statistical anomaly detection (IQR and Z-score) - the ONE implementation.

Also hosts the shared *feature selector* used by the ML detectors, the
explainability layer and the drift detector, so that every module agrees on
which columns are analysable measurements.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.config import AnalysisConfig
from app.utils.helpers import (is_ground_truth_name, is_numeric_series, looks_like_id,
                               rnd)


# --------------------------------------------------------------------------
# Common result type (also returned by the ML detectors)
# --------------------------------------------------------------------------
@dataclass
class DetectorResult:
    name: str
    kind: str                                   # "statistical" | "machine_learning"
    status: str = "OK"                          # OK | SKIPPED | FAILED
    message: str = ""
    row_flags: Optional[pd.Series] = None       # bool Series aligned with df.index
    scores: Optional[pd.Series] = None          # higher = more anomalous (ML only)
    feature_masks: Dict[str, pd.Series] = field(default_factory=dict)
    per_feature: Dict[str, dict] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.status == "OK" and self.row_flags is not None

    @property
    def flagged(self) -> int:
        return int(self.row_flags.sum()) if self.ok else 0

    def summary(self, total_rows: int) -> dict:
        return {"model": self.name, "type": self.kind, "status": self.status,
                "message": self.message, "anomalies_flagged": self.flagged if self.ok else None,
                "anomaly_pct": rnd(self.flagged / total_rows * 100, 2) if (self.ok and total_rows) else None,
                "execution_seconds": rnd(self.seconds, 4), "params": self.params}


# --------------------------------------------------------------------------
# Feature selection
# --------------------------------------------------------------------------
def select_features(df: pd.DataFrame, cfg: AnalysisConfig,
                    kinds: Optional[Dict[str, str]] = None) -> Tuple[List[str], List[dict]]:
    """Choose numeric measurement columns suitable for outlier analysis.

    Returns (features, excluded) where excluded = [{"feature", "reason"}].
    """
    features: List[str] = []
    excluded: List[dict] = []
    n = len(df)
    for column in df.columns:
        series = df[column]
        if not is_numeric_series(series):
            if is_ground_truth_name(column):
                excluded.append({"feature": column, "reason": "ground-truth label column"})
            continue
        values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
        present = values.dropna()

        def skip(reason: str) -> None:
            excluded.append({"feature": column, "reason": reason})

        if is_ground_truth_name(column):
            skip("ground-truth label column")
        elif looks_like_id(column):
            skip("identifier column")
        elif len(present) < cfg.min_values_for_stats:
            skip("too few non-missing values")
        elif present.nunique() <= 1:
            skip("constant column")
        elif present.nunique() == 2:
            skip("binary / flag column")
        elif (n >= 5 and present.nunique() == len(present) and (present % 1 == 0).all()
              and (present.is_monotonic_increasing or present.is_monotonic_decreasing)):
            skip("identifier-like sequence")
        elif (present % 1 == 0).all() and present.nunique() <= 10 and (present.max() - present.min()) <= 12:
            skip("small discrete scale (ordinal / coded values)")
        else:
            features.append(column)
    return features, excluded


# --------------------------------------------------------------------------
# Feature statistics - computed ONCE and shared (detectors, severity, XAI)
# --------------------------------------------------------------------------
SKEW_THRESHOLD = 1.0


def _body_skew(values: pd.Series) -> float:
    """Skewness of the distribution *body* (1%-99% clipped).

    Plain skewness is dominated by a single extreme value, which would let one error
    decide the analysis scale. Clipping the tails means only a genuinely long-tailed
    distribution (not one outlier) triggers the log transform.
    """
    clipped = values.clip(values.quantile(0.01), values.quantile(0.99))
    skew = clipped.skew()
    return 0.0 if pd.isna(skew) else float(skew)


def _inverse(value: float, transform: Optional[str]) -> float:
    if transform == "log1p":
        return float(max(np.expm1(value), 0.0))
    return float(value)


def compute_feature_stats(df: pd.DataFrame, features: List[str], cfg: AnalysisConfig) -> Dict[str, dict]:
    """Per-feature statistics, computed ONCE and shared by detectors, severity and XAI.

    Strongly right-skewed non-negative features (body skewness > 1) are analysed on a log1p
    scale so that natural long tails (e.g. notification counts) are not mislabelled as
    errors. ``values`` is the analysis-scale series; ``raw`` keeps the original units
    and every ``*_raw`` field is expressed in original units for display.
    """
    stats: Dict[str, dict] = {}
    for f in features:
        raw = pd.to_numeric(df[f], errors="coerce").replace([np.inf, -np.inf], np.nan)
        p = raw.dropna()
        if p.empty:
            continue
        transform = None
        v = raw
        if len(p) >= 8 and p.min() >= 0 and abs(_body_skew(p)) > SKEW_THRESHOLD:
            transform, v = "log1p", np.log1p(raw)
            p = v.dropna()
        q1, q3 = float(p.quantile(0.25)), float(p.quantile(0.75))
        iqr = q3 - q1
        std = float(p.std()) if len(p) > 1 else 0.0
        median = float(p.median())
        mean = float(p.mean())
        lower, upper = q1 - cfg.iqr_multiplier * iqr, q3 + cfg.iqr_multiplier * iqr
        floor0 = float(raw.min()) >= 0          # non-negative measure: a negative bound is meaningless
        lower_raw = _inverse(lower, transform) if transform else lower
        z_lower_raw = _inverse(mean - cfg.zscore_threshold * std, transform) if transform \
            else mean - cfg.zscore_threshold * std
        if floor0:
            lower_raw, z_lower_raw = max(lower_raw, 0.0), max(z_lower_raw, 0.0)
        stats[f] = {
            "n": int(len(p)), "mean": mean, "std": std, "median": median,
            "mad": float((p - median).abs().median()), "q1": q1, "q3": q3, "iqr": iqr,
            "lower": lower, "upper": upper, "min": float(p.min()), "max": float(p.max()),
            "values": v, "raw": raw, "transform": transform,
            "median_raw": _inverse(median, transform),
            "lower_raw": lower_raw, "upper_raw": _inverse(upper, transform),
            "z_lower_raw": z_lower_raw,
            "z_upper_raw": _inverse(mean + cfg.zscore_threshold * std, transform),
        }
    return stats


def zscore_of(value: float, st: dict) -> Optional[float]:
    return (value - st["mean"]) / st["std"] if st["std"] and st["std"] > 0 else None


def iqr_distance(value: float, st: dict) -> Optional[float]:
    """Distance beyond the nearer quartile, in IQR units (0 when inside the box)."""
    if not st["iqr"] or st["iqr"] <= 0:
        return None
    if value > st["q3"]:
        return (value - st["q3"]) / st["iqr"]
    if value < st["q1"]:
        return (st["q1"] - value) / st["iqr"]
    return 0.0


# --------------------------------------------------------------------------
# Detectors
# --------------------------------------------------------------------------
def detect_iqr(df: pd.DataFrame, features: List[str], stats: Dict[str, dict],
               cfg: AnalysisConfig) -> DetectorResult:
    start = time.perf_counter()
    result = DetectorResult("IQR", "statistical", params={"multiplier": cfg.iqr_multiplier})
    flags = pd.Series(False, index=df.index)
    for f in features:
        st = stats.get(f)
        if st is None:
            continue
        if st["iqr"] <= 0:
            result.per_feature[f] = {"skipped": "IQR is zero (most values identical)"}
            continue
        v = st["values"]
        mask = ((v < st["lower"]) | (v > st["upper"])) & v.notna()
        result.feature_masks[f] = mask
        flags |= mask
        result.per_feature[f] = {
            "q1": rnd(st["q1"]), "q3": rnd(st["q3"]), "iqr": rnd(st["iqr"]),
            "lower_bound": rnd(st["lower_raw"]), "upper_bound": rnd(st["upper_raw"]),
            "scale": st["transform"] or "linear",
            "anomaly_count": int(mask.sum()), "anomaly_pct": rnd(mask.sum() / max(st["n"], 1) * 100, 2)}
    if not features:
        result.status, result.message = "SKIPPED", "No suitable numerical features."
    result.row_flags, result.seconds = flags, time.perf_counter() - start
    return result


def detect_zscore(df: pd.DataFrame, features: List[str], stats: Dict[str, dict],
                  cfg: AnalysisConfig) -> DetectorResult:
    start = time.perf_counter()
    result = DetectorResult("Z-Score", "statistical", params={"threshold": cfg.zscore_threshold})
    flags = pd.Series(False, index=df.index)
    for f in features:
        st = stats.get(f)
        if st is None:
            continue
        if not st["std"] or st["std"] <= 0:
            result.per_feature[f] = {"skipped": "standard deviation is zero"}
            continue
        z = (st["values"] - st["mean"]) / st["std"]
        mask = (z.abs() > cfg.zscore_threshold) & z.notna()
        result.feature_masks[f] = mask
        flags |= mask
        result.per_feature[f] = {
            "mean": rnd(st["mean"]), "std": rnd(st["std"]), "threshold": cfg.zscore_threshold,
            "lower_bound": rnd(st["z_lower_raw"]), "upper_bound": rnd(st["z_upper_raw"]),
            "scale": st["transform"] or "linear",
            "max_abs_z": rnd(z.abs().max()),
            "anomaly_count": int(mask.sum()), "anomaly_pct": rnd(mask.sum() / max(st["n"], 1) * 100, 2)}
    if not features:
        result.status, result.message = "SKIPPED", "No suitable numerical features."
    result.row_flags, result.seconds = flags, time.perf_counter() - start
    return result


def run_statistical_detection(df: pd.DataFrame, features: List[str], excluded: List[dict],
                              cfg: AnalysisConfig) -> Tuple[Dict[str, dict], List[DetectorResult], dict]:
    """Run IQR + Z-score once. Returns (feature_stats, [iqr, zscore], public_summary)."""
    stats = compute_feature_stats(df, features, cfg)
    usable = [f for f in features if f in stats]
    iqr, zsc = detect_iqr(df, usable, stats, cfg), detect_zscore(df, usable, stats, cfg)
    union = (iqr.row_flags | zsc.row_flags) if (iqr.ok and zsc.ok) else pd.Series(False, index=df.index)
    n = len(df)
    per_feature = []
    for f in usable:
        a, b = iqr.per_feature.get(f, {}), zsc.per_feature.get(f, {})
        both = (iqr.feature_masks.get(f, pd.Series(False, index=df.index))
                | zsc.feature_masks.get(f, pd.Series(False, index=df.index)))
        per_feature.append({
            "feature": f, "iqr_anomalies": a.get("anomaly_count", 0),
            "zscore_anomalies": b.get("anomaly_count", 0),
            "records_flagged": int(both.sum()), "anomaly_pct": rnd(both.sum() / max(n, 1) * 100, 2),
            "lower_bound": a.get("lower_bound"), "upper_bound": a.get("upper_bound"),
            "iqr": a, "zscore": b})
    message = ""
    if not features:
        message = ("No suitable numerical columns for statistical anomaly detection "
                   "(need at least one non-constant, non-identifier numeric column).")
    public = {
        "status": "OK" if features else "SKIPPED", "message": message,
        "features_used": features, "features_excluded": excluded,
        "log_scaled_features": [f for f in usable if stats[f]["transform"]],
        "thresholds": {"iqr_multiplier": cfg.iqr_multiplier, "zscore_threshold": cfg.zscore_threshold},
        "per_feature": per_feature,
        "affected_features": [p["feature"] for p in per_feature if p["records_flagged"] > 0],
        "records_flagged": int(union.sum()), "records_flagged_pct": rnd(union.sum() / max(n, 1) * 100, 2),
        "iqr_records": iqr.flagged, "zscore_records": zsc.flagged,
    }
    return stats, [iqr, zsc], public
