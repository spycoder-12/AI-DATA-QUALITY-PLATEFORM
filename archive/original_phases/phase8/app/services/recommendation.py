def calculate_severity(
    z_score: float
) -> str:

    score = abs(
        float(z_score)
    )

    if score >= 5:

        return "CRITICAL"

    elif score >= 4:

        return "HIGH"

    elif score >= 3:

        return "MEDIUM"

    return "LOW"


def generate_recommendation(
    feature: str,
    severity: str
) -> str:

    if severity == "CRITICAL":

        action = (
            "Immediately investigate "
            "this record."
        )

    elif severity == "HIGH":

        action = (
            "Perform manual validation "
            "of this record."
        )

    elif severity == "MEDIUM":

        action = (
            "Perform additional "
            "data validation."
        )

    else:

        action = (
            "Monitor this record."
        )

    feature_lower = (
        feature.lower()
    )

    if "income" in feature_lower:

        detail = (
            "Verify the income against "
            "the original financial source."
        )

    elif "score" in feature_lower:

        detail = (
            "Verify the score against "
            "the original assessment."
        )

    elif "hours" in feature_lower:

        detail = (
            "Check whether the recorded "
            "hours are realistic."
        )

    elif "age" in feature_lower:

        detail = (
            "Verify the person's age "
            "in the original source."
        )

    else:

        detail = (
            "Verify the value against "
            "the original data source."
        )

    return (
        f"{action} {detail}"
    )