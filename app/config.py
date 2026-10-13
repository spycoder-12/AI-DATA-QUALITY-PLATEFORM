"""Application configuration.

Everything configurable comes from environment variables (optionally loaded
from a local ``.env`` file). Nothing secret is ever hard-coded here.
Analysis thresholds live in :class:`AnalysisConfig` so that every service reads
the *same* numbers (one severity system, one set of alert thresholds).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, fields, replace
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv

APP_NAME = "AI Data Quality Intelligence Platform"
APP_VERSION = "1.0.0"
BASE_DIR = Path(__file__).resolve().parent.parent


class ConfigError(Exception):
    """Raised when the environment configuration is invalid."""


# --------------------------------------------------------------------------
# Analysis thresholds (defaults; individual runs may override a subset)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class AnalysisConfig:
    # statistical detection
    iqr_multiplier: float = 1.5
    zscore_threshold: float = 3.0
    min_values_for_stats: int = 4
    # machine-learning detection
    ml_min_rows: int = 20
    ml_max_fit_rows: int = 10000
    ml_max_features: int = 50
    if_contamination: str = "auto"          # "auto" or a float in (0, 0.5]
    lof_neighbors: int = 20
    svm_nu: float = 0.05
    ml_include_categorical: bool = False
    random_state: int = 42
    # consensus
    min_votes: int = 2                      # detectors needed to report a record
    # quality / issue thresholds (percent)
    missing_col_alert_pct: float = 20.0
    max_missing_col_pct_for_impute: float = 60.0
    # alerts
    quality_critical: float = 50.0
    quality_high: float = 65.0
    quality_medium: float = 80.0
    quality_drop_medium: float = 5.0
    quality_drop_high: float = 10.0
    anomaly_rate_medium_pct: float = 5.0
    anomaly_rate_high_pct: float = 10.0
    anomaly_increase_pct: float = 50.0
    anomaly_increase_min_records: int = 5
    # drift
    drift_min_samples: int = 30
    psi_moderate: float = 0.10
    psi_significant: float = 0.25
    drift_alpha: float = 0.05
    # trends / forecast
    forecast_min_points: int = 5
    forecast_horizon: int = 3
    # decision engine
    risk_medium: float = 20.0
    risk_high: float = 40.0
    risk_critical: float = 70.0


ANALYSIS_DEFAULTS = AnalysisConfig()


def merge_analysis_config(overrides: Optional[Dict[str, Any]] = None) -> AnalysisConfig:
    """Return a config with validated per-run overrides applied."""
    if not overrides:
        return ANALYSIS_DEFAULTS
    valid = {f.name: f for f in fields(AnalysisConfig)}
    clean: Dict[str, Any] = {}
    for key, value in overrides.items():
        if key not in valid or value is None:
            continue
        default = getattr(ANALYSIS_DEFAULTS, key)
        if isinstance(default, bool):
            clean[key] = bool(value)
        elif isinstance(default, int):
            clean[key] = int(value)
        elif isinstance(default, float):
            clean[key] = float(value)
        else:
            clean[key] = str(value)
    return replace(ANALYSIS_DEFAULTS, **clean)


# --------------------------------------------------------------------------
# Environment settings
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Settings:
    app_name: str
    version: str
    base_dir: Path
    database_url: str
    secret_key: str
    upload_dir: Path
    processed_dir: Path
    report_dir: Path
    max_upload_bytes: int
    allowed_extensions: Tuple[str, ...]
    cors_origins: Tuple[str, ...]
    host: str
    port: int
    log_level: str
    debug: bool
    max_rows: int = 1_000_000
    frontend_dir: Path = field(default=BASE_DIR / "frontend")


_SIZE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(b|kb|k|mb|m|gb|g)?\s*$", re.I)
_UNITS = {None: 1, "b": 1, "k": 1024, "kb": 1024, "m": 1024 ** 2, "mb": 1024 ** 2,
          "g": 1024 ** 3, "gb": 1024 ** 3}


def parse_size(value: str) -> int:
    """Parse '50MB', '50m' or a plain number of bytes."""
    match = _SIZE_RE.match(value or "")
    if not match:
        raise ConfigError(
            f"MAX_UPLOAD_SIZE='{value}' is invalid. Use e.g. 50MB or a number of bytes.")
    number, unit = match.groups()
    size = int(float(number) * _UNITS[unit.lower() if unit else None])
    if size <= 0:
        raise ConfigError("MAX_UPLOAD_SIZE must be greater than zero.")
    return size


def _resolve(path_value: str) -> Path:
    path = Path(path_value).expanduser()
    return path if path.is_absolute() else (BASE_DIR / path)


def load_settings(env: Optional[Dict[str, str]] = None, load_env_file: bool = True) -> Settings:
    if load_env_file and env is None:
        load_dotenv(BASE_DIR / ".env", override=False)
    source = os.environ if env is None else env

    def get(name: str, default: str = "") -> str:
        value = source.get(name)
        return default if value is None or value.strip() == "" else value.strip()

    database_url = get("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'data' / 'platform.db').as_posix()}")
    if "://" not in database_url:
        raise ConfigError(
            "DATABASE_URL is not a valid SQLAlchemy URL "
            "(expected something like sqlite:///data/platform.db or postgresql+psycopg2://user:pass@host/db).")
    if database_url.startswith("sqlite:///") and not database_url.startswith("sqlite:////") \
            and ":memory:" not in database_url:
        # relative sqlite path -> anchor to project root
        rel = database_url[len("sqlite:///"):]
        database_url = f"sqlite:///{_resolve(rel).as_posix()}"

    try:
        port = int(get("PORT", "8000"))
    except ValueError as exc:
        raise ConfigError("PORT must be an integer.") from exc
    if not 1 <= port <= 65535:
        raise ConfigError("PORT must be between 1 and 65535.")

    origins = tuple(o.strip() for o in get(
        "CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",") if o.strip())
    extensions = tuple(e.strip().lower() if e.strip().startswith(".") else "." + e.strip().lower()
                       for e in get("ALLOWED_EXTENSIONS", ".csv,.xlsx,.xls,.pdf").split(",") if e.strip())

    settings = Settings(
        app_name=APP_NAME,
        version=APP_VERSION,
        base_dir=BASE_DIR,
        database_url=database_url,
        secret_key=get("SECRET_KEY", "change-me"),
        upload_dir=_resolve(get("UPLOAD_DIR", "data/uploads")),
        processed_dir=_resolve(get("PROCESSED_DIR", "data/processed")),
        report_dir=_resolve(get("REPORT_DIR", "data/reports")),
        max_upload_bytes=parse_size(get("MAX_UPLOAD_SIZE", "50MB")),
        allowed_extensions=extensions,
        cors_origins=origins,
        host=get("HOST", "127.0.0.1"),
        port=port,
        log_level=get("LOG_LEVEL", "INFO").upper(),
        debug=get("DEBUG", "false").lower() in {"1", "true", "yes"},
    )
    for directory in (settings.upload_dir, settings.processed_dir, settings.report_dir):
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ConfigError(f"Cannot create directory '{directory}': {exc.strerror or exc}") from exc
    return settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
