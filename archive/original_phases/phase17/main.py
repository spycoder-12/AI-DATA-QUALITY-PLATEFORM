import os

import pandas as pd

from Monitor import (
    load_datasets,
    calculate_quality_metrics,
    detect_anomalies,
    analyze_drift,
    calculate_quality_score
)

from AlertEngine import (
    generate_alerts,
    determine_status,
    determine_risk
)

from Recommendation import (
    generate_recommendations
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

REFERENCE_PATH = os.path.join(
    BASE_DIR,
    "data",
    "reference_dataset.csv"
)

CURRENT_PATH = os.path.join(
    BASE_DIR,
    "data",
    "current_dataset.csv"
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
    "PHASE 17 - AI DATA QUALITY MONITORING "
    "& INTELLIGENT ALERT ENGINE"
)

print("=" * 70)


# ============================================================
# 1. DATASET LOADING
# ============================================================

print("\n1. DATASET LOADING")

reference, current = load_datasets(
    REFERENCE_PATH,
    CURRENT_PATH
)

print(
    "Reference dataset loaded successfully!"
)

print(
    f"Reference rows: {len(reference)}"
)

print(
    f"Reference columns: {len(reference.columns)}"
)

print()

print(
    "Current dataset loaded successfully!"
)

print(
    f"Current rows: {len(current)}"
)

print(
    f"Current columns: {len(current.columns)}"
)


# ============================================================
# 2. CURRENT DATA QUALITY
# ============================================================

print("\n2. DATA QUALITY MONITORING")

quality = calculate_quality_metrics(
    current
)

print(
    f"Missing values: "
    f"{quality['missing_values']}"
)

print(
    f"Duplicate rows: "
    f"{quality['duplicate_rows']}"
)

print(
    f"Completeness: "
    f"{quality['completeness']}/100"
)


# ============================================================
# 3. ANOMALY MONITORING
# ============================================================

print("\n3. ANOMALY MONITORING")

anomaly_details, anomaly_count = (
    detect_anomalies(current)
)

print(
    f"Total unique anomalous rows: "
    f"{anomaly_count}"
)


# ============================================================
# 4. DATA DRIFT MONITORING
# ============================================================

print("\n4. DATA DRIFT MONITORING")

drift_results = analyze_drift(
    reference,
    current
)

print(
    f"Features monitored: "
    f"{len(drift_results)}"
)

drifted_features = [
    item
    for item in drift_results
    if item["risk"] != "LOW"
]

print(
    f"Drifted features: "
    f"{len(drifted_features)}"
)


# ============================================================
# 5. QUALITY SCORE
# ============================================================

print("\n5. OVERALL QUALITY SCORE")

# FIXED:
# calculate_quality_score now accepts
# quality and anomaly_count only.

quality_score = calculate_quality_score(
    quality,
    anomaly_count
)

print(
    f"Quality Score: "
    f"{quality_score}/100"
)


# ============================================================
# 6. ALERT GENERATION
# ============================================================

print("\n6. INTELLIGENT ALERT ENGINE")

alerts = generate_alerts(
    quality,
    anomaly_count,
    drift_results,
    quality_score
)

print(
    f"Alerts generated: "
    f"{len(alerts)}"
)

if alerts:

    for alert in alerts:

        print(
            f"[{alert['severity']}] "
            f"{alert['type']}: "
            f"{alert['message']}"
        )

else:

    print(
        "No alerts generated."
    )


# ============================================================
# 7. SYSTEM STATUS
# ============================================================

print("\n7. SYSTEM HEALTH")

status = determine_status(
    alerts
)

risk = determine_risk(
    status
)

print(
    f"Overall Status: "
    f"{status}"
)

print(
    f"Risk Level: "
    f"{risk}"
)


# ============================================================
# 8. AI RECOMMENDATIONS
# ============================================================

print("\n8. AI RECOMMENDATIONS")

recommendations = generate_recommendations(
    quality,
    anomaly_count,
    drift_results,
    status
)

if recommendations:

    for number, recommendation in enumerate(
        recommendations,
        start=1
    ):

        print(
            f"{number}. {recommendation}"
        )

else:

    print(
        "No additional recommendations."
    )


# ============================================================
# 9. FEATURE MONITORING REPORT
# ============================================================

print("\n9. REPORT GENERATION")

feature_report = pd.DataFrame(
    drift_results
)

feature_report_path = os.path.join(
    REPORT_DIR,
    "phase17_feature_monitoring.csv"
)

feature_report.to_csv(
    feature_report_path,
    index=False
)


# ============================================================
# 10. ALERT REPORT
# ============================================================

alert_report = pd.DataFrame(
    alerts
)

alert_report_path = os.path.join(
    REPORT_DIR,
    "phase17_alert_report.csv"
)

alert_report.to_csv(
    alert_report_path,
    index=False
)


# ============================================================
# 11. RECOMMENDATION REPORT
# ============================================================

recommendation_report = pd.DataFrame({

    "recommendation":
        recommendations

})

recommendation_report_path = os.path.join(
    REPORT_DIR,
    "phase17_recommendation_report.csv"
)

recommendation_report.to_csv(
    recommendation_report_path,
    index=False
)


# ============================================================
# 12. OVERALL SUMMARY
# ============================================================

summary = pd.DataFrame([{

    "rows":
        len(current),

    "columns":
        len(current.columns),

    "missing_values":
        quality["missing_values"],

    "duplicate_rows":
        quality["duplicate_rows"],

    "completeness":
        quality["completeness"],

    "anomalies":
        anomaly_count,

    "drifted_features":
        len(drifted_features),

    "features_monitored":
        len(drift_results),

    "quality_score":
        quality_score,

    "alerts":
        len(alerts),

    "status":
        status,

    "risk":
        risk

}])


summary_path = os.path.join(
    REPORT_DIR,
    "phase17_monitoring_summary.csv"
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
    "Feature monitoring report saved to:"
)

print(
    feature_report_path
)

print()

print(
    "Alert report saved to:"
)

print(
    alert_report_path
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
    "Overall monitoring summary saved to:"
)

print(
    summary_path
)


# ============================================================
# 10. PHASE 17 SUMMARY
# ============================================================

print("\n10. PHASE 17 SUMMARY")

print("-" * 70)

print(
    f"Quality Score          : "
    f"{quality_score}/100"
)

print(
    f"Unique Anomalous Rows  : "
    f"{anomaly_count}"
)

print(
    f"Features Monitored     : "
    f"{len(drift_results)}"
)

print(
    f"Drifted Features       : "
    f"{len(drifted_features)}"
)

print(
    f"Alerts                 : "
    f"{len(alerts)}"
)

print(
    f"Overall Status         : "
    f"{status}"
)

print(
    f"Risk Level             : "
    f"{risk}"
)

print("-" * 70)

print()

print(
    "Phase 17 completed successfully! 🚀"
)

print("=" * 70)