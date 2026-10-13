"""ONE severity system for the whole platform: LOW < MEDIUM < HIGH < CRITICAL.

Every module (anomalies, quality findings, alerts, recommendations, decision
engine) calls into this file - there are no module-local severity rules.

Anomaly (record / feature) severity
-----------------------------------
For each feature that contributed to an anomalous record three independent
signals are converted to a level, and the highest one wins:

  * z-score magnitude      |z| >= 5 -> CRITICAL, >= 4 -> HIGH, >= 3 -> MEDIUM, else LOW
  * IQR (Tukey) distance   value beyond 3 x IQR outside the quartiles ("extreme
                           outlier") -> HIGH, otherwise LOW
  * validity-rule breach   value outside a hard domain range (e.g. age 0-120)
                           -> HIGH, or CRITICAL when it exceeds the range by at
                           least 50 % of the range width (age 185, score 400 ...)

A record's severity is the highest feature severity. If at least three
independent detectors support the record, the severity is raised one level
because agreement between methods is stronger evidence - but agreement alone
can never create a CRITICAL: CRITICAL needs |z| >= 5 or a severe rule breach.

Data-quality finding severity (missing / duplicates / invalid / inconsistent)
-----------------------------------------------------------------------------
Rate in percent -> LOW (<5), MEDIUM (<20), HIGH (<40), CRITICAL (>=40) for missing
values; duplicates and invalid/inconsistent records use their own (documented)
tables below. A rate of exactly 0 yields ``None`` (no finding).
"""
from __future__ import annotations

from typing import Optional

from app.utils.helpers import SEVERITY_ORDER, bump_severity, max_severity

# (upper bound exclusive, level) - anything above the last bound is CRITICAL
_RATE_TABLES = {
    "missing": [(5, "LOW"), (20, "MEDIUM"), (40, "HIGH")],
    "duplicates": [(5, "LOW"), (15, "MEDIUM"), (30, "HIGH")],
    "invalid": [(1, "LOW"), (5, "MEDIUM"), (15, "HIGH")],
    "inconsistent": [(1, "LOW"), (5, "MEDIUM"), (15, "HIGH")],
}


def severity_from_rate(kind: str, rate_pct: float) -> Optional[str]:
    """Severity for a data-quality problem rate (percent). None when rate is 0."""
    if rate_pct is None or rate_pct <= 0:
        return None
    for bound, level in _RATE_TABLES[kind]:
        if rate_pct < bound:
            return level
    return "CRITICAL"


def level_from_zscore(z: float) -> str:
    z = abs(float(z))
    if z >= 5:
        return "CRITICAL"
    if z >= 4:
        return "HIGH"
    if z >= 3:
        return "MEDIUM"
    return "LOW"


def level_from_iqr(distance_in_iqr: Optional[float]) -> str:
    """``distance_in_iqr`` = distance beyond the nearer quartile, in IQR units."""
    if distance_in_iqr is not None and distance_in_iqr >= 3.0:
        return "HIGH"
    return "LOW"


def level_from_rule(excess_ratio: Optional[float]) -> str:
    """Validity-rule breach. ``excess_ratio`` = overshoot / range width (None if unbounded)."""
    if excess_ratio is not None and excess_ratio >= 0.5:
        return "CRITICAL"
    return "HIGH"


def feature_severity(z: Optional[float] = None, iqr_distance: Optional[float] = None,
                     rule_breached: bool = False, rule_excess_ratio: Optional[float] = None,
                     stat_flagged: bool = True) -> str:
    levels = ["LOW"]
    if z is not None and stat_flagged:
        levels.append(level_from_zscore(z))
    if iqr_distance is not None and stat_flagged:
        levels.append(level_from_iqr(iqr_distance))
    if rule_breached:
        levels.append(level_from_rule(rule_excess_ratio))
    return max_severity(levels)


def record_severity(feature_levels: list, support_count: int) -> str:
    """Highest feature severity, raised one level when >= 3 detectors agree."""
    base = max_severity(feature_levels) if feature_levels else "LOW"
    if support_count < 3:
        return base
    bumped = bump_severity(base, 1)
    return "HIGH" if (bumped == "CRITICAL" and base != "CRITICAL") else bumped


def evidence_level(support_count: int, rule_breached: bool = False) -> str:
    """Evidence-based wording (we never claim an anomaly is 'definitely' wrong)."""
    if support_count >= 3 or (support_count >= 2 and rule_breached):
        return "STRONG"
    if support_count >= 2 or rule_breached:
        return "MODERATE"
    return "WEAK"


def severity_rank(level: str) -> int:
    return SEVERITY_ORDER.index(level) if level in SEVERITY_ORDER else -1


def risk_level_from_score(score: float, medium: float = 20.0, high: float = 40.0,
                          critical: float = 70.0) -> str:
    if score >= critical:
        return "CRITICAL"
    if score >= high:
        return "HIGH"
    if score >= medium:
        return "MEDIUM"
    return "LOW"
