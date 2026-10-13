"""Analysis endpoints: start the unified pipeline and read any part of its result."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import (get_app_settings, get_completed_run, get_dataset_or_404, get_run_or_404,
                          run_brief)
from app.config import Settings, merge_analysis_config
from app.database import get_db
from app.models import AnalysisRun, Dataset, RemediationRun
from app.schemas import AnalyzeRequest, RemediationRequest
from app.services import remediation
from app.services.anomaly import select_features
from app.services.pipeline import run_analysis
from app.services.quality import assess_quality
from app.utils.file_handler import load_cached
from app.utils.helpers import SEVERITY_ORDER, iso, json_safe, utcnow
from app.utils.validators import AppError

router = APIRouter(prefix="/api", tags=["Analysis"])


def _full(run: AnalysisRun) -> dict:
    return {"analysis": run_brief(run), **run.result}


@router.post("/analyze/{dataset_id}", status_code=202,
             summary="Run the complete analysis pipeline on a dataset")
def analyze(dataset_id: int, background: BackgroundTasks, response: Response, wait: bool = Query(
            False, description="true = run synchronously and return the full result"),
            body: Optional[AnalyzeRequest] = Body(None), db: Session = Depends(get_db),
            settings: Settings = Depends(get_app_settings)):
    ds = get_dataset_or_404(db, dataset_id)
    body = body or AnalyzeRequest()
    if body.reference_dataset_id is not None:
        if body.reference_dataset_id == ds.id:
            raise AppError("A dataset cannot be its own reference.", 400, "invalid_reference")
        get_dataset_or_404(db, body.reference_dataset_id)
    options = {"auto_reference": body.auto_reference}
    thresholds = dict(body.thresholds or {})
    if thresholds:
        merge_analysis_config(thresholds)                  # validates types early
        options["thresholds"] = thresholds
    if body.validity_rules:
        options["validity_rules"] = body.validity_rules
    if body.allowed_values:
        options["allowed_values"] = body.allowed_values
    run = AnalysisRun(dataset_id=ds.id, reference_dataset_id=body.reference_dataset_id, status="QUEUED",
                      progress=0, current_step="Queued", options=options)
    db.add(run)
    db.commit()
    if wait:
        run_analysis(run.id, settings)
        db.refresh(run)
        if run.status == "FAILED":
            raise AppError(run.error_message or "The analysis failed.", 422, "analysis_failed")
        response.status_code = 200                         # finished synchronously -> 200 with the result
        return _full(run)
    background.add_task(run_analysis, run.id, settings)
    return {"analysis_id": run.id, "status": "QUEUED",
            "status_url": f"/api/analysis/{run.id}/status", "result_url": f"/api/analysis/{run.id}"}


@router.get("/analysis", summary="List analysis runs")
def list_analyses(dataset_id: Optional[int] = None, limit: int = Query(50, ge=1, le=500),
                  db: Session = Depends(get_db)):
    q = db.query(AnalysisRun, Dataset.original_filename).join(Dataset, Dataset.id == AnalysisRun.dataset_id)
    if dataset_id:
        q = q.filter(AnalysisRun.dataset_id == dataset_id)
    rows = q.order_by(AnalysisRun.id.desc()).limit(limit).all()
    return {"count": len(rows), "analyses": [{**run_brief(r), "dataset": name} for r, name in rows]}


@router.get("/analysis/{analysis_id}/status", summary="Progress of a running analysis")
def analysis_status(analysis_id: int, db: Session = Depends(get_db)):
    return run_brief(get_run_or_404(db, analysis_id))


@router.get("/analysis/{analysis_id}", summary="Unified analysis result")
def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    run = get_run_or_404(db, analysis_id)
    if run.status != "COMPLETED":
        return {"analysis": run_brief(run)}
    return _full(run)


@router.get("/analysis/{analysis_id}/profile", summary="Dataset profile")
def get_profile(run: AnalysisRun = Depends(get_completed_run)):
    return run.result["profile"]


@router.get("/analysis/{analysis_id}/quality", summary="Data quality assessment and canonical score")
def get_quality(run: AnalysisRun = Depends(get_completed_run)):
    return run.result["quality"]


@router.get("/analysis/{analysis_id}/anomalies", summary="Anomaly summary, detectors and records")
def get_anomalies(severity: Optional[str] = Query(None, description="LOW|MEDIUM|HIGH|CRITICAL"),
                  limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0),
                  run: AnalysisRun = Depends(get_completed_run)):
    if severity and severity.upper() not in SEVERITY_ORDER:
        raise AppError(f"severity must be one of {', '.join(SEVERITY_ORDER)}", 400, "invalid_severity")
    a = run.result["anomalies"]
    records = [r for r in a["records"] if not severity or r["severity"] == severity.upper()]
    return {"summary": a["summary"], "statistical": a["statistical"], "machine_learning": a["machine_learning"],
            "detectors": a["detectors"], "evaluation": run.result["evaluation"],
            "total_matching": len(records), "offset": offset, "limit": limit,
            "records": records[offset:offset + limit]}


@router.get("/analysis/{analysis_id}/explanations", summary="Plain-language explanation of important anomalies")
def get_explanations(severity: Optional[str] = None, limit: int = Query(100, ge=1, le=200),
                     run: AnalysisRun = Depends(get_completed_run)):
    items = run.result["explanations"]
    if severity:
        items = [e for e in items if e["severity"] == severity.upper()]
    return {"count": len(items), "explanations": items[:limit]}


@router.get("/analysis/{analysis_id}/recommendations", summary="Actionable recommendations")
def get_recommendations(run: AnalysisRun = Depends(get_completed_run)):
    return {"count": len(run.result["recommendations"]), "recommendations": run.result["recommendations"]}


@router.get("/analysis/{analysis_id}/remediation", summary="Remediation plan and any applied remediation")
def get_remediation(run: AnalysisRun = Depends(get_completed_run), db: Session = Depends(get_db)):
    applied = (db.query(RemediationRun).filter(RemediationRun.analysis_id == run.id)
               .order_by(RemediationRun.id.desc()).first())
    return {"plan": run.result["remediation"]["plan"],
            "safe_operations": remediation.SAFE_OPERATIONS, "opt_in_operations": remediation.OPT_IN_OPERATIONS,
            "applied": ({"remediation_id": applied.id, "created_at": iso(applied.created_at),
                         "download_url": f"/api/analysis/{run.id}/remediation/download", **applied.summary}
                        if applied else None)}


@router.post("/analysis/{analysis_id}/remediation/apply",
             summary="Apply remediation to a COPY of the data and return what changed")
def apply_remediation(body: Optional[RemediationRequest] = Body(None),
                      dry_run: bool = Query(False, description="true = preview the changes without saving anything"),
                      run: AnalysisRun = Depends(get_completed_run), db: Session = Depends(get_db),
                      settings: Settings = Depends(get_app_settings)):
    body = body or RemediationRequest()
    dataset = db.get(Dataset, run.dataset_id)
    df, meta = load_cached(settings.upload_dir / dataset.stored_filename, "." + dataset.file_type, settings.max_rows)
    cfg = merge_analysis_config((run.options or {}).get("thresholds"))
    opts = (run.options or {})
    quality, internal = assess_quality(df, cfg, meta.get("coerced"), opts)
    features, _ = select_features(df, cfg, internal["kinds"])
    try:
        cleaned, summary = remediation.apply_remediation(
            df, body.operations, {"numeric_strategy": body.numeric_strategy,
                                  "categorical_strategy": body.categorical_strategy,
                                  "winsorize_multiplier": body.winsorize_multiplier},
            quality, internal, features, cfg, meta.get("coerced"))
    except ValueError as exc:
        raise AppError(str(exc), 400, "invalid_remediation") from exc
    if dry_run:
        return {"dry_run": True, "download_url": None, **summary}
    filename = f"{run.id}_cleaned_{utcnow().strftime('%Y%m%d%H%M%S')}.csv"
    cleaned.to_csv(settings.processed_dir / filename, index=False)
    rec = RemediationRun(analysis_id=run.id, options=body.model_dump(exclude_none=True),
                         summary=json_safe(summary), cleaned_filename=filename)
    db.add(rec)
    db.commit()
    return {"remediation_id": rec.id, "download_url": f"/api/analysis/{run.id}/remediation/download", **summary}


@router.get("/analysis/{analysis_id}/remediation/download", summary="Download the cleaned dataset (CSV)")
def download_cleaned(analysis_id: int, db: Session = Depends(get_db),
                     settings: Settings = Depends(get_app_settings)):
    run = get_run_or_404(db, analysis_id)
    rec = (db.query(RemediationRun).filter(RemediationRun.analysis_id == run.id)
           .order_by(RemediationRun.id.desc()).first())
    if rec is None:
        raise AppError("No cleaned dataset exists yet. Apply remediation first.", 404, "no_cleaned_dataset")
    path = settings.processed_dir / rec.cleaned_filename
    if not path.exists():
        raise AppError("The cleaned file is no longer available. Apply remediation again.", 404, "file_missing")
    stem = db.get(Dataset, run.dataset_id).original_filename.rsplit(".", 1)[0]
    return FileResponse(path, media_type="text/csv", filename=f"{stem}_cleaned.csv")


@router.get("/analysis/{analysis_id}/decision", summary="Final decision and risk breakdown")
def get_decision(run: AnalysisRun = Depends(get_completed_run)):
    return {"decision": run.result["decision"], "insights": run.result["insights"],
            "pipeline": run.result["pipeline"]}


@router.delete("/analysis/{analysis_id}", summary="Delete an analysis run")
def delete_analysis(analysis_id: int, db: Session = Depends(get_db)):
    run = get_run_or_404(db, analysis_id)
    db.delete(run)
    db.commit()
    return {"deleted": analysis_id}
