# ============================================================
# INTELLIGENT RECOMMENDATIONS
# ============================================================

def generate_recommendations(
    quality,
    anomaly_count,
    drift_results,
    status
):

    recommendations = []


    # --------------------------------------------------------
    # MISSING VALUES
    # --------------------------------------------------------

    if quality["missing_values"] > 0:

        recommendations.append(
            "Review missing values and apply appropriate "
            "imputation or data collection procedures."
        )


    # --------------------------------------------------------
    # DUPLICATES
    # --------------------------------------------------------

    if quality["duplicate_rows"] > 0:

        recommendations.append(
            "Remove or investigate duplicate records "
            "before performing analysis."
        )


    # --------------------------------------------------------
    # ANOMALIES
    # --------------------------------------------------------

    if anomaly_count > 0:

        recommendations.append(
            "Investigate detected anomalies using the "
            "Explainable AI results from Phase 13."
        )


    # --------------------------------------------------------
    # DRIFT
    # --------------------------------------------------------

    high_drift = [
        item["feature"]
        for item in drift_results
        if item["risk"] == "HIGH"
    ]

    medium_drift = [
        item["feature"]
        for item in drift_results
        if item["risk"] == "MEDIUM"
    ]


    if high_drift:

        recommendations.append(
            "High distribution drift detected in: "
            + ", ".join(high_drift)
            + ". Review the data-generation process."
        )


    if medium_drift:

        recommendations.append(
            "Monitor moderate drift in: "
            + ", ".join(medium_drift)
            + "."
        )


    # --------------------------------------------------------
    # FINAL RECOMMENDATION
    # --------------------------------------------------------

    if status == "HEALTHY":

        recommendations.append(
            "Dataset is healthy. No immediate "
            "data-quality action is required."
        )

    elif status == "WARNING":

        recommendations.append(
            "Dataset requires monitoring and "
            "data-quality investigation."
        )

    elif status == "CRITICAL":

        recommendations.append(
            "Critical data-quality problems detected. "
            "Investigate the dataset before using it "
            "for important analysis or machine learning."
        )


    return recommendations