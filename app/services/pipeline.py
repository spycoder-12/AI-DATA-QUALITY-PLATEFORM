"""The ONE analysis pipeline.

``execute`` is a pure function (DataFrame in, unified result out) so it is easy
to test; ``run_analysis`` wraps it with database persistence and progress
reporting. Every dataset is loaded once, features are selected once, the ML
models run once, and each intermediate result is reused downstream.

Step order (recommendations are generated after all evidence exists):
 profile -> quality -> statistical anomalies -> ML anomalies -> consensus ->
 evaluation -> explanations -> remediation plan -> drift -> monitoring ->
 alerts -> trends -> forecast -> recommendations -> final decision -> save
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from app import database
from app.config import AnalysisConfig, Settings, get_settings, merge_analysis_config
from app.models import Alert, AnalysisRun, Anomaly, Dataset, Recommendation
from app.services import (alerts as alerts_svc, anomaly, consensus, decision_engine, drift as drift_svc,
                          evaluation, explainability, forecasting, ml_detection, monitoring,
                          profiler, quality, recommendation, remediation, reports, trends)
from app.utils.file_handler import load_cached, public_meta
from app.utils.helpers import iso, json_safe, utcnow
from app.utils.validators import AppError

log = logging.getLogger("aidq.pipeline")
Progress = Callable[[str, int], None]

NO_REFERENCE = ("Not available — no reference dataset. Choose a reference dataset (or re-upload a "
                "newer version of the same file) to enable drift detection.")


def execute(df: pd.DataFrame, load_meta: dict, cfg: AnalysisConfig, options: dict, dataset_info: dict,
            reference_df: Optional[pd.DataFrame] = None, reference_info: Optional[dict] = None,
            history: Optional[List[dict]] = None, progress: Optional[Progress] = None) -> dict:
    history = history or []
    steps: List[dict] = []
    started = time.perf_counter()

    def step(name: str, pct: int, fn: Callable[[], Any], fallback: Any = None, critical: bool = False):
        if progress:
            progress(name, pct)
        t0 = time.perf_counter()
        try:
            value = fn()
            steps.append({"name": name, "status": "OK", "seconds": round(time.perf_counter() - t0, 3)})
            return value
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("Pipeline step '%s' failed", name)
            steps.append({"name": name, "status": "FAILED", "seconds": round(time.perf_counter() - t0, 3),
                          "message": f"{name} could not be completed ({type(exc).__name__})."})
            if critical:
                raise AppError(f"The analysis could not complete the step '{name}'. "
                               f"The dataset may contain unsupported values.", 422, "analysis_failed") from exc
            return fallback() if callable(fallback) else fallback

    # ---------------------------------------------------------------- profile / quality
    profile = step("Profiling dataset", 10, lambda: profiler.profile_dataset(df, load_meta), critical=True)
    quality_pub, quality_int = step("Checking data quality", 20,
                                    lambda: quality.assess_quality(df, cfg, load_meta.get("coerced"), options),
                                    critical=True)
    kinds = quality_int["kinds"]

    # ---------------------------------------------------------------- statistical anomalies
    def _stat():
        features, excluded = anomaly.select_features(df, cfg, kinds)
        stats, detectors, public = anomaly.run_statistical_detection(df, features, excluded, cfg)
        return features, stats, detectors, public

    features, stats, stat_detectors, stat_public = step(
        "Statistical anomaly detection", 30, _stat,
        fallback=lambda: ([], {}, [], {"status": "FAILED", "message": "Statistical detection failed.",
                                        "features_used": [], "features_excluded": [], "per_feature": [],
                                        "affected_features": [], "records_flagged": 0}))
    usable = [f for f in features if f in stats]

    # ---------------------------------------------------------------- ML anomalies
    ml_results, ml_public = step(
        "Machine-learning anomaly detection", 42, lambda: ml_detection.run_ml_detection(df, usable, cfg, kinds, stats),
        fallback=lambda: ([], {"status": "FAILED", "message": "ML detection failed.", "models": [],
                               "features_used": [], "preprocessing": []}))

    # ---------------------------------------------------------------- consensus + severity
    detectors = stat_detectors + ml_results
    records, cons_summary = step(
        "Model agreement and severity", 52,
        lambda: consensus.build_consensus(df, detectors, stats, usable, quality_int["rule_rows"], cfg),
        fallback=lambda: ([], {"anomaly_count": 0, "anomaly_pct": 0, "critical_count": 0, "high_count": 0,
                               "severity_distribution": {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0},
                               "detectors_run": [], "affected_features": {}, "_reported_index": []}))
    reported_index = cons_summary.pop("_reported_index", [])
    reported_rows = pd.Series(df.index.isin(reported_index), index=df.index)

    eval_result = step("Model comparison", 58, lambda: evaluation.evaluate(df, detectors, reported_rows, cons_summary),
                       fallback={"comparison": [], "agreement": {}, "ground_truth": {
                           "available": False, "message": "Not available — insufficient data."}})
    explanations = step("Explainable AI", 63, lambda: explainability.explain_records(records, stats), fallback=[])

    # ---------------------------------------------------------------- remediation plan
    rem_plan = step("Remediation plan", 68, lambda: remediation.build_plan(df, quality_pub, quality_int, usable, cfg, load_meta),
                    fallback=[])

    # ---------------------------------------------------------------- drift
    def _drift():
        if reference_df is None:
            return {"available": False, "reference": None, "message": NO_REFERENCE}
        return drift_svc.detect_drift(reference_df, df, cfg, reference_info)

    drift_result = step("Drift analysis", 73, _drift,
                        fallback={"available": False, "message": "Drift analysis could not be completed."})

    # ---------------------------------------------------------------- monitoring / alerts
    previous = history[-1] if history else None
    alert_list = step("Alert generation", 78, lambda: alerts_svc.generate_alerts(
        cfg, dataset_info["name"], quality_pub, cons_summary, drift_result, previous), fallback=[])

    current_point = {
        "analysis_id": dataset_info.get("analysis_id"), "dataset_id": dataset_info["id"],
        "dataset": dataset_info["name"], "timestamp": iso(utcnow()),
        "quality_score": quality_pub["overall_score"], "anomaly_count": cons_summary["anomaly_count"],
        "anomaly_pct": cons_summary["anomaly_pct"], "critical_count": cons_summary["critical_count"],
        "drifted_features": drift_result.get("drifted_features") if drift_result.get("available") else None,
        "alert_count": len(alert_list), "rows": quality_pub["summary"]["rows"],
        "risk_score": None, "risk_level": None, "decision": None, "status": None}

    # first-pass risk (without trend/forecast) so that history has a risk value for this run
    pre = decision_engine.decide(cfg, quality_pub, cons_summary, drift_result,
                                 {"available": False}, {"available": False}, alert_list, rem_plan)
    current_point["risk_score"] = pre["risk_score"]
    series = history + [current_point]

    trend_result = step("Trend analysis", 83, lambda: trends.analyze_trends(series),
                        fallback={"available": False, "message": "Trend analysis failed.", "overall_trend": "INSUFFICIENT DATA",
                                  "metrics": {}, "series": []})
    forecast_result = step("Forecasting", 87, lambda: forecasting.forecast(series, cfg),
                           fallback={"available": False, "message": forecasting.INSUFFICIENT})

    # ---------------------------------------------------------------- recommendations
    recs = step("Recommendations", 91, lambda: recommendation.generate_recommendations(
        quality_pub, cons_summary, explanations, profile, drift_result, trend_result, forecast_result,
        ml_public, kinds), fallback=[])

    decision = step("Final decision", 95, lambda: decision_engine.decide(
        cfg, quality_pub, cons_summary, drift_result, trend_result, forecast_result, alert_list, rem_plan),
        critical=True)
    insights = decision_engine.build_insights(quality_pub, cons_summary, drift_result, trend_result, decision, kinds)

    current_point.update(risk_score=decision["risk_score"], risk_level=decision["risk_level"],
                         decision=decision["decision"], status=decision["overall_status"])
    if trend_result.get("series"):
        trend_result["series"][-1]["risk_score"] = decision["risk_score"]   # display the final value
    monitoring_result = monitoring.build_monitoring(current_point, history)

    # ---------------------------------------------------------------- assemble unified result
    anomalies_section = {
        "summary": cons_summary, "records": consensus.public_records(records),
        "statistical": stat_public, "machine_learning": ml_public,
        "detectors": [d.summary(len(df)) for d in detectors],
    }
    result = {
        "dataset": dataset_info, "generated_at": iso(utcnow()),
        "options": options, "thresholds": {k: v for k, v in cfg.__dict__.items()},
        "profile": profile, "quality": quality_pub, "anomalies": anomalies_section,
        "evaluation": eval_result, "explanations": explanations, "recommendations": recs,
        "remediation": {"plan": rem_plan, "applied": None},
        "drift": drift_result, "monitoring": monitoring_result, "alerts": alert_list,
        "trends": trend_result, "forecast": forecast_result, "decision": decision, "insights": insights,
        "pipeline": {"steps": steps, "total_seconds": round(time.perf_counter() - started, 3),
                     "failed_steps": [s["name"] for s in steps if s["status"] != "OK"]},
    }
    if progress:
        progress("Saving results", 98)
    return json_safe(result)


# --------------------------------------------------------------------------
# Persistence wrapper
# --------------------------------------------------------------------------
def _find_auto_reference(db, dataset: Dataset) -> Optional[Dataset]:
    return (db.query(Dataset).filter(Dataset.group_key == dataset.group_key, Dataset.id < dataset.id)
            .order_by(Dataset.id.desc()).first())


def run_analysis(run_id: int, settings: Optional[Settings] = None) -> None:
    """Execute and persist one analysis run. Never raises (failures are stored on the run)."""
    settings = settings or get_settings()
    db = database.SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        if run is None:
            return
        dataset = db.get(Dataset, run.dataset_id)
        run.status, run.progress, run.current_step = "RUNNING", 2, "Loading data"
        db.commit()

        def progress(step_name: str, pct: int) -> None:
            run.progress, run.current_step = pct, step_name
            db.commit()

        try:
            cfg = merge_analysis_config((run.options or {}).get("thresholds"))
            options = run.options or {}
            df, meta = load_cached(settings.upload_dir / dataset.stored_filename,
                                   "." + dataset.file_type, settings.max_rows)

            reference_df, reference_info = None, None
            ref = db.get(Dataset, run.reference_dataset_id) if run.reference_dataset_id else None
            mode = "explicit"
            if ref is None and options.get("auto_reference", True):
                ref, mode = _find_auto_reference(db, dataset), "previous_version"
            if ref is not None:
                try:
                    reference_df, _ = load_cached(settings.upload_dir / ref.stored_filename,
                                                  "." + ref.file_type, settings.max_rows)
                    run.reference_dataset_id = ref.id
                    reference_info = {"dataset_id": ref.id, "name": ref.original_filename, "rows": ref.rows,
                                      "mode": mode, "uploaded_at": iso(ref.uploaded_at)}
                except AppError as exc:
                    log.warning("Reference dataset unavailable: %s", exc.message)

            history = monitoring.get_history(db, group_key=dataset.group_key, exclude_run_id=run.id)
            info = {"id": dataset.id, "analysis_id": run.id, "name": dataset.original_filename,
                    "rows": int(len(df)), "columns": int(df.shape[1]), "file_type": dataset.file_type,
                    "size_bytes": dataset.size_bytes, "uploaded_at": iso(dataset.uploaded_at),
                    "load": public_meta(meta)}
            result = execute(df, meta, cfg, options, info, reference_df, reference_info, history, progress)
            _persist(db, run, dataset, result)
            try:
                reports.write_reports(result, history + [result["monitoring"]["current"]],
                                      settings.report_dir / f"analysis_{run.id}")
            except Exception:  # noqa: BLE001
                log.exception("Report files could not be written (they can still be generated on demand).")
        except AppError as exc:
            db.rollback()
            run = db.get(AnalysisRun, run_id)
            run.status, run.error_message, run.completed_at = "FAILED", exc.message, utcnow()
            db.commit()
        except Exception:  # noqa: BLE001
            log.exception("Analysis run %s failed", run_id)
            db.rollback()
            run = db.get(AnalysisRun, run_id)
            run.status, run.completed_at = "FAILED", utcnow()
            run.error_message = "The analysis failed unexpectedly. Please check the file and try again."
            db.commit()
    finally:
        db.close()


def _persist(db, run: AnalysisRun, dataset: Dataset, result: dict) -> None:
    q, a, d = result["quality"], result["anomalies"]["summary"], result["decision"]
    drift = result["drift"]
    run.rows, run.columns = q["summary"]["rows"], q["summary"]["columns"]
    run.quality_score = q["overall_score"]
    run.missing_values, run.duplicate_rows = q["summary"]["missing_values"], q["summary"]["duplicate_rows"]
    run.anomaly_count, run.anomaly_pct = a["anomaly_count"], a["anomaly_pct"]
    run.critical_count = a["critical_count"]
    run.drifted_features = drift.get("drifted_features") if drift.get("available") else None
    run.risk_score, run.risk_level = d["risk_score"], d["risk_level"]
    run.overall_status, run.decision = d["overall_status"], d["decision"]
    run.alert_count = len(result["alerts"])
    run.trend = result["trends"].get("overall_trend")
    run.result = result
    run.status, run.progress, run.current_step, run.completed_at = "COMPLETED", 100, "Completed", utcnow()
    dataset.rows, dataset.columns = q["summary"]["rows"], q["summary"]["columns"]
    for rec in result["anomalies"]["records"]:
        db.add(Anomaly(analysis_id=run.id, row_number=rec["row"], severity=rec["severity"],
                       evidence_level=rec["evidence_level"], support_count=rec["support_count"],
                       detectors=", ".join(rec["detectors"])[:200], primary_feature=rec["primary_feature"],
                       primary_value=rec.get("primary_value"), detail={"features": rec["features"]}))
    for al in result["alerts"]:
        db.add(Alert(analysis_id=run.id, dataset_id=dataset.id, alert_type=al["type"], severity=al["severity"],
                     message=al["message"], affected=al["affected"], recommended_action=al["recommended_action"],
                     metric=al.get("metric"), value=al.get("value") if isinstance(al.get("value"), (int, float)) else None,
                     threshold=al.get("threshold") if isinstance(al.get("threshold"), (int, float)) else None))
    for rec in result["recommendations"]:
        db.add(Recommendation(analysis_id=run.id, category=rec["category"], severity=rec["severity"],
                              priority=rec["priority"], target=(rec["target"] or "")[:255], finding=rec["finding"],
                              recommendation=rec["recommendation"], evidence=rec.get("evidence"),
                              automated_fix=rec.get("automated_fix")))
    db.commit()
