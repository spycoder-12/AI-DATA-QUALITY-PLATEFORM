"""Recommendations, remediation, drift, alerts, trends, forecast, decision engine, pipeline."""
import numpy as np
import pandas as pd
import pytest

from app.config import ANALYSIS_DEFAULTS as CFG, merge_analysis_config
from app.services import alerts as alerts_svc, decision_engine, drift, forecasting, monitoring, trends
from app.services.anomaly import select_features
from app.services.quality import assess_quality
from app.services.remediation import (ALL_OPERATIONS, SAFE_OPERATIONS, apply_remediation, build_plan)
from tests.conftest import make_df, make_dirty_df, run_pipeline


@pytest.fixture(scope="module")
def dirty_result():
    return run_pipeline(make_dirty_df())


@pytest.fixture(scope="module")
def clean_result():
    return run_pipeline(make_df())


# ---------------------------------------------------------------- recommendations
def test_recommendations_come_from_real_findings(dirty_result):
    recs = dirty_result["recommendations"]
    cats = {r["category"] for r in recs}
    assert {"Missing values", "Duplicates", "Invalid values", "Consistency", "Anomalies"} <= cats
    miss = next(r for r in recs if r["category"] == "Missing values")
    assert miss["target"] == "income" and "median" in miss["recommendation"].lower()
    dup = next(r for r in recs if r["category"] == "Duplicates")
    assert "2 exact duplicate" in dup["finding"] and dup["automated_fix"] == "remove_duplicates"
    inv = next(r for r in recs if r["category"] == "Invalid values" and r["target"] == "age")
    assert "business rules" in inv["recommendation"]
    cons = next(r for r in recs if r["category"] == "Consistency" and r["target"] == "city")
    assert "approved" in cons["recommendation"].lower() or "Trim" in cons["recommendation"]
    sevs = [r["severity"] for r in recs]
    order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    assert sevs == sorted(sevs, key=order.index)                      # most urgent first
    assert [r["id"] for r in recs] == list(range(1, len(recs) + 1))


def test_clean_data_gets_no_invented_problems(clean_result):
    recs = clean_result["recommendations"]
    assert all(r["category"] in {"Overall", "Anomalies", "Consistency"} for r in recs), recs
    assert not [r for r in recs if r["category"] in {"Missing values", "Duplicates", "Invalid values"}]


# ---------------------------------------------------------------- remediation
def remediate(df, ops=None, options=None):
    q, internal = assess_quality(df, CFG)
    feats, _ = select_features(df, CFG, internal["kinds"])
    return apply_remediation(df, ops, options, q, internal, feats, CFG), q, internal, feats


def test_remediation_never_modifies_original(dirty_df):
    before = dirty_df.copy(deep=True)
    (cleaned, summary), *_ = remediate(dirty_df, ALL_OPERATIONS)
    pd.testing.assert_frame_equal(dirty_df, before)
    assert cleaned is not dirty_df


def test_safe_fixes_default_and_change_log(dirty_df):
    (cleaned, s), *_ = remediate(dirty_df)                          # no operations -> safe fixes only
    assert s["operations_applied"] == [o for o in ["standardize_column_names", "trim_whitespace",
                                                   "normalize_categories", "remove_duplicates"]]
    assert s["rows_before"] == 302 and s["rows_after"] == 300 and s["rows_removed"] == 2
    assert cleaned["income"].isna().sum() == 3                      # imputation is opt-in: untouched
    assert (cleaned["age"] == 185).sum() == 1                       # values are never silently "fixed"
    ops = {c["operation"] for c in s["changes"]}
    assert {"trim_whitespace", "normalize_categories", "remove_duplicates"} <= ops
    assert all(c["detail"] for c in s["changes"])


def test_before_after_statistics(dirty_df):
    (cleaned, s), *_ = remediate(dirty_df)
    assert s["before"]["duplicate_rows"] == 2 and s["after"]["duplicate_rows"] == 0
    assert s["before"]["inconsistent_rows"] > 0 and s["after"]["inconsistent_rows"] == 0
    assert s["after"]["quality_score"] > s["before"]["quality_score"]
    assert s["improvement"]["quality_score"] == pytest.approx(s["after"]["quality_score"] - s["before"]["quality_score"], abs=0.01)
    assert cleaned["city"].str.strip().eq(cleaned["city"]).all()
    assert set(cleaned["city"]) == {"Pune", "Delhi", "Mumbai"}


def test_impute_missing_configurable(dirty_df):
    (c1, _), *_ = remediate(dirty_df, ["impute_missing"], {"numeric_strategy": "median"})
    assert c1["income"].isna().sum() == 0
    (c2, s2), *_ = remediate(dirty_df, ["impute_missing"], {"numeric_strategy": "zero"})
    assert (c2["income"] == 0).sum() == 3
    (c3, s3), *_ = remediate(dirty_df, ["impute_missing"], {"numeric_strategy": "drop_rows"})
    assert len(c3) == len(dirty_df) - 3
    (c4, _), *_ = remediate(dirty_df, ["impute_missing"], {"numeric_strategy": "none"})
    assert c4["income"].isna().sum() == 3
    with pytest.raises(ValueError):
        remediate(dirty_df, ["impute_missing"], {"numeric_strategy": "magic"})


def test_columns_mostly_missing_are_not_imputed():
    df = make_df(100); df["sparse"] = np.nan; df.loc[:9, "sparse"] = 1.0
    (cleaned, s), *_ = remediate(df, ["impute_missing"])
    assert cleaned["sparse"].isna().sum() == 90
    assert any("Skipped" in c["detail"] for c in s["changes"] if c["column"] == "sparse")


def test_winsorize_is_opt_in_and_caps_extremes(dirty_df):
    (safe, _), *_ = remediate(dirty_df)
    assert safe["income"].max() == 5_000_000
    (capped, s), *_ = remediate(dirty_df, ["winsorize"])
    assert capped["income"].max() < 200_000 and any(c["operation"] == "winsorize" for c in s["changes"])


def test_invalid_to_missing_then_impute(dirty_df):
    (cleaned, s), *_ = remediate(dirty_df, ["invalid_to_missing", "impute_missing"])
    assert cleaned["age"].between(0, 120).all() and cleaned["age"].isna().sum() == 0


def test_dedupe_happens_before_imputation():
    base = pd.DataFrame({"a": [1.0, 1.0, 2.0, 2.0, np.nan, 3.0] * 6, "b": list("xyxyzz") * 6})
    df = pd.concat([base, base.iloc[[4]]], ignore_index=True)
    (cleaned, s), *_ = remediate(df, ["impute_missing", "remove_duplicates"])
    ops = [c["operation"] for c in s["changes"]]
    assert ops.index("remove_duplicates") < ops.index("impute_missing")


def test_unknown_operation_rejected(dirty_df):
    with pytest.raises(ValueError):
        remediate(dirty_df, ["delete_everything"])


def test_plan_lists_safe_and_opt_in(dirty_df):
    q, internal = assess_quality(dirty_df, CFG)
    feats, _ = select_features(dirty_df, CFG, internal["kinds"])
    plan = {p["operation"]: p for p in build_plan(dirty_df, q, internal, feats, CFG)}
    assert plan["remove_duplicates"]["affected"] == 2 and plan["remove_duplicates"]["safe"]
    assert plan["trim_whitespace"]["affected"] == 3
    assert not plan["impute_missing"]["safe"] and not plan["impute_missing"]["default"]
    assert plan["invalid_to_missing"]["affected"] == 2 and not plan["winsorize"]["safe"]


# ---------------------------------------------------------------- drift
def shifted():
    rng = np.random.default_rng(5)
    ref = pd.DataFrame({"x": rng.normal(0, 1, 500), "y": rng.normal(10, 2, 500),
                        "c": rng.choice(["a", "b", "c"], 500, p=[.5, .3, .2])})
    cur = pd.DataFrame({"x": rng.normal(1.5, 1, 500), "y": rng.normal(10, 2, 500),
                        "c": rng.choice(["a", "b", "c"], 500, p=[.2, .3, .5])})
    return ref, cur


def test_drift_detects_numeric_and_categorical_shift():
    ref, cur = shifted()
    d = drift.detect_drift(ref, cur, CFG, {"name": "ref"})
    f = {x["feature"]: x for x in d["features"]}
    assert d["available"] and d["drift_detected"] and set(d["affected_features"]) == {"x", "c"}
    assert f["x"]["status"] == "SIGNIFICANT DRIFT" and f["x"]["type"] == "numeric" and f["x"]["psi"] > 0.25
    assert f["c"]["type"] == "categorical" and f["c"]["test"] == "Chi-square" and f["c"]["drifted"]
    assert f["y"]["status"] == "NO DRIFT" and not f["y"]["drifted"]
    assert d["overall_status"] == "SIGNIFICANT DRIFT" and d["drifted_features"] == 2
    assert f["x"]["distribution"]["reference"] and f["x"]["reference_summary"]["mean"] < f["x"]["current_summary"]["mean"]


def test_no_drift_between_samples_of_same_distribution():
    rng = np.random.default_rng(9)
    mk = lambda: pd.DataFrame({"x": rng.normal(0, 1, 800), "c": rng.choice(["a", "b"], 800)})
    d = drift.detect_drift(mk(), mk(), CFG)
    assert d["overall_status"] == "NO DRIFT" and d["drifted_features"] == 0


def test_insufficient_samples_never_claim_drift():
    ref, cur = shifted()
    d = drift.detect_drift(ref.head(10), cur.head(10), CFG)
    assert d["available"] is False and d["overall_status"] == "INSUFFICIENT DATA"
    assert all(f["status"] == "INSUFFICIENT DATA" and not f["drifted"] for f in d["features"])


def test_drift_schema_changes_and_no_common_columns():
    ref, cur = shifted()
    d = drift.detect_drift(ref, cur.rename(columns={"y": "z"}), CFG)
    assert d["schema"]["columns_added"] == ["z"] and d["schema"]["columns_removed"] == ["y"]
    assert drift.detect_drift(ref, pd.DataFrame({"q": [1, 2]}), CFG)["available"] is False


def test_pipeline_drift_requires_reference(dirty_result):
    assert dirty_result["drift"]["available"] is False and "no reference" in dirty_result["drift"]["message"].lower()
    ref, cur = shifted()
    res = run_pipeline(cur, reference=ref)
    assert res["drift"]["available"] and res["monitoring"]["current"]["drifted_features"] == 2
    assert any(a["type"] == "DATA_DRIFT" for a in res["alerts"])
    assert any(r["category"] == "Data drift" for r in res["recommendations"])


# ---------------------------------------------------------------- alerts
def q_for(df):
    return assess_quality(df, CFG)[0]


NO_ANOM = {"critical_count": 0, "high_count": 0, "anomaly_pct": 0, "anomaly_count": 0, "affected_features": {}}


def test_no_meaningless_alerts_for_trivial_issues():
    df = make_df(2000); df.loc[0, "income"] = np.nan; df = pd.concat([df, df.iloc[[1]]], ignore_index=True)
    assert alerts_svc.generate_alerts(CFG, "d", q_for(df), NO_ANOM, {"available": False}, None) == []


def test_alerts_fire_on_thresholds_with_required_fields(dirty_result):
    al = dirty_result["alerts"]
    types = {a["type"] for a in al}
    assert "CRITICAL_ANOMALIES" in types           # the impossible age 185 is surfaced...
    assert "INVALID_VALUES" not in types           # ...but 2/302 invalid rows (0.7%) is below the 1% alert threshold
    for a in al:
        assert {"type", "severity", "message", "timestamp", "affected", "recommended_action"} <= set(a)
        assert a["severity"] in {"MEDIUM", "HIGH", "CRITICAL"}
    assert [a["severity"] for a in al] == sorted([a["severity"] for a in al], key=["CRITICAL", "HIGH", "MEDIUM"].index)


def test_alerts_quality_thresholds_and_drop():
    q = q_for(make_df(100)); 
    q = {**q, "overall_score": 45.0}
    assert alerts_svc.generate_alerts(CFG, "d", q, NO_ANOM, {"available": False}, None)[0]["severity"] == "CRITICAL"
    q["overall_score"] = 90.0
    prev = {"quality_score": 99.0, "anomaly_count": 2}
    al = alerts_svc.generate_alerts(CFG, "d", q, NO_ANOM, {"available": False}, prev)
    assert [a["type"] for a in al] == ["QUALITY_DROP"] and al[0]["severity"] == "MEDIUM"
    custom = merge_analysis_config({"quality_drop_medium": 20})
    assert alerts_svc.generate_alerts(custom, "d", q, NO_ANOM, {"available": False}, prev) == []


def test_anomaly_increase_alert():
    q = q_for(make_df(100))
    anomalies = {**NO_ANOM, "anomaly_count": 30, "anomaly_pct": 1}
    al = alerts_svc.generate_alerts(CFG, "d", q, anomalies, {"available": False}, {"quality_score": 100, "anomaly_count": 10})
    assert any(a["type"] == "ANOMALY_INCREASE" for a in al)


def test_missing_column_alert():
    df = make_df(100); df.loc[:39, "income"] = np.nan
    al = alerts_svc.generate_alerts(CFG, "d", q_for(df), NO_ANOM, {"available": False}, None)
    assert any(a["type"] == "MISSING_VALUES" and a["affected"] == "income" for a in al)


# ---------------------------------------------------------------- trends / forecast
def pts(quality, anomalies=None, risk=None, drifted=None, alerts=None):
    n = len(quality)
    return [{"analysis_id": i + 1, "timestamp": f"2026-01-{i + 1:02d}", "quality_score": quality[i],
             "anomaly_count": (anomalies or [10] * n)[i], "risk_score": (risk or [20] * n)[i],
             "drifted_features": (drifted or [0] * n)[i], "alert_count": (alerts or [1] * n)[i]} for i in range(n)]


def test_trend_insufficient_history():
    t = trends.analyze_trends(pts([90]))
    assert t["available"] is False and "Not available — insufficient data" in t["message"]


def test_trend_direction_semantics_are_correct():
    t = trends.analyze_trends(pts([90, 88, 85, 80, 76], anomalies=[5, 8, 12, 20, 30], risk=[20, 25, 35, 45, 55]))
    m = t["metrics"]
    assert m["quality_score"]["trend"] == "DECLINING" and m["quality_score"]["direction"] == "DOWN"
    assert m["anomaly_count"]["trend"] == "DECLINING" and m["anomaly_count"]["direction"] == "UP"   # more anomalies = worse
    assert m["risk_score"]["trend"] == "DECLINING" and t["overall_trend"] == "DECLINING"


def test_falling_anomalies_are_improving_not_declining():
    t = trends.analyze_trends(pts([80, 84, 88, 92, 95], anomalies=[40, 30, 20, 10, 5], risk=[50, 40, 30, 20, 10]))
    assert t["metrics"]["anomaly_count"]["trend"] == "IMPROVING" and t["metrics"]["anomaly_count"]["direction"] == "DOWN"
    assert t["overall_trend"] == "IMPROVING"


def test_stable_trend():
    t = trends.analyze_trends(pts([90.0, 90.1, 89.9, 90.0, 90.1]))
    assert t["overall_trend"] == "STABLE" and t["metrics"]["quality_score"]["trend"] == "STABLE"


def test_forecast_refuses_without_enough_history():
    for n in (1, 2, 4):
        f = forecasting.forecast(pts([90 - i for i in range(n)]), CFG)
        assert f["available"] is False and f["message"] == "Insufficient historical data for reliable forecasting."
        assert "forecast" not in f


def test_forecast_with_enough_history():
    f = forecasting.forecast(pts([90, 88, 86, 84, 82, 80], risk=[10, 15, 20, 25, 30, 35]), CFG)
    assert f["available"] and f["horizon"] == 3 and f["forecast_trend"] == "DECLINING"
    q = f["forecast"]["quality_score"]
    assert [p["period"] for p in q] == [1, 2, 3] and q[0]["value"] == pytest.approx(78, abs=0.5)
    assert q[2]["value"] < q[0]["value"] and 0 <= q[2]["lower"] <= q[2]["value"] <= q[2]["upper"] <= 100
    assert f["forecast"]["risk_score"][-1]["value"] == pytest.approx(50, abs=1) and f["forecast_risk_level"] == "HIGH"


def test_forecast_values_clamped():
    f = forecasting.forecast(pts([30, 25, 20, 15, 10, 5]), CFG)
    assert all(0 <= p["value"] <= 100 for p in f["forecast"]["quality_score"])


# ---------------------------------------------------------------- decision engine
def decide_for(df, **kw):
    r = run_pipeline(df, **kw)
    return r["decision"], r


def test_decision_is_deterministic(dirty_df):
    a, _ = decide_for(dirty_df)
    b, _ = decide_for(dirty_df.copy())
    for k in ("risk_score", "risk_level", "overall_status", "decision", "priority"):
        assert a[k] == b[k]


def test_clean_data_is_healthy(clean_df):
    d, r = decide_for(clean_df)
    assert d["risk_level"] == "LOW" and d["overall_status"] == "HEALTHY" and d["decision"] == "DATASET HEALTHY"
    assert d["priority"].startswith("P4") and r["quality"]["overall_score"] == 100


def test_status_priority_decision_all_follow_risk_level(dirty_result):
    d = dirty_result["decision"]
    assert d["overall_status"] == decision_engine.STATUS[d["risk_level"]]
    assert d["priority"] == decision_engine.PRIORITY[d["risk_level"]]
    assert d["decision"] == decision_engine.DECISION[d["risk_level"]]
    assert d["risk_level"] == decision_engine.risk_level_from_score(d["risk_score"], CFG.risk_medium, CFG.risk_high, CFG.risk_critical)
    assert dirty_result["monitoring"]["current"]["risk_level"] == d["risk_level"]     # no module disagrees
    assert dirty_result["quality"]["overall_score"] == d["quality_score"]               # ONE quality score


def test_components_sum_and_unavailable_parts_are_not_guessed(dirty_result):
    d = dirty_result["decision"]
    assert sum(c["points"] for c in d["components"]) == d["raw_points"]
    assert all(c["points"] <= c["max_points"] for c in d["components"])
    assert any("drift" in n for n in d["not_available"]) and any("forecast" in n for n in d["not_available"])
    assert next(c for c in d["components"] if c["name"] == "Data drift")["points"] == 0


def test_floor_critical_anomaly_never_healthy():
    df = make_df(500); df.loc[10, "age"] = 900
    d, r = decide_for(df)
    assert r["anomalies"]["summary"]["critical_count"] >= 1
    assert d["risk_level"] != "LOW" and d["overall_status"] != "HEALTHY"


def test_floor_mostly_missing_data_is_at_least_high():
    df = make_df(100); df.loc[:59, ["income", "score", "city", "gender"]] = np.nan     # 40% of cells missing
    d, r = decide_for(df)
    assert r["quality"]["summary"]["missing_pct"] >= 40
    assert d["risk_level"] in {"HIGH", "CRITICAL"} and d["risk_score"] >= CFG.risk_high
    assert any("40%" in f for f in d["floors_applied"])


def test_history_changes_trend_forecast_and_decision(dirty_df):
    hist = pts([95, 92, 90, 88, 86], anomalies=[2, 4, 6, 8, 10], risk=[10, 15, 20, 25, 30])
    r = run_pipeline(make_df(), history=hist)
    assert r["trends"]["available"] and r["forecast"]["available"]
    assert r["monitoring"]["previous"]["analysis_id"] == 5 and r["monitoring"]["runs_in_series"] == 6
    assert r["monitoring"]["delta"]["quality_score"] == pytest.approx(r["quality"]["overall_score"] - 86, abs=0.01)
    assert r["trends"]["series"][-1]["risk_score"] == r["decision"]["risk_score"]


# ---------------------------------------------------------------- pipeline robustness
def test_pipeline_result_has_every_section(dirty_result):
    for key in ("profile", "quality", "anomalies", "evaluation", "explanations", "recommendations", "remediation",
                "drift", "monitoring", "alerts", "trends", "forecast", "decision", "insights", "pipeline"):
        assert key in dirty_result
    assert dirty_result["pipeline"]["failed_steps"] == []
    names = [s["name"] for s in dirty_result["pipeline"]["steps"]]
    assert names.index("Checking data quality") < names.index("Statistical anomaly detection") < names.index("Final decision")


@pytest.mark.parametrize("df", [
    pd.DataFrame({"a": list("abcdefghij"), "b": list("klmnopqrst")}),                      # no numeric columns
    pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]}),                                         # too few rows
    pd.DataFrame({"a": [5] * 50, "b": ["x"] * 50}),                                         # everything constant
    pd.DataFrame({"a": [np.nan] * 40, "b": np.arange(40.0)}),                               # mostly missing
    pd.DataFrame({"only": np.arange(25.0)}),                                                # single column
    pd.DataFrame({"a": np.arange(30.0), "b": np.arange(30.0)}).assign(c=lambda d: d.a * 2),  # perfectly correlated
])
def test_pipeline_never_crashes_on_awkward_data(df):
    r = run_pipeline(df)
    assert r["pipeline"]["failed_steps"] == []
    assert 0 <= r["quality"]["overall_score"] <= 100 and r["decision"]["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert r["recommendations"] and isinstance(r["insights"], list)


def test_pipeline_output_is_valid_json(dirty_result):
    import json
    json.dumps(dirty_result, allow_nan=False)                      # no NaN / inf / numpy types leak out
