from pathlib import Path

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Depends
)

from fastapi.staticfiles import (
    StaticFiles
)

from fastapi.responses import (
    FileResponse
)

from sqlalchemy.orm import Session

from app.config import (
    APP_NAME,
    APP_VERSION
)

from app.database import (
    engine,
    Base,
    get_db
)

from app.schemas import (
    HealthResponse,
    AnalysisResponse,
    HistoryResponse
)

from app.utils.file_handler import (
    save_upload
)

from app.services.analyzer import (
    analyze_dataset
)

from app.services.history import (
    save_analysis,
    get_analysis_history,
    get_analysis_by_id
)


# =====================================================
# CREATE DATABASE TABLES
# =====================================================

Base.metadata.create_all(
    bind=engine
)


# =====================================================
# PATH CONFIGURATION
# =====================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

FRONTEND_DIR = (
    BASE_DIR / "frontend"
)


# =====================================================
# FASTAPI APPLICATION
# =====================================================

app = FastAPI(

    title=APP_NAME,

    description=(
        "AI-powered data quality "
        "and anomaly detection "
        "with PostgreSQL history."
    ),

    version=APP_VERSION
)


# =====================================================
# FRONTEND
# =====================================================

app.mount(

    "/static",

    StaticFiles(
        directory=FRONTEND_DIR
    ),

    name="static"
)


# =====================================================
# DASHBOARD
# =====================================================

@app.get("/")
def dashboard():

    return FileResponse(
        FRONTEND_DIR /
        "index.html"
    )


# =====================================================
# HEALTH
# =====================================================

@app.get(
    "/health",
    response_model=HealthResponse
)
def health():

    return {

        "status":
            "healthy",

        "version":
            APP_VERSION,

        "message":
            "API is running successfully."
    }


# =====================================================
# ANALYZE DATASET
# =====================================================

@app.post(
    "/api/analyze",
    response_model=AnalysisResponse
)
async def analyze(

    file: UploadFile = File(...),

    db: Session = Depends(
        get_db
    )

):

    try:

        # ---------------------------------------------
        # SAVE CSV
        # ---------------------------------------------

        file_path = await save_upload(
            file
        )


        # ---------------------------------------------
        # ANALYZE
        # ---------------------------------------------

        result = analyze_dataset(
            file_path
        )


        # ---------------------------------------------
        # SAVE TO POSTGRESQL
        # ---------------------------------------------

        save_analysis(

            db=db,

            filename=file.filename,

            result=result

        )


        # ---------------------------------------------
        # RESPONSE
        # ---------------------------------------------

        return {

            "filename":
                file.filename,

            **result
        }


    except ValueError as error:

        raise HTTPException(

            status_code=400,

            detail=str(error)

        )


    except Exception as error:

        db.rollback()

        raise HTTPException(

            status_code=500,

            detail=(
                f"Analysis failed: "
                f"{str(error)}"
            )

        )


# =====================================================
# ANALYSIS HISTORY
# =====================================================

@app.get(
    "/api/history",
    response_model=list[
        HistoryResponse
    ]
)
def history(

    db: Session = Depends(
        get_db
    )

):

    return get_analysis_history(
        db
    )


# =====================================================
# SINGLE ANALYSIS
# =====================================================

@app.get(
    "/api/history/{analysis_id}"
)
def analysis_details(

    analysis_id: int,

    db: Session = Depends(
        get_db
    )

):

    analysis = (
        get_analysis_by_id(
            db,
            analysis_id
        )
    )


    if not analysis:

        raise HTTPException(

            status_code=404,

            detail=(
                "Analysis not found."
            )

        )


    return {

        "id":
            analysis.id,

        "filename":
            analysis.filename,

        "rows":
            analysis.rows,

        "columns":
            analysis.columns,

        "missing_values":
            analysis.missing_values,

        "duplicate_rows":
            analysis.duplicate_rows,

        "anomalies_detected":
            analysis.anomalies_detected,

        "created_at":
            analysis.created_at,

        "anomalies": [

            {

                "row":
                    anomaly.row_number,

                "feature":
                    anomaly.feature,

                "value":
                    anomaly.value,

                "z_score":
                    anomaly.z_score,

                "severity":
                    anomaly.severity,

                "recommendation":
                    anomaly.recommendation

            }

            for anomaly
            in analysis.anomalies

        ]

    }