from pathlib import Path

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException
)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import (
    APP_NAME,
    APP_VERSION
)

from app.schemas import (
    HealthResponse,
    AnalysisResponse
)

from app.utils.file_handler import (
    save_upload
)

from app.services.analyzer import (
    analyze_dataset
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
        "and anomaly detection API."
    ),

    version=APP_VERSION
)


# =====================================================
# SERVE FRONTEND STATIC FILES
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
        FRONTEND_DIR / "index.html"
    )


# =====================================================
# HEALTH CHECK
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
# ANALYZE CSV
# =====================================================

@app.post(
    "/api/analyze",
    response_model=AnalysisResponse
)
async def analyze(

    file: UploadFile = File(...)

):

    try:

        # -------------------------------------------------
        # SAVE UPLOADED FILE
        # -------------------------------------------------

        file_path = await save_upload(
            file
        )


        # -------------------------------------------------
        # ANALYZE DATASET
        # -------------------------------------------------

        result = analyze_dataset(
            file_path
        )


        # -------------------------------------------------
        # RETURN RESULT
        # -------------------------------------------------

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

        raise HTTPException(

            status_code=500,

            detail=(
                f"Analysis failed: "
                f"{str(error)}"
            )

        )