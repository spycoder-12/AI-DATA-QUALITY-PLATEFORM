"""AI recommendation engine.

Every recommendation is generated from a *detected* problem (quality finding,
anomaly cluster, drifted feature, trend) and carries the evidence that
triggered it. Nothing here is generic filler: if nothing is wrong the engine
says so.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.utils.helpers import json_safe
from app.services.severity import severity_rank

_SEVERITY_ACTION = {
    "CRITICAL": "Investigate this record immediately and verify the source data before using it.",
    "HIGH": "Review this record manually and validate it against the original source.",
    "MEDIUM": "Perform a secondary validation before relying on this record.",
    "LOW": "Keep an eye on this record for repeated unusual behaviour.",
}
_PRIORITY = {"CRITICAL": "P1", "HIGH": "P2", "MEDIUM": "P3", "LOW": "P4"}


def severity_action(severity: str) -> str:
    return _SEVERITY_ACTION.get(severity, _SEVERITY_ACTION["LOW"])


def feature_hint(feature: str) -> str:
    """Domain hint derived from the feature name (kept from the original engine)."""
    name = (feature or "").lower()
    tokens = set(name.split("_"))
    if tokens & {"income", "salary", "price", "revenue", "cost", "amount", "wage"}:
        return "Check that the amount was entered correctly and matches the original financial source."
    if "score" in tokens or "rating" in tokens:
        return "Verify the value against the original assessment or scoring record."
    if tokens & {"hours", "minutes", "duration", "seconds"}:
        return "Check that the recorded duration is realistic and in the expected unit."
    if "age" in tokens:
        return "Verify the person's age and look for data-entry or unit errors."
    if not name:
        return ""
    return "Check the original source and validate the value against business rules."


def _rec(category: str, severity: str, target: str, finding: str, action: str,
         evidence: str = "", fix: Optional[str] = None) -> dict:
    return {"category": category, "severity": severity, "priority": _PRIORITY.get(severity, "P4"),
            "target": target, "finding": finding, "recommendation": action,
            "evidence": evidence, "automated_fix": fix}


def generate_recommendations(quality: dict, anomaly_summary: dict, explanations: List[dict],
                             profile: dict, drift: dict, trends: dict, forecast: dict,
                             ml_public: dict, kinds: Dict[str, str]) -> List[dict]:
    recs: List[dict] = []
    rows = quality["summary"]["rows"]

    # ------------------------------------------------------------ data volume
    if rows < 20:
        recs.append(_rec("Data volume", "MEDIUM", "dataset",
                         f"Only {rows} row(s) available.",
                         "Collect more records before drawing conclusions; machine-learning "
                         "anomaly detection needs at least 20 rows.",
                         f"rows = {rows}"))
    elif ml_public.get("status") == "SKIPPED":
        recs.append(_rec("Data volume", "LOW", "dataset", ml_public.get("message", "ML detection skipped."),
                         "Add numeric measurement columns if you want machine-learning anomaly detection.",
                         ml_public.get("message", "")))

    # --------------------------------------------------------------- missing
    low_missing = []
    for finding in quality["findings"]:
        if finding["type"] != "missing_values":
            continue
        col, pct, sev = finding["column"], finding["pct"], finding["severity"]
        kind = kinds.get(col, "categorical")
        if severity_rank(sev) <= severity_rank("LOW"):
            low_missing.append(f"{col} ({pct}%)")
            continue
        if pct >= 50:
            action = (f"'{col}' is mostly empty. Consider dropping the column or recollecting the "
                      f"data; imputing it would mostly invent values.")
        elif kind == "numeric":
            action = (f"Consider median imputation for '{col}' (robust to extreme values) or investigate why "
                      f"the values are missing.")
        else:
            action = (f"Consider mode imputation or an explicit 'Unknown' category for '{col}', "
                      f"and check the data-collection step that leaves it blank.")
        recs.append(_rec("Missing values", sev, col, finding["message"], action,
                         f"{finding['count']} missing ({pct}%)", "impute_missing"))
    if low_missing:
        recs.append(_rec("Missing values", "LOW", ", ".join(c.split(" ")[0] for c in low_missing[:10]),
                         "Small amounts of missing data in: " + ", ".join(low_missing[:10]) + ".",
                         "Review affected rows; simple median (numeric) or mode (categorical) imputation "
                         "is usually adequate at these levels.", "", "impute_missing"))

    # ------------------------------------------------------------ duplicates
    dup = quality["duplicates"]
    if dup["count"] > 0:
        recs.append(_rec("Duplicates", dup["severity"], "dataset",
                         f"{dup['count']} exact duplicate rows ({dup['pct']}%).",
                         "Review the duplicate identifiers to confirm they are true duplicates, then "
                         "remove them (a safe automated fix is available).",
                         f"example rows: {dup['sample_rows'][:5]}", "remove_duplicates"))

    # ------------------------------------------------------- invalid values
    for col, detail in quality["validity"]["columns"].items():
        sev = next((f["severity"] for f in quality["findings"]
                    if f["type"] == "invalid_values" and f["column"] == col), "MEDIUM")
        if detail["rule_violations"]:
            recs.append(_rec("Invalid values", sev, col,
                             f"{detail['rule_violations']} value(s) in '{col}' break the valid range "
                             f"({detail['rule']['source']}).",
                             "Investigate the source data and validate business rules. Do not auto-correct: "
                             "these may be unit errors or typos that need a human decision.",
                             "; ".join(f"row {e['row']} = {e['value']}" for e in detail["examples"][:3])))
        if detail["datatype_problems"]:
            recs.append(_rec("Invalid values", sev, col,
                             f"'{col}' is numeric but {detail['datatype_problems']} value(s) are text "
                             f"(e.g. {', '.join(map(repr, detail['datatype_examples'][:3]))}).",
                             "Enforce a numeric type at the source and correct or remove the text tokens.",
                             "datatype problem"))
        if detail["not_allowed"]:
            recs.append(_rec("Invalid values", sev, col,
                             f"{detail['not_allowed']} value(s) in '{col}' are not in the approved list.",
                             "Standardize against the approved category list.",
                             ", ".join(map(repr, detail.get("examples_not_allowed", [])[:5]))))
        if detail["infinite"]:
            recs.append(_rec("Invalid values", sev, col, f"'{col}' contains infinite values.",
                             "Replace infinite values with missing or correct the calculation that produced them."))

    # ------------------------------------------------------- consistency
    for col, detail in quality["consistency"]["columns"].items():
        sev = next((f["severity"] for f in quality["findings"]
                    if f["type"] == "inconsistent_values" and f["column"] == col), "LOW")
        if detail["variant_groups"]:
            example = detail["variant_groups"][0]["variants"]
            recs.append(_rec("Consistency", sev, col,
                             f"Category values in '{col}' are written inconsistently.",
                             "Standardize spelling and case against an approved category list "
                             "(a safe automated fix is available).",
                             "e.g. " + ", ".join(f"{k!r}×{v}" for k, v in list(example.items())[:4]),
                             "normalize_categories"))
        if detail["whitespace_issues"]:
            recs.append(_rec("Consistency", sev, col,
                             f"{detail['whitespace_issues']} value(s) in '{col}' have leading/trailing spaces.",
                             "Trim whitespace at ingestion (a safe automated fix is available).",
                             "", "trim_whitespace"))
    for col, items in quality["consistency"]["suspicious_categories"].items():
        recs.append(_rec("Consistency", "LOW", col,
                         f"Rare value(s) in '{col}': " + ", ".join(repr(i["value"]) for i in items[:5]) + ".",
                         "Check these against the approved category list; they may be data-entry errors "
                         "or legitimate rare categories.",
                         "; ".join(f"{i['value']!r}×{i['count']} (rows {i['rows'][:3]})" for i in items[:3])))

    # ------------------------------------------------------------- structure
    const = quality["summary"]["constant_columns"]
    if const and rows > 1:
        recs.append(_rec("Structure", "LOW", ", ".join(const[:8]),
                         f"{len(const)} constant column(s) hold a single value.",
                         "Remove them from analysis and machine-learning features; they carry no information.",
                         ", ".join(const[:8])))

    # -------------------------------------------------------------- anomalies
    if anomaly_summary.get("anomaly_count", 0) > 0:
        by_feature: Dict[str, dict] = {}
        for exp in explanations:
            if not exp["findings"]:
                continue
            f = exp["findings"][0]["feature"]
            slot = by_feature.setdefault(f, {"count": 0, "critical": 0, "high": 0, "rows": [], "sev": "LOW"})
            slot["count"] += 1
            slot["critical"] += exp["severity"] == "CRITICAL"
            slot["high"] += exp["severity"] == "HIGH"
            slot["rows"].append(exp["row"])
            if severity_rank(exp["severity"]) > severity_rank(slot["sev"]):
                slot["sev"] = exp["severity"]
        ranked = sorted(by_feature.items(), key=lambda kv: (-severity_rank(kv[1]["sev"]), -kv[1]["count"]))
        for feature, slot in ranked[:5]:
            extra = []
            if slot["critical"]:
                extra.append(f"{slot['critical']} critical")
            if slot["high"]:
                extra.append(f"{slot['high']} high")
            recs.append(_rec("Anomalies", slot["sev"], feature,
                             f"{slot['count']} anomalous record(s) driven by '{feature}'"
                             f"{' (' + ', '.join(extra) + ')' if extra else ''}.",
                             ("Investigate the source data and validate business rules. "
                              + feature_hint(feature)).strip(),
                             f"rows {slot['rows'][:5]}"))
        if anomaly_summary.get("critical_count", 0) > 0:
            recs.append(_rec("Anomalies", "CRITICAL", "dataset",
                             f"{anomaly_summary['critical_count']} critical anomalous record(s) detected.",
                             "Do not use these records for reporting or model training until they are verified.",
                             "see AI Explanations"))

    # ----------------------------------------------------------------- drift
    if drift.get("available"):
        drifted = [f for f in drift["features"] if f["drifted"]]
        if drifted:
            worst = max(drifted, key=lambda f: severity_rank(f["risk"]))
            recs.append(_rec("Data drift", worst["risk"], ", ".join(f["feature"] for f in drifted[:8]),
                             f"{len(drifted)} feature(s) show distribution drift versus the reference data.",
                             "Investigate changes in upstream data generation (new source, schema, unit or "
                             "population change) and review the drifted features before retraining models.",
                             "; ".join(f"{f['feature']} PSI={f['psi']}" for f in drifted[:4])))

    # ------------------------------------------------------- trend / forecast
    if trends.get("available") and trends.get("overall_trend") == "DECLINING":
        recs.append(_rec("Monitoring", "MEDIUM", "dataset",
                         "Data quality is declining over recent analyses.",
                         "Increase monitoring frequency and look for a recurring upstream cause.",
                         f"quality trend: {trends['metrics']['quality_score']['trend']}"))
    if forecast.get("available") and forecast.get("forecast_trend") == "DECLINING":
        recs.append(_rec("Monitoring", "MEDIUM", "dataset",
                         "Forecast indicates further quality decline.",
                         "Address the leading quality issues now to prevent the projected decline.",
                         f"forecast quality: {forecast['forecast']['quality_score'][-1]['value']}"))

    if not recs:
        recs.append(_rec("Overall", "LOW", "dataset", "No data-quality problems were detected.",
                         "No action required. Continue routine monitoring.", ""))
    recs.sort(key=lambda r: -severity_rank(r["severity"]))
    for i, r in enumerate(recs, start=1):
        r["id"] = i
    return json_safe(recs)
