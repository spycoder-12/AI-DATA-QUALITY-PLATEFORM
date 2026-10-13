import os

import pandas as pd

from TrendAnalyzer import (
    load_historical_data,
    analyze_quality_trend,
    analyze_anomaly_trend,
    analyze_drift_trend,
    analyze_alert_trend,
    determine_overall_trend
)

from ForecastEngine import (
    forecast_quality,
    forecast_anomalies,
    forecast_risk,
    determine_future_risk,
    generate_forecast_recommendation
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATA_PATH = os.path.join(
    BASE_DIR,
    "data",
    "historical_quality.csv"
)

REPORT_DIR = os.path.join(
    BASE_DIR,
    "reports"
)

os.makedirs(
    REPORT_DIR,
    exist_ok=True
)


# ============================================================
# HEADER
# ============================================================

print("=" * 70)

print(
    "AI DATA QUALITY & ANOMALY DETECTION ENGINE"
)

print("=" * 70)

print(
    "PHASE 18 - AI DATA QUALITY TREND "
    "& FORECASTING ENGINE"
)

print("=" * 70)


# ============================================================
# 1. LOAD HISTORICAL DATA
# ============================================================

print("\n1. HISTORICAL DATA LOADING")

df = load_historical_data(
    DATA_PATH
)

print(
    "Historical monitoring data loaded successfully!"
)

print(
    f"Monitoring records: {len(df)}"
)

print(
    f"First date: "
    f"{df['date'].min().date()}"
)

print(
    f"Last date: "
    f"{df['date'].max().date()}"
)


# ============================================================
# 2. QUALITY TREND
# ============================================================

print("\n2. QUALITY SCORE TREND")

quality_result = (
    analyze_quality_trend(
        df
    )
)

print(
    f"Quality trend: "
    f"{quality_result['trend']}"
)

print(
    f"Quality slope: "
    f"{quality_result['slope']}"
)


# ============================================================
# 3. ANOMALY TREND
# ============================================================

print("\n3. ANOMALY TREND")

anomaly_result = (
    analyze_anomaly_trend(
        df
    )
)

print(
    f"Anomaly trend: "
    f"{anomaly_result['trend']}"
)

print(
    f"Anomaly slope: "
    f"{anomaly_result['slope']}"
)


# ============================================================
# 4. DRIFT TREND
# ============================================================

print("\n4. DATA DRIFT TREND")

drift_result = (
    analyze_drift_trend(
        df
    )
)

print(
    f"Drift trend: "
    f"{drift_result['trend']}"
)

print(
    f"Drift slope: "
    f"{drift_result['slope']}"
)


# ============================================================
# 5. ALERT TREND
# ============================================================

print("\n5. ALERT TREND")

alert_result = (
    analyze_alert_trend(
        df
    )
)

print(
    f"Alert trend: "
    f"{alert_result['trend']}"
)

print(
    f"Alert slope: "
    f"{alert_result['slope']}"
)


# ============================================================
# 6. OVERALL TREND
# ============================================================

print("\n6. OVERALL TREND")

overall_trend = determine_overall_trend(

    quality_result["trend"],

    anomaly_result["trend"],

    drift_result["trend"]
)

print(
    f"Overall data-quality trend: "
    f"{overall_trend}"
)


# ============================================================
# 7. QUALITY FORECAST
# ============================================================

print("\n7. QUALITY FORECAST")

quality_forecast = forecast_quality(
    df["quality_score"].tolist(),
    periods=3
)

for number, value in enumerate(
    quality_forecast,
    start=1
):

    print(
        f"Future period {number}: "
        f"{value}/100"
    )


# ============================================================
# 8. ANOMALY FORECAST
# ============================================================

print("\n8. ANOMALY FORECAST")

anomaly_forecast = forecast_anomalies(
    df["anomalies"].tolist(),
    periods=3
)

for number, value in enumerate(
    anomaly_forecast,
    start=1
):

    print(
        f"Future period {number}: "
        f"{value} anomalies"
    )


# ============================================================
# 9. RISK FORECAST
# ============================================================

print("\n9. RISK FORECAST")

risk_forecast = forecast_risk(
    df["risk_score"].tolist(),
    periods=3
)

for number, value in enumerate(
    risk_forecast,
    start=1
):

    risk_level = determine_future_risk(
        value
    )

    print(
        f"Future period {number}: "
        f"Risk Score = {value}, "
        f"Risk = {risk_level}"
    )


# ============================================================
# 10. AI RECOMMENDATIONS
# ============================================================

print("\n10. AI FORECAST RECOMMENDATIONS")

recommendations = (
    generate_forecast_recommendation(

        quality_forecast,

        anomaly_forecast,

        risk_forecast
    )
)

for number, recommendation in enumerate(
    recommendations,
    start=1
):

    print(
        f"{number}. "
        f"{recommendation}"
    )


# ============================================================
# 11. FORECAST REPORT
# ============================================================

print("\n11. REPORT GENERATION")

forecast_report = pd.DataFrame({

    "future_period": [
        1,
        2,
        3
    ],

    "predicted_quality_score":
        quality_forecast,

    "predicted_anomalies":
        anomaly_forecast,

    "predicted_risk_score":
        risk_forecast,

    "predicted_risk_level": [
        determine_future_risk(
            value
        )
        for value in risk_forecast
    ]

})


forecast_report_path = os.path.join(
    REPORT_DIR,
    "phase18_forecast_report.csv"
)

forecast_report.to_csv(
    forecast_report_path,
    index=False
)


# ============================================================
# 12. TREND REPORT
# ============================================================

trend_report = pd.DataFrame([{

    "quality_trend":
        quality_result["trend"],

    "quality_slope":
        quality_result["slope"],

    "anomaly_trend":
        anomaly_result["trend"],

    "anomaly_slope":
        anomaly_result["slope"],

    "drift_trend":
        drift_result["trend"],

    "drift_slope":
        drift_result["slope"],

    "alert_trend":
        alert_result["trend"],

    "alert_slope":
        alert_result["slope"],

    "overall_trend":
        overall_trend

}])


trend_report_path = os.path.join(
    REPORT_DIR,
    "phase18_trend_report.csv"
)

trend_report.to_csv(
    trend_report_path,
    index=False
)


# ============================================================
# 13. RECOMMENDATION REPORT
# ============================================================

recommendation_report = pd.DataFrame({

    "recommendation":
        recommendations

})


recommendation_report_path = os.path.join(
    REPORT_DIR,
    "phase18_recommendation_report.csv"
)

recommendation_report.to_csv(
    recommendation_report_path,
    index=False
)


# ============================================================
# 14. FINAL SUMMARY
# ============================================================

final_quality = (
    quality_forecast[-1]
)

final_risk = (
    risk_forecast[-1]
)

final_risk_level = (
    determine_future_risk(
        final_risk
    )
)


summary = pd.DataFrame([{

    "historical_records":
        len(df),

    "current_quality_score":
        df["quality_score"].iloc[-1],

    "forecast_quality_score":
        final_quality,

    "current_risk_score":
        df["risk_score"].iloc[-1],

    "forecast_risk_score":
        final_risk,

    "forecast_risk_level":
        final_risk_level,

    "overall_trend":
        overall_trend

}])


summary_path = os.path.join(
    REPORT_DIR,
    "phase18_forecast_summary.csv"
)

summary.to_csv(
    summary_path,
    index=False
)


# ============================================================
# FINAL OUTPUT
# ============================================================

print()

print(
    "Forecast report saved to:"
)

print(
    forecast_report_path
)

print()

print(
    "Trend report saved to:"
)

print(
    trend_report_path
)

print()

print(
    "Recommendation report saved to:"
)

print(
    recommendation_report_path
)

print()

print(
    "Forecast summary saved to:"
)

print(
    summary_path
)


# ============================================================
# PHASE SUMMARY
# ============================================================

print("\n15. PHASE 18 SUMMARY")

print("-" * 70)

print(
    f"Historical Records   : "
    f"{len(df)}"
)

print(
    f"Current Quality      : "
    f"{df['quality_score'].iloc[-1]}/100"
)

print(
    f"Forecast Quality     : "
    f"{final_quality}/100"
)

print(
    f"Current Risk         : "
    f"{df['risk_score'].iloc[-1]}/100"
)

print(
    f"Forecast Risk        : "
    f"{final_risk}/100"
)

print(
    f"Forecast Risk Level  : "
    f"{final_risk_level}"
)

print(
    f"Overall Trend        : "
    f"{overall_trend}"
)

print("-" * 70)

print()

print(
    "Phase 18 completed successfully! 🚀"
)

print("=" * 70)