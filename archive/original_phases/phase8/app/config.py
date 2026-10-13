import os

from pathlib import Path

from dotenv import load_dotenv


# =====================================================
# LOAD ENVIRONMENT VARIABLES
# =====================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

load_dotenv(
    BASE_DIR / ".env"
)


# =====================================================
# APPLICATION
# =====================================================

APP_NAME = (
    "AI Data Quality & "
    "Anomaly Detection Engine"
)

APP_VERSION = "2.0.0"


# =====================================================
# DATABASE
# =====================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL"
)


if not DATABASE_URL:

    raise RuntimeError(
        "DATABASE_URL is not configured."
    )


# =====================================================
# DIRECTORIES
# =====================================================

DATA_DIR = (
    BASE_DIR / "data"
)

UPLOAD_DIR = (
    DATA_DIR / "uploads"
)

REPORT_DIR = (
    BASE_DIR / "reports"
)


UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)

REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# =====================================================
# FILE SETTINGS
# =====================================================

ALLOWED_EXTENSIONS = {
    ".csv"
}