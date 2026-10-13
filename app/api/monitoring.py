"""Monitoring, drift, trends, forecast and alerts endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_dataset_or_404, get_run_or_404
from app.config import ANALYSIS_DEFAULTS, Settings
from app.database import get_db
from app.models import Alert, AnalysisRun, Dataset
from app.schemas import DriftCompareRequest
from app.services import drift as drift_svc, forecasting, monitoring, trends
from app.utils.file_handler import load_cached
from app.utils.helpers import SEVERITY_ORDER, iso
from app.utils.validators import AppError

router = APIRouter(prefix="/api", tags=["Monitoring"])


def resolve_scope(db: Session, dataset_id: Optional[int], scope: str) -> dict:
    """Which monitoring series to use: one dataset series (default: that of the latest run) or all."""
    if scope == "all" and not dataset_id:
        return {"mode": "all", "group_key": None, "name": "All datasets"}
    if dataset_id:
        ds = get_dataset_or_404(db, dataset_id)
    else:
        latest = (db.query(AnalysisRun).filter(AnalysisRun.status == "COMPLETED")
                  .order_by(AnalysisRun.id.desc()).first())
        if latest is None:
            return {"mode": "none", "group_key": None, "name": None}
        ds = db.get(Dataset, latest.dataset_id)
    return {"mode": "series", "group_key": ds.group_key, "name": ds.original_filename}


@router.get("/monitoring", summary="Monitoring history (one point per analysis)")
def monitoring_history(dataset_id: Optional[int] = None, scope: str = Query("series", pattern="^(series|all)$"),
                       limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    sc = resolve_scope(db, dataset_id, scope)
    if sc["mode"] == "none":
        return {"scope": sc, "count": 0, "history": [], "message": "No analyses have been run yet."}
    history = monitoring.get_history(db, group_key=sc["group_key"], limit=limit)
    return {"scope": sc, "count": len(history), "history": history,
            "latest": history[-1] if history else None, "previous": history[-2] if len(history) > 1 else None}


@router.get("/trends", summary="Quality / anomaly / drift / risk trends from history")
def get_trends(dataset_id: Optional[int] = None, scope: str = Query("series", pattern="^(series|all)$"),
               db: Session = Depends(get_db)):
    sc = resolve_scope(db, dataset_id, scope)
    history = monitoring.get_history(db, group_key=sc["group_key"]) if sc["mode"] != "none" else []
    return {"scope": sc, **trends.analyze_trends(history)}


@router.get("/forecast", summary="Forecast of future quality and risk (needs enough history)")
def get_forecast(dataset_id: Optional[int] = None, scope: str = Query("series", pattern="^(series|all)$"),
                 db: Session = Depends(get_db)):
    sc = resolve_scope(db, dataset_id, scope)
    history = monitoring.get_history(db, group_key=sc["group_key"]) if sc["mode"] != "none" else []
    return {"scope": sc, **forecasting.forecast(history, ANALYSIS_DEFAULTS)}


@router.get("/drift", summary="Drift result of an analysis (latest run that assessed drift by default)")
def get_drift(analysis_id: Optional[int] = None, db: Session = Depends(get_db)):
    if analysis_id:
        run = get_run_or_404(db, analysis_id)
        if run.status != "COMPLETED":
            raise AppError("That analysis is not completed.", 409, "analysis_not_ready")
        return {"analysis_id": run.id, **run.result["drift"]}
    runs = (db.query(AnalysisRun).filter(AnalysisRun.status == "COMPLETED")
            .order_by(AnalysisRun.id.desc()).limit(50).all())
    for run in runs:
        if run.result and run.result["drift"].get("available"):
            return {"analysis_id": run.id, **run.result["drift"]}
    return {"available": False, "analysis_id": runs[0].id if runs else None,
            "message": "Not available — no analysis has been compared with a reference dataset yet."}


@router.post("/drift/compare", summary="Compare two uploaded datasets for drift (not stored)")
def compare_drift(body: DriftCompareRequest, db: Session = Depends(get_db),
                  settings: Settings = Depends(get_app_settings)):
    if body.reference_dataset_id == body.current_dataset_id:
        raise AppError("Choose two different datasets.", 400, "invalid_reference")
    ref, cur = get_dataset_or_404(db, body.reference_dataset_id), get_dataset_or_404(db, body.current_dataset_id)
    ref_df, _ = load_cached(settings.upload_dir / ref.stored_filename, "." + ref.file_type, settings.max_rows)
    cur_df, _ = load_cached(settings.upload_dir / cur.stored_filename, "." + cur.file_type, settings.max_rows)
    info = {"dataset_id": ref.id, "name": ref.original_filename, "rows": ref.rows, "mode": "explicit"}
    return drift_svc.detect_drift(ref_df, cur_df, ANALYSIS_DEFAULTS, info)


@router.get("/alerts", summary="Alerts (default: those of the latest analysis)")
def list_alerts(analysis_id: Optional[int] = None, severity: Optional[str] = None,
                status: Optional[str] = Query(None, pattern="^(ACTIVE|ACKNOWLEDGED)$"),
                all_runs: bool = False, limit: int = Query(200, ge=1, le=1000), db: Session = Depends(get_db)):
    q = db.query(Alert, Dataset.original_filename).join(AnalysisRun, AnalysisRun.id == Alert.analysis_id) \
        .join(Dataset, Dataset.id == AnalysisRun.dataset_id)
    target = analysis_id
    if not target and not all_runs:
        latest = (db.query(AnalysisRun).filter(AnalysisRun.status == "COMPLETED")
                  .order_by(AnalysisRun.id.desc()).first())
        target = latest.id if latest else None
        if latest is None:
            return {"count": 0, "alerts": [], "by_severity": {}}
    if target:
        q = q.filter(Alert.analysis_id == target)
    if severity:
        if severity.upper() not in SEVERITY_ORDER:
            raise AppError(f"severity must be one of {', '.join(SEVERITY_ORDER)}", 400, "invalid_severity")
        q = q.filter(Alert.severity == severity.upper())
    if status:
        q = q.filter(Alert.status == status)
    rows = q.order_by(Alert.id.desc()).limit(limit).all()
    alerts = [{"id": a.id, "analysis_id": a.analysis_id, "dataset": name, "type": a.alert_type,
               "severity": a.severity, "message": a.message, "affected": a.affected,
               "recommended_action": a.recommended_action, "metric": a.metric, "value": a.value,
               "threshold": a.threshold, "status": a.status, "timestamp": iso(a.created_at)}
              for a, name in rows]
    alerts.sort(key=lambda a: (-SEVERITY_ORDER.index(a["severity"]), -a["id"]))
    return {"analysis_id": target, "count": len(alerts), "alerts": alerts,
            "by_severity": {lvl: sum(1 for a in alerts if a["severity"] == lvl) for lvl in reversed(SEVERITY_ORDER)}}


@router.patch("/alerts/{alert_id}/acknowledge", summary="Mark an alert as acknowledged")
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise AppError(f"Alert {alert_id} was not found.", 404, "alert_not_found")
    alert.status = "ACKNOWLEDGED"
    db.commit()
    return {"id": alert.id, "status": alert.status}
