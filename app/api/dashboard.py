"""Dashboard summary, health check and configuration endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import database
from app.api.deps import get_app_settings, get_run_or_404, run_brief
from app.config import ANALYSIS_DEFAULTS, APP_NAME, APP_VERSION, Settings
from app.database import get_db
from app.models import Alert, AnalysisRun, Dataset
from app.services import monitoring, reports
from app.utils.helpers import NOT_AVAILABLE, rnd
from app.utils.validators import AppError

router = APIRouter(prefix="/api", tags=["Dashboard"])


@router.get("/health", summary="Service and database health")
def health(settings: Settings = Depends(get_app_settings)):
    ok, detail = database.check_connection()
    return {"status": "ok" if ok else "degraded", "app": APP_NAME, "version": APP_VERSION,
            "database": {"connected": ok, "detail": detail,
                         "dialect": settings.database_url.split(":", 1)[0].split("+")[0]},
            "upload_limit_mb": settings.max_upload_bytes // (1024 * 1024),
            "allowed_extensions": list(settings.allowed_extensions)}


@router.get("/config", summary="Analysis thresholds and limits")
def config(settings: Settings = Depends(get_app_settings)):
    return {"thresholds": ANALYSIS_DEFAULTS.__dict__, "max_upload_mb": settings.max_upload_bytes // (1024 * 1024),
            "allowed_extensions": list(settings.allowed_extensions)}


@router.get("/dashboard/summary", summary="Everything the dashboard needs for one analysis (default: latest)")
def dashboard_summary(analysis_id: Optional[int] = Query(None, ge=1), db: Session = Depends(get_db)):
    totals = {"datasets": db.query(func.count(Dataset.id)).scalar() or 0,
              "analyses": db.query(func.count(AnalysisRun.id)).filter(AnalysisRun.status == "COMPLETED").scalar() or 0}
    if analysis_id:
        run = get_run_or_404(db, analysis_id)
        if run.status != "COMPLETED":
            raise AppError("That analysis has not completed.", 409, "analysis_not_ready")
    else:
        run = (db.query(AnalysisRun).filter(AnalysisRun.status == "COMPLETED")
               .order_by(AnalysisRun.id.desc()).first())
    if run is None or not run.result:
        return {"has_data": False, "totals": totals,
                "message": "No analysis yet. Upload a dataset and click “Analyze Dataset”."}

    r = run.result
    q, d, a, dr = r["quality"], r["decision"], r["anomalies"]["summary"], r["drift"]
    sev = a.get("severity_distribution", {})
    mon = r["monitoring"]
    prev = mon.get("previous")
    fc = r["forecast"]
    history = monitoring.get_history(db, group_key=run.dataset.group_key)
    history = [p for p in history if p["analysis_id"] <= run.id]
    from app.services import trends as trends_svc
    trend_live = trends_svc.analyze_trends(history)
    active_alerts = db.query(func.count(Alert.id)).filter(Alert.analysis_id == run.id, Alert.status == "ACTIVE").scalar()

    forecast_block = {"available": bool(fc.get("available")),
                      "message": fc.get("message") if not fc.get("available") else None}
    if fc.get("available"):
        forecast_block.update(
            quality=fc["forecast"]["quality_score"][-1]["value"],
            risk=fc["forecast"]["risk_score"][-1]["value"] if "risk_score" in fc["forecast"] else NOT_AVAILABLE,
            trend=fc.get("forecast_trend"), series=fc["forecast"], horizon=fc["horizon"])

    return {
        "has_data": True, "totals": totals, "analysis": run_brief(run),
        "dataset": r["dataset"],
        "health": {"quality_score": q["overall_score"], "quality_grade": q["grade"],
                   "risk_score": d["risk_score"], "risk_level": d["risk_level"],
                   "overall_status": d["overall_status"], "priority": d["priority"], "decision": d["decision"],
                   "recommended_action": d["recommended_action"], "automation": d["automation"],
                   "main_drivers": d["main_drivers"]},
        "profile": {"rows": q["summary"]["rows"], "columns": q["summary"]["columns"],
                    "missing_values": q["summary"]["missing_values"], "duplicate_rows": q["summary"]["duplicate_rows"],
                    "invalid_rows": q["summary"]["invalid_rows"],
                    "numerical_columns": len(r["profile"]["numerical_columns"]),
                    "categorical_columns": len(r["profile"]["categorical_columns"])},
        "anomalies": {"total": a["anomaly_count"], "pct": a["anomaly_pct"], "critical": sev.get("CRITICAL", 0),
                      "high": sev.get("HIGH", 0), "medium": sev.get("MEDIUM", 0), "low": sev.get("LOW", 0),
                      "weak_signals": a.get("weak_signal_count", 0), "detectors_run": a.get("detectors_run", []),
                      "ml_status": r["anomalies"]["machine_learning"].get("status"),
                      "ml_message": r["anomalies"]["machine_learning"].get("message")},
        "drift": ({"available": True, "drifted_features": dr["drifted_features"], "overall_status": dr["overall_status"],
                   "evaluated": dr["features_evaluated"], "reference": dr.get("reference")}
                  if dr.get("available") else {"available": False, "message": dr.get("message", NOT_AVAILABLE)}),
        "monitoring": {"previous_quality": prev["quality_score"] if prev else None,
                       "current_quality": q["overall_score"],
                       "trend": trend_live["overall_trend"], "runs_in_series": mon["runs_in_series"],
                       "message": mon["message"]},
        "forecast": forecast_block,
        "alerts": {"active": active_alerts, "top": r["alerts"][:5]},
        "insights": r["insights"],
        "top_recommendations": r["recommendations"][:5],
        "remediation": {"safe_fixes": [p for p in r["remediation"]["plan"] if p["safe"] and p["affected"]],
                        "plan_size": len(r["remediation"]["plan"])},
        "reports": [{"name": n, "url": f"/api/analysis/{run.id}/reports/{n}"} for n in reports.REPORT_NAMES],
        "charts": {
            "severity_distribution": sev,
            "feature_quality": [{"column": c["column"], "score": c["score"]} for c in q["column_quality"]],
            "dimensions": {k: v["score"] for k, v in q["dimensions"].items()},
            "drift_overview": ([{"feature": f["feature"], "psi": f["psi"], "status": f["status"]}
                                for f in dr["features"] if f["psi"] is not None][:12] if dr.get("available") else []),
            "trend_series": trend_live["series"], "trend": trend_live,
        },
    }
