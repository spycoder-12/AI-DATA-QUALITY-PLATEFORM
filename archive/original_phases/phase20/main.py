import os
import uuid

from pathlib import Path

from datetime import datetime

import pandas as pd

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException
)

from fastapi.responses import FileResponse

from fastapi.staticfiles import StaticFiles

from sqlalchemy.orm import Session

from database import (
    engine,
    SessionLocal,
    Base,
    MonitoringRun,
    UploadedDataset
)

from upload_service import (
    read_uploaded_file
)


# ============================================================
# APPLICATION PATH
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PROJECT_DIR = os.path.dirname(
    BASE_DIR
)


# ============================================================
# PHASE REPORT DIRECTORIES
# ============================================================

PHASE17_DIR = os.path.join(
    PROJECT_DIR,
    "phase17",
    "reports"
)

PHASE18_DIR = os.path.join(
    PROJECT_DIR,
    "phase18",
    "reports"
)

PHASE19_DIR = os.path.join(
    PROJECT_DIR,
    "phase19",
    "reports"
)


# ============================================================
# PHASE 20 DIRECTORIES
# ============================================================

REPORT_DIR = os.path.join(
    BASE_DIR,
    "reports"
)

STATIC_DIR = os.path.join(
    BASE_DIR,
    "static"
)

UPLOAD_DIR = os.path.join(
    BASE_DIR,
    "uploads"
)


# ============================================================
# CREATE DIRECTORIES
# ============================================================

os.makedirs(
    REPORT_DIR,
    exist_ok=True
)

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(

    title=(
        "AI Data Quality "
        "Intelligence Platform"
    ),

    description=(
        "Unified AI Data Quality "
        "Monitoring, Anomaly Detection, "
        "Drift Analysis, Forecasting "
        "and Dataset Upload Platform"
    ),

    version="20.0.0"
)


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

Base.metadata.create_all(
    bind=engine
)


# ============================================================
# REPORT HELPER
# ============================================================

def find_report(
    directory,
    filename
):

    path = os.path.join(
        directory,
        filename
    )

    if os.path.exists(path):

        return path

    return None


# ============================================================
# SAFE CSV READER
# ============================================================

def read_csv_safe(path):

    if not path:

        return pd.DataFrame()

    try:

        return pd.read_csv(
            path
        )

    except Exception as error:

        print(
            f"Could not read report: {error}"
        )

        return pd.DataFrame()


# ============================================================
# PHASE 17
# ============================================================

def load_phase17():

    path = find_report(
        PHASE17_DIR,
        "phase17_monitoring_summary.csv"
    )

    return read_csv_safe(
        path
    )


# ============================================================
# PHASE 17 ALERTS
# ============================================================

def load_alerts():

    path = find_report(
        PHASE17_DIR,
        "phase17_alert_report.csv"
    )

    return read_csv_safe(
        path
    )


# ============================================================
# PHASE 18 SUMMARY
# ============================================================

def load_phase18_summary():

    path = find_report(
        PHASE18_DIR,
        "phase18_forecast_summary.csv"
    )

    return read_csv_safe(
        path
    )


# ============================================================
# PHASE 18 FORECAST
# ============================================================

def load_forecast():

    path = find_report(
        PHASE18_DIR,
        "phase18_forecast_report.csv"
    )

    return read_csv_safe(
        path
    )


# ============================================================
# PHASE 18 TREND
# ============================================================

def load_trend():

    path = find_report(
        PHASE18_DIR,
        "phase18_trend_report.csv"
    )

    return read_csv_safe(
        path
    )


# ============================================================
# PHASE 19
# ============================================================

def load_phase19():

    path = find_report(
        PHASE19_DIR,
        "phase19_decision_report.csv"
    )

    return read_csv_safe(
        path
    )


# ============================================================
# SAFE VALUE
# ============================================================

def safe_value(
    dataframe,
    column,
    default=0
):

    if dataframe.empty:

        return default

    if column not in dataframe.columns:

        return default

    value = dataframe.iloc[0][
        column
    ]

    if pd.isna(value):

        return default

    return value


# ============================================================
# BUILD DASHBOARD DATA
# ============================================================

def build_dashboard_data():

    phase17 = load_phase17()

    alerts_df = load_alerts()

    phase18 = load_phase18_summary()

    forecast_df = load_forecast()

    trend_df = load_trend()

    phase19 = load_phase19()


    # ========================================================
    # PHASE 17
    # ========================================================

    quality_score = float(
        safe_value(
            phase17,
            "quality_score",
            0
        )
    )

    anomaly_count = int(
        safe_value(
            phase17,
            "anomalies",
            0
        )
    )

    drifted_features = int(
        safe_value(
            phase17,
            "drifted_features",
            0
        )
    )

    alert_count = int(
        safe_value(
            phase17,
            "alerts",
            len(alerts_df)
        )
    )

    status = str(
        safe_value(
            phase17,
            "status",
            "UNKNOWN"
        )
    )

    risk_level = str(
        safe_value(
            phase17,
            "risk",
            "UNKNOWN"
        )
    )


    # ========================================================
    # PHASE 18
    # ========================================================

    forecast_quality = float(
        safe_value(
            phase18,
            "forecast_quality",
            quality_score
        )
    )

    forecast_risk = float(
        safe_value(
            phase18,
            "forecast_risk",
            max(
                100 - forecast_quality,
                0
            )
        )
    )

    overall_trend = str(
        safe_value(
            phase18,
            "overall_trend",
            "STABLE"
        )
    )


    # ========================================================
    # PHASE 19
    # ========================================================

    risk_score = float(
        safe_value(
            phase19,
            "risk_score",
            max(
                100 - quality_score,
                0
            )
        )
    )

    decision = str(
        safe_value(
            phase19,
            "decision",
            "DATASET HEALTHY"
        )
    )

    priority = str(
        safe_value(
            phase19,
            "priority",
            "P4 - LOW"
        )
    )

    automation = str(
        safe_value(
            phase19,
            "automation",
            "NO REMEDIATION REQUIRED"
        )
    )


    # ========================================================
    # TREND
    # ========================================================

    trend_records = []

    if not trend_df.empty:

        trend_records = (
            trend_df
            .fillna("")
            .to_dict(
                orient="records"
            )
        )


    # ========================================================
    # FORECAST
    # ========================================================

    forecast_records = []

    if not forecast_df.empty:

        forecast_records = (
            forecast_df
            .fillna("")
            .to_dict(
                orient="records"
            )
        )


    # ========================================================
    # ALERTS
    # ========================================================

    alert_records = []

    if not alerts_df.empty:

        alert_records = (
            alerts_df
            .fillna("")
            .to_dict(
                orient="records"
            )
        )


    return {

        "quality_score":
            round(
                quality_score,
                2
            ),

        "anomaly_count":
            anomaly_count,

        "drifted_features":
            drifted_features,

        "alert_count":
            alert_count,

        "risk_score":
            round(
                risk_score,
                2
            ),

        "risk_level":
            risk_level,

        "status":
            status,

        "forecast_quality":
            round(
                forecast_quality,
                2
            ),

        "forecast_risk":
            round(
                forecast_risk,
                2
            ),

        "overall_trend":
            overall_trend,

        "decision":
            decision,

        "priority":
            priority,

        "automation":
            automation,

        "trend":
            trend_records,

        "forecast":
            forecast_records,

        "alerts":
            alert_records
    }


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def home():

    return FileResponse(
        os.path.join(
            STATIC_DIR,
            "index.html"
        )
    )


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {

        "status": "healthy",

        "phase": 20,

        "service":
            "AI Data Quality Intelligence Platform"
    }


# ============================================================
# DASHBOARD SUMMARY
# ============================================================

@app.get(
    "/api/dashboard/summary"
)
def dashboard_summary():

    data = build_dashboard_data()

    return {

        "quality_score":
            data["quality_score"],

        "anomaly_count":
            data["anomaly_count"],

        "drifted_features":
            data["drifted_features"],

        "alert_count":
            data["alert_count"],

        "risk_score":
            data["risk_score"],

        "risk_level":
            data["risk_level"],

        "status":
            data["status"],

        "forecast_quality":
            data["forecast_quality"],

        "forecast_risk":
            data["forecast_risk"],

        "overall_trend":
            data["overall_trend"],

        "decision":
            data["decision"],

        "priority":
            data["priority"],

        "automation":
            data["automation"]
    }


# ============================================================
# SEVERITY
# ============================================================

@app.get(
    "/api/dashboard/severity"
)
def dashboard_severity():

    alerts_df = load_alerts()

    result = {

        "CRITICAL": 0,

        "HIGH": 0,

        "MEDIUM": 0,

        "WARNING": 0,

        "LOW": 0
    }


    if not alerts_df.empty:

        if "severity" in alerts_df.columns:

            for value in alerts_df[
                "severity"
            ].astype(str):

                severity = value.upper()

                if severity in result:

                    result[
                        severity
                    ] += 1


    return [

        {
            "severity": severity,
            "count": count
        }

        for severity, count
        in result.items()
    ]


# ============================================================
# ALERTS
# ============================================================

@app.get(
    "/api/dashboard/alerts"
)
def dashboard_alerts():

    data = build_dashboard_data()

    return data["alerts"]


# ============================================================
# TRENDS
# ============================================================

@app.get(
    "/api/dashboard/trends"
)
def dashboard_trends():

    data = build_dashboard_data()

    return data["trend"]


# ============================================================
# FORECAST
# ============================================================

@app.get(
    "/api/dashboard/forecast"
)
def dashboard_forecast():

    data = build_dashboard_data()

    return data["forecast"]


# ============================================================
# COMPLETE DASHBOARD
# ============================================================

@app.get(
    "/api/dashboard/all"
)
def dashboard_all():

    data = build_dashboard_data()

    save_monitoring_run(data)

    return data


# ============================================================
# DATABASE HISTORY
# ============================================================

@app.get(
    "/api/history"
)
def database_history():

    db: Session = SessionLocal()

    try:

        records = (
            db.query(
                MonitoringRun
            )
            .order_by(
                MonitoringRun.id.desc()
            )
            .limit(30)
            .all()
        )


        return [

            {

                "id":
                    item.id,

                "quality_score":
                    item.quality_score,

                "anomaly_count":
                    item.anomaly_count,

                "drifted_features":
                    item.drifted_features,

                "alerts":
                    item.alerts,

                "risk_score":
                    item.risk_score,

                "risk_level":
                    item.risk_level,

                "status":
                    item.status,

                "decision":
                    item.decision,

                "created_at":
                    (
                        item.created_at.isoformat()
                        if item.created_at
                        else None
                    )
            }

            for item in records
        ]

    finally:

        db.close()



# ============================================================
# SAVE MONITORING RUN
# ============================================================

def save_monitoring_run(data):
    """Persist a dashboard snapshot in PostgreSQL."""
    db: Session = SessionLocal()

    try:
        run = MonitoringRun(
            quality_score=float(data.get("quality_score", 0)),
            anomaly_count=int(data.get("anomaly_count", 0)),
            drifted_features=int(data.get("drifted_features", 0)),
            alerts=int(data.get("alert_count", 0)),
            risk_score=float(data.get("risk_score", 0)),
            risk_level=str(data.get("risk_level", "UNKNOWN")),
            status=str(data.get("status", "UNKNOWN")),
            decision=str(data.get("decision", "UNKNOWN")),
            created_at=datetime.now()
        )

        db.add(run)
        db.commit()
        db.refresh(run)
        return run.id

    except Exception as error:
        db.rollback()
        print(f"Monitoring history save error: {error}")
        return None

    finally:
        db.close()


# ============================================================
# RECORD CURRENT DASHBOARD SNAPSHOT
# ============================================================

@app.post("/api/history/record")
def record_dashboard_history():
    data = build_dashboard_data()

    record_id = save_monitoring_run(data)

    if record_id is None:
        raise HTTPException(
            status_code=500,
            detail="Could not save monitoring history."
        )

    return {
        "success": True,
        "id": record_id,
        "message": "Monitoring snapshot saved successfully."
    }


# ============================================================
# DELETE ONE MONITORING HISTORY RECORD
# ============================================================

@app.delete("/api/history/{run_id}")
def delete_history(run_id: int):
    db: Session = SessionLocal()

    try:
        record = (
            db.query(MonitoringRun)
            .filter(MonitoringRun.id == run_id)
            .first()
        )

        if not record:
            raise HTTPException(
                status_code=404,
                detail="Monitoring history record not found."
            )

        db.delete(record)
        db.commit()

        return {
            "success": True,
            "message": f"Monitoring history record {run_id} deleted."
        }

    except HTTPException:
        raise

    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Could not delete history: {error}"
        )

    finally:
        db.close()


# ============================================================
# DELETE ALL MONITORING HISTORY
# ============================================================

@app.delete("/api/history")
def delete_all_history():
    db: Session = SessionLocal()

    try:
        deleted_count = (
            db.query(MonitoringRun)
            .delete(synchronize_session=False)
        )

        db.commit()

        return {
            "success": True,
            "deleted_records": deleted_count,
            "message": "All monitoring history deleted."
        }

    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Could not delete history: {error}"
        )

    finally:
        db.close()


# ============================================================
# ANALYZE DATAFRAME
# ============================================================

def analyze_dataframe(
    dataframe
):

    rows = len(
        dataframe
    )

    columns = len(
        dataframe.columns
    )


    # ========================================================
    # MISSING
    # ========================================================

    missing_values = int(
        dataframe
        .isnull()
        .sum()
        .sum()
    )


    # ========================================================
    # DUPLICATES
    # ========================================================

    duplicate_rows = int(
        dataframe
        .duplicated()
        .sum()
    )


    # ========================================================
    # COMPLETENESS
    # ========================================================

    total_cells = (
        rows * columns
    )

    if total_cells > 0:

        completeness = round(
            (
                1 -
                missing_values /
                total_cells
            ) * 100,
            2
        )

    else:

        completeness = 0


    # ========================================================
    # NUMERIC FEATURES
    # ========================================================

    numeric_columns = (
        dataframe
        .select_dtypes(
            include="number"
        )
        .columns
        .tolist()
    )


    # ========================================================
    # ANOMALIES
    # ========================================================

    anomaly_rows = set()

    anomaly_features = []


    for column in numeric_columns:

        if column.lower() in [
            "id",
            "is_anomaly"
        ]:

            continue


        series = dataframe[
            column
        ].dropna()


        if len(series) < 3:

            continue


        std = series.std()


        if pd.isna(std) or std == 0:

            continue


        mean = series.mean()


        z_scores = (
            series - mean
        ) / std


        abnormal = (
            z_scores.abs() >= 3
        )


        indices = (
            series.index[
                abnormal
            ]
        )


        for index in indices:

            anomaly_rows.add(
                int(index)
            )


        if abnormal.any():

            anomaly_features.append(
                column
            )


    anomaly_count = len(
        anomaly_rows
    )


    # ========================================================
    # QUALITY SCORE
    # ========================================================

    quality_score = 100.0


    if total_cells > 0:

        missing_rate = (
            missing_values /
            total_cells
        ) * 100

        quality_score -= min(
            missing_rate * 2,
            30
        )


    if rows > 0:

        duplicate_rate = (
            duplicate_rows /
            rows
        ) * 100

        quality_score -= min(
            duplicate_rate * 2,
            20
        )


        anomaly_rate = (
            anomaly_count /
            rows
        )


        quality_score -= min(
            anomaly_rate * 20,
            30
        )


    quality_score = round(
        max(
            quality_score,
            0
        ),
        2
    )


    # ========================================================
    # RISK
    # ========================================================

    if quality_score >= 90:

        risk_level = "LOW"

    elif quality_score >= 75:

        risk_level = "MEDIUM"

    elif quality_score >= 50:

        risk_level = "HIGH"

    else:

        risk_level = "CRITICAL"


    # ========================================================
    # RECOMMENDATIONS
    # ========================================================

    recommendations = []


    if missing_values > 0:

        recommendations.append(
            "Review and handle missing values."
        )


    if duplicate_rows > 0:

        recommendations.append(
            "Remove or investigate duplicate rows."
        )


    if anomaly_count > 0:

        recommendations.append(
            "Investigate anomalous records using XAI."
        )


    if not recommendations:

        recommendations.append(
            "No major data-quality issue detected."
        )


    return {

        "rows":
            rows,

        "columns":
            columns,

        "column_names":
            dataframe.columns.tolist(),

        "numeric_features":
            numeric_columns,

        "missing_values":
            missing_values,

        "duplicate_rows":
            duplicate_rows,

        "completeness":
            completeness,

        "anomaly_count":
            anomaly_count,

        "anomaly_features":
            anomaly_features,

        "quality_score":
            quality_score,

        "risk_level":
            risk_level,

        "recommendations":
            recommendations
    }


# ============================================================
# UPLOAD DATASET
# ============================================================

@app.post(
    "/api/upload"
)
async def upload_dataset(
    file: UploadFile = File(...)
):

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="No file selected."
        )


    extension = Path(
        file.filename
    ).suffix.lower()


    allowed_extensions = {

        ".csv",
        ".xlsx",
        ".xls",
        ".pdf"
    }


    if extension not in allowed_extensions:

        raise HTTPException(

            status_code=400,

            detail=(
                "Unsupported file type. "
                "Allowed formats: "
                "CSV, XLSX, XLS and PDF."
            )
        )


    # ========================================================
    # SAFE STORED NAME
    # ========================================================

    stored_filename = (
        f"{uuid.uuid4().hex}"
        f"{extension}"
    )


    file_path = os.path.join(
        UPLOAD_DIR,
        stored_filename
    )


    # ========================================================
    # SAVE FILE
    # ========================================================

    try:

        with open(
            file_path,
            "wb"
        ) as buffer:

            while True:

                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:

                    break

                buffer.write(
                    chunk
                )

    except Exception as error:

        raise HTTPException(

            status_code=500,

            detail=(
                f"Could not save file: {error}"
            )
        )


    # ========================================================
    # READ DATA
    # ========================================================

    try:

        dataframe = read_uploaded_file(
            file_path
        )

    except Exception as error:

        if os.path.exists(
            file_path
        ):

            os.remove(
                file_path
            )


        raise HTTPException(

            status_code=400,

            detail=(
                f"Could not process file: {error}"
            )
        )


    # ========================================================
    # ANALYZE
    # ========================================================

    analysis = analyze_dataframe(
        dataframe
    )


    # ========================================================
    # SAVE DATABASE RECORD
    # ========================================================

    db: Session = SessionLocal()


    try:

        dataset = UploadedDataset(

            original_filename=
                file.filename,

            stored_filename=
                stored_filename,

            file_type=
                extension,

            rows=
                analysis["rows"],

            columns=
                analysis["columns"],

            missing_values=
                analysis["missing_values"],

            duplicate_rows=
                analysis["duplicate_rows"],

            anomaly_count=
                analysis["anomaly_count"],

            completeness=
                analysis["completeness"],

            quality_score=
                analysis["quality_score"],

            risk_level=
                analysis["risk_level"],

            uploaded_at=
                datetime.now()
        )


        db.add(
            dataset
        )

        db.commit()

        db.refresh(
            dataset
        )


        dataset_id = dataset.id


    except Exception as error:

        db.rollback()

        if os.path.exists(
            file_path
        ):

            os.remove(
                file_path
            )


        raise HTTPException(

            status_code=500,

            detail=(
                f"Database error: {error}"
            )
        )


    finally:

        db.close()


    # ========================================================
    # RESPONSE
    # ========================================================

    return {

        "success": True,

        "message":
            "Dataset uploaded and analyzed successfully.",

        "dataset_id":
            dataset_id,

        "filename":
            file.filename,

        "stored_filename":
            stored_filename,

        "file_type":
            extension,

        "analysis":
            analysis
    }


# ============================================================
# UPLOAD HISTORY
# ============================================================

@app.get(
    "/api/uploads"
)
def uploaded_datasets():

    db: Session = SessionLocal()


    try:

        records = (
            db.query(
                UploadedDataset
            )
            .order_by(
                UploadedDataset.id.desc()
            )
            .limit(50)
            .all()
        )


        return [

            {

                "id":
                    item.id,

                "filename":
                    item.original_filename,

                "stored_filename":
                    item.stored_filename,

                "file_type":
                    item.file_type,

                "rows":
                    item.rows,

                "columns":
                    item.columns,

                "missing_values":
                    item.missing_values,

                "duplicate_rows":
                    item.duplicate_rows,

                "anomaly_count":
                    item.anomaly_count,

                "completeness":
                    item.completeness,

                "quality_score":
                    item.quality_score,

                "risk_level":
                    item.risk_level,

                "uploaded_at":
                    (
                        item.uploaded_at.isoformat()
                        if item.uploaded_at
                        else None
                    )
            }

            for item in records
        ]

    finally:

        db.close()


# ============================================================
# DELETE UPLOAD
# ============================================================

@app.delete(
    "/api/uploads/{dataset_id}"
)
def delete_uploaded_dataset(
    dataset_id: int
):

    db: Session = SessionLocal()


    try:

        dataset = (
            db.query(
                UploadedDataset
            )
            .filter(
                UploadedDataset.id ==
                dataset_id
            )
            .first()
        )


        if not dataset:

            raise HTTPException(

                status_code=404,

                detail="Dataset not found."
            )


        file_path = os.path.join(
            UPLOAD_DIR,
            dataset.stored_filename
        )


        if os.path.exists(
            file_path
        ):

            os.remove(
                file_path
            )


        db.delete(
            dataset
        )

        db.commit()


        return {

            "success": True,

            "message":
                "Dataset deleted successfully."
        }


    except HTTPException:

        raise


    except Exception as error:

        db.rollback()

        raise HTTPException(

            status_code=500,

            detail=str(error)
        )


    finally:

        db.close()


# ============================================================
# STATIC FILES
# ============================================================

app.mount(

    "/static",

    StaticFiles(
        directory=STATIC_DIR
    ),

    name="static"
)


# ============================================================
# STARTUP
# ============================================================

@app.on_event(
    "startup"
)
def startup():

    print("=" * 70)

    print(
        "AI DATA QUALITY & ANOMALY DETECTION ENGINE"
    )

    print("=" * 70)

    print(
        "PHASE 20 - UNIFIED AI DATA QUALITY "
        "INTELLIGENCE PLATFORM"
    )

    print("=" * 70)

    print(
        f"Phase 17 reports: "
        f"{os.path.exists(PHASE17_DIR)}"
    )

    print(
        f"Phase 18 reports: "
        f"{os.path.exists(PHASE18_DIR)}"
    )

    print(
        f"Phase 19 reports: "
        f"{os.path.exists(PHASE19_DIR)}"
    )

    print(
        f"Upload directory: "
        f"{UPLOAD_DIR}"
    )

    print(
        "Supported files:"
    )

    print(
        "CSV | XLSX | XLS | PDF"
    )

    print(
        "PostgreSQL database initialized."
    )

    print("=" * 70)