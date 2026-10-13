"""Unified reports generated from the stored analysis result.

Seven CSV files (one per concern) plus a
self-contained HTML report. Reports are rendered from the saved result, so
downloading them never re-runs the analysis.
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import Dict, List

import pandas as pd

from app.utils.helpers import NOT_AVAILABLE

CSV_REPORTS = ["dataset_profile", "quality_report", "anomaly_report", "recommendations",
               "drift_report", "monitoring_report", "final_analysis_report"]
REPORT_NAMES = CSV_REPORTS + ["full_report"]


def _profile_frame(r: dict) -> pd.DataFrame:
    rows = []
    for c in r["profile"]["column_profiles"]:
        rows.append({k: c.get(k) for k in ("name", "dtype", "kind", "missing", "missing_pct", "unique",
                                           "is_constant", "min", "max", "mean", "median", "std", "q1", "q3")})
    return pd.DataFrame(rows).rename(columns={"name": "column"})


def _quality_frame(r: dict) -> pd.DataFrame:
    q = r["quality"]
    rows = [{"level": "overall", "item": "quality_score", "score": q["overall_score"],
             "severity": None, "detail": f"{q['grade']} — {q['formula']}"}]
    for name, d in q["dimensions"].items():
        rows.append({"level": "dimension", "item": name, "score": d["score"], "severity": None,
                     "detail": f"weight {d['weight']}; {d['detail']}"})
    for c in q["column_quality"]:
        rows.append({"level": "column", "item": c["column"], "score": c["score"], "severity": None,
                     "detail": "; ".join(c["issues"]) or "no issues"})
    for f in q["findings"]:
        rows.append({"level": "finding", "item": f["type"] + (f":{f['column']}" if f.get("column") else ""),
                     "score": None, "severity": f["severity"], "detail": f["message"]})
    return pd.DataFrame(rows)


def _anomaly_frame(r: dict) -> pd.DataFrame:
    explained = {e["row"]: e for e in r["explanations"]}
    rows = []
    for a in r["anomalies"]["records"]:
        e = explained.get(a["row"], {})
        f = (e.get("findings") or [{}])[0]
        rng = f.get("expected_range") or {}
        rows.append({
            "row": a["row"], "severity": a["severity"], "evidence_level": a["evidence_level"],
            "detectors_supporting": f"{a['support_count']} of {a['available_detectors']}",
            "detectors": ", ".join(a["detectors"]), "primary_feature": a["primary_feature"],
            "value": a.get("primary_value"), "expected_min": rng.get("min"), "expected_max": rng.get("max"),
            "reason": f.get("reason"), "recommended_action": e.get("recommended_action")})
    return pd.DataFrame(rows, columns=["row", "severity", "evidence_level", "detectors_supporting", "detectors",
                                       "primary_feature", "value", "expected_min", "expected_max", "reason",
                                       "recommended_action"])


def _drift_frame(r: dict) -> pd.DataFrame:
    d = r["drift"]
    if not d.get("available"):
        return pd.DataFrame([{"feature": None, "status": d.get("overall_status", "NOT AVAILABLE"),
                              "note": d.get("message", NOT_AVAILABLE)}])
    rows = []
    for f in d["features"]:
        rows.append({"feature": f["feature"], "type": f["type"], "status": f["status"], "risk": f["risk"],
                     "psi": f["psi"], "test": f["test"], "test_statistic": f["statistic"], "p_value": f["p_value"],
                     "reference_n": f["reference_n"], "current_n": f["current_n"],
                     "reference_mean": (f.get("reference_summary") or {}).get("mean"),
                     "current_mean": (f.get("current_summary") or {}).get("mean"),
                     "mean_change_pct": f.get("mean_change_pct"), "note": f.get("note")})
    return pd.DataFrame(rows)


def _final_frame(r: dict, history: List[dict]) -> pd.DataFrame:
    q, d, a, dr = r["quality"], r["decision"], r["anomalies"]["summary"], r["drift"]
    sev = a.get("severity_distribution", {})
    fc = r["forecast"]
    pairs = [
        ("dataset", r["dataset"]["name"]), ("generated_at", r["generated_at"]),
        ("rows", q["summary"]["rows"]), ("columns", q["summary"]["columns"]),
        ("quality_score", q["overall_score"]), ("quality_grade", q["grade"]),
        ("missing_values", q["summary"]["missing_values"]), ("duplicate_rows", q["summary"]["duplicate_rows"]),
        ("invalid_rows", q["summary"]["invalid_rows"]),
        ("anomaly_count", a["anomaly_count"]), ("anomaly_pct", a["anomaly_pct"]),
        ("anomalies_critical", sev.get("CRITICAL")), ("anomalies_high", sev.get("HIGH")),
        ("anomalies_medium", sev.get("MEDIUM")), ("anomalies_low", sev.get("LOW")),
        ("drifted_features", dr.get("drifted_features") if dr.get("available") else NOT_AVAILABLE),
        ("drift_status", dr.get("overall_status", NOT_AVAILABLE)),
        ("active_alerts", len(r["alerts"])), ("trend", r["trends"].get("overall_trend")),
        ("forecast_quality", fc["forecast"]["quality_score"][-1]["value"] if fc.get("available") else NOT_AVAILABLE),
        ("forecast_risk", fc["forecast"]["risk_score"][-1]["value"]
         if fc.get("available") and "risk_score" in fc["forecast"] else NOT_AVAILABLE),
        ("risk_score", d["risk_score"]), ("risk_level", d["risk_level"]), ("overall_status", d["overall_status"]),
        ("priority", d["priority"]), ("decision", d["decision"]), ("recommended_action", d["recommended_action"]),
    ]
    return pd.DataFrame(pairs, columns=["metric", "value"])


def build_frames(result: dict, history: List[dict]) -> Dict[str, pd.DataFrame]:
    return {
        "dataset_profile": _profile_frame(result),
        "quality_report": _quality_frame(result),
        "anomaly_report": _anomaly_frame(result),
        "recommendations": pd.DataFrame(result["recommendations"]).drop(columns=["id"], errors="ignore"),
        "drift_report": _drift_frame(result),
        "monitoring_report": pd.DataFrame(history),
        "final_analysis_report": _final_frame(result, history),
    }


def _table(headers: List[str], rows: List[list]) -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(str(c if c is not None else ''))}</td>" for c in row) + "</tr>"
                   for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def build_html(result: dict, history: List[dict]) -> str:
    q, d, a = result["quality"], result["decision"], result["anomalies"]["summary"]
    e = html.escape
    sev = a.get("severity_distribution", {})
    parts = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Data Quality Report — {e(result['dataset']['name'])}</title>
<style>body{{font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:980px;margin:2rem auto;padding:0 1rem;color:#1b2430}}
h1{{margin-bottom:.2rem}}h2{{border-bottom:2px solid #e3e8ef;padding-bottom:.3rem;margin-top:2rem}}
table{{border-collapse:collapse;width:100%;font-size:.9rem;margin:.6rem 0}}th,td{{border:1px solid #dde3ec;padding:.4rem .6rem;text-align:left;vertical-align:top}}
th{{background:#f3f6fb}}.pill{{display:inline-block;padding:.15rem .6rem;border-radius:99px;font-weight:600;background:#eef2ff}}
.muted{{color:#5d6b82}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem}}.card{{border:1px solid #dde3ec;border-radius:10px;padding:.8rem}}
.card b{{display:block;font-size:1.5rem}}</style></head><body>
<h1>AI Data Quality Intelligence Report</h1>
<p class="muted">Dataset: <b>{e(result['dataset']['name'])}</b> · Generated {e(result['generated_at'])} · {q['summary']['rows']:,} rows × {q['summary']['columns']} columns</p>
<div class="grid">
<div class="card">Quality score<b>{q['overall_score']}</b>{e(q['grade'])}</div>
<div class="card">Risk score<b>{d['risk_score']}</b>{e(d['risk_level'])}</div>
<div class="card">Anomalies<b>{a['anomaly_count']}</b>{sev.get('CRITICAL', 0)} critical · {sev.get('HIGH', 0)} high</div>
<div class="card">Alerts<b>{len(result['alerts'])}</b>active</div></div>
<h2>Final decision</h2><p><span class="pill">{e(d['overall_status'])}</span> {e(d['decision'])} · {e(d['priority'])}</p>
<p>{e(d['recommended_action'])}</p><p class="muted">{e(d['automation'])}</p>
<h3>Insights</h3><ul>{''.join(f'<li>{e(i)}</li>' for i in result['insights'])}</ul>
<h2>Quality score breakdown</h2><p class="muted">{e(q['formula'])}</p>"""]
    parts.append(_table(["Dimension", "Score", "Weight", "Detail"],
                        [[k, v["score"], v["weight"], v["detail"]] for k, v in q["dimensions"].items()]))
    parts.append("<h2>Quality findings</h2>" + (_table(["Severity", "Finding"], [[f["severity"], f["message"]] for f in q["findings"]])
                                                 if q["findings"] else "<p>No findings.</p>"))
    expl = result["explanations"][:20]
    parts.append("<h2>Top anomalies (evidence for review, not proof of error)</h2>" + (_table(
        ["Row", "Severity", "Evidence", "Explanation", "Action"],
        [[x["row"], x["severity"], f"{x['support_count']}/{x['available_detectors']} detectors · {x['evidence_level']}",
          x["explanation"], x["recommended_action"]] for x in expl]) if expl else "<p>No anomalies reported.</p>"))
    parts.append("<h2>Recommendations</h2>" + _table(["Priority", "Category", "Target", "Recommendation"],
                 [[r["priority"], r["category"], r["target"], f"{r['finding']} {r['recommendation']}"]
                  for r in result["recommendations"]]))
    dr = result["drift"]
    parts.append("<h2>Data drift</h2>" + (_table(["Feature", "Status", "PSI", "p-value"],
                 [[f["feature"], f["status"], f["psi"], f["p_value"]] for f in dr["features"]]) if dr.get("available")
                 else f"<p>{e(dr.get('message', NOT_AVAILABLE))}</p>"))
    parts.append("<h2>Alerts</h2>" + (_table(["Severity", "Type", "Message", "Action"],
                 [[x["severity"], x["type"], x["message"], x["recommended_action"]] for x in result["alerts"]])
                 if result["alerts"] else "<p>No active alerts.</p>"))
    fc = result["forecast"]
    parts.append(f"<h2>Trend &amp; forecast</h2><p>Trend: <b>{e(str(result['trends'].get('overall_trend')))}</b>. "
                 f"{'Forecast quality (next 3 runs): ' + ', '.join(str(p['value']) for p in fc['forecast']['quality_score']) if fc.get('available') else e(fc.get('message', NOT_AVAILABLE))}</p>")
    parts.append("<h2>Risk components</h2>" + _table(["Component", "Points", "Max", "Reason"],
                 [[c["name"], c["points"], c["max_points"], c["reason"]] for c in result["decision"]["components"]]))
    parts.append("</body></html>")
    return "".join(parts)


def write_reports(result: dict, history: List[dict], directory: Path) -> List[str]:
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, frame in build_frames(result, history).items():
        frame.to_csv(directory / f"{name}.csv", index=False)
        written.append(f"{name}.csv")
    (directory / "full_report.html").write_text(build_html(result, history), encoding="utf-8")
    written.append("full_report.html")
    return written
