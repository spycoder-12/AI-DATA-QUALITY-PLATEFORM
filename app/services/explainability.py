"""Explainable AI: turn detector evidence into plain-language explanations.

For each important anomaly we state which feature raised concern, the actual
value, the expected/normal range, the detection methods, the severity, the
reason and the supporting evidence - in words a non-technical user can follow.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.services.recommendation import feature_hint, severity_action
from app.utils.helpers import json_safe, rnd

MAX_EXPLAINED = 200


def fmt(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    value = float(value)
    if abs(value) >= 1000 and value == int(value):
        return f"{int(value):,}"
    if value == int(value):
        return str(int(value))
    return f"{value:,.4g}" if abs(value) < 1000 else f"{value:,.1f}"


def _expected_range(evidence: dict, st: Optional[dict]) -> dict:
    rule = evidence.get("rule")
    if rule:
        return {"min": rule.get("min"), "max": rule.get("max"), "source": "validity rule"}
    scale = " (log scale)" if st and st.get("transform") else ""
    if st and st["iqr"] > 0:
        return {"min": rnd(st["lower_raw"]), "max": rnd(st["upper_raw"]), "source": "IQR fences" + scale}
    if st and st["std"] > 0:
        return {"min": rnd(st["z_lower_raw"]), "max": rnd(st["z_upper_raw"]),
                "source": "mean ± 3 standard deviations" + scale}
    return {"min": None, "max": None, "source": "unavailable"}


def _range_text(rng: dict) -> str:
    lo, hi = rng.get("min"), rng.get("max")
    if lo is not None and hi is not None:
        return f"{fmt(lo)} to {fmt(hi)}"
    if hi is not None:
        return f"at most {fmt(hi)}"
    if lo is not None:
        return f"at least {fmt(lo)}"
    return "not available"


def _reason(evidence: dict, rng: dict, record: dict, st: Optional[dict]) -> str:
    f, value = evidence["feature"], evidence["value"]
    direction = evidence.get("direction") or "outside"
    z = evidence.get("z_score")
    if evidence.get("rule"):
        return (f"{f} = {fmt(value)} breaks a basic validity rule: it should be {_range_text(rng)} "
                f"({rng.get('source')}).")
    if evidence.get("ml_context_only"):
        return (f"{f} = {fmt(value)} is the most unusual value in this record"
                f"{f' (z-score {z:+.1f})' if z is not None else ''}, but on its own it is inside the "
                f"normal range. The record was flagged because the machine-learning models found its "
                f"*combination* of values unusual compared with the rest of the dataset.")
    ztxt = f" (z-score {z:+.1f})" if z is not None else ""
    return (f"{f} = {fmt(value)} is {direction} the statistically expected range "
            f"({_range_text(rng)}){ztxt}.")


def explain_records(records: List[dict], stats: Dict[str, dict], limit: int = MAX_EXPLAINED) -> List[dict]:
    explanations: List[dict] = []
    for rec in records[:limit]:
        findings = []
        for ev in rec["features"][:3]:
            st = stats.get(ev["feature"])
            rng = _expected_range(ev, st)
            methods = list(ev["methods"])
            ml = [m for m in rec["detectors_flagged"] if m not in ("IQR", "Z-Score")]
            detection = " + ".join(methods + ml) if (methods or ml) else "not flagged individually"
            support = []
            if ev.get("z_score") is not None:
                support.append(f"z-score {ev['z_score']:+.2f}")
            if ev.get("iqr_distance") is not None and ev["iqr_distance"] > 0:
                support.append(f"{ev['iqr_distance']:.1f}×IQR beyond the quartiles")
            if st:
                support.append(f"typical (median) value {fmt(st['median_raw'])}")
            findings.append({
                "feature": ev["feature"], "value": ev["value"], "expected_range": rng,
                "z_score": ev.get("z_score"), "detection": detection, "severity": ev["severity"],
                "reason": _reason(ev, rng, rec, st), "evidence": support,
            })
        top = findings[0] if findings else None
        detectors = rec["methods"]
        rule_note = " plus a validity-rule breach" if rec.get("rule_breach") else ""
        headline = (f"Row {rec['row']}: {top['feature']} = {fmt(top['value'])}" if top
                    else f"Row {rec['row']}: unusual record")
        summary = (f"Flagged by {len(rec['detectors_flagged'])} of {rec['available_detectors']} detectors"
                   f"{' (' + ', '.join(rec['detectors_flagged']) + ')' if rec['detectors_flagged'] else ''}"
                   f"{rule_note}; "
                   f"evidence level {rec['evidence_level'].lower()}, severity {rec['severity']}.")
        explanations.append(json_safe({
            "row": rec["row"], "severity": rec["severity"], "evidence_level": rec["evidence_level"],
            "support_count": rec["support_count"], "available_detectors": rec["available_detectors"],
            "detectors": detectors, "headline": headline,
            "findings": findings,
            "explanation": " ".join([top["reason"]] if top else []) + " " + summary,
            "recommended_action": (severity_action(rec["severity"]) + " "
                                   + feature_hint(top["feature"] if top else "")).strip(),
        }))
    return explanations
