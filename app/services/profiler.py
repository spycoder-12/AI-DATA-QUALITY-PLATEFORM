"""Automatic dataset profiling (one unified profile used by every other service)."""
from __future__ import annotations

import warnings
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from app.utils.helpers import is_numeric_series, is_text_series, json_safe, rnd

_BOOL_TOKENS = {"true", "false", "yes", "no", "y", "n", "t", "f", "0", "1"}


def _looks_like_datetime(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if not is_text_series(series):
        return False
    sample = series.dropna().astype(str).head(200)
    if len(sample) < 3 or not sample.str.contains(r"\d").all():
        return False
    if not sample.str.contains(r"[-/:]").mean() > 0.9:
        return False
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
        return bool(parsed.notna().mean() >= 0.9)
    except Exception:  # noqa: BLE001
        return False


def infer_kind(series: pd.Series) -> str:
    """numeric | boolean | datetime | categorical | text (high-cardinality strings)."""
    non_null = series.dropna()
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if is_numeric_series(series):
        if non_null.nunique() <= 2 and set(non_null.unique()) <= {0, 1, 0.0, 1.0}:
            return "boolean"
        return "numeric"
    if _looks_like_datetime(series):
        return "datetime"
    if is_text_series(series):
        lowered = set(non_null.astype(str).str.strip().str.lower().unique())
        if 0 < len(lowered) <= 2 and lowered <= _BOOL_TOKENS:
            return "boolean"
        nunique = non_null.nunique()
        if nunique <= 50 or (len(non_null) and nunique / len(non_null) <= 0.5):
            return "categorical"
        return "text"
    return "categorical"


def _numeric_stats(series: pd.Series) -> Dict[str, Any]:
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        return {}
    q1, q3 = values.quantile(0.25), values.quantile(0.75)
    std = values.std() if len(values) > 1 else 0.0
    return {
        "min": rnd(values.min()), "max": rnd(values.max()), "mean": rnd(values.mean()),
        "median": rnd(values.median()), "std": rnd(std), "q1": rnd(q1), "q3": rnd(q3),
        "iqr": rnd(q3 - q1), "skewness": rnd(values.skew()) if len(values) > 2 else None,
        "zeros": int((values == 0).sum()), "negatives": int((values < 0).sum()),
    }


def profile_dataset(df: pd.DataFrame, meta: dict | None = None) -> Dict[str, Any]:
    rows, cols = df.shape
    columns: List[Dict[str, Any]] = []
    groups = {"numeric": [], "categorical": [], "datetime": [], "boolean": [], "text": []}
    constant_columns: List[str] = []

    for name in df.columns:
        series = df[name]
        kind = infer_kind(series)
        groups[kind].append(name)
        missing = int(series.isna().sum())
        nunique = int(series.nunique(dropna=True))
        is_constant = nunique <= 1
        if is_constant:
            constant_columns.append(name)
        info: Dict[str, Any] = {
            "name": name, "dtype": str(series.dtype), "kind": kind,
            "missing": missing, "missing_pct": rnd(missing / rows * 100 if rows else 0, 2),
            "unique": nunique, "unique_pct": rnd(nunique / rows * 100 if rows else 0, 2),
            "is_constant": is_constant,       # no raw sample values are kept: previews are read from the file on demand
        }
        if kind == "numeric":
            info.update(_numeric_stats(series))
        elif kind in ("categorical", "boolean"):
            # only genuinely repeating categories are listed; near-unique text (names, e-mails,
            # ids) would expose individual raw values, so it is summarised by counts only
            if nunique <= max(1, 0.5 * max(rows - missing, 1)):
                top = series.dropna().astype(str).value_counts().head(5)
                info["top_values"] = [{"value": str(k), "count": int(v),
                                       "pct": rnd(v / max(rows - missing, 1) * 100, 2)}
                                      for k, v in top.items()]
        elif kind == "datetime":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                parsed = pd.to_datetime(series, errors="coerce", format="mixed") \
                    if is_text_series(series) else series
            parsed = parsed.dropna()
            if not parsed.empty:
                info["min"], info["max"] = str(parsed.min().date()), str(parsed.max().date())
        columns.append(info)

    duplicate_rows = int(df.duplicated().sum())
    numeric_df = df[groups["numeric"]] if groups["numeric"] else pd.DataFrame()
    return json_safe({
        "rows": int(rows), "columns": int(cols),
        "memory_mb": rnd(df.memory_usage(deep=True).sum() / (1024 * 1024), 3),
        "column_names": [str(c) for c in df.columns],
        "data_types": {c["name"]: c["dtype"] for c in columns},
        "numerical_columns": groups["numeric"], "categorical_columns": groups["categorical"],
        "date_columns": groups["datetime"], "boolean_columns": groups["boolean"],
        "text_columns": groups["text"],
        "constant_columns": constant_columns,
        "missing_values": int(df.isna().sum().sum()),
        "missing_cells_pct": rnd(df.isna().sum().sum() / max(rows * cols, 1) * 100, 2),
        "duplicate_rows": duplicate_rows,
        "duplicate_pct": rnd(duplicate_rows / max(rows, 1) * 100, 2),
        "unique_values": {c["name"]: c["unique"] for c in columns},
        "descriptive_statistics": {c["name"]: {k: c.get(k) for k in
                                               ("min", "max", "mean", "median", "std", "q1", "q3")}
                                   for c in columns if c["kind"] == "numeric"},
        "column_profiles": columns,
        "has_numeric_columns": bool(groups["numeric"]),
        "load": {k: meta.get(k) for k in ("file_type", "encoding", "delimiter", "sheet_names",
                                          "dropped_empty_rows", "dropped_empty_columns",
                                          "columns_renamed", "column_map", "warnings")} if meta else {},
    })
