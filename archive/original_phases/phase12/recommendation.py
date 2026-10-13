def generate_recommendation(
    missing_rate,
    std,
    unique_values
):

    recommendations = []

    if missing_rate > 0.20:

        recommendations.append(
            "High missing-value rate detected. "
            "Consider imputation or reviewing the data collection process."
        )

    elif missing_rate > 0:

        recommendations.append(
            "Some missing values detected. "
            "Review affected records before analysis."
        )

    if std == 0:

        recommendations.append(
            "Feature has no variation. "
            "Consider removing it from machine-learning analysis."
        )

    if unique_values <= 1:

        recommendations.append(
            "Feature contains only one unique value."
        )

    if not recommendations:

        recommendations.append(
            "No major quality issue detected."
        )

    return recommendations