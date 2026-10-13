import os
import pandas as pd

from quality_scorer import (
    calculate_quality_score
)

from decision_engine import (
    generate_final_decision
)


# =====================================================
# CONFIGURATION
# =====================================================

DATASET_PATH = (
    "data/evaluation_dataset.csv"
)

REPORT_DIRECTORY = (
    "reports"
)


os.makedirs(
    REPORT_DIRECTORY,
    exist_ok=True
)


# =====================================================
# HEADER
# =====================================================

print("=" * 70)

print(
    "AI DATA QUALITY & ANOMALY DETECTION ENGINE"
)

print("=" * 70)

print(
    "PHASE 14 - INTELLIGENT DATA QUALITY "
    "SCORING & DECISION ENGINE"
)

print("=" * 70)


# =====================================================
# 1. DATASET LOADING
# =====================================================

print("\n1. DATASET LOADING")

df = pd.read_csv(
    DATASET_PATH
)

print(
    "Dataset loaded successfully!"
)

print(
    f"Rows: {len(df)}"
)

print(
    f"Columns: {len(df.columns)}"
)


# =====================================================
# 2. QUALITY ANALYSIS
# =====================================================

print("\n2. DATA QUALITY ANALYSIS")

quality = calculate_quality_score(
    df
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
    f"Missing score: "
    f"{quality['missing_score']}/100"
)

print(
    f"Duplicate score: "
    f"{quality['duplicate_score']}/100"
)

print(
    f"Completeness score: "
    f"{quality['completeness_score']}/100"
)


# =====================================================
# 3. ANOMALY COUNT
# =====================================================

print("\n3. ANOMALY ANALYSIS")

if "is_anomaly" in df.columns:

    anomaly_count = int(
        df["is_anomaly"]
        .sum()
    )

    print(
        "Ground-truth anomaly column found."
    )

else:

    anomaly_count = 0

    print(
        "No anomaly label found."
    )


print(
    f"Anomalies: {anomaly_count}"
)


# =====================================================
# 4. BASE QUALITY SCORE
# =====================================================

print("\n4. BASE QUALITY SCORE")

base_score = (
    quality["overall_score"]
)

print(
    f"Base Quality Score: "
    f"{base_score}/100"
)


# =====================================================
# 5. FINAL DECISION
# =====================================================

print("\n5. INTELLIGENT DECISION ENGINE")

decision = generate_final_decision(

    quality_score=base_score,

    anomaly_count=anomaly_count,

    total_rows=len(df)
)


print(
    f"Anomaly penalty: "
    f"{decision['anomaly_penalty']}"
)

print(
    f"Final Data Quality Score: "
    f"{decision['final_score']}/100"
)

print(
    f"Quality Level: "
    f"{decision['level']}"
)

print(
    f"Risk Level: "
    f"{decision['risk']}"
)

print(
    f"Decision: "
    f"{decision['decision']}"
)

print(
    f"Recommended Action: "
    f"{decision['action']}"
)


# =====================================================
# 6. REPORT
# =====================================================

print("\n6. REPORT GENERATION")

report = {

    **quality,

    "anomaly_count":
        decision["anomaly_count"],

    "anomaly_penalty":
        decision["anomaly_penalty"],

    "final_score":
        decision["final_score"],

    "quality_level":
        decision["level"],

    "risk_level":
        decision["risk"],

    "decision":
        decision["decision"],

    "recommended_action":
        decision["action"]
}


report_df = pd.DataFrame(
    [report]
)


report_path = (
    os.path.join(
        REPORT_DIRECTORY,
        "phase14_quality_decision.csv"
    )
)


report_df.to_csv(
    report_path,
    index=False
)


print(
    f"Report saved to:\n"
    f"{os.path.abspath(report_path)}"
)


# =====================================================
# 7. SUMMARY
# =====================================================

print("\n7. PHASE 14 SUMMARY")

print("-" * 70)

print(
    f"Base Score      : "
    f"{decision['base_quality_score']}/100"
)

print(
    f"Anomalies       : "
    f"{decision['anomaly_count']}"
)

print(
    f"Anomaly Penalty : "
    f"{decision['anomaly_penalty']}"
)

print(
    f"Final Score     : "
    f"{decision['final_score']}/100"
)

print(
    f"Quality Level   : "
    f"{decision['level']}"
)

print(
    f"Risk Level      : "
    f"{decision['risk']}"
)

print("-" * 70)

print(
    "\nPhase 14 completed successfully! 🚀"
)

print("=" * 70)