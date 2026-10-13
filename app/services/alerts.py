"""Alert engine: threshold-based alerts with severity, target and recommended action.

Alerts only fire when a configurable threshold is exceeded (see AnalysisConfig)
- a single missing value or one duplicate row does not raise an alert.
Severity uses the platform-wide LOW / MEDIUM / HIGH / CRITICAL system.
"""
from __future__ import annotations

from typing import List, Optional

from app.config import AnalysisConfig
from app.services.severity import severity_from_rate, severity_rank
from app.utils.helpers import iso, json_safe, utcnow

MIN_ALERT_LEVEL = "MEDIUM"          # LOW-level findings are shown as findings, not alerts


def _alert(kind: str, severity: str, message: str, affected: str, action: str,
           metric: Optional[str] = None, value=None, threshold=None) -> dict:
    return {"type": kind, "severity": severity, "message": message, "timestamp": iso(utcnow()),
            "affected": affected, "recommended_action": action, "metric": metric,
            "value": value, "threshold": threshold, "status": "ACTIVE"}


def generate_alerts(cfg: AnalysisConfig, dataset_name: str, quality: dict, anomaly_summary: dict,
                    drift: dict, previous: Optional[dict]) -> List[dict]:
    alerts: List[dict] = []
    q = quality["summary"]
    score = quality["overall_score"]

    # ---- quality score level
    if score < cfg.quality_critical:
        sev, thr = "CRITICAL", cfg.quality_critical
    elif score < cfg.quality_high:
        sev, thr = "HIGH", cfg.quality_high
    elif score < cfg.quality_medium:
        sev, thr = "MEDIUM", cfg.quality_medium
    else:
        sev = thr = None
    if sev:
        alerts.append(_alert("QUALITY_SCORE", sev, f"Overall quality score is {score:.1f}/100 "
                             f"(below {thr:.0f}).", dataset_name,
                             "Review the data-quality findings and apply the recommended fixes.",
                             "quality_score", score, thr))

    # ---- quality drop vs previous run
    if previous and previous.get("quality_score") is not None:
        drop = previous["quality_score"] - score
        if drop >= cfg.quality_drop_high:
            drop_sev = "HIGH"
        elif drop >= cfg.quality_drop_medium:
            drop_sev = "MEDIUM"
        else:
            drop_sev = None
        if drop_sev:
            alerts.append(_alert("QUALITY_DROP", drop_sev,
                                 f"Quality dropped by {drop:.1f} points since the previous analysis "
                                 f"({previous['quality_score']:.1f} → {score:.1f}).", dataset_name,
                                 "Compare this dataset with the previous version and check what changed upstream.",
                                 "quality_delta", round(-drop, 2), -cfg.quality_drop_medium))

    # ---- missing values
    sev = severity_from_rate("missing", q["missing_pct"])
    if sev and severity_rank(sev) >= severity_rank(MIN_ALERT_LEVEL):
        alerts.append(_alert("MISSING_VALUES", sev, f"{q['missing_values']} missing values "
                             f"({q['missing_pct']}% of all cells).", dataset_name,
                             "Impute or investigate the data-collection step that leaves fields empty.",
                             "missing_pct", q["missing_pct"], 5))
    flagged = 0
    for col, info in quality["missing"]["columns"].items():
        if info["pct"] >= cfg.missing_col_alert_pct and flagged < 5:
            flagged += 1
            alerts.append(_alert("MISSING_VALUES", info["severity"],
                                 f"'{col}' is {info['pct']}% empty.", col,
                                 "Consider imputation, or drop the column if it is mostly empty.",
                                 "column_missing_pct", info["pct"], cfg.missing_col_alert_pct))

    # ---- duplicates
    sev = severity_from_rate("duplicates", q["duplicate_pct"])
    if sev and severity_rank(sev) >= severity_rank(MIN_ALERT_LEVEL):
        alerts.append(_alert("DUPLICATE_RECORDS", sev, f"{q['duplicate_rows']} duplicate rows "
                             f"({q['duplicate_pct']}%).", dataset_name,
                             "Review duplicate keys and remove confirmed duplicates.",
                             "duplicate_pct", q["duplicate_pct"], 5))

    # ---- invalid data
    sev = severity_from_rate("invalid", q["invalid_pct"])
    if sev and severity_rank(sev) >= severity_rank(MIN_ALERT_LEVEL):
        alerts.append(_alert("INVALID_VALUES", sev, f"{q['invalid_rows']} rows ({q['invalid_pct']}%) contain "
                             f"invalid values.", dataset_name,
                             "Validate the affected columns against business rules at the source.",
                             "invalid_pct", q["invalid_pct"], 1))

    # ---- anomalies
    n_crit, n_high = anomaly_summary.get("critical_count", 0), anomaly_summary.get("high_count", 0)
    top_feature = next(iter(anomaly_summary.get("affected_features", {})), dataset_name)
    if n_crit:
        alerts.append(_alert("CRITICAL_ANOMALIES", "CRITICAL",
                             f"{n_crit} critical anomalous record(s) detected.", top_feature,
                             "Investigate these records immediately and verify the source data.",
                             "critical_count", n_crit, 0))
    if n_high:
        alerts.append(_alert("HIGH_SEVERITY_ANOMALIES", "HIGH",
                             f"{n_high} high-severity anomalous record(s) detected.", top_feature,
                             "Review these records manually against the original source.",
                             "high_count", n_high, 0))
    rate = anomaly_summary.get("anomaly_pct") or 0
    if rate >= cfg.anomaly_rate_high_pct:
        rate_sev = "HIGH"
    elif rate >= cfg.anomaly_rate_medium_pct:
        rate_sev = "MEDIUM"
    else:
        rate_sev = None
    if rate_sev:
        alerts.append(_alert("ANOMALY_RATE", rate_sev, f"{rate}% of records are anomalous.", dataset_name,
                             "Check whether the data-generating process changed.",
                             "anomaly_pct", rate, cfg.anomaly_rate_medium_pct))
    if previous and previous.get("anomaly_count") is not None:
        prev, cur = previous["anomaly_count"], anomaly_summary.get("anomaly_count", 0)
        if cur - prev >= cfg.anomaly_increase_min_records and cur >= prev * (1 + cfg.anomaly_increase_pct / 100):
            alerts.append(_alert("ANOMALY_INCREASE", "MEDIUM",
                                 f"Anomaly count rose from {prev} to {cur} since the previous analysis.",
                                 dataset_name, "Investigate what changed since the last analysis.",
                                 "anomaly_count", cur, prev))

    # ---- drift
    if drift.get("available"):
        drifted = [f for f in drift["features"] if f["drifted"]]
        for f in drifted[:10]:
            alerts.append(_alert("DATA_DRIFT", f["risk"],
                                 f"{f['status'].title()} in '{f['feature']}' (PSI {f['psi']}).", f["feature"],
                                 "Investigate upstream data generation for this feature.",
                                 "psi", f["psi"], cfg.psi_moderate))
        if len(drifted) > 10:
            alerts.append(_alert("DATA_DRIFT", "MEDIUM", f"{len(drifted) - 10} more feature(s) drifted.",
                                 dataset_name, "Open the Drift Monitoring page for the full list."))

    alerts.sort(key=lambda a: -severity_rank(a["severity"]))
    return json_safe(alerts)
