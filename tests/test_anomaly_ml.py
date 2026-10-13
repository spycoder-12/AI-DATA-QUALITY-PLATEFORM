"""Statistical detectors, ML models, consensus, severity, explainability, evaluation."""
import numpy as np
import pandas as pd
import pytest

from app.config import ANALYSIS_DEFAULTS as CFG, merge_analysis_config
from app.ml import isolation_forest, local_outlier_factor, one_class_svm
from app.services import severity
from app.services.anomaly import (compute_feature_stats, detect_iqr, detect_zscore, select_features,
                                  run_statistical_detection)
from app.services.consensus import build_consensus
from app.services.evaluation import evaluate, find_ground_truth
from app.services.explainability import explain_records
from app.services.ml_detection import prepare_features, run_ml_detection
from app.services.quality import assess_quality
from tests.conftest import make_df


def prepared(df):
    q, internal = assess_quality(df, CFG)
    feats, excl = select_features(df, CFG, internal["kinds"])
    stats, det, pub = run_statistical_detection(df, feats, excl, CFG)
    return q, internal, feats, excl, stats, det, pub


# ---------------------------------------------------------------- feature selection
def test_feature_selection_excludes_ids_constants_binary_labels():
    df = make_df(100)
    df["const"] = 5; df["flag"] = [0, 1] * 50; df["is_anomaly"] = [0] * 99 + [1]
    df["row_id"] = np.arange(100)
    feats, excl = select_features(df, CFG)
    assert set(feats) == {"age", "income", "score"}
    reasons = {e["feature"]: e["reason"] for e in excl}
    assert "identifier" in reasons["customer_id"] and "constant" in reasons["const"]
    assert "binary" in reasons["flag"] and "ground-truth" in reasons["is_anomaly"]


def test_small_discrete_scales_excluded_but_wide_age_with_outlier_kept():
    df = pd.DataFrame({"scale": np.random.default_rng(0).integers(1, 11, 100),
                       "age": [20, 21, 22, 23, 24] * 19 + [185] * 5})
    feats, excl = select_features(df, CFG)
    assert "scale" not in feats and "age" in feats


# ---------------------------------------------------------------- IQR / Z-score
def test_iqr_boundaries_and_counts(dirty_df):
    _, _, feats, _, stats, det, pub = prepared(dirty_df)
    iqr = det[0]
    st = stats["income"]
    assert iqr.per_feature["income"]["lower_bound"] == pytest.approx(st["q1"] - 1.5 * st["iqr"], abs=1)
    flagged = set(iqr.feature_masks["income"].index[iqr.feature_masks["income"]])
    assert 30 in flagged                                             # the 5,000,000 income
    assert iqr.per_feature["age"]["anomaly_count"] >= 2              # 185 and -5
    assert pub["records_flagged"] >= 3 and "income" in pub["affected_features"]
    assert 0 < pub["records_flagged_pct"] < 20


def test_zscore_flags_extremes_only(dirty_df):
    _, _, feats, _, stats, det, _ = prepared(dirty_df)
    z = det[1]
    mask = z.feature_masks["income"]
    assert mask[30] and mask.sum() <= 5
    assert z.per_feature["income"]["max_abs_z"] > 3


def test_iqr_skipped_when_iqr_zero():
    df = pd.DataFrame({"x": [0] * 90 + list(range(1, 11)) + [500] * 2, "y": np.arange(102) * 1.5})
    st = compute_feature_stats(df, ["x"], CFG)
    res = detect_iqr(df, ["x"], st, CFG)
    assert "skipped" in res.per_feature["x"]


def test_skewed_features_use_log_scale_so_long_tails_are_not_critical():
    rng = np.random.default_rng(1)
    df = pd.DataFrame({"notifications": rng.lognormal(3.8, 0.8, 3000).round(), "age": rng.normal(30, 8, 3000).round()})
    st = compute_feature_stats(df, ["notifications", "age"], CFG)
    assert st["notifications"]["transform"] == "log1p" and st["age"]["transform"] is None
    z = detect_zscore(df, ["notifications"], st, CFG)
    assert z.per_feature["notifications"]["anomaly_pct"] < 1.0       # natural tail is not mass-flagged
    df.loc[0, "notifications"] = 1_000_000                            # but a real error still is
    st = compute_feature_stats(df, ["notifications"], CFG)
    assert detect_zscore(df, ["notifications"], st, CFG).feature_masks["notifications"][0]


def test_threshold_override_changes_results(dirty_df):
    strict = merge_analysis_config({"zscore_threshold": 1.5})
    _, _, feats, excl, stats, det, _ = prepared(dirty_df)
    stats2 = compute_feature_stats(dirty_df, feats, strict)
    assert detect_zscore(dirty_df, feats, stats2, strict).flagged > det[1].flagged
    with pytest.raises(ValueError):
        merge_analysis_config({"iqr_multiplier": "abc"})


def test_no_numeric_columns_returns_status_not_crash():
    df = pd.DataFrame({"a": list("abcdefghij") * 3, "b": list("xy") * 15})
    _, _, feats, excl, stats, det, pub = prepared(df)
    assert feats == [] and pub["status"] == "SKIPPED" and "No suitable numerical" in pub["message"]


# ---------------------------------------------------------------- ML models
def _blob():
    rng = np.random.default_rng(0)
    X = np.vstack([rng.normal(0, 1, (200, 3)), [[9, 9, 9], [-9, 9, -9], [10, -10, 10]]])
    return X


@pytest.mark.parametrize("module,kwargs", [(isolation_forest, {}), (local_outlier_factor, {}), (one_class_svm, {})])
def test_ml_model_wrappers_find_planted_outliers(module, kwargs):
    X = _blob()
    flags, scores, params = module.run(X, X, **kwargs)
    assert flags.dtype == bool and len(flags) == len(X) and len(scores) == len(X)
    assert flags[-3:].all()                                          # the three planted points
    assert scores[-3:].min() > np.median(scores[:-3])                # higher score = more anomalous
    assert isinstance(params, dict)


def test_isolation_forest_is_reproducible():
    X = _blob()
    a, _, _ = isolation_forest.run(X, X, "auto", 7)
    b, _, _ = isolation_forest.run(X, X, "auto", 7)
    assert (a == b).all()


def test_lof_novelty_mode_when_fit_set_is_sample():
    X = _blob()
    flags, _, params = local_outlier_factor.run(X[::2], X, 20)
    assert params["mode"] == "novelty" and len(flags) == len(X)


def test_ml_detection_full_run(dirty_df):
    q, internal, feats, excl, stats, _, _ = prepared(dirty_df)
    results, pub = run_ml_detection(dirty_df, feats, CFG, internal["kinds"], stats)
    assert pub["status"] == "OK" and [r.name for r in results] == ["Isolation Forest", "Local Outlier Factor", "One-Class SVM"]
    assert all(r.ok and r.flagged > 0 for r in results)
    assert "Median imputation" in pub["preprocessing"]


def test_ml_handles_missing_values_scaling_and_constants():
    df = make_df(100); df.loc[:20, "income"] = np.nan
    X, used, notes = prepare_features(df, ["age", "income", "score"], CFG)
    assert not np.isnan(X).any() and abs(X.mean()) < 1e-6 and used == ["age", "income", "score"]
    df2 = df.assign(flat=3.0)
    X2, used2, _ = prepare_features(df2, ["age", "flat"], CFG)
    assert "flat" not in used2
    df3 = df.copy(); df3["mostly_missing"] = np.nan; df3.loc[:5, "mostly_missing"] = 1.0
    _, used3, notes3 = prepare_features(df3, ["age", "mostly_missing"], CFG)
    assert "mostly_missing" not in used3 and any("50% missing" in n for n in notes3)


def test_ml_categorical_frequency_encoding_option():
    df = make_df(200); df.loc[:3, "city"] = "Rare"
    cfg = merge_analysis_config({"ml_include_categorical": True})
    X, used, _ = prepare_features(df, ["age"], cfg, {"city": "categorical", "gender": "categorical"})
    assert "city (frequency)" in used


def test_ml_skipped_for_small_dataset_and_no_features():
    small = make_df(10)
    res, pub = run_ml_detection(small, ["age", "income"], CFG)
    assert pub["status"] == "SKIPPED" and "Too few rows" in pub["message"] and all(r.status == "SKIPPED" for r in res)
    res, pub = run_ml_detection(make_df(100), [], CFG)
    assert pub["status"] == "SKIPPED" and "No suitable numerical" in pub["message"]


def test_ml_model_failure_is_contained(monkeypatch, dirty_df):
    q, internal, feats, excl, stats, _, _ = prepared(dirty_df)
    monkeypatch.setattr(one_class_svm, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    import app.services.ml_detection as md
    monkeypatch.setattr(md.one_class_svm, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    results, pub = run_ml_detection(dirty_df, feats, CFG, internal["kinds"], stats)
    assert [r.status for r in results] == ["OK", "OK", "FAILED"] and pub["status"] == "OK"


# ---------------------------------------------------------------- severity
def test_severity_scale_is_one_consistent_system():
    assert severity.level_from_zscore(2.0) == "LOW" and severity.level_from_zscore(3.2) == "MEDIUM"
    assert severity.level_from_zscore(-4.5) == "HIGH" and severity.level_from_zscore(5.1) == "CRITICAL"
    assert severity.level_from_iqr(3.5) == "HIGH" and severity.level_from_iqr(2.0) == "LOW"
    assert severity.level_from_rule(0.54) == "CRITICAL" and severity.level_from_rule(0.05) == "HIGH"
    assert severity.severity_from_rate("missing", 0) is None
    assert [severity.severity_from_rate("missing", r) for r in (2, 10, 30, 60)] == ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert severity.risk_level_from_score(19) == "LOW" and severity.risk_level_from_score(70) == "CRITICAL"


def test_agreement_raises_severity_but_never_creates_critical():
    assert severity.record_severity(["MEDIUM"], 3) == "HIGH"
    assert severity.record_severity(["HIGH"], 5) == "HIGH"          # agreement alone can't make CRITICAL
    assert severity.record_severity(["CRITICAL"], 1) == "CRITICAL"
    assert severity.record_severity(["LOW"], 3) == "MEDIUM"
    assert severity.evidence_level(3) == "STRONG" and severity.evidence_level(1) == "WEAK"


# ---------------------------------------------------------------- consensus + explainability
def consensus_for(df):
    q, internal, feats, excl, stats, det, pub = prepared(df)
    ml, mlpub = run_ml_detection(df, feats, CFG, internal["kinds"], stats)
    records, summary = build_consensus(df, det + ml, stats, feats, internal["rule_rows"], CFG)
    return records, summary, stats, det + ml


def test_consensus_counts_support_and_assigns_severity(dirty_df):
    records, summary, stats, dets = consensus_for(dirty_df)
    by_row = {r["row"]: r for r in records}
    age185 = by_row[22]                                   # df index 20 -> row 22
    assert age185["severity"] == "CRITICAL" and age185["rule_breach"] and age185["support_count"] >= 2
    assert "Validity rule" in age185["methods"] and age185["available_detectors"] == 5
    assert summary["anomaly_count"] == len(records) and summary["critical_count"] >= 2
    assert sum(summary["severity_distribution"].values()) == summary["anomaly_count"]
    assert summary["detectors_run"] == ["IQR", "Z-Score", "Isolation Forest", "Local Outlier Factor", "One-Class SVM"]
    assert records[0]["severity"] == "CRITICAL"            # sorted by severity first


def test_consensus_uses_only_available_detectors():
    df = make_df(10); df.loc[3, "age"] = 400
    records, summary, _, _ = consensus_for(df)           # 10 rows -> ML skipped
    assert summary["detectors_run"] == ["IQR", "Z-Score"] and records
    assert all(r["available_detectors"] == 2 for r in records)
    assert any("ML" in str(u) or "Too few" in u["message"] for u in summary["detectors_unavailable"])


def test_explanations_contain_required_fields(dirty_df):
    records, summary, stats, _ = consensus_for(dirty_df)
    exp = {e["row"]: e for e in explain_records(records, stats)}
    e = exp[22]
    f = e["findings"][0]
    assert f["feature"] == "age" and f["value"] == 185
    assert f["expected_range"] == {"min": 0.0, "max": 120.0, "source": "validity rule"}
    assert f["severity"] == "CRITICAL" and "validity rule" in f["reason"]
    assert "IQR" in f["detection"] and f["evidence"]
    assert e["recommended_action"] and "Flagged by" in e["explanation"] and "evidence level" in e["explanation"]
    income = exp[32]["findings"][0]                       # df index 30
    assert income["feature"] == "income" and income["expected_range"]["max"] < 5_000_000
    assert "statistically expected range" in income["reason"]


def test_ml_only_records_explained_honestly():
    rng = np.random.default_rng(3)
    x = rng.normal(0, 1, 400); y = x + rng.normal(0, 0.05, 400)
    df = pd.DataFrame({"a": x, "b": y}); df.loc[0, ["a", "b"]] = [2.0, -2.0]      # fine alone, odd together
    records, summary, stats, _ = consensus_for(df)
    ml_only = [r for r in records if r["features"] and r["features"][0]["ml_context_only"]]
    if ml_only:
        e = explain_records(ml_only[:1], stats)[0]
        assert "combination" in e["findings"][0]["reason"]


# ---------------------------------------------------------------- evaluation
def labelled(n=300, k=6, seed=0):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({"a": rng.normal(0, 1, n), "b": rng.normal(0, 1, n), "is_anomaly": 0})
    idx = rng.choice(n, k, replace=False)
    df.loc[idx, ["a", "b"]] = rng.uniform(8, 12, (k, 2)); df.loc[idx, "is_anomaly"] = 1
    return df, idx


def test_ground_truth_metrics_when_labels_exist():
    df, idx = labelled()
    records, summary, stats, dets = consensus_for(df)
    rep = pd.Series(df.index.isin([r["index"] for r in records]), index=df.index)
    ev = evaluate(df, dets, rep, summary)
    gt = ev["ground_truth"]
    assert gt["available"] and gt["actual_anomalies"] == 6 and gt["label_column"] == "is_anomaly"
    iqr = next(m for m in gt["metrics"] if m["model"] == "IQR")
    assert iqr["recall"] == 1.0 and 0 < iqr["precision"] <= 1 and iqr["true_positive"] == 6
    assert iqr["true_positive"] + iqr["false_negative"] == 6
    assert ev["agreement"]["jaccard"]["IQR"]["IQR"] == 1.0


def test_no_fabricated_metrics_without_labels(dirty_df):
    records, summary, stats, dets = consensus_for(dirty_df)
    rep = pd.Series(dirty_df.index.isin([r["index"] for r in records]), index=dirty_df.index)
    gt = evaluate(dirty_df, dets, rep, summary)["ground_truth"]
    assert gt["available"] is False and "Not available" in gt["message"] and "metrics" not in gt


def test_single_class_labels_not_evaluated():
    df, _ = labelled(); df["is_anomaly"] = 0
    records, summary, stats, dets = consensus_for(df)
    rep = pd.Series(False, index=df.index)
    gt = evaluate(df, dets, rep, summary)["ground_truth"]
    assert gt["available"] is False and "only one class" in gt["message"]


def test_label_column_never_used_as_feature():
    df, _ = labelled()
    feats, excl = select_features(df, CFG)
    assert "is_anomaly" not in feats and find_ground_truth(df) is not None
