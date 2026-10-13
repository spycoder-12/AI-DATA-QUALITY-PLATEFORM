from pathlib import Path

import pandas as pd

from anomaly.feature_selector import (
    select_numerical_features
)

from anomaly.iqr_detector import (
    detect_iqr_anomalies
)

from anomaly.zscore_detector import (
    detect_zscore_anomalies
)

from anomaly.anomaly_summary import (
    create_anomaly_summary
)


# =====================================================
# CONFIGURATION
# =====================================================

DATASET_PATH = Path(
    "data/anomaly_sample.csv"
)

REPORT_PATH = Path(
    "reports/anomaly_report.csv"
)


# =====================================================
# HELPER FUNCTION
# =====================================================

def print_header(title: str):

    print("\n" + "=" * 70)

    print(title)

    print("=" * 70)


# =====================================================
# MAIN
# =====================================================

def main():

    print_header(
        "AI DATA QUALITY & ANOMALY DETECTION ENGINE"
    )

    print(
        "PHASE 3 - STATISTICAL ANOMALY DETECTION"
    )

    # =================================================
    # STEP 1 — LOAD DATASET
    # =================================================

    print_header(
        "1. DATASET LOADING"
    )

    try:

        df = pd.read_csv(
            DATASET_PATH
        )

    except FileNotFoundError:

        print(
            f"ERROR: Dataset not found:"
        )

        print(
            DATASET_PATH
        )

        print(
            "\nMake sure the file exists:"
        )

        print(
            "phase3/data/anomaly_sample.csv"
        )

        return

    except Exception as error:

        print(
            f"ERROR: {error}"
        )

        return

    if df.empty:

        print(
            "ERROR: Dataset is empty."
        )

        return

    print(
        "Dataset loaded successfully!"
    )

    print(
        f"Rows    : {len(df)}"
    )

    print(
        f"Columns : {len(df.columns)}"
    )

    # =================================================
    # STEP 2 — FEATURE SELECTION
    # =================================================

    print_header(
        "2. FEATURE SELECTION"
    )

    (
        numerical_features,
        excluded_features
    ) = select_numerical_features(df)

    print(
        "Features used for anomaly detection:"
    )

    for feature in numerical_features:

        print(
            f"  ✓ {feature}"
        )

    print(
        "\nExcluded features:"
    )

    if excluded_features:

        for feature in excluded_features:

            print(
                f"  ✗ {feature}"
            )

    else:

        print(
            "  None"
        )

    if not numerical_features:

        print(
            "\nERROR: No suitable numerical "
            "features found."
        )

        return

    # =================================================
    # STEP 3 — IQR DETECTION
    # =================================================

    print_header(
        "3. IQR ANOMALY DETECTION"
    )

    iqr_results = detect_iqr_anomalies(
        df,
        columns=numerical_features,
        multiplier=1.5
    )

    print(
        f"Total IQR detections: "
        f"{iqr_results['total_anomalies']}"
    )

    for column, result in (
        iqr_results["columns"].items()
    ):

        print(
            f"\n{column}"
        )

        print(
            f"  Q1          : "
            f"{result['q1']}"
        )

        print(
            f"  Q3          : "
            f"{result['q3']}"
        )

        print(
            f"  IQR         : "
            f"{result['iqr']}"
        )

        print(
            f"  Lower Bound : "
            f"{result['lower_bound']}"
        )

        print(
            f"  Upper Bound : "
            f"{result['upper_bound']}"
        )

        print(
            f"  Anomalies   : "
            f"{result['anomaly_count']}"
        )

        for anomaly in result[
            "anomalies"
        ]:

            print(
                f"      Row "
                f"{anomaly['row']} "
                f"→ "
                f"{anomaly['value']}"
            )

    # =================================================
    # STEP 4 — Z-SCORE DETECTION
    # =================================================

    print_header(
        "4. Z-SCORE ANOMALY DETECTION"
    )

    zscore_results = (
        detect_zscore_anomalies(
            df,
            columns=numerical_features,
            threshold=3.0
        )
    )

    print(
        f"Total Z-Score detections: "
        f"{zscore_results['total_anomalies']}"
    )

    for column, result in (
        zscore_results["columns"].items()
    ):

        print(
            f"\n{column}"
        )

        print(
            f"  Mean      : "
            f"{result['mean']}"
        )

        print(
            f"  Std       : "
            f"{result['std']}"
        )

        print(
            f"  Threshold : "
            f"{result['threshold']}"
        )

        print(
            f"  Anomalies : "
            f"{result['anomaly_count']}"
        )

        for anomaly in result[
            "anomalies"
        ]:

            print(
                f"      Row "
                f"{anomaly['row']} "
                f"→ "
                f"{anomaly['value']} "
                f"(Z = "
                f"{anomaly['z_score']})"
            )

    # =================================================
    # STEP 5 — COMBINE RESULTS
    # =================================================

    print_header(
        "5. ANOMALY COMPARISON"
    )

    summary_df = create_anomaly_summary(
        df,
        iqr_results,
        zscore_results
    )

    print(
        summary_df.to_string(
            index=False
        )
    )

    # =================================================
    # STEP 6 — SAVE REPORT
    # =================================================

    print_header(
        "6. REPORT GENERATION"
    )

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    summary_df.to_csv(
        REPORT_PATH,
        index=False
    )

    print(
        "Anomaly report generated!"
    )

    print(
        f"Saved to: {REPORT_PATH}"
    )

    # =================================================
    # STEP 7 — FINAL SUMMARY
    # =================================================

    print_header(
        "PHASE 3 SUMMARY"
    )

    print(
        f"Dataset Rows       : "
        f"{len(df)}"
    )

    print(
        f"Features Analyzed  : "
        f"{len(numerical_features)}"
    )

    print(
        f"IQR Detections     : "
        f"{iqr_results['total_anomalies']}"
    )

    print(
        f"Z-Score Detections : "
        f"{zscore_results['total_anomalies']}"
    )

    print(
        f"Report             : "
        f"{REPORT_PATH}"
    )

    print(
        "\nPhase 3 completed successfully! 🚀"
    )


# =====================================================
# PROGRAM ENTRY POINT
# =====================================================

if __name__ == "__main__":

    main()