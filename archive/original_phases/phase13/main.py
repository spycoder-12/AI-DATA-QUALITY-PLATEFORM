import os

import pandas as pd

from xai_engine import (
    explain_anomalies
)


print("=" * 70)

print(
    "AI DATA QUALITY & ANOMALY DETECTION ENGINE"
)

print("=" * 70)

print(
    "PHASE 13 - EXPLAINABLE AI "
    "(XAI) & ANOMALY REASONING"
)

print("=" * 70)


# =====================================================
# 1. DATASET LOADING
# =====================================================

print("\n1. DATASET LOADING")

DATASET_PATH = (
    "data/evaluation_dataset.csv"
)

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
# 2. ANOMALY EXPLANATION
# =====================================================

print("\n2. XAI ANOMALY ANALYSIS")

explanations = (
    explain_anomalies(df)
)

print(
    f"Explainable anomalies: "
    f"{len(explanations)}"
)


# =====================================================
# 3. DISPLAY EXPLANATIONS
# =====================================================

print("\n3. ANOMALY EXPLANATIONS")

print("-" * 70)

for item in explanations:

    print(
        f"Row: {item['row_number']}"
    )

    print(
        f"Feature: {item['feature']}"
    )

    print(
        f"Value: {item['value']}"
    )

    print(
        f"Z-Score: {item['z_score']}"
    )

    print(
        f"Severity: {item['severity']}"
    )

    print(
        f"Reason: {item['reason']}"
    )

    print(
        f"Recommendation: "
        f"{item['recommendation']}"
    )

    print("-" * 70)


# =====================================================
# 4. CREATE REPORT
# =====================================================

print("\n4. GENERATING XAI REPORT")

os.makedirs(
    "reports",
    exist_ok=True
)


if explanations:

    report = pd.DataFrame(
        explanations
    )

else:

    report = pd.DataFrame(
        columns=[
            "row_number",
            "feature",
            "value",
            "z_score",
            "severity",
            "reason",
            "recommendation"
        ]
    )


report_path = (
    "reports/phase13_xai_report.csv"
)

report.to_csv(
    report_path,
    index=False
)


print(
    "XAI report saved to:"
)

print(
    os.path.abspath(
        report_path
    )
)


# =====================================================
# 5. SUMMARY
# =====================================================

print("\n5. PHASE 13 SUMMARY")

print("-" * 70)

print(
    f"Total rows analyzed: {len(df)}"
)

print(
    f"Explainable anomalies: "
    f"{len(explanations)}"
)

if explanations:

    critical = sum(
        1
        for item in explanations
        if item["severity"] == "CRITICAL"
    )

    high = sum(
        1
        for item in explanations
        if item["severity"] == "HIGH"
    )

    medium = sum(
        1
        for item in explanations
        if item["severity"] == "MEDIUM"
    )

    print(
        f"Critical: {critical}"
    )

    print(
        f"High: {high}"
    )

    print(
        f"Medium: {medium}"
    )

print("-" * 70)

print(
    "\nPhase 13 completed successfully! 🚀"
)

print("=" * 70)