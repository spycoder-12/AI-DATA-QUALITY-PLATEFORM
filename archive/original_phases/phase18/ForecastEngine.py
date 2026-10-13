import numpy as np


# ============================================================
# LINEAR FORECAST
# ============================================================

def linear_forecast(
    values,
    periods=3
):

    values = np.asarray(
        values,
        dtype=float
    )

    if len(values) < 2:

        return [
            round(
                float(values[-1]),
                2
            )
        ] * periods

    x = np.arange(
        len(values)
    )

    slope, intercept = np.polyfit(
        x,
        values,
        1
    )

    future_x = np.arange(
        len(values),
        len(values) + periods
    )

    predictions = (
        slope * future_x
        +
        intercept
    )

    return [
        round(
            float(value),
            2
        )
        for value in predictions
    ]


# ============================================================
# QUALITY FORECAST
# ============================================================

def forecast_quality(
    quality_scores,
    periods=3
):

    predictions = linear_forecast(
        quality_scores,
        periods
    )

    predictions = [
        min(
            max(
                value,
                0
            ),
            100
        )
        for value in predictions
    ]

    return predictions


# ============================================================
# ANOMALY FORECAST
# ============================================================

def forecast_anomalies(
    anomalies,
    periods=3
):

    predictions = linear_forecast(
        anomalies,
        periods
    )

    return [
        max(
            0,
            round(
                value,
                2
            )
        )
        for value in predictions
    ]


# ============================================================
# RISK FORECAST
# ============================================================

def forecast_risk(
    risk_scores,
    periods=3
):

    predictions = linear_forecast(
        risk_scores,
        periods
    )

    return [
        min(
            max(
                round(
                    value,
                    2
                ),
                0
            ),
            100
        )
        for value in predictions
    ]


# ============================================================
# FUTURE RISK LEVEL
# ============================================================

def determine_future_risk(
    risk_score
):

    if risk_score >= 70:

        return "CRITICAL"

    elif risk_score >= 50:

        return "HIGH"

    elif risk_score >= 25:

        return "MEDIUM"

    return "LOW"


# ============================================================
# FORECAST RECOMMENDATION
# ============================================================

def generate_forecast_recommendation(
    quality_forecast,
    anomaly_forecast,
    risk_forecast
):

    recommendations = []

    current_quality = quality_forecast[0]
    future_quality = quality_forecast[-1]

    current_risk = risk_forecast[0]
    future_risk = risk_forecast[-1]

    if future_quality < current_quality:

        recommendations.append(
            "Data quality is expected to decline. Increase monitoring frequency."
        )

    elif future_quality > current_quality:

        recommendations.append(
            "Data quality is showing an improving forecast trend."
        )

    else:

        recommendations.append(
            "Data quality is expected to remain relatively stable."
        )

    if future_risk > current_risk:

        recommendations.append(
            "Future data-quality risk is increasing. Investigate recurring quality problems."
        )

    elif future_risk < current_risk:

        recommendations.append(
            "Future data-quality risk is expected to decrease."
        )

    else:

        recommendations.append(
            "Future data-quality risk is expected to remain stable."
        )

    if max(anomaly_forecast) > 3:

        recommendations.append(
            "Forecasted anomaly volume is elevated. Investigate anomaly-producing features."
        )

    return recommendations