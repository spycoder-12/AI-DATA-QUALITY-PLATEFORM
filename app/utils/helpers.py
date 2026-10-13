"""Small helpers shared by every service (kept dependency-light)."""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone
from typing import Any, Iterable, List

import numpy as np
import pandas as pd

SEVERITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
NOT_AVAILABLE = "Not available — insufficient data"

# names that look like record identifiers or ground-truth labels are never
# treated as analysable measurement features
_ID_RE = re.compile(r"(^id$|_id$|^id_|^uuid$|_uuid$|^index$|^unnamed)", re.I)
GROUND_TRUTH_NAMES = {"is_anomaly", "anomaly", "is_outlier", "outlier", "anomaly_label",
                      "ground_truth", "is_fraud_label"}


def utcnow() -> datetime:
    """Naive UTC timestamp (what the DB stores)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt: Any) -> Any:
    if isinstance(dt, datetime):
        return dt.replace(microsecond=0).isoformat() + "Z"
    return dt


def row_number(index: Any) -> int:
    """Spreadsheet-style row number (header is row 1, first data row is 2)."""
    return int(index) + 2


def json_safe(obj: Any) -> Any:
    """Recursively convert numpy/pandas objects to JSON-serialisable Python.

    NaN / inf become ``None`` so responses are always valid JSON.
    """
    if obj is None:
        return None
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        value = float(obj)
        return None if (math.isnan(value) or math.isinf(value)) else value
    if isinstance(obj, (int, str)):
        return obj
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [json_safe(v) for v in obj.tolist()]
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.isoformat()
    if isinstance(obj, pd.Series):
        return [json_safe(v) for v in obj.tolist()]
    if obj is pd.NaT or (not isinstance(obj, (str, bytes)) and pd.isna(obj) is True):
        return None
    return str(obj)


def rnd(value: Any, digits: int = 4) -> Any:
    """Round to ``digits``; returns None for NaN/inf/None."""
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, digits)


def is_text_series(series: pd.Series) -> bool:
    """True for object / string dtype columns (works on pandas 2 and 3)."""
    if pd.api.types.is_bool_dtype(series) or pd.api.types.is_numeric_dtype(series):
        return False
    if pd.api.types.is_datetime64_any_dtype(series):
        return False
    return bool(pd.api.types.is_string_dtype(series) or series.dtype == object
                or isinstance(series.dtype, pd.CategoricalDtype))


def is_numeric_series(series: pd.Series) -> bool:
    return bool(pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series))


def looks_like_id(name: str) -> bool:
    return bool(_ID_RE.search(str(name).strip()))


def is_ground_truth_name(name: str) -> bool:
    return str(name).strip().lower() in GROUND_TRUTH_NAMES


def normalize_column_name(name: Any, position: int) -> str:
    text = str(name).strip().lower()
    text = re.sub(r"[^0-9a-z]+", "_", text).strip("_")
    if not text:
        return f"column_{position + 1}"
    if text[0].isdigit():
        text = "col_" + text
    return text


def normalize_columns(columns: Iterable[Any]) -> tuple[List[str], dict]:
    """snake_case + de-duplicate column names. Returns (names, original->new map)."""
    seen: dict[str, int] = {}
    names: List[str] = []
    mapping: dict[str, str] = {}
    for position, original in enumerate(columns):
        base = normalize_column_name(original, position)
        count = seen.get(base, 0) + 1
        seen[base] = count
        final = base if count == 1 else f"{base}_{count}"
        names.append(final)
        mapping[str(original)] = final
    return names, mapping


def max_severity(levels: Iterable[str]) -> str:
    best = -1
    for level in levels:
        if level in SEVERITY_ORDER:
            best = max(best, SEVERITY_ORDER.index(level))
    return SEVERITY_ORDER[best] if best >= 0 else "LOW"


def bump_severity(level: str, steps: int = 1) -> str:
    idx = SEVERITY_ORDER.index(level) if level in SEVERITY_ORDER else 0
    return SEVERITY_ORDER[min(idx + steps, len(SEVERITY_ORDER) - 1)]


def sample_values(series: pd.Series, limit: int = 5) -> list:
    return [json_safe(v) for v in series.dropna().head(limit).tolist()]
