from pathlib import Path

from fastapi import (
    FastAPI,
    HTTPException
)

from fastapi.staticfiles import StaticFiles

from fastapi.responses import FileResponse

from sqlalchemy import create_engine, text


# =====================================================
# DATABASE CONFIGURATION
# =====================================================

DATABASE_URL = (
    "postgresql+psycopg2://"
    "postgres:<REDACTED>@localhost:5432/"
    "ai_data_quality"
)


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)


# =====================================================
# PATH CONFIGURATION
# =====================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
)

FRONTEND_DIR = (
    BASE_DIR / "frontend"
)


# =====================================================
# FASTAPI
# =====================================================

app = FastAPI(

    title=(
        "AI Data Quality "
        "Analytics Dashboard"
    ),

    version="11.0.0",

    description=(
        "Advanced analytics dashboard "
        "for AI Data Quality and "
        "Anomaly Detection Engine."
    )
)


# =====================================================
# STATIC FILES
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
# HEALTH
# =====================================================

@app.get("/health")
def health():

    try:

        with engine.connect() as connection:

            connection.execute(
                text("SELECT 1")
            )

        return {

            "status": "healthy",

            "database":
                "connected",

            "version":
                "11.0.0"
        }

    except Exception as error:

        return {

            "status":
                "unhealthy",

            "database":
                "disconnected",

            "error":
                str(error)
        }


# =====================================================
# DASHBOARD SUMMARY
# =====================================================

@app.get("/api/dashboard/summary")
def dashboard_summary():

    try:

        with engine.connect() as db:

            total_analyses = db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM analyses
                    """
                )
            ).scalar()

            total_rows = db.execute(
                text(
                    """
                    SELECT COALESCE(
                        SUM(rows), 0
                    )
                    FROM analyses
                    """
                )
            ).scalar()

            total_anomalies = db.execute(
                text(
                    """
                    SELECT COALESCE(
                        SUM(anomalies_detected),
                        0
                    )
                    FROM analyses
                    """
                )
            ).scalar()

            total_missing = db.execute(
                text(
                    """
                    SELECT COALESCE(
                        SUM(missing_values),
                        0
                    )
                    FROM analyses
                    """
                )
            ).scalar()

            total_duplicates = db.execute(
                text(
                    """
                    SELECT COALESCE(
                        SUM(duplicate_rows),
                        0
                    )
                    FROM analyses
                    """
                )
            ).scalar()


        return {

            "total_analyses":
                total_analyses,

            "total_rows":
                total_rows,

            "total_anomalies":
                total_anomalies,

            "total_missing_values":
                total_missing,

            "total_duplicates":
                total_duplicates
        }


    except Exception as error:

        raise HTTPException(

            status_code=500,

            detail=str(error)
        )


# =====================================================
# SEVERITY DISTRIBUTION
# =====================================================

@app.get(
    "/api/dashboard/severity"
)
def severity_distribution():

    try:

        with engine.connect() as db:

            result = db.execute(
                text(
                    """
                    SELECT
                        severity,
                        COUNT(*) AS total
                    FROM anomalies
                    GROUP BY severity
                    ORDER BY total DESC
                    """
                )
            )

            data = [

                {
                    "severity":
                        row[0],

                    "count":
                        row[1]
                }

                for row in result
            ]


        return data


    except Exception as error:

        raise HTTPException(

            status_code=500,

            detail=str(error)
        )


# =====================================================
# FEATURE DISTRIBUTION
# =====================================================

@app.get(
    "/api/dashboard/features"
)
def feature_distribution():

    try:

        with engine.connect() as db:

            result = db.execute(
                text(
                    """
                    SELECT
                        feature,
                        COUNT(*) AS total
                    FROM anomalies
                    GROUP BY feature
                    ORDER BY total DESC
                    LIMIT 10
                    """
                )
            )

            data = [

                {
                    "feature":
                        row[0],

                    "count":
                        row[1]
                }

                for row in result
            ]


        return data


    except Exception as error:

        raise HTTPException(

            status_code=500,

            detail=str(error)
        )


# =====================================================
# ANALYSIS HISTORY
# =====================================================

@app.get(
    "/api/dashboard/history"
)
def analysis_history():

    try:

        with engine.connect() as db:

            result = db.execute(
                text(
                    """
                    SELECT
                        id,
                        filename,
                        rows,
                        columns,
                        missing_values,
                        duplicate_rows,
                        anomalies_detected,
                        created_at
                    FROM analyses
                    ORDER BY created_at DESC
                    LIMIT 20
                    """
                )
            )

            data = [

                {

                    "id":
                        row[0],

                    "filename":
                        row[1],

                    "rows":
                        row[2],

                    "columns":
                        row[3],

                    "missing_values":
                        row[4],

                    "duplicate_rows":
                        row[5],

                    "anomalies_detected":
                        row[6],

                    "created_at":
                        str(row[7])
                }

                for row in result
            ]


        return data


    except Exception as error:

        raise HTTPException(

            status_code=500,

            detail=str(error)
        )


# =====================================================
# RECENT ANOMALIES
# =====================================================

@app.get(
    "/api/dashboard/anomalies"
)
def recent_anomalies():

    try:

        with engine.connect() as db:

            result = db.execute(
                text(
                    """
                    SELECT
                        a.id,
                        a.analysis_id,
                        a.row_number,
                        a.feature,
                        a.value,
                        a.z_score,
                        a.severity,
                        a.recommendation,
                        an.filename
                    FROM anomalies a
                    JOIN analyses an
                    ON a.analysis_id = an.id
                    ORDER BY a.id DESC
                    LIMIT 50
                    """
                )
            )

            data = [

                {

                    "id":
                        row[0],

                    "analysis_id":
                        row[1],

                    "row":
                        row[2],

                    "feature":
                        row[3],

                    "value":
                        row[4],

                    "z_score":
                        row[5],

                    "severity":
                        row[6],

                    "recommendation":
                        row[7],

                    "filename":
                        row[8]
                }

                for row in result
            ]


        return data


    except Exception as error:

        raise HTTPException(

            status_code=500,

            detail=str(error)
        )