import os

import pandas as pd

from drift_detector import (
    detect_dataset_drift,
    calculate_overall_drift
)


# =====================================================
# CONFIGURATION
# =====================================================

REFERENCE_DATASET = (
    "data/reference_dataset.csv"
)

CURRENT_DATASET = (
    "data/current_dataset.csv"
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
    "PHASE 16 - DATA DRIFT & "
    "DISTRIBUTION MONITORING ENGINE"
)

print("=" * 70)


# =====================================================
# 1. LOAD DATASETS
# =====================================================

print("\n1. DATASET LOADING")

reference_df = pd.read_csv(
    REFERENCE_DATASET
)

current_df = pd.read_csv(
    CURRENT_DATASET
)

print(
    "Reference dataset loaded!"
)

print(
    f"Reference rows: "
    f"{len(reference_df)}"
)

print(
    f"Reference columns: "
    f"{len(reference_df.columns)}"
)

print()

print(
    "Current dataset loaded!"
)

print(
    f"Current rows: "
    f"{len(current_df)}"
)

print(
    f"Current columns: "
    f"{len(current_df.columns)}"
)


# =====================================================
# 2. FEATURE IDENTIFICATION
# =====================================================

print("\n2. FEATURE IDENTIFICATION")

common_numeric_features = (
    sorted(
        set(
            reference_df
            .select_dtypes(
                include="number"
            )
            .columns
        )
        &
        set(
            current_df
            .select_dtypes(
                include="number"
            )
            .columns
        )
        -
        {
            "id",
            "is_anomaly"
        }
    )
)

print(
    f"Common numeric features: "
    f"{len(common_numeric_features)}"
)

print(
    "Features:"
)

for feature in common_numeric_features:

    print(
        f"  - {feature}"
    )


# =====================================================
# 3. DRIFT ANALYSIS
# =====================================================

print("\n3. DISTRIBUTION DRIFT ANALYSIS")

results = detect_dataset_drift(
    reference_df,
    current_df
)

print(
    f"Features analyzed: "
    f"{len(results)}"
)


# =====================================================
# 4. FEATURE RESULTS
# =====================================================

print("\n4. FEATURE DRIFT RESULTS")

print("-" * 70)

for result in results:

    print(
        f"Feature: "
        f"{result['feature']}"
    )

    print(
        f"Reference Mean: "
        f"{result['reference_mean']}"
    )

    print(
        f"Current Mean: "
        f"{result['current_mean']}"
    )

    print(
        f"Mean Change: "
        f"{result['mean_change_percentage']}%"
    )

    print(
        f"PSI: "
        f"{result['psi']}"
    )

    print(
        f"KS Statistic: "
        f"{result['ks_statistic']}"
    )

    print(
        f"KS p-value: "
        f"{result['ks_p_value']}"
    )

    print(
        f"Status: "
        f"{result['drift_status']}"
    )

    print(
        f"Risk: "
        f"{result['risk']}"
    )

    print("-" * 70)


# =====================================================
# 5. OVERALL DRIFT
# =====================================================

print("\n5. OVERALL DRIFT ANALYSIS")

overall = calculate_overall_drift(
    results
)

print(
    f"Average PSI: "
    f"{overall['average_psi']}"
)

print(
    f"Drift Score: "
    f"{overall['drift_score']}/100"
)

print(
    f"Drifted Features: "
    f"{overall['drifted_features']}"
)

print(
    f"Significant Features: "
    f"{overall['significant_features']}"
)

print(
    f"Overall Status: "
    f"{overall['overall_status']}"
)

print(
    f"Overall Risk: "
    f"{overall['overall_risk']}"
)


# =====================================================
# 6. REPORT GENERATION
# =====================================================

print("\n6. REPORT GENERATION")

feature_report_path = (
    os.path.join(
        REPORT_DIRECTORY,
        "phase16_feature_drift_report.csv"
    )
)

overall_report_path = (
    os.path.join(
        REPORT_DIRECTORY,
        "phase16_overall_drift_report.csv"
    )
)


feature_report = pd.DataFrame(
    results
)

feature_report.to_csv(
    feature_report_path,
    index=False
)


overall_report = pd.DataFrame(
    [
        overall
    ]
)

overall_report.to_csv(
    overall_report_path,
    index=False
)


print(
    "Feature drift report saved to:"
)

print(
    os.path.abspath(
        feature_report_path
    )
)

print()

print(
    "Overall drift report saved to:"
)

print(
    os.path.abspath(
        overall_report_path
    )
)


# =====================================================
# 7. PHASE SUMMARY
# =====================================================

print("\n7. PHASE 16 SUMMARY")

print("-" * 70)

print(
    f"Features analyzed    : "
    f"{overall['total_features']}"
)

print(
    f"Drifted features     : "
    f"{overall['drifted_features']}"
)

print(
    f"Significant features : "
    f"{overall['significant_features']}"
)

print(
    f"Average PSI          : "
    f"{overall['average_psi']}"
)

print(
    f"Drift Score          : "
    f"{overall['drift_score']}/100"
)

print(
    f"Overall Status       : "
    f"{overall['overall_status']}"
)

print(
    f"Overall Risk         : "
    f"{overall['overall_risk']}"
)

print("-" * 70)

print(
    "\nPhase 16 completed successfully! 🚀"
)

print("=" * 70)