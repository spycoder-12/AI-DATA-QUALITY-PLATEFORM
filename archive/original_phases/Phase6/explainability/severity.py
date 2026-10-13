def calculate_severity(
    anomaly_score: float
) -> str:
    """
    Convert anomaly score into
    a human-readable severity level.

    Higher absolute score means
    more suspicious behaviour.
    """

    score = abs(float(anomaly_score))

    if score >= 5:
        return "CRITICAL"

    elif score >= 4:
        return "HIGH"

    elif score >= 3:
        return "MEDIUM"

    else:
        return "LOW"


def severity_priority(
    severity: str
) -> int:
    """
    Convert severity into a numeric priority.
    """

    priorities = {
        "LOW": 1,
        "MEDIUM": 2,
        "HIGH": 3,
        "CRITICAL": 4
    }

    return priorities.get(
        severity.upper(),
        0
    )