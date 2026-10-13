def classify_quality(score):

    if score >= 90:

        return {
            "level": "EXCELLENT",
            "risk": "LOW",
            "decision":
                "Dataset is ready for analysis.",
            "action":
                "No major data-quality action required."
        }

    elif score >= 75:

        return {
            "level": "GOOD",
            "risk": "LOW",
            "decision":
                "Dataset is generally suitable for analysis.",
            "action":
                "Perform minor quality checks before production use."
        }

    elif score >= 50:

        return {
            "level": "NEEDS REVIEW",
            "risk": "MEDIUM",
            "decision":
                "Dataset contains noticeable quality issues.",
            "action":
                "Review missing values, duplicates, and suspicious records."
        }

    else:

        return {
            "level": "POOR",
            "risk": "HIGH",
            "decision":
                "Dataset should not be used without cleaning.",
            "action":
                "Perform data cleaning and validation before analysis."
        }


def anomaly_penalty(
    anomaly_count,
    total_rows
):

    if total_rows == 0:

        return 0

    anomaly_rate = (
        anomaly_count
        / total_rows
    )

    # Maximum anomaly penalty = 30 points

    penalty = (
        anomaly_rate * 100 * 0.30
    )

    return min(
        30,
        penalty
    )


def generate_final_decision(
    quality_score,
    anomaly_count,
    total_rows
):

    penalty = anomaly_penalty(
        anomaly_count,
        total_rows
    )

    final_score = (
        quality_score
        - penalty
    )

    final_score = round(
        max(
            0,
            min(
                100,
                final_score
            )
        ),
        2
    )

    classification = classify_quality(
        final_score
    )

    return {

        "base_quality_score":
            quality_score,

        "anomaly_count":
            anomaly_count,

        "anomaly_penalty":
            round(
                penalty,
                2
            ),

        "final_score":
            final_score,

        **classification
    }