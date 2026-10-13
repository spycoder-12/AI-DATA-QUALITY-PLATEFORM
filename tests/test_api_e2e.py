"""Database layer, API contract, configuration, and complete end-to-end workflows."""
import io
import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import database
from app.config import ConfigError, load_settings, parse_size
from app.main import create_app
from app.models import Alert, AnalysisRun, Anomaly, Dataset, Recommendation
from tests.conftest import csv_bytes, make_df, make_dirty_df


def upload(client, df, name="customers.csv"):
    r = client.post("/api/datasets/upload", files={"file": (name, csv_bytes(df), "text/csv")})
    assert r.status_code == 201, r.text
    return r.json()["dataset"]["id"]


def analyze(client, dataset_id, body=None, **params):
    r = client.post(f"/api/analyze/{dataset_id}?wait=true", json=body or {})
    assert r.status_code == 200, r.text
    return r.json()


# ======================================================================= configuration
def test_parse_size_and_invalid_env():
    assert parse_size("50MB") == 50 * 1024 ** 2 and parse_size("2k") == 2048 and parse_size("1000") == 1000
    for env in ({"MAX_UPLOAD_SIZE": "lots"}, {"PORT": "abc"}, {"PORT": "99999"}, {"DATABASE_URL": "not-a-url"},
                {"MAX_UPLOAD_SIZE": "0"}):
        with pytest.raises(ConfigError):
            load_settings(env=env, load_env_file=False)


def test_settings_come_from_environment_not_code(tmp_path):
    s = load_settings(env={"DATABASE_URL": "sqlite:///x.db", "UPLOAD_DIR": str(tmp_path / "up"), "PROCESSED_DIR": str(tmp_path / "pr"),
                           "REPORT_DIR": str(tmp_path / "rp"), "MAX_UPLOAD_SIZE": "1MB", "CORS_ORIGINS": "http://a.test"}, load_env_file=False)
    assert s.max_upload_bytes == 1024 ** 2 and s.cors_origins == ("http://a.test",) and (tmp_path / "up").is_dir()


def test_no_credentials_hardcoded_in_source():
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    pattern = re.compile(r"(postgres(?:ql)?(?:\+\w+)?://[^\s'\"]*:[^\s'\"@]+@|password\s*=\s*['\"][^'\"]+['\"])", re.I)
    placeholder = re.compile(r"user:pass@host")                  # documented example in an error message
    offenders = [str(p) for p in list((root / "app").rglob("*.py")) + [root / "run.py"]
                 if pattern.search(placeholder.sub("", p.read_text()))]
    assert offenders == []


def test_env_file_is_ignored_by_git():
    from pathlib import Path
    gi = (Path(__file__).resolve().parent.parent / ".gitignore").read_text()
    assert ".env" in gi.splitlines()


# ======================================================================= database layer
def test_database_crud_and_cascade(client, dirty_df):
    did = upload(client, dirty_df)
    aid = analyze(client, did)["analysis"]["id"]
    db = database.SessionLocal()
    try:
        ds = db.get(Dataset, did)
        assert ds.original_filename == "customers.csv" and len(ds.sha256) == 64 and ds.rows == 302
        run = db.get(AnalysisRun, aid)
        assert run.status == "COMPLETED" and run.quality_score and run.risk_level and run.result
        assert db.query(Anomaly).filter_by(analysis_id=aid).count() == run.anomaly_count
        assert db.query(Alert).filter_by(analysis_id=aid).count() == run.alert_count > 0
        assert db.query(Recommendation).filter_by(analysis_id=aid).count() >= 4
        # no raw dataset values are persisted beyond aggregate statistics and the flagged records
        assert all("sample" not in c for c in run.result["profile"]["column_profiles"])
        db.delete(ds)
        db.commit()
        assert db.query(AnalysisRun).count() == 0 and db.query(Anomaly).count() == 0 and db.query(Alert).count() == 0
    finally:
        db.close()


def test_database_unavailable_gives_friendly_503(tmp_path):
    bad = load_settings(env={"DATABASE_URL": "sqlite:////nonexistent_dir_xyz/sub/x.db", "UPLOAD_DIR": str(tmp_path / "u"),
                             "PROCESSED_DIR": str(tmp_path / "p"), "REPORT_DIR": str(tmp_path / "r")}, load_env_file=False)
    with TestClient(create_app(bad), raise_server_exceptions=False) as c:
        h = c.get("/api/health").json()
        assert h["status"] == "degraded" and h["database"]["connected"] is False
        r = c.get("/api/datasets")
        assert r.status_code == 503 and r.json()["error"]["code"] == "database_unavailable"
        assert "Traceback" not in r.text and "sqlalchemy" not in r.text.lower()


# ======================================================================= API contract
def test_health_and_config(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["database"]["connected"] and h["database"]["dialect"] == "sqlite"
    cfg = client.get("/api/config").json()
    assert cfg["thresholds"]["iqr_multiplier"] == 1.5 and cfg["max_upload_mb"] == 2


def test_error_format_is_consistent_and_hides_internals(client):
    for path in ("/api/analysis/999", "/api/datasets/999", "/api/analysis/999/quality", "/api/analysis/999/reports/final_analysis_report"):
        r = client.get(path)
        assert r.status_code == 404 and set(r.json()) == {"error"} and {"code", "message"} <= set(r.json()["error"])
    r = client.post("/api/analyze/abc")
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_input_validation(client, clean_df):
    did = upload(client, clean_df)
    assert client.post(f"/api/analyze/{did}", json={"thresholds": {"bogus": 1}}).status_code == 422
    assert client.post(f"/api/analyze/{did}", json={"unknown_field": 1}).status_code == 422
    assert client.post(f"/api/analyze/{did}", json={"reference_dataset_id": did}).status_code == 400
    assert client.post(f"/api/analyze/{did}", json={"reference_dataset_id": 999}).status_code == 404
    assert client.post(f"/api/analyze/{did}", json={"validity_rules": {"age": [1]}}).status_code == 422
    assert client.post("/api/analyze/999").status_code == 404


def test_all_documented_endpoints_exist(client):
    paths = set(client.get("/api/openapi.json").json()["paths"])
    required = ["/api/datasets/upload", "/api/datasets", "/api/datasets/{dataset_id}", "/api/analyze/{dataset_id}",
                "/api/analysis/{analysis_id}", "/api/analysis/{analysis_id}/profile", "/api/analysis/{analysis_id}/quality",
                "/api/analysis/{analysis_id}/anomalies", "/api/analysis/{analysis_id}/explanations",
                "/api/analysis/{analysis_id}/recommendations", "/api/analysis/{analysis_id}/remediation",
                "/api/monitoring", "/api/drift", "/api/trends", "/api/forecast", "/api/alerts",
                "/api/dashboard/summary", "/api/health"]
    assert [p for p in required if p not in paths] == []


def test_security_headers_and_cors(client):
    r = client.options("/api/health", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers
    r = client.get("/api/health", headers={"Origin": "http://localhost:8000"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:8000"
    assert client.get("/.env").status_code in (404, 405)
    assert client.get("/static/../.env").status_code in (404, 400)


def test_frontend_is_served(client):
    html = client.get("/").text
    assert "AI Data Quality Intelligence Platform" in html and "/static/app.js" in html
    assert "Phase" not in html and "phase" not in client.get("/static/app.js").text.lower().replace("phase-", "")
    assert client.get("/static/style.css").status_code == 200


# ======================================================================= end to end
def test_full_workflow_upload_analyze_persist_dashboard(client, dirty_df):
    # empty state first
    assert client.get("/api/dashboard/summary").json()["has_data"] is False
    did = upload(client, dirty_df)

    # asynchronous run with progress polling, exactly as the UI does it
    r = client.post(f"/api/analyze/{did}")
    assert r.status_code == 202
    aid = r.json()["analysis_id"]
    st = client.get(f"/api/analysis/{aid}/status").json()
    assert st["status"] == "COMPLETED" and st["progress"] == 100

    full = client.get(f"/api/analysis/{aid}").json()
    q = full["quality"]
    assert q["summary"]["missing_values"] == 3 and q["summary"]["duplicate_rows"] == 2
    assert full["anomalies"]["summary"]["critical_count"] >= 2
    assert full["decision"]["risk_level"] in {"MEDIUM", "HIGH", "CRITICAL"}

    # every section endpoint serves the SAME stored result (one pipeline, one score)
    assert client.get(f"/api/analysis/{aid}/profile").json() == full["profile"]
    assert client.get(f"/api/analysis/{aid}/quality").json() == q
    anomalies = client.get(f"/api/analysis/{aid}/anomalies").json()
    assert anomalies["summary"] == full["anomalies"]["summary"] and anomalies["total_matching"] == len(full["anomalies"]["records"])
    crit = client.get(f"/api/analysis/{aid}/anomalies?severity=CRITICAL").json()
    assert crit["total_matching"] == anomalies["summary"]["critical_count"]
    assert client.get(f"/api/analysis/{aid}/anomalies?severity=NOPE").status_code == 400
    exp = client.get(f"/api/analysis/{aid}/explanations?severity=CRITICAL").json()
    assert exp["count"] >= 2 and all(e["severity"] == "CRITICAL" for e in exp["explanations"])
    recs = client.get(f"/api/analysis/{aid}/recommendations").json()
    assert recs["count"] == len(full["recommendations"])
    rem = client.get(f"/api/analysis/{aid}/remediation").json()
    assert rem["applied"] is None and any(p["operation"] == "remove_duplicates" for p in rem["plan"])

    # dashboard reflects the saved analysis
    d = client.get("/api/dashboard/summary").json()
    assert d["has_data"] and d["analysis"]["id"] == aid
    assert d["health"]["quality_score"] == q["overall_score"] == full["decision"]["quality_score"]
    assert d["health"]["risk_score"] == full["decision"]["risk_score"]
    assert d["profile"]["rows"] == 302 and d["profile"]["duplicate_rows"] == 2 and d["profile"]["missing_values"] == 3
    assert d["anomalies"]["total"] == full["anomalies"]["summary"]["anomaly_count"]
    assert d["drift"]["available"] is False and d["forecast"]["available"] is False
    assert "Insufficient historical data for reliable forecasting." in d["forecast"]["message"]
    assert d["alerts"]["active"] == len(full["alerts"]) > 0 and d["insights"] and d["top_recommendations"]
    assert {r["name"] for r in d["reports"]} >= {"dataset_profile", "quality_report", "anomaly_report", "recommendations",
                                                 "drift_report", "monitoring_report", "final_analysis_report"}
    assert d["charts"]["severity_distribution"] == full["anomalies"]["summary"]["severity_distribution"]
    assert client.get("/api/alerts").json()["count"] == len(full["alerts"])
    assert client.get("/api/monitoring").json()["count"] == 1
    assert client.get("/api/trends").json()["available"] is False
    assert client.get("/api/forecast").json()["available"] is False
    assert client.get("/api/drift").json()["available"] is False


def test_reports_download_and_content(client, dirty_df):
    aid = analyze(client, upload(client, dirty_df))["analysis"]["id"]
    listing = client.get(f"/api/analysis/{aid}/reports").json()["reports"]
    assert len(listing) == 8
    for name in ["dataset_profile", "quality_report", "anomaly_report", "recommendations", "drift_report",
                 "monitoring_report", "final_analysis_report"]:
        r = client.get(f"/api/analysis/{aid}/reports/{name}")
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
        df = pd.read_csv(io.StringIO(r.text)); assert len(df) >= 1
    anomalies = pd.read_csv(io.StringIO(client.get(f"/api/analysis/{aid}/reports/anomaly_report").text))
    assert {"row", "severity", "reason", "recommended_action"} <= set(anomalies.columns) and "CRITICAL" in set(anomalies.severity)
    final = dict(pd.read_csv(io.StringIO(client.get(f"/api/analysis/{aid}/reports/final_analysis_report").text)).values)
    assert float(final["quality_score"]) > 0 and final["forecast_quality"].startswith("Not available")
    html = client.get(f"/api/analysis/{aid}/reports/full_report").text
    assert "<html" in html and "customers.csv" in html and "Final decision" in html
    assert client.get(f"/api/analysis/{aid}/reports/../../etc/passwd").status_code == 404
    assert client.get(f"/api/analysis/{aid}/reports/secrets").status_code == 404
    assert any((client.settings.report_dir / f"analysis_{aid}").glob("*.csv"))          # also written to disk


def test_remediation_workflow_via_api(client, dirty_df):
    did = upload(client, dirty_df)
    aid = analyze(client, did)["analysis"]["id"]
    original = (client.settings.upload_dir / next(p.name for p in client.settings.upload_dir.iterdir())).read_bytes()
    assert client.get(f"/api/analysis/{aid}/remediation/download").status_code == 404        # nothing yet

    prev = client.post(f"/api/analysis/{aid}/remediation/apply?dry_run=true", json={}).json()
    assert prev["dry_run"] and prev["rows_removed"] == 2
    assert list(client.settings.processed_dir.iterdir()) == []                                 # preview saves nothing

    res = client.post(f"/api/analysis/{aid}/remediation/apply", json={}).json()
    assert res["rows_before"] == 302 and res["rows_after"] == 300 and res["after"]["quality_score"] > res["before"]["quality_score"]
    dl = client.get(res["download_url"])
    cleaned = pd.read_csv(io.StringIO(dl.text))
    assert len(cleaned) == 300 and dl.headers["content-disposition"].endswith('customers_cleaned.csv"')
    assert (client.settings.upload_dir / next(p.name for p in client.settings.upload_dir.iterdir())).read_bytes() == original
    assert client.get(f"/api/analysis/{aid}/remediation").json()["applied"]["rows_after"] == 300
    assert client.post(f"/api/analysis/{aid}/remediation/apply", json={"operations": ["nope"]}).status_code == 400
    assert client.post(f"/api/analysis/{aid}/remediation/apply", json={"numeric_strategy": "median", "operations": ["impute_missing"]}).status_code == 200


def test_drift_workflow_explicit_and_automatic_reference(client):
    rng = np.random.default_rng(1)
    ref = pd.DataFrame({"x": rng.normal(0, 1, 400), "y": rng.normal(5, 1, 400), "g": rng.choice(["a", "b"], 400)})
    cur = pd.DataFrame({"x": rng.normal(2, 1, 400), "y": rng.normal(5, 1, 400), "g": rng.choice(["a", "b"], 400)})
    rid, cid = upload(client, ref, "ref.csv"), upload(client, cur, "cur.csv")
    res = analyze(client, cid, {"reference_dataset_id": rid})
    assert res["drift"]["available"] and res["drift"]["affected_features"] == ["x"] and res["drift"]["reference"]["mode"] == "explicit"
    assert client.get("/api/drift").json()["affected_features"] == ["x"]
    cmp = client.post("/api/drift/compare", json={"reference_dataset_id": rid, "current_dataset_id": cid}).json()
    assert cmp["drifted_features"] == 1
    assert client.post("/api/drift/compare", json={"reference_dataset_id": rid, "current_dataset_id": rid}).status_code == 400

    # automatic reference: second upload of the same file name compares with the first
    a1 = upload(client, ref, "orders.csv"); analyze(client, a1)
    a2 = upload(client, cur, "orders.csv")
    auto = analyze(client, a2)
    assert auto["drift"]["available"] and auto["drift"]["reference"]["mode"] == "previous_version"
    assert auto["monitoring"]["previous"] is not None
    off = analyze(client, upload(client, cur, "orders.csv"), {"auto_reference": False})
    assert off["drift"]["available"] is False


def test_monitoring_trend_and_forecast_build_up_over_runs(client):
    ids = []
    for i in range(6):                                            # same file name -> one monitored series
        df = make_df(300, seed=i)
        df.loc[: i * 8, "income"] = np.nan                       # increasingly missing data
        df.loc[: i * 3, "age"] = 500
        ids.append(analyze(client, upload(client, df, "feed.csv"))["analysis"]["id"])
        t = client.get("/api/trends").json(); f = client.get("/api/forecast").json()
        if i == 0:
            assert not t["available"] and not f["available"]
        if 1 <= i < 4:
            assert t["available"] and not f["available"] and f["message"] == "Insufficient historical data for reliable forecasting."
    t = client.get("/api/trends").json()
    assert t["points"] == 6 and t["overall_trend"] == "DECLINING"
    assert t["metrics"]["risk_score"]["trend"] == "DECLINING" and t["metrics"]["anomaly_count"]["trend"] == "DECLINING"
    assert t["metrics"]["quality_score"]["slope"] < 0                 # quality falls, though within the 'stable' tolerance
    f = client.get("/api/forecast").json()
    assert f["available"] and len(f["forecast"]["quality_score"]) == 3
    hist = client.get("/api/monitoring").json()["history"]
    assert [h["analysis_id"] for h in hist] == ids and hist[0]["quality_score"] > hist[-1]["quality_score"]
    assert {"timestamp", "dataset", "quality_score", "anomaly_count", "drifted_features", "risk_level", "decision", "status"} <= set(hist[0])
    last = client.get(f"/api/analysis/{ids[-1]}").json()
    assert last["trends"]["available"] and last["forecast"]["available"]
    assert any(a["type"] == "QUALITY_DROP" for a in last["alerts"]) or any(a["type"] == "ANOMALY_INCREASE" for a in last["alerts"]) or last["alerts"]
    d = client.get("/api/dashboard/summary").json()
    assert d["monitoring"]["trend"] == "DECLINING" and d["forecast"]["available"] and d["monitoring"]["previous_quality"] is not None


def test_unique_text_values_are_never_stored(client):
    df = make_df(60); df["email"] = [f"person{i}@secret-corp.example" for i in range(60)]
    aid = analyze(client, upload(client, df, "pii.csv"))["analysis"]["id"]
    db = database.SessionLocal()
    try:
        stored = json.dumps(db.get(AnalysisRun, aid).result)
        assert "secret-corp.example" not in stored and "person7@" not in stored
    finally:
        db.close()
    assert "secret-corp.example" not in client.get(f"/api/analysis/{aid}").text


def test_alert_acknowledge(client, dirty_df):
    analyze(client, upload(client, dirty_df))
    alerts = client.get("/api/alerts").json()["alerts"]
    assert alerts and alerts[0]["status"] == "ACTIVE"
    assert client.patch(f"/api/alerts/{alerts[0]['id']}/acknowledge").json()["status"] == "ACKNOWLEDGED"
    assert client.get("/api/alerts?status=ACTIVE").json()["count"] == len(alerts) - 1
    assert client.patch("/api/alerts/99999/acknowledge").status_code == 404
    assert client.get("/api/alerts?severity=bad").status_code == 400


def test_failed_analysis_is_reported_not_crashed(client, clean_df):
    did = upload(client, clean_df)
    (client.settings.upload_dir / next(p.name for p in client.settings.upload_dir.iterdir())).unlink()   # file vanishes
    r = client.post(f"/api/analyze/{did}?wait=true")
    assert r.status_code in (404, 422) and "no longer available" in r.json()["error"]["message"]
    aid = client.get("/api/analysis").json()["analyses"][0]["id"]
    assert client.get(f"/api/analysis/{aid}/status").json()["status"] == "FAILED"
    assert client.get(f"/api/analysis/{aid}/quality").status_code == 409


def test_user_validity_rules_via_api(client):
    df = make_df(100)
    res = analyze(client, upload(client, df, "r.csv"), {"validity_rules": {"income": [0, 40000]}})
    assert res["quality"]["validity"]["columns"]["income"]["rule_violations"] > 0
    assert res["quality"]["validity"]["rules_applied"]["income"]["source"] == "user-defined rule"


def test_excel_file_end_to_end(client, dirty_df):
    buf = io.BytesIO(); dirty_df.to_excel(buf, index=False)
    r = client.post("/api/datasets/upload", files={"file": ("book.xlsx", buf.getvalue(), "application/vnd.ms-excel")})
    res = analyze(client, r.json()["dataset"]["id"])
    assert res["quality"]["summary"]["duplicate_rows"] == 2 and res["dataset"]["file_type"] == "xlsx"


def test_unsuitable_dataset_gets_messages_not_errors(client):
    df = pd.DataFrame({"name": list("abcdefghijklmnopqrstuvwxy"), "team": list("xyzxyzxyzxyzxyzxyzxyzxyzx")})
    res = analyze(client, upload(client, df, "text_only.csv"))
    assert res["anomalies"]["statistical"]["status"] == "SKIPPED" and res["anomalies"]["machine_learning"]["status"] == "SKIPPED"
    assert "No suitable numerical" in res["anomalies"]["machine_learning"]["message"]
    assert res["anomalies"]["summary"]["anomaly_count"] == 0 and res["decision"]["risk_level"] == "LOW"
    assert any("anomaly detection" in n for n in res["decision"]["not_available"])
