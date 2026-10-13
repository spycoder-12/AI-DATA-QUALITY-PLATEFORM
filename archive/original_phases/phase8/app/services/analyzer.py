import pandas as pd

from app.services.quality import (
    analyze_quality
)

from app.services.anomaly import (
    detect_anomalies
)

from app.services.recommendation import (
    calculate_severity,
    generate_recommendation
)


def analyze_dataset(
    file_path
) -> dict:

    # ================================================
    # LOAD DATA
    # ================================================

    df = pd.read_csv(
        file_path
    )

    # ================================================
    # QUALITY ANALYSIS
    # ================================================

    quality = analyze_quality(
        df
    )

    # ================================================
    # ANOMALY DETECTION
    # ================================================

    raw_anomalies = (
        detect_anomalies(df)
    )

    # ================================================
    # ADD SEVERITY + RECOMMENDATION
    # ================================================

    anomalies = []

    for anomaly in raw_anomalies:

        severity = calculate_severity(
            anomaly["z_score"]
        )

        recommendation = (
            generate_recommendation(
                anomaly["feature"],
                severity
            )
        )

        anomaly[
            "severity"
        ] = severity

        anomaly[
            "recommendation"
        ] = recommendation

        anomalies.append(
            anomaly
        )

    # ================================================
    # RESULT
    # ================================================

    return {

        "rows":
            len(df),

        "columns":
            len(df.columns),

        "quality":
            quality,

        "anomalies_detected":
            len(anomalies),

        "anomalies":
            anomalies
    }