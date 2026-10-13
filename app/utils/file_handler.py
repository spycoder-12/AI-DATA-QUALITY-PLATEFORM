"""Upload storage and dataset loading.

* uploads are streamed to disk under a generated uuid name (the client's
  filename is never used as a path) with a hard size limit;
* the original file is never modified - all analysis works on a DataFrame
  loaded from it;
* loading normalises column names, drops completely empty rows / columns and
  coerces numeric-looking text columns, recording everything it did.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import re
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from app.config import Settings
from app.utils.helpers import is_text_series, json_safe, normalize_columns
from app.utils.validators import (AppError, safe_join, sanitize_filename,
                                  validate_extension, validate_signature)

CHUNK = 1024 * 1024
NUMERIC_LIKE_RATIO = 0.90
_THOUSANDS = re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$")
_CURRENCY = re.compile(r"^([\-]?)[\$€£]\s*")


# --------------------------------------------------------------------------
# Upload storage
# --------------------------------------------------------------------------
@dataclass
class SavedFile:
    original_filename: str
    stored_filename: str
    path: Path
    extension: str
    size_bytes: int
    sha256: str


def save_upload(upload, settings: Settings) -> SavedFile:
    """Validate and stream an uploaded file to ``settings.upload_dir``."""
    original = sanitize_filename(getattr(upload, "filename", None))
    extension = validate_extension(original, settings.allowed_extensions)
    stored = f"{uuid.uuid4().hex}{extension}"
    destination = safe_join(settings.upload_dir, stored)

    hasher = hashlib.sha256()
    size = 0
    head = b""
    stream = upload.file
    try:
        with open(destination, "wb") as out:
            while True:
                chunk = stream.read(CHUNK)
                if not chunk:
                    break
                if not head:
                    head = chunk[:8192]
                    validate_signature(head, extension)
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise AppError(
                        f"File is too large. Maximum allowed size is "
                        f"{settings.max_upload_bytes // (1024 * 1024)} MB.", 413, "file_too_large")
                hasher.update(chunk)
                out.write(chunk)
    except AppError:
        destination.unlink(missing_ok=True)
        raise
    except OSError as exc:
        destination.unlink(missing_ok=True)
        raise AppError("The file could not be stored on the server.", 500, "storage_error") from exc

    if size == 0:
        destination.unlink(missing_ok=True)
        raise AppError("The uploaded file is empty.", 400, "empty_file")
    return SavedFile(original, stored, destination, extension, size, hasher.hexdigest())


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------
def _decode(raw: bytes, warnings: List[str]) -> Tuple[str, str]:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(encoding)
            if encoding != "utf-8-sig":
                warnings.append("File is not UTF-8; it was decoded as Windows-1252.")
            return text, encoding
        except UnicodeDecodeError:
            continue
    warnings.append("File encoding could not be determined; it was decoded as Latin-1 "
                    "and some characters may be wrong.")
    return raw.decode("latin-1"), "latin-1"


def _read_csv(path: Path, meta: dict) -> pd.DataFrame:
    warnings = meta["warnings"]
    text, encoding = _decode(path.read_bytes(), warnings)
    meta["encoding"] = encoding
    if not text.strip():
        raise AppError("The CSV file is empty.", 400, "empty_dataset")
    sample = text[:65536]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    meta["delimiter"] = delimiter
    kwargs = dict(sep=delimiter, na_values=["?"], skipinitialspace=False)
    try:
        return pd.read_csv(io.StringIO(text), **kwargs)
    except pd.errors.EmptyDataError as exc:
        raise AppError("The CSV file contains no data.", 400, "empty_dataset") from exc
    except pd.errors.ParserError:
        try:
            df = pd.read_csv(io.StringIO(text), engine="python", on_bad_lines="skip", **kwargs)
        except Exception as exc:  # noqa: BLE001
            raise AppError("The CSV file is corrupted and could not be parsed. Check the "
                           "delimiter, quoting and that every row has the same number of "
                           "columns.", 400, "corrupted_csv") from exc
        expected = max(text.count("\n") - 1, 0)
        skipped = max(expected - len(df), 0)
        warnings.append(f"Some malformed lines were skipped while parsing the CSV"
                        f"{f' (~{skipped} lines)' if skipped else ''}.")
        meta["malformed_lines_skipped"] = skipped
        return df
    except (ValueError, UnicodeError) as exc:
        raise AppError(f"The CSV file could not be parsed: {exc}", 400, "corrupted_csv") from exc


def _read_excel(path: Path, extension: str, meta: dict) -> pd.DataFrame:
    engine = "openpyxl" if extension == ".xlsx" else "xlrd"
    try:
        book = pd.ExcelFile(path, engine=engine)
    except ImportError as exc:
        raise AppError(f"Reading {extension} files requires the '{engine}' package.", 500,
                       "missing_dependency") from exc
    except Exception as exc:  # noqa: BLE001
        raise AppError("The Excel file could not be opened. It may be corrupted, "
                       "password-protected or not a real Excel workbook.", 400, "invalid_excel") from exc
    meta["sheet_names"] = list(book.sheet_names)
    if not book.sheet_names:
        raise AppError("The Excel workbook contains no sheets.", 400, "empty_dataset")
    if len(book.sheet_names) > 1:
        meta["warnings"].append(
            f"Workbook has {len(book.sheet_names)} sheets; only the first sheet "
            f"('{book.sheet_names[0]}') was analysed.")
    try:
        return book.parse(book.sheet_names[0])
    except Exception as exc:  # noqa: BLE001
        raise AppError("The first sheet of the Excel file could not be read.", 400, "invalid_excel") from exc


def _read_pdf(path: Path, meta: dict) -> pd.DataFrame:
    try:
        import pdfplumber
    except ImportError as exc:
        raise AppError("PDF support requires the 'pdfplumber' package.", 500, "missing_dependency") from exc
    tables: List[pd.DataFrame] = []
    try:
        with pdfplumber.open(path) as pdf:
            meta["pdf_pages"] = len(pdf.pages)
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    if not table or len(table) < 2:
                        continue
                    header = [str(c).strip() if c not in (None, "") else f"column_{i + 1}"
                              for i, c in enumerate(table[0])]
                    tables.append(pd.DataFrame(table[1:], columns=header))
    except Exception as exc:  # noqa: BLE001
        raise AppError("The PDF could not be read (it may be encrypted, scanned or corrupted).",
                       400, "invalid_pdf") from exc
    if not tables:
        raise AppError("No structured table could be extracted from this PDF. Only PDFs that "
                       "contain real tables (not scanned images) are supported.", 400, "unsupported_pdf")
    meta["pdf_tables"] = len(tables)
    first_header = tuple(tables[0].columns)
    same = [t for t in tables if tuple(t.columns) == first_header]
    if len(same) != len(tables):
        largest = max(tables, key=len)
        meta["warnings"].append(
            f"The PDF contains {len(tables)} tables with different headers; only the largest "
            f"one ({len(largest)} rows) was analysed.")
        same = [largest]
    df = pd.concat(same, ignore_index=True)
    # tables spanning pages often repeat the header row
    header_row = df.astype(str).apply(lambda r: tuple(r) == tuple(df.columns), axis=1)
    if header_row.any():
        df = df[~header_row].reset_index(drop=True)
    return df


def _coerce_numeric_like(df: pd.DataFrame, meta: dict) -> pd.DataFrame:
    """Turn text columns that are (almost) entirely numeric into numeric columns.

    Values that cannot be parsed become NaN but are *recorded* (meta["coerced"])
    so the quality analysis can report them as datatype problems instead of
    silently treating them as ordinary missing values.
    """
    coerced: Dict[str, dict] = {}
    for column in list(df.columns):
        series = df[column]
        if not is_text_series(series):
            continue
        present = series.dropna()
        if present.empty:
            continue
        text = present.astype(str).str.strip()
        text = text.str.replace(_CURRENCY, r"\1", regex=True)
        thousands = text.str.match(_THOUSANDS)
        text = text.where(~thousands, text.str.replace(",", "", regex=False))
        parsed = pd.to_numeric(text, errors="coerce")
        ratio = parsed.notna().mean()
        if ratio < NUMERIC_LIKE_RATIO:
            continue
        bad = parsed.isna()
        full = pd.Series(np.nan, index=series.index, dtype="float64")
        full.loc[parsed.index] = parsed
        if (parsed.dropna() % 1 == 0).all() and not series.isna().any() and not bad.any():
            full = full.astype("int64")
        df[column] = full
        if bad.any():
            bad_idx = present.index[bad.values]
            coerced[column] = {
                "count": int(bad.sum()),
                "examples": [str(v) for v in present[bad].astype(str).unique()[:5]],
                "index": [int(i) for i in bad_idx],
            }
    meta["coerced"] = coerced
    for column, info in coerced.items():
        meta["warnings"].append(
            f"Column '{column}' is mostly numeric but {info['count']} value(s) are not "
            f"(e.g. {', '.join(repr(e) for e in info['examples'][:3])}); they were flagged as "
            f"datatype problems.")
    return df


def _prepare(df: pd.DataFrame, meta: dict) -> pd.DataFrame:
    meta["original_rows"], meta["original_columns"] = int(df.shape[0]), int(df.shape[1])
    if df.shape[0] == 0 or df.shape[1] == 0:
        raise AppError("The dataset is empty (no data rows found).", 400, "empty_dataset")

    # blank / whitespace-only strings are just missing values
    blank_total = 0
    for column in df.columns:
        if is_text_series(df[column]):
            blank = df[column].astype("string").str.strip().eq("").fillna(False)
            if blank.any():
                blank_total += int(blank.sum())
                df[column] = df[column].mask(blank.values)
    meta["blank_strings_converted"] = blank_total

    before_rows, before_cols = df.shape
    df = df.dropna(axis=0, how="all")
    df = df.dropna(axis=1, how="all")
    meta["dropped_empty_rows"] = int(before_rows - df.shape[0])
    meta["dropped_empty_columns"] = int(before_cols - df.shape[1])
    if meta["dropped_empty_rows"]:
        meta["warnings"].append(f"{meta['dropped_empty_rows']} completely empty row(s) were ignored.")
    if meta["dropped_empty_columns"]:
        meta["warnings"].append(f"{meta['dropped_empty_columns']} completely empty column(s) were ignored.")
    if df.shape[0] == 0 or df.shape[1] == 0:
        raise AppError("The dataset contains no usable data (every row or column is empty).",
                       400, "empty_dataset")

    names, mapping = normalize_columns(df.columns)
    df.columns = names
    meta["column_map"] = mapping
    renamed = sum(1 for k, v in mapping.items() if k != v)
    meta["columns_renamed"] = renamed
    return _coerce_numeric_like(df, meta)


def load_dataset(path: Path | str, extension: str | None = None,
                 max_rows: int = 1_000_000) -> Tuple[pd.DataFrame, dict]:
    """Load CSV / XLSX / XLS / PDF-table into a cleaned DataFrame plus load metadata."""
    path = Path(path)
    if not path.exists():
        raise AppError("The dataset file is no longer available on the server.", 404, "file_missing")
    extension = (extension or path.suffix).lower()
    meta: Dict[str, Any] = {"file_type": extension.lstrip("."), "warnings": []}
    if extension == ".csv":
        df = _read_csv(path, meta)
    elif extension in (".xlsx", ".xls"):
        df = _read_excel(path, extension, meta)
    elif extension == ".pdf":
        df = _read_pdf(path, meta)
    else:
        raise AppError(f"Unsupported file type '{extension}'.", 400, "unsupported_type")
    if len(df) > max_rows:
        raise AppError(f"The dataset has {len(df):,} rows; the maximum supported is {max_rows:,}.",
                       413, "too_many_rows")
    return _prepare(df, meta), meta


def public_meta(meta: dict) -> dict:
    """Load metadata without the (potentially large) internal row indexes."""
    out = copy.deepcopy(meta)
    for info in out.get("coerced", {}).values():
        info.pop("index", None)
    return json_safe(out)


# --------------------------------------------------------------------------
# Small LRU cache so preview / analysis / remediation don't re-parse the file
# --------------------------------------------------------------------------
_CACHE: "OrderedDict[tuple, tuple]" = OrderedDict()
_CACHE_SIZE = 3


def load_cached(path: Path | str, extension: str | None = None,
                max_rows: int = 1_000_000) -> Tuple[pd.DataFrame, dict]:
    path = Path(path)
    try:
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return load_dataset(path, extension, max_rows)
    if key in _CACHE:
        _CACHE.move_to_end(key)
        df, meta = _CACHE[key]
        return df.copy(), copy.deepcopy(meta)
    df, meta = load_dataset(path, extension, max_rows)
    _CACHE[key] = (df, meta)
    while len(_CACHE) > _CACHE_SIZE:
        _CACHE.popitem(last=False)
    return df.copy(), copy.deepcopy(meta)


def clear_cache() -> None:
    _CACHE.clear()


def preview_frame(df: pd.DataFrame, rows: int = 10) -> dict:
    head = df.head(rows)
    return {
        "columns": [str(c) for c in head.columns],
        "rows": [[json_safe(v) for v in row] for row in head.itertuples(index=False, name=None)],
        "total_rows": int(len(df)),
    }
