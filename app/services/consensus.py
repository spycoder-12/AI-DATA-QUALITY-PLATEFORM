"""Ensemble / consensus anomaly analysis.

Detectors that can vote: IQR, Z-Score, Isolation Forest, Local Outlier Factor,
One-Class SVM (only those that actually ran). A validity-rule breach is
additional *evidence* but is not counted as a model vote.

A record is REPORTED as an anomaly when at least one of these holds:
  * it breaches a validity rule (e.g. age 185 outside 0-120);
  * >= ``min_votes`` detectors flag it (default 2);
  * a single detector flags it but the deviation is extreme (severity >= HIGH).
Records flagged by exactly one detector with only mild deviation are counted as
"weak signals" and kept out of the anomaly list - they are common in skewed
data and would otherwise flood users with noise.

Wording is evidence-based: STRONG / MODERATE / WEAK evidence. The platform
never states that a record is *definitely* wrong.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from app.config import AnalysisConfig
from app.services.anomaly import DetectorResult, iqr_distance, zscore_of
from app.services.severity import (evidence_level, feature_severity, record_severity,
                                   severity_rank)
from app.utils.helpers import SEVERITY_ORDER, json_safe, rnd, row_number

MAX_REPORTED = 1000


def build_consensus(df: pd.DataFrame, detectors: List[DetectorResult], stats: Dict[str, dict],
                    features: List[str], rule_rows: Dict[str, dict],
                    cfg: AnalysisConfig) -> Tuple[List[dict], dict]:
    n = len(df)
    available = [d for d in detectors if d.ok]
    unavailable = [{"model": d.name, "status": d.status, "message": d.message}
                   for d in detectors if not d.ok]
    names = [d.name for d in available]
    min_votes = max(1, min(cfg.min_votes, len(available))) if available else 1

    # ---- per-detector row votes
    if available:
        votes = pd.DataFrame({d.name: d.row_flags.reindex(df.index).fillna(False) for d in available})
        support = votes.sum(axis=1)
    else:
        votes, support = pd.DataFrame(index=df.index), pd.Series(0, index=df.index)

    rule_by_row: Dict[Any, List[str]] = defaultdict(list)
    for feature, info in rule_rows.items():
        for idx in info["indices"]:
            rule_by_row[idx].append(feature)

    # ---- feature-level statistical evidence, indexed by row
    stat_by_row: Dict[Any, Dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for d in available:
        if d.kind != "statistical":
            continue
        for feature, mask in d.feature_masks.items():
            for idx in mask.index[mask.values]:
                stat_by_row[idx][feature].add(d.name)

    candidates = set(support.index[support > 0]) | set(rule_by_row.keys())

    # z-matrix used only to describe ML-only records
    zmat = pd.DataFrame({f: (stats[f]["values"] - stats[f]["mean"]) / stats[f]["std"]
                         for f in features if f in stats and stats[f]["std"] > 0})

    records: List[dict] = []
    for idx in candidates:
        sup = int(support.get(idx, 0))
        flagged_by = [c for c in names if bool(votes.at[idx, c])] if names else []
        feat_evidence: List[dict] = []
        touched = set(stat_by_row.get(idx, {}).keys()) | set(rule_by_row.get(idx, []))
        for f in touched:
            st = stats.get(f)
            value = float(st["raw"].at[idx]) if st is not None else float(pd.to_numeric(df.at[idx, f], errors="coerce"))
            analysis_value = float(st["values"].at[idx]) if st is not None else value
            methods = sorted(stat_by_row.get(idx, {}).get(f, set()), key=lambda m: ["IQR", "Z-Score"].index(m))
            rule_info = rule_rows.get(f) if f in rule_by_row.get(idx, []) else None
            excess = rule_info["excess"].get(idx) if rule_info else None
            z = zscore_of(analysis_value, st) if st else None
            dist = iqr_distance(analysis_value, st) if st else None
            if rule_info:
                methods = methods + ["Validity rule"]
            sev = feature_severity(z=z, iqr_distance=dist, rule_breached=bool(rule_info),
                                   rule_excess_ratio=excess, stat_flagged=bool(methods) and methods != ["Validity rule"])
            feat_evidence.append({
                "feature": f, "value": value, "z_score": rnd(z, 3), "iqr_distance": rnd(dist, 3),
                "methods": methods, "severity": sev, "rule": rule_info["rule"] if rule_info else None,
                "direction": ("above" if value > st["median_raw"] else "below") if st else None,
                "ml_context_only": False})
        # ML-only record: describe the most unusual feature so the user has something to look at
        if not feat_evidence and idx in zmat.index and not zmat.loc[idx].dropna().empty:
            row_z = zmat.loc[idx].dropna()
            f = row_z.abs().idxmax()
            st = stats[f]
            value = float(st["raw"].at[idx])
            feat_evidence.append({
                "feature": f, "value": value, "z_score": rnd(row_z[f], 3),
                "iqr_distance": rnd(iqr_distance(float(st["values"].at[idx]), st), 3), "methods": [],
                "severity": "LOW", "rule": None, "direction": "above" if value > st["median_raw"] else "below",
                "ml_context_only": True})
        feat_evidence.sort(key=lambda e: (-severity_rank(e["severity"]), -abs(e["z_score"] or 0)))
        rule_breach = idx in rule_by_row
        methods_all = flagged_by + (["Validity rule"] if rule_breach else [])
        severity = record_severity([e["severity"] for e in feat_evidence], sup)
        reportable = (rule_breach or sup >= min_votes or severity_rank(severity) >= severity_rank("HIGH"))
        ml_scores = [float(d.scores.at[idx]) for d in available if d.scores is not None and bool(votes.at[idx, d.name])]
        records.append({
            "index": idx, "row": row_number(idx), "support_count": sup,
            "available_detectors": len(available), "detectors_flagged": flagged_by,
            "methods": methods_all, "rule_breach": rule_breach, "features": feat_evidence,
            "primary_feature": feat_evidence[0]["feature"] if feat_evidence else None,
            "severity": severity, "evidence_level": evidence_level(sup, rule_breach),
            "reportable": bool(reportable), "max_ml_score": rnd(max(ml_scores), 4) if ml_scores else None,
        })

    reported = [r for r in records if r["reportable"]]
    weak = len(records) - len(reported)
    reported.sort(key=lambda r: (-severity_rank(r["severity"]), -r["support_count"],
                                 -max([abs(e["z_score"] or 0) for e in r["features"]] or [0]), r["row"]))
    severity_dist = {lvl: sum(1 for r in reported if r["severity"] == lvl) for lvl in SEVERITY_ORDER}
    affected = Counter(r["primary_feature"] for r in reported if r["primary_feature"])
    summary = {
        "total_records": int(n),
        "detectors_run": names, "detectors_unavailable": unavailable,
        "min_votes": min_votes,
        "anomaly_count": len(reported), "anomaly_pct": rnd(len(reported) / n * 100 if n else 0, 2),
        "weak_signal_count": int(weak),
        "severity_distribution": severity_dist,
        "critical_count": severity_dist["CRITICAL"], "high_count": severity_dist["HIGH"],
        "evidence_distribution": dict(Counter(r["evidence_level"] for r in reported)),
        "support_distribution": {str(k): v for k, v in sorted(Counter(r["support_count"] for r in reported).items())},
        "affected_features": dict(affected.most_common()),
        "truncated": len(reported) > MAX_REPORTED, "listed": min(len(reported), MAX_REPORTED),
        "_reported_index": [r["index"] for r in reported],   # internal; removed before persisting
        "method_note": ("Each record shows how many independent detectors support it. "
                        "Findings are evidence for review, not proof of error."),
    }
    if not available:
        summary["message"] = "No anomaly detector could run (no suitable numerical features)."
    return reported[:MAX_REPORTED], summary


def public_records(records: List[dict]) -> List[dict]:
    """API-friendly rows (no internal DataFrame index)."""
    out = []
    for r in records:
        out.append(json_safe({
            "row": r["row"], "severity": r["severity"], "evidence_level": r["evidence_level"],
            "support_count": r["support_count"], "available_detectors": r["available_detectors"],
            "detectors": r["methods"], "primary_feature": r["primary_feature"],
            "features": [{k: e[k] for k in ("feature", "value", "z_score", "methods", "severity", "direction")}
                         for e in r["features"]],
            "primary_value": r["features"][0]["value"] if r["features"] else None,
        }))
    return out
