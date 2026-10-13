"""Final decision engine - one deterministic dataset-health assessment.

RISK SCORE (0-100, higher = riskier) is the sum of capped component points:

  component          max  rule
  ----------------   ---  ---------------------------------------------------
  quality score       35  <50: 35 | <60: 30 | <75: 22 | <90: 12 | <95: 5 | else 0
  data issues         15  per issue (missing / duplicate / invalid rows):
                          6 / 4 / 2 points at (>=40 / 20 / 5 %), (>=30 / 15 / 5 %),
                          (>=10 / 5 / 1 %) respectively
  anomalies           25  max(severity points, rate points) (+7 if >=5 critical):
                          severity CRITICAL 18 | HIGH 12 | MEDIUM 6 | LOW 2
                          rate     >=10% 15 | >=5% 10 | >=1% 5 | >0 2
  drift               15  significant 15 | moderate 8   (only with reference data)
  trend                5  declining history
  forecast             5  forecast risk >=40: 5 | >=20: 3 (only when forecast exists)
  alerts               5  critical alert 5 | high 3 | medium 1

Components that cannot be computed contribute 0 and are listed under
``not_available`` - they are never guessed.

FLOORS keep outputs consistent (no "healthy" dataset with critical findings):
  * any CRITICAL anomaly            -> risk score >= 20 (at least MEDIUM)
  * quality score < 50              -> risk score >= 40 (at least HIGH)
  * >= 40 % of cells missing        -> risk score >= 40 (at least HIGH)

RISK LEVEL: >=70 CRITICAL, >=40 HIGH, >=20 MEDIUM, else LOW.
STATUS / PRIORITY / DECISION are all derived from the risk level, so no two
modules can disagree.
"""
from __future__ import annotations

from typing import Dict, List

from app.config import AnalysisConfig
from app.services.severity import risk_level_from_score, severity_rank
from app.utils.helpers import json_safe, rnd

STATUS = {"LOW": "HEALTHY", "MEDIUM": "ATTENTION REQUIRED", "HIGH": "AT RISK", "CRITICAL": "CRITICAL"}
PRIORITY = {"LOW": "P4 - Routine", "MEDIUM": "P3 - Planned", "HIGH": "P2 - Urgent", "CRITICAL": "P1 - Immediate"}
DECISION = {"LOW": "DATASET HEALTHY", "MEDIUM": "REVIEW BEFORE PRODUCTION USE",
            "HIGH": "REMEDIATION RECOMMENDED", "CRITICAL": "IMMEDIATE REMEDIATION REQUIRED"}
ACTION = {
    "LOW": "No urgent action. Continue routine monitoring.",
    "MEDIUM": "Review the flagged issues and apply the recommended fixes before relying on this dataset.",
    "HIGH": "Do not use for critical decisions until the high-severity issues are remediated.",
    "CRITICAL": "Stop using this dataset for decisions or model training until critical issues are resolved.",
}


def _quality_points(score: float) -> int:
    return 35 if score < 50 else 30 if score < 60 else 22 if score < 75 else 12 if score < 90 else 5 if score < 95 else 0


def _tier(value: float, tiers) -> int:
    for threshold, pts in tiers:
        if value >= threshold:
            return pts
    return 0


def decide(cfg: AnalysisConfig, quality: dict, anomaly_summary: dict, drift: dict, trends: dict,
           forecast: dict, alerts: List[dict], remediation_plan: List[dict]) -> dict:
    q = quality["summary"]
    components: List[dict] = []
    not_available: List[str] = []

    def add(name: str, pts: int, max_pts: int, reason: str) -> None:
        components.append({"name": name, "points": pts, "max_points": max_pts, "reason": reason})

    score = quality["overall_score"]
    add("Quality score", _quality_points(score), 35, f"quality score {score:.1f}/100 ({quality['grade']})")

    issue = (_tier(q["missing_pct"], [(40, 6), (20, 4), (5, 2)])
             + _tier(q["duplicate_pct"], [(30, 6), (15, 4), (5, 2)])
             + _tier(q["invalid_pct"], [(10, 6), (5, 4), (1, 2)]))
    add("Data issues", min(15, issue), 15,
        f"missing {q['missing_pct']}% of cells, duplicates {q['duplicate_pct']}%, invalid rows {q['invalid_pct']}%")

    sev = anomaly_summary.get("severity_distribution", {})
    present = [lvl for lvl in ("CRITICAL", "HIGH", "MEDIUM", "LOW") if sev.get(lvl)]
    sev_pts = {"CRITICAL": 18, "HIGH": 12, "MEDIUM": 6, "LOW": 2}.get(present[0], 0) if present else 0
    rate = anomaly_summary.get("anomaly_pct") or 0
    rate_pts = 15 if rate >= 10 else 10 if rate >= 5 else 5 if rate >= 1 else 2 if rate > 0 else 0
    a_pts = min(25, max(sev_pts, rate_pts) + (7 if anomaly_summary.get("critical_count", 0) >= 5 else 0))
    if anomaly_summary.get("detectors_run"):
        add("Anomalies", a_pts, 25,
            f"{anomaly_summary.get('anomaly_count', 0)} anomalous records ({rate}%), "
            f"{anomaly_summary.get('critical_count', 0)} critical, {anomaly_summary.get('high_count', 0)} high")
    else:
        add("Anomalies", 0, 25, "no anomaly detector could run")
        not_available.append("anomaly detection (no suitable numerical features)")

    if drift.get("available"):
        d_pts = 15 if drift["overall_status"] == "SIGNIFICANT DRIFT" else 8 if drift["overall_status"] == "MODERATE DRIFT" else 0
        add("Data drift", d_pts, 15, f"{drift['drifted_features']} of {drift['features_evaluated']} "
                                     f"features drifted ({drift['overall_status'].lower()})")
    else:
        add("Data drift", 0, 15, "no reference dataset / insufficient data")
        not_available.append("drift (no reference dataset)")

    if trends.get("available"):
        add("Historical trend", 5 if trends["overall_trend"] == "DECLINING" else 0, 5,
            f"trend {trends['overall_trend'].lower()}")
    else:
        add("Historical trend", 0, 5, "insufficient history")
        not_available.append("trend (fewer than 2 analyses)")

    if forecast.get("available") and forecast.get("forecast", {}).get("risk_score"):
        fr = forecast["forecast"]["risk_score"][-1]["value"]
        add("Forecast", 5 if fr >= 40 else 3 if fr >= 20 else 0, 5, f"forecast risk {fr}")
    else:
        add("Forecast", 0, 5, "insufficient history")
        not_available.append("forecast (insufficient historical data)")

    levels = [a["severity"] for a in alerts]
    al_pts = 5 if "CRITICAL" in levels else 3 if "HIGH" in levels else 1 if "MEDIUM" in levels else 0
    add("Alerts", al_pts, 5, f"{len(alerts)} active alert(s)")

    raw = float(sum(c["points"] for c in components))
    risk = min(100.0, raw)
    floors: List[str] = []
    if anomaly_summary.get("critical_count", 0) > 0 and risk < cfg.risk_medium:
        risk = cfg.risk_medium
        floors.append("critical anomalies present → risk raised to at least MEDIUM")
    if score < 50 and risk < cfg.risk_high:
        risk = cfg.risk_high
        floors.append("quality score below 50 → risk raised to at least HIGH")
    if q["missing_pct"] >= 40 and risk < cfg.risk_high:
        risk = cfg.risk_high
        floors.append("40% or more of cells missing → risk raised to at least HIGH")

    level = risk_level_from_score(risk, cfg.risk_medium, cfg.risk_high, cfg.risk_critical)
    drivers = [c for c in sorted(components, key=lambda c: -c["points"]) if c["points"] > 0][:3]
    safe_fixes = [p for p in remediation_plan if p["safe"] and p["affected"] and p["operation"] != "standardize_column_names"]
    automation = (f"{len(safe_fixes)} safe automated fix(es) available (" +
                  ", ".join(p["label"].lower() for p in safe_fixes) + ")."
                  if safe_fixes else "No safe automated fixes needed." if level == "LOW"
                  else "No safe automated fixes available; manual review required.")
    return json_safe({
        "risk_score": rnd(risk, 1), "raw_points": raw, "risk_level": level,
        "overall_status": STATUS[level], "priority": PRIORITY[level], "decision": DECISION[level],
        "recommended_action": ACTION[level], "automation": automation,
        "quality_score": score, "quality_grade": quality["grade"],
        "components": components, "floors_applied": floors, "not_available": not_available,
        "main_drivers": [f"{c['name']}: {c['reason']}" for c in drivers],
        "framework": "Additive risk points with consistency floors; see documentation in README.",
    })


def build_insights(quality: dict, anomaly_summary: dict, drift: dict, trends: dict,
                   decision: dict, kinds: Dict[str, str]) -> List[str]:
    """Short plain-language insights for the dashboard (all derived from results)."""
    out: List[str] = []
    cq = sorted(quality["column_quality"], key=lambda c: c["score"])
    if cq and cq[0]["score"] < 90:
        c = cq[0]
        out.append(f"Major quality issue detected in '{c['column']}' ({', '.join(c['issues'])}).")
    for col, info in sorted(quality["missing"]["columns"].items(), key=lambda kv: -kv[1]["pct"])[:1]:
        if info["pct"] >= 5:
            out.append(f"Missing values are concentrated in '{col}' ({info['pct']}% empty).")
    if quality["summary"]["duplicate_rows"]:
        out.append(f"{quality['summary']['duplicate_rows']} duplicate record(s) inflate the row count.")
    if quality["summary"]["invalid_rows"]:
        out.append(f"{quality['summary']['invalid_rows']} record(s) contain impossible or invalid values.")
    if anomaly_summary.get("anomaly_count"):
        top = next(iter(anomaly_summary.get("affected_features", {})), None)
        out.append(f"{anomaly_summary['anomaly_count']} anomalous record(s) found"
                   f"{f', most driven by {top!r}' if top else ''}; "
                   f"{anomaly_summary.get('critical_count', 0)} critical.")
    if drift.get("available") and drift.get("drifted_features"):
        out.append(f"{drift['drifted_features']} feature(s) show distribution drift versus the reference data.")
    if trends.get("available") and trends["overall_trend"] != "STABLE":
        out.append(f"Data quality is {trends['overall_trend'].lower()} across recent analyses.")
    if not out:
        out.append("No significant data-quality problems were detected.")
    return out
