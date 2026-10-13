import os
import pandas as pd
import numpy as np


# ============================================================
# PHASE 19
# AI DATA QUALITY DECISION & AUTOMATED ACTION ENGINE
# ============================================================


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

REPORT_DIR = os.path.join(
    BASE_DIR,
    "reports"
)

DATA_DIR = os.path.join(
    BASE_DIR,
    "data"
)

os.makedirs(
    REPORT_DIR,
    exist_ok=True
)

os.makedirs(
    DATA_DIR,
    exist_ok=True
)


# ============================================================
# SOURCE REPORT PATHS
# ============================================================

PROJECT_ROOT = os.path.dirname(
    BASE_DIR
)


PHASE14_REPORT = os.path.join(
    PROJECT_ROOT,
    "phase14",
    "reports",
    "phase14_quality_decision.csv"
)


PHASE17_SUMMARY = os.path.join(
    PROJECT_ROOT,
    "phase17",
    "reports",
    "phase17_monitoring_summary.csv"
)


PHASE18_SUMMARY = os.path.join(
    PROJECT_ROOT,
    "phase18",
    "reports",
    "phase18_forecast_summary.csv"
)


PHASE18_FORECAST = os.path.join(
    PROJECT_ROOT,
    "phase18",
    "reports",
    "phase18_forecast_report.csv"
)


PHASE18_TREND = os.path.join(
    PROJECT_ROOT,
    "phase18",
    "reports",
    "phase18_trend_report.csv"
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
    "PHASE 19 - AI DATA QUALITY DECISION "
    "& AUTOMATED ACTION ENGINE"
)

print("=" * 70)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_read_csv(path):

    if not os.path.exists(path):

        print(
            f"WARNING: Report not found:"
        )

        print(path)

        return pd.DataFrame()

    try:

        return pd.read_csv(path)

    except Exception as error:

        print(
            f"WARNING: Could not read {path}"
        )

        print(
            f"Reason: {error}"
        )

        return pd.DataFrame()


def get_value(
    dataframe,
    column,
    default=0
):

    if dataframe.empty:

        return default

    if column not in dataframe.columns:

        return default

    value = dataframe.iloc[0][column]

    if pd.isna(value):

        return default

    return value


# ============================================================
# 1. LOAD PREVIOUS PHASE REPORTS
# ============================================================

print("\n1. LOADING PREVIOUS PHASE REPORTS")


phase14 = safe_read_csv(
    PHASE14_REPORT
)

phase17 = safe_read_csv(
    PHASE17_SUMMARY
)

phase18_summary = safe_read_csv(
    PHASE18_SUMMARY
)

phase18_forecast = safe_read_csv(
    PHASE18_FORECAST
)

phase18_trend = safe_read_csv(
    PHASE18_TREND
)


print(
    f"Phase 14 report loaded: "
    f"{not phase14.empty}"
)

print(
    f"Phase 17 report loaded: "
    f"{not phase17.empty}"
)

print(
    f"Phase 18 summary loaded: "
    f"{not phase18_summary.empty}"
)

print(
    f"Phase 18 forecast loaded: "
    f"{not phase18_forecast.empty}"
)

print(
    f"Phase 18 trend loaded: "
    f"{not phase18_trend.empty}"
)


# ============================================================
# 2. EXTRACT CURRENT QUALITY INFORMATION
# ============================================================

print("\n2. CURRENT DATA QUALITY ANALYSIS")


quality_score = float(
    get_value(
        phase17,
        "quality_score",
        get_value(
            phase14,
            "final_quality_score",
            0
        )
    )
)

anomaly_count = int(
    float(
        get_value(
            phase17,
            "anomalies",
            0
        )
    )
)

drifted_features = int(
    float(
        get_value(
            phase17,
            "drifted_features",
            0
        )
    )
)

alert_count = int(
    float(
        get_value(
            phase17,
            "alerts",
            0
        )
    )
)

current_status = str(
    get_value(
        phase17,
        "status",
        "UNKNOWN"
    )
)

current_risk = str(
    get_value(
        phase17,
        "risk",
        "UNKNOWN"
    )
)


print(
    f"Current Quality Score : "
    f"{quality_score}/100"
)

print(
    f"Anomalies             : "
    f"{anomaly_count}"
)

print(
    f"Drifted Features      : "
    f"{drifted_features}"
)

print(
    f"Active Alerts         : "
    f"{alert_count}"
)

print(
    f"Current Status        : "
    f"{current_status}"
)

print(
    f"Current Risk          : "
    f"{current_risk}"
)


# ============================================================
# 3. FORECAST ANALYSIS
# ============================================================

print("\n3. FUTURE QUALITY FORECAST")


forecast_quality = quality_score

forecast_risk = max(
    0,
    100 - quality_score
)

forecast_risk_level = "LOW"


if not phase18_summary.empty:

    forecast_quality = float(
        get_value(
            phase18_summary,
            "forecast_quality",
            quality_score
        )
    )

    forecast_risk = float(
        get_value(
            phase18_summary,
            "forecast_risk",
            max(
                0,
                100 - forecast_quality
            )
        )
    )

    forecast_risk_level = str(
        get_value(
            phase18_summary,
            "forecast_risk_level",
            "UNKNOWN"
        )
    )


print(
    f"Forecast Quality : "
    f"{forecast_quality}/100"
)

print(
    f"Forecast Risk    : "
    f"{forecast_risk}/100"
)

print(
    f"Forecast Risk    : "
    f"{forecast_risk_level}"
)


# ============================================================
# 4. TREND ANALYSIS
# ============================================================

print("\n4. DATA QUALITY TREND ANALYSIS")


overall_trend = "UNKNOWN"

quality_trend = "UNKNOWN"

anomaly_trend = "UNKNOWN"

drift_trend = "UNKNOWN"

alert_trend = "UNKNOWN"


if not phase18_trend.empty:

    columns = (
        phase18_trend.columns
        .tolist()
    )

    for column in columns:

        value = str(
            phase18_trend.iloc[0][column]
        )

        column_lower = column.lower()

        if "overall" in column_lower:

            overall_trend = value

        elif "quality" in column_lower:

            quality_trend = value

        elif "anomaly" in column_lower:

            anomaly_trend = value

        elif "drift" in column_lower:

            drift_trend = value

        elif "alert" in column_lower:

            alert_trend = value


print(
    f"Quality Trend : "
    f"{quality_trend}"
)

print(
    f"Anomaly Trend : "
    f"{anomaly_trend}"
)

print(
    f"Drift Trend   : "
    f"{drift_trend}"
)

print(
    f"Alert Trend   : "
    f"{alert_trend}"
)

print(
    f"Overall Trend : "
    f"{overall_trend}"
)


# ============================================================
# 5. DECISION ENGINE
# ============================================================

print("\n5. AI DECISION ENGINE")


risk_score = 0.0


# ------------------------------------------------------------
# QUALITY SCORE RISK
# ------------------------------------------------------------

if quality_score < 60:

    risk_score += 40

elif quality_score < 75:

    risk_score += 30

elif quality_score < 90:

    risk_score += 20

elif quality_score < 95:

    risk_score += 10


# ------------------------------------------------------------
# ANOMALY RISK
# ------------------------------------------------------------

if anomaly_count >= 10:

    risk_score += 30

elif anomaly_count >= 5:

    risk_score += 20

elif anomaly_count > 0:

    risk_score += 10


# ------------------------------------------------------------
# DRIFT RISK
# ------------------------------------------------------------

if drifted_features >= 5:

    risk_score += 20

elif drifted_features >= 3:

    risk_score += 15

elif drifted_features > 0:

    risk_score += 10


# ------------------------------------------------------------
# ALERT RISK
# ------------------------------------------------------------

if alert_count >= 5:

    risk_score += 10

elif alert_count > 0:

    risk_score += 5


# ------------------------------------------------------------
# FORECAST RISK
# ------------------------------------------------------------

if forecast_risk >= 40:

    risk_score += 20

elif forecast_risk >= 20:

    risk_score += 10

elif forecast_risk >= 10:

    risk_score += 5


risk_score = round(
    min(
        risk_score,
        100
    ),
    2
)


# ============================================================
# 6. RISK LEVEL
# ============================================================

if risk_score >= 70:

    decision_risk = "CRITICAL"

elif risk_score >= 40:

    decision_risk = "HIGH"

elif risk_score >= 20:

    decision_risk = "MEDIUM"

else:

    decision_risk = "LOW"


# ============================================================
# 7. PRIORITY
# ============================================================

if decision_risk == "CRITICAL":

    priority = "P1 - IMMEDIATE"

elif decision_risk == "HIGH":

    priority = "P2 - HIGH"

elif decision_risk == "MEDIUM":

    priority = "P3 - MODERATE"

else:

    priority = "P4 - LOW"


# ============================================================
# 8. AI DECISION
# ============================================================

if decision_risk == "CRITICAL":

    decision = (
        "IMMEDIATE REMEDIATION REQUIRED"
    )

    action = (
        "Stop or isolate the affected data pipeline, "
        "investigate anomalies and drift, and execute "
        "data-quality remediation."
    )


elif decision_risk == "HIGH":

    decision = (
        "INVESTIGATION REQUIRED"
    )

    action = (
        "Investigate anomalies, review drifted features "
        "and apply appropriate data-quality corrections."
    )


elif decision_risk == "MEDIUM":

    decision = (
        "MONITOR AND INVESTIGATE"
    )

    action = (
        "Continue monitoring the dataset and investigate "
        "the detected quality issues."
    )


else:

    decision = (
        "DATASET HEALTHY"
    )

    action = (
        "Dataset is suitable for analysis. "
        "Continue routine monitoring."
    )


# ============================================================
# 9. ADDITIONAL INTELLIGENT ACTIONS
# ============================================================

recommended_actions = []


if anomaly_count > 0:

    recommended_actions.append(
        "Investigate anomalous records using Phase 13 XAI."
    )


if drifted_features > 0:

    recommended_actions.append(
        "Investigate distribution drift detected by Phase 16."
    )


if alert_count > 0:

    recommended_actions.append(
        "Review active monitoring alerts from Phase 17."
    )


if (
    str(quality_trend).upper()
    in ["DECLINING", "DETERIORATING"]
):

    recommended_actions.append(
        "Increase monitoring frequency because "
        "data quality is declining."
    )


if (
    str(anomaly_trend).upper()
    in ["INCREASING", "RISING"]
):

    recommended_actions.append(
        "Investigate the increasing anomaly trend."
    )


if (
    str(drift_trend).upper()
    in ["INCREASING", "RISING"]
):

    recommended_actions.append(
        "Investigate increasing feature distribution drift."
    )


if not recommended_actions:

    recommended_actions.append(
        "No immediate action required. "
        "Continue routine monitoring."
    )


print(
    f"Risk Score : "
    f"{risk_score}/100"
)

print(
    f"Risk Level : "
    f"{decision_risk}"
)

print(
    f"Priority   : "
    f"{priority}"
)

print(
    f"Decision   : "
    f"{decision}"
)

print(
    f"Action     : "
    f"{action}"
)


# ============================================================
# 10. AUTOMATION DECISION
# ============================================================

print("\n6. AUTOMATION DECISION")


if decision_risk == "CRITICAL":

    automation = (
        "AUTOMATED REMEDIATION RECOMMENDED"
    )

elif decision_risk == "HIGH":

    automation = (
        "SEMI-AUTOMATED REMEDIATION RECOMMENDED"
    )

elif decision_risk == "MEDIUM":

    automation = (
        "MANUAL REVIEW RECOMMENDED"
    )

else:

    automation = (
        "NO REMEDIATION REQUIRED"
    )


print(
    f"Automation Status: "
    f"{automation}"
)


# ============================================================
# 11. RECOMMENDATIONS
# ============================================================

print("\n7. AI RECOMMENDATIONS")


for index, recommendation in enumerate(
    recommended_actions,
    start=1
):

    print(
        f"{index}. {recommendation}"
    )


# ============================================================
# 12. DECISION REPORT
# ============================================================

decision_report = pd.DataFrame([{

    "quality_score":
        quality_score,

    "anomaly_count":
        anomaly_count,

    "drifted_features":
        drifted_features,

    "alert_count":
        alert_count,

    "current_status":
        current_status,

    "current_risk":
        current_risk,

    "forecast_quality":
        forecast_quality,

    "forecast_risk":
        forecast_risk,

    "forecast_risk_level":
        forecast_risk_level,

    "quality_trend":
        quality_trend,

    "anomaly_trend":
        anomaly_trend,

    "drift_trend":
        drift_trend,

    "alert_trend":
        alert_trend,

    "overall_trend":
        overall_trend,

    "risk_score":
        risk_score,

    "decision_risk":
        decision_risk,

    "priority":
        priority,

    "decision":
        decision,

    "automation":
        automation,

    "recommended_action":
        action

}])


decision_report_path = os.path.join(
    REPORT_DIR,
    "phase19_decision_report.csv"
)

decision_report.to_csv(
    decision_report_path,
    index=False
)


# ============================================================
# 13. ACTION REPORT
# ============================================================

action_report = pd.DataFrame({

    "priority": [
        priority
    ],

    "risk_level": [
        decision_risk
    ],

    "decision": [
        decision
    ],

    "action": [
        action
    ],

    "automation_status": [
        automation
    ]

})


action_report_path = os.path.join(
    REPORT_DIR,
    "phase19_action_report.csv"
)

action_report.to_csv(
    action_report_path,
    index=False
)


# ============================================================
# 14. RECOMMENDATION REPORT
# ============================================================

recommendation_report = pd.DataFrame({

    "recommendation":
        recommended_actions

})


recommendation_report_path = os.path.join(
    REPORT_DIR,
    "phase19_recommendation_report.csv"
)

recommendation_report.to_csv(
    recommendation_report_path,
    index=False
)


# ============================================================
# 15. EXECUTIVE SUMMARY
# ============================================================

executive_summary = pd.DataFrame([{

    "system":
        "AI Data Quality & Anomaly Detection Engine",

    "phase":
        19,

    "quality_score":
        quality_score,

    "risk_score":
        risk_score,

    "risk_level":
        decision_risk,

    "priority":
        priority,

    "anomalies":
        anomaly_count,

    "drifted_features":
        drifted_features,

    "alerts":
        alert_count,

    "forecast_quality":
        forecast_quality,

    "forecast_risk":
        forecast_risk,

    "overall_trend":
        overall_trend,

    "decision":
        decision,

    "automation":
        automation

}])


executive_summary_path = os.path.join(
    REPORT_DIR,
    "phase19_executive_summary.csv"
)

executive_summary.to_csv(
    executive_summary_path,
    index=False
)


# ============================================================
# 16. FINAL OUTPUT
# ============================================================

print("\n8. REPORT GENERATION")

print()

print(
    "Decision report saved to:"
)

print(
    decision_report_path
)

print()

print(
    "Action report saved to:"
)

print(
    action_report_path
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
    "Executive summary saved to:"
)

print(
    executive_summary_path
)


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n9. PHASE 19 SUMMARY")

print("-" * 70)

print(
    f"Current Quality      : "
    f"{quality_score}/100"
)

print(
    f"Risk Score           : "
    f"{risk_score}/100"
)

print(
    f"Risk Level           : "
    f"{decision_risk}"
)

print(
    f"Priority             : "
    f"{priority}"
)

print(
    f"Anomalies            : "
    f"{anomaly_count}"
)

print(
    f"Drifted Features     : "
    f"{drifted_features}"
)

print(
    f"Alerts               : "
    f"{alert_count}"
)

print(
    f"Forecast Quality     : "
    f"{forecast_quality}/100"
)

print(
    f"Overall Trend        : "
    f"{overall_trend}"
)

print(
    f"Decision             : "
    f"{decision}"
)

print(
    f"Automation           : "
    f"{automation}"
)

print("-" * 70)

print()

print(
    "Phase 19 completed successfully! 🚀"
)

print("=" * 70)