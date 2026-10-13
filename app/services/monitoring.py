"""Continuous monitoring: every analysis run is recorded as one monitoring point.

The ``analysis_runs`` table *is* the monitoring history (timestamp, dataset,
quality score, anomaly count, drifted features, risk level, alerts, decision,
status). This module converts rows into plain "points" and builds the
current-vs-previous comparison.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import AnalysisRun, Dataset
from app.utils.helpers import iso, rnd


def run_to_point(run: AnalysisRun, dataset_name: Optional[str] = None) -> dict:
    return {
        "analysis_id": run.id, "dataset_id": run.dataset_id,
        "dataset": dataset_name or (run.dataset.original_filename if run.dataset else None),
        "timestamp": iso(run.completed_at or run.started_at),
        "quality_score": run.quality_score, "anomaly_count": run.anomaly_count,
        "anomaly_pct": run.anomaly_pct, "critical_count": run.critical_count,
        "drifted_features": run.drifted_features, "risk_score": run.risk_score,
        "risk_level": run.risk_level, "alert_count": run.alert_count,
        "decision": run.decision, "status": run.overall_status, "rows": run.rows,
    }


def get_history(db: Session, group_key: Optional[str] = None, dataset_id: Optional[int] = None,
                limit: int = 200, exclude_run_id: Optional[int] = None) -> List[dict]:
    """Completed runs, oldest first. Scope: one dataset series (group_key) or everything."""
    query = db.query(AnalysisRun).join(Dataset, Dataset.id == AnalysisRun.dataset_id) \
        .filter(AnalysisRun.status == "COMPLETED")
    if group_key:
        query = query.filter(Dataset.group_key == group_key)
    if dataset_id:
        query = query.filter(AnalysisRun.dataset_id == dataset_id)
    if exclude_run_id:
        query = query.filter(AnalysisRun.id != exclude_run_id)
    runs = query.order_by(AnalysisRun.completed_at.desc(), AnalysisRun.id.desc()).limit(limit).all()
    return [run_to_point(r) for r in reversed(runs)]


def build_monitoring(current: dict, history: List[dict]) -> dict:
    """Compare the current run with the previous one of the same dataset series."""
    previous = history[-1] if history else None
    delta = {}
    if previous:
        for key in ("quality_score", "anomaly_count", "risk_score", "drifted_features", "alert_count"):
            a, b = current.get(key), previous.get(key)
            delta[key] = rnd(a - b, 2) if a is not None and b is not None else None
    return {
        "recorded": True, "timestamp": current.get("timestamp"),
        "runs_in_series": len(history) + 1,
        "previous": previous, "current": current, "delta": delta,
        "message": ("First recorded analysis for this dataset series - no comparison available yet."
                    if not previous else "Compared with the previous analysis of this dataset series."),
    }
