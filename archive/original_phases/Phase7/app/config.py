from pathlib import Path


# =====================================================
# BASE DIRECTORY
# =====================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# =====================================================
# DATA DIRECTORIES
# =====================================================

DATA_DIR = BASE_DIR / "data"

UPLOAD_DIR = DATA_DIR / "uploads"

REPORT_DIR = BASE_DIR / "reports"


# =====================================================
# FILE SETTINGS
# =====================================================

ALLOWED_EXTENSIONS = {
    ".csv"
}

MAX_FILE_SIZE_MB = 10


# =====================================================
# APPLICATION SETTINGS
# =====================================================

APP_NAME = (
    "AI Data Quality & "
    "Anomaly Detection Engine"
)

APP_VERSION = "1.0.0"


# =====================================================
# CREATE DIRECTORIES
# =====================================================

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)

REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True
)