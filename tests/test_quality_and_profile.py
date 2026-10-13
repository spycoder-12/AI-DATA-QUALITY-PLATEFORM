"""Profiling and the canonical quality score."""
import numpy as np
import pandas as pd
import pytest

from app.config import ANALYSIS_DEFAULTS as CFG
from app.services.profiler import profile_dataset
from app.services.quality import WEIGHTS, assess_quality
from tests.conftest import make_df


def test_profile_basics(clean_df):
    p = profile_dataset(clean_df)
    assert p["rows"] == 300 and p["columns"] == 6
    assert {"age", "income", "score", "customer_id"} <= set(p["numerical_columns"])
    assert set(p["categorical_columns"]) == {"city", "gender"} or "gender" in p["boolean_columns"] + p["categorical_columns"]
    st = p["descriptive_statistics"]["income"]
    assert set(st) == {"min", "max", "mean", "median", "std", "q1", "q3"}
    assert st["min"] <= st["q1"] <= st["median"] <= st["q3"] <= st["max"]
    assert p["duplicate_rows"] == 0 and p["missing_values"] == 0 and p["constant_columns"] == []


def test_profile_detects_dates_constants_and_missing():
    df = pd.DataFrame({"d": ["2024-01-01", "2024-02-01", "2024-03-05", "2024-04-01"], "c": ["x"] * 4,
                       "n": [1.0, None, 3.0, 4.0]})
    p = profile_dataset(df)
    assert p["date_columns"] == ["d"] and p["constant_columns"] == ["c"]
    assert p["missing_values"] == 1


def test_missing_and_duplicates_detected(dirty_df):
    q, _ = assess_quality(dirty_df, CFG)
    assert q["summary"]["missing_values"] == 3
    assert q["missing"]["columns"]["income"]["count"] == 3
    assert q["summary"]["duplicate_rows"] == 2 and q["duplicates"]["count"] == 2


def test_constant_columns_flagged():
    df = make_df(50); df["const"] = 1
    q, _ = assess_quality(df, CFG)
    assert q["summary"]["constant_columns"] == ["const"]
    assert q["dimensions"]["structure"]["score"] < 100


def test_invalid_values_and_rules(dirty_df):
    q, internal = assess_quality(dirty_df, CFG)
    assert q["validity"]["columns"]["age"]["rule_violations"] == 2     # 185 and -5
    assert q["summary"]["invalid_rows"] == 2
    assert set(internal["rule_rows"]["age"]["indices"]) == {20, 21}
    # 'score' follows the 0-100 rule and has no violations here
    assert "score" in q["validity"]["rules_applied"] and "score" not in q["validity"]["columns"]


def test_range_rule_from_column_name_and_user_override():
    df = pd.DataFrame({"anxiety_0to27": [1, 5, 30, 8, 9] * 4, "x": range(20)})
    q, _ = assess_quality(df, CFG)
    assert q["validity"]["columns"]["anxiety_0to27"]["rule_violations"] == 4
    q2, _ = assess_quality(df, CFG, options={"validity_rules": {"x": [0, 10]}})
    assert q2["validity"]["columns"]["x"]["rule_violations"] == 9


def test_allowed_values_option(clean_df):
    q, _ = assess_quality(clean_df, CFG, options={"allowed_values": {"city": ["Pune", "Delhi"]}})
    assert q["validity"]["columns"]["city"]["not_allowed"] > 0


def test_inconsistent_categories_and_whitespace(dirty_df):
    q, _ = assess_quality(dirty_df, CFG)
    c = q["consistency"]["columns"]["city"]
    assert c["whitespace_issues"] == 3
    assert any("PUNE" in g["variants"] or "Pune" in g["variants"] for g in c["variant_groups"])
    assert q["summary"]["inconsistent_rows"] >= 8


def test_datatype_problem_counts_as_invalid_not_missing(tmp_path):
    from app.utils.file_handler import load_dataset
    p = tmp_path / "t.csv"; p.write_text("v\n" + "\n".join(map(str, range(40))) + "\nabc\n")
    df, meta = load_dataset(p)
    q, _ = assess_quality(df, CFG, meta["coerced"])
    assert q["validity"]["columns"]["v"]["datatype_problems"] == 1
    assert q["summary"]["missing_values"] == 0         # not double-counted


def test_quality_score_formula_is_exact_and_documented(dirty_df):
    q, _ = assess_quality(dirty_df, CFG)
    expected = sum(q["dimensions"][k]["score"] * w for k, w in WEIGHTS.items())
    assert q["overall_score"] == pytest.approx(expected, abs=0.02)
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)
    assert "0.30*completeness" in q["formula"]


def test_perfect_data_scores_100_and_dirty_scores_lower(clean_df, dirty_df):
    assert assess_quality(clean_df, CFG)[0]["overall_score"] == 100.0
    assert assess_quality(dirty_df, CFG)[0]["overall_score"] < 100.0


def test_grade_is_capped_by_weakest_dimension():
    df = make_df(100); df.loc[:29, "age"] = 500          # 30% invalid rows
    q, _ = assess_quality(df, CFG)
    assert q["overall_score"] >= 90 and q["grade"] != "Excellent"


def test_quality_is_deterministic(dirty_df):
    assert assess_quality(dirty_df, CFG)[0] == assess_quality(dirty_df.copy(), CFG)[0]


def test_tiny_dataset_note():
    q, _ = assess_quality(pd.DataFrame({"a": [1, 2, 3]}), CFG)
    assert any("only 3" in n for n in q["notes"])
