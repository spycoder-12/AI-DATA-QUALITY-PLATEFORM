def generate_recommendation(
    feature,
    severity,
    value,
    z_score
) -> str:
    """
    Generate a recommendation based
    on the anomalous feature.
    """

    feature_name = feature.lower()

    if severity == "CRITICAL":

        action = (
            "Immediately investigate this "
            "record and verify the source data."
        )

    elif severity == "HIGH":

        action = (
            "Review this record manually "
            "and validate the original source."
        )

    elif severity == "MEDIUM":

        action = (
            "Perform a secondary validation "
            "before using this record."
        )

    else:

        action = (
            "Monitor this record for repeated "
            "anomalous behaviour."
        )

    # Feature-specific suggestions

    if "income" in feature_name:

        detail = (
            "Check whether the income value "
            "was entered correctly and verify "
            "the original financial source."
        )

    elif "score" in feature_name:

        detail = (
            "Verify the score against the "
            "original assessment or examination "
            "record."
        )

    elif "hours" in feature_name:

        detail = (
            "Check whether the recorded hours "
            "are realistic and correctly entered."
        )

    elif "age" in feature_name:

        detail = (
            "Verify the person's age and check "
            "for data-entry or formatting errors."
        )

    else:

        detail = (
            "Check the original source and "
            "validate the value."
        )

    return (
        f"{action} {detail}"
    )


def generate_general_recommendation(
    severity
) -> str:

    if severity == "CRITICAL":

        return (
            "Critical anomaly detected. "
            "Do not automatically trust this "
            "record until it has been verified."
        )

    elif severity == "HIGH":

        return (
            "High-risk anomaly detected. "
            "Manual validation is recommended."
        )

    elif severity == "MEDIUM":

        return (
            "Moderate anomaly detected. "
            "Additional data validation is advised."
        )

    return (
        "Low-risk anomaly detected. "
        "Continue monitoring the record."
    )