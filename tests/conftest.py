"""Shared fixtures: isolated settings / database per test, deterministic data."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import ANALYSIS_DEFAULTS, load_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.pipeline import execute  # noqa: E402

logging.getLogger("httpx").setLevel(logging.WARNING)


@pytest.fixture()
def settings(tmp_path):
    return load_settings(env={
        "DATABASE_URL": f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        "UPLOAD_DIR": str(tmp_path / "uploads"), "PROCESSED_DIR": str(tmp_path / "processed"),
        "REPORT_DIR": str(tmp_path / "reports"), "MAX_UPLOAD_SIZE": "2MB", "LOG_LEVEL": "WARNING",
    }, load_env_file=False)


@pytest.fixture()
def client(settings):
    with TestClient(create_app(settings)) as c:
        c.settings = settings
        yield c


def make_df(n: int = 300, seed: int = 0) -> pd.DataFrame:
    """Clean, realistic frame: 3 numeric measurements + 2 categoricals + an id."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "customer_id": np.arange(1, n + 1),
        "age": np.clip(rng.normal(40, 10, n), 18, 80).round().astype(int),
        "income": rng.normal(50000, 8000, n).round(0),
        "score": np.clip(rng.normal(70, 10, n), 0, 100).round(1),
        "city": rng.choice(["Pune", "Delhi", "Mumbai"], n),
        "gender": rng.choice(["M", "F"], n),
    })


def make_dirty_df(seed: int = 0) -> pd.DataFrame:
    """make_df + known, countable problems."""
    df = make_df(300, seed)
    df.loc[[5, 6, 7], "income"] = np.nan                    # 3 missing
    df = pd.concat([df, df.iloc[[10, 11]]], ignore_index=True)   # 2 duplicates
    df.loc[20, "age"] = 185                                  # impossible value
    df.loc[21, "age"] = -5
    df.loc[30, "income"] = 5_000_000                         # extreme value
    df.loc[40:44, "city"] = "PUNE"                           # case variants
    df.loc[50:52, "city"] = " Delhi"                         # whitespace
    return df


@pytest.fixture()
def clean_df():
    return make_df()


@pytest.fixture()
def dirty_df():
    return make_dirty_df()


def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode()


def run_pipeline(df: pd.DataFrame, history=None, reference=None, cfg=ANALYSIS_DEFAULTS, options=None):
    meta = {"warnings": [], "coerced": {}}
    info = {"id": 1, "analysis_id": 1, "name": "test.csv", "rows": len(df), "columns": df.shape[1],
            "file_type": "csv", "size_bytes": 1, "uploaded_at": None}
    return execute(df, meta, cfg, options or {}, info, reference_df=reference,
                   reference_info={"dataset_id": 0, "name": "ref.csv", "rows": len(reference), "mode": "explicit"}
                   if reference is not None else None, history=history)
