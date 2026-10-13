"""Shared API dependencies and serializers."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import get_db
from app.models import AnalysisRun, Dataset
from app.utils.helpers import iso
from app.utils.validators import AppError


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def dataset_out(ds: Dataset, latest: Optional[AnalysisRun] = None, analyses: int = 0) -> dict:
    return {
        "id": ds.id, "name": ds.original_filename, "file_type": ds.file_type, "size_bytes": ds.size_bytes,
        "rows": ds.rows, "columns": ds.columns, "is_reference": ds.is_reference,
        "uploaded_at": iso(ds.uploaded_at), "analyses": analyses,
        "latest_analysis": run_brief(latest) if latest else None,
    }


def run_brief(run: AnalysisRun) -> dict:
    return {
        "id": run.id, "dataset_id": run.dataset_id, "status": run.status, "progress": run.progress,
        "current_step": run.current_step, "error": run.error_message, "started_at": iso(run.started_at),
        "completed_at": iso(run.completed_at), "quality_score": run.quality_score,
        "anomaly_count": run.anomaly_count, "critical_count": run.critical_count,
        "drifted_features": run.drifted_features, "risk_score": run.risk_score, "risk_level": run.risk_level,
        "overall_status": run.overall_status, "decision": run.decision, "alert_count": run.alert_count,
        "trend": run.trend, "rows": run.rows, "columns": run.columns,
    }


def get_dataset_or_404(db: Session, dataset_id: int) -> Dataset:
    ds = db.get(Dataset, dataset_id)
    if ds is None:
        raise AppError(f"Dataset {dataset_id} was not found.", 404, "dataset_not_found")
    return ds


def get_run_or_404(db: Session, analysis_id: int) -> AnalysisRun:
    run = db.get(AnalysisRun, analysis_id)
    if run is None:
        raise AppError(f"Analysis {analysis_id} was not found.", 404, "analysis_not_found")
    return run


def get_completed_run(analysis_id: int, db: Session = Depends(get_db)) -> AnalysisRun:
    run = get_run_or_404(db, analysis_id)
    if run.status == "FAILED":
        raise AppError(run.error_message or "This analysis failed.", 409, "analysis_failed")
    if run.status != "COMPLETED" or not run.result:
        raise AppError(f"Analysis {analysis_id} is still {run.status.lower()} "
                       f"({run.progress}% complete). Poll /api/analysis/{analysis_id}/status.",
                       409, "analysis_not_ready")
    return run
