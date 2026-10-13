"""Report downloads (rendered from the stored analysis result - no re-analysis)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_completed_run
from app.database import get_db
from app.models import AnalysisRun, Dataset
from app.services import monitoring, reports
from app.utils.validators import AppError

router = APIRouter(prefix="/api/analysis", tags=["Reports"])


def _history(db: Session, run: AnalysisRun) -> list:
    ds = db.get(Dataset, run.dataset_id)
    points = [p for p in monitoring.get_history(db, group_key=ds.group_key) if p["analysis_id"] <= run.id]
    return points


@router.get("/{analysis_id}/reports", summary="List downloadable reports")
def list_reports(run: AnalysisRun = Depends(get_completed_run)):
    return {"analysis_id": run.id, "reports": [
        {"name": n, "format": "html" if n == "full_report" else "csv",
         "url": f"/api/analysis/{run.id}/reports/{n}"} for n in reports.REPORT_NAMES]}


@router.get("/{analysis_id}/reports/{name}", summary="Download one report (CSV, or full_report as HTML)")
def download_report(name: str, run: AnalysisRun = Depends(get_completed_run), db: Session = Depends(get_db)):
    if name not in reports.REPORT_NAMES:                       # whitelist - no path is ever built from input
        raise AppError(f"Unknown report '{name}'. Available: {', '.join(reports.REPORT_NAMES)}.", 404, "unknown_report")
    history = _history(db, run)
    if name == "full_report":
        return Response(reports.build_html(run.result, history), media_type="text/html",
                        headers={"Content-Disposition": f'attachment; filename="full_report_{run.id}.html"'})
    frame = reports.build_frames(run.result, history)[name]
    return Response(frame.to_csv(index=False), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}_{run.id}.csv"'})
