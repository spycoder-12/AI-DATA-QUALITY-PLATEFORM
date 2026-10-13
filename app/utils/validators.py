"""Input validation: filenames, extensions, magic bytes and safe paths."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Iterable

_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._ \-()]")

# file signatures ("magic bytes") - we never trust the extension alone
_ZIP = b"PK\x03\x04"
_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_PDF = b"%PDF"


class AppError(Exception):
    """An error whose message is safe to show to end users."""

    def __init__(self, message: str, status_code: int = 400, code: str = "bad_request"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def sanitize_filename(filename: str | None) -> str:
    """Return a display-safe filename (no directories, no control characters)."""
    if not filename:
        raise AppError("The uploaded file has no filename.", 400, "missing_filename")
    name = unicodedata.normalize("NFKC", filename)
    name = name.replace("\\", "/").split("/")[-1]          # strip any directory part
    name = _FILENAME_SAFE.sub("_", name).strip(" .")
    if not name or set(name) <= {"."}:
        raise AppError("The uploaded filename is not valid.", 400, "invalid_filename")
    return name[:200]


def validate_extension(filename: str, allowed: Iterable[str]) -> str:
    extension = Path(filename).suffix.lower()
    allowed = tuple(allowed)
    if extension not in allowed:
        pretty = ", ".join(e.lstrip(".").upper() for e in allowed)
        raise AppError(f"Unsupported file type '{extension or 'none'}'. Allowed formats: {pretty}.",
                       400, "unsupported_type")
    return extension


def validate_signature(head: bytes, extension: str) -> None:
    """Check that file content matches its extension."""
    if extension == ".xlsx" and not head.startswith(_ZIP):
        raise AppError("This file is not a valid .xlsx workbook (it may be corrupted or "
                       "have the wrong extension).", 400, "invalid_excel")
    if extension == ".xls" and not head.startswith(_OLE):
        raise AppError("This file is not a valid legacy .xls workbook (it may be corrupted "
                       "or have the wrong extension).", 400, "invalid_excel")
    if extension == ".pdf" and not head.startswith(_PDF):
        raise AppError("This file is not a valid PDF document.", 400, "invalid_pdf")
    if extension == ".csv" and (b"\x00" in head[:4096] and not head.startswith((b"\xff\xfe", b"\xfe\xff"))):
        raise AppError("This file does not look like a text CSV (binary content detected).",
                       400, "invalid_csv")


def safe_join(base: Path, name: str) -> Path:
    """Join ``name`` under ``base`` and refuse anything that escapes it."""
    candidate = (base / name).resolve()
    if base.resolve() not in candidate.parents and candidate != base.resolve():
        raise AppError("Invalid file path.", 400, "path_traversal")
    return candidate


def clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))
