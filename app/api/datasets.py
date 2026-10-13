"""Dataset upload and management endpoints."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import dataset_out, get_app_settings, get_dataset_or_404
from app.config import Settings
from app.database import get_db
from app.models import AnalysisRun, Dataset
from app.utils.file_handler import load_cached, preview_frame, public_meta, save_upload
from app.utils.validators import AppError

router = APIRouter(prefix="/api/datasets", tags=["Datasets"])


def group_key_for(filename: str) -> str:
    """Uploads with the same base name form one monitored dataset series."""
    return re.sub(r"[^a-z0-9]+", "_", Path(filename).stem.lower()).strip("_") or "dataset"


@router.post("/upload", status_code=201, summary="Upload and validate a dataset (CSV, XLSX, XLS, PDF table)")
def upload_dataset(file: UploadFile = File(...), is_reference: bool = Form(False),
                   db: Session = Depends(get_db), settings: Settings = Depends(get_app_settings)):
    saved = save_upload(file, settings)
    try:
        df, meta = load_cached(saved.path, saved.extension, settings.max_rows)   # validates the content
    except AppError:
        saved.path.unlink(missing_ok=True)
        raise
    ds = Dataset(original_filename=saved.original_filename, stored_filename=saved.stored_filename,
                 file_type=saved.extension.lstrip("."), size_bytes=saved.size_bytes, sha256=saved.sha256,
                 group_key=group_key_for(saved.original_filename), is_reference=is_reference,
                 rows=int(len(df)), columns=int(df.shape[1]), load_info=public_meta(meta))
    try:
        db.add(ds)
        db.commit()
    except Exception:
        db.rollback()
        saved.path.unlink(missing_ok=True)
        raise
    info = public_meta(meta)
    return {
        "dataset": dataset_out(ds),
        "validation": {
            "status": "VALID", "rows": int(len(df)), "columns": int(df.shape[1]),
            "column_names": list(df.columns), "encoding": info.get("encoding"),
            "delimiter": info.get("delimiter"), "column_map": info.get("column_map"),
            "dropped_empty_rows": info.get("dropped_empty_rows", 0),
            "dropped_empty_columns": info.get("dropped_empty_columns", 0),
            "missing_values": int(df.isna().sum().sum()), "duplicate_rows": int(df.duplicated().sum()),
            "warnings": info.get("warnings", []),
        },
        "preview": preview_frame(df),
    }


@router.get("", summary="List uploaded datasets")
def list_datasets(db: Session = Depends(get_db)):
    counts = dict(db.query(AnalysisRun.dataset_id, func.count(AnalysisRun.id)).group_by(AnalysisRun.dataset_id).all())
    out = []
    for ds in db.query(Dataset).order_by(Dataset.uploaded_at.desc(), Dataset.id.desc()).all():
        latest = (db.query(AnalysisRun).filter(AnalysisRun.dataset_id == ds.id)
                  .order_by(AnalysisRun.id.desc()).first())
        out.append(dataset_out(ds, latest, counts.get(ds.id, 0)))
    return {"count": len(out), "datasets": out}


@router.get("/{dataset_id}", summary="Dataset details and its analyses")
def get_dataset(dataset_id: int, db: Session = Depends(get_db)):
    ds = get_dataset_or_404(db, dataset_id)
    runs = db.query(AnalysisRun).filter(AnalysisRun.dataset_id == ds.id).order_by(AnalysisRun.id.desc()).all()
    from app.api.deps import run_brief
    out = dataset_out(ds, runs[0] if runs else None, len(runs))
    out["load_info"] = ds.load_info
    out["analyses_list"] = [run_brief(r) for r in runs]
    return out


@router.get("/{dataset_id}/preview", summary="First rows of the dataset")
def preview(dataset_id: int, rows: int = 20, db: Session = Depends(get_db),
            settings: Settings = Depends(get_app_settings)):
    ds = get_dataset_or_404(db, dataset_id)
    df, _ = load_cached(settings.upload_dir / ds.stored_filename, "." + ds.file_type, settings.max_rows)
    return preview_frame(df, max(1, min(rows, 200)))


@router.get("/{dataset_id}/download", summary="Download the ORIGINAL uploaded file (never modified)")
def download_original(dataset_id: int, db: Session = Depends(get_db),
                      settings: Settings = Depends(get_app_settings)):
    ds = get_dataset_or_404(db, dataset_id)
    path = settings.upload_dir / ds.stored_filename
    if not path.exists():
        raise AppError("The original file is no longer on the server.", 404, "file_missing")
    return FileResponse(path, filename=ds.original_filename)


@router.delete("/{dataset_id}", summary="Delete a dataset, its analyses and its stored file")
def delete_dataset(dataset_id: int, db: Session = Depends(get_db),
                   settings: Settings = Depends(get_app_settings)):
    ds = get_dataset_or_404(db, dataset_id)
    stored = settings.upload_dir / ds.stored_filename
    db.delete(ds)
    db.commit()
    stored.unlink(missing_ok=True)
    return {"deleted": dataset_id}
