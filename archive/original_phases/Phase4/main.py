from pathlib import Path

import pandas as pd

from preprocessing.preprocessor import (
    prepare_features
)

from models.isolation_forest import (
    detect_isolation_forest
)

from models.local_outlier_factor import (
    detect_lof
)

from models.one_class_svm import (
    detect_one_class_svm
)


# =====================================================
# CONFIGURATION
# =====================================================

DATASET_PATH = Path(
    "data/anomaly_sample.csv"
)

REPORT_PATH = Path(
    "reports/ml_anomaly_report.csv"
)


# =====================================================
# HELPER
# =====================================================

def print_header(title):

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
        "PHASE 4 - MACHINE LEARNING "
        "ANOMALY DETECTION"
    )

    # =================================================
    # 1. LOAD DATA
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
            f"ERROR: Dataset not found: "
            f"{DATASET_PATH}"
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
    # 2. SELECT FEATURES
    # =================================================

    print_header(
        "2. FEATURE SELECTION"
    )

    numerical_columns = (
        df.select_dtypes(
            include="number"
        )
        .columns
        .tolist()
    )

    # Remove ID-like columns
    feature_columns = []

    excluded_columns = []

    for column in numerical_columns:

        column_lower = column.lower()

        if (
            column_lower == "id"
            or column_lower.endswith("_id")
            or column_lower.startswith("id_")
        ):

            excluded_columns.append(
                column
            )

        elif df[column].nunique(
            dropna=True
        ) <= 1:

            excluded_columns.append(
                column
            )

        else:

            feature_columns.append(
                column
            )

    print(
        "Features used:"
    )

    for column in feature_columns:

        print(
            f"  ✓ {column}"
        )

    print(
        "\nExcluded:"
    )

    for column in excluded_columns:

        print(
            f"  ✗ {column}"
        )

    if not feature_columns:

        print(
            "ERROR: No suitable features."
        )

        return

    # =================================================
    # 3. PREPROCESSING
    # =================================================

    print_header(
        "3. DATA PREPROCESSING"
    )

    try:

        X = prepare_features(
            df,
            feature_columns
        )

    except Exception as error:

        print(
            f"Preprocessing error: "
            f"{error}"
        )

        return

    print(
        "Missing values handled."
    )

    print(
        "Features standardized."
    )

    print(
        f"ML matrix shape: {X.shape}"
    )

    # =================================================
    # 4. ISOLATION FOREST
    # =================================================

    print_header(
        "4. ISOLATION FOREST"
    )

    isolation_results = (
        detect_isolation_forest(X)
    )

    print(
        "Model: Isolation Forest"
    )

    print(
        f"Anomalies detected: "
        f"{isolation_results['anomaly_count']}"
    )

    for anomaly in (
        isolation_results["anomalies"]
    ):

        print(
            f"  Row {anomaly['row']} "
            f"→ Score: "
            f"{anomaly['score']}"
        )

    # =================================================
    # 5. LOF
    # =================================================

    print_header(
        "5. LOCAL OUTLIER FACTOR"
    )

    # Make sure n_neighbors is valid
    n_neighbors = min(
        20,
        len(df) - 1
    )

    lof_results = detect_lof(
        X,
        n_neighbors=n_neighbors
    )

    print(
        "Model: Local Outlier Factor"
    )

    print(
        f"Anomalies detected: "
        f"{lof_results['anomaly_count']}"
    )

    for anomaly in (
        lof_results["anomalies"]
    ):

        print(
            f"  Row {anomaly['row']} "
            f"→ Score: "
            f"{anomaly['score']}"
        )

    # =================================================
    # 6. ONE-CLASS SVM
    # =================================================

    print_header(
        "6. ONE-CLASS SVM"
    )

    svm_results = detect_one_class_svm(
        X,
        nu=0.05
    )

    print(
        "Model: One-Class SVM"
    )

    print(
        f"Anomalies detected: "
        f"{svm_results['anomaly_count']}"
    )

    for anomaly in (
        svm_results["anomalies"]
    ):

        print(
            f"  Row {anomaly['row']} "
            f"→ Score: "
            f"{anomaly['score']}"
        )

    # =================================================
    # 7. MODEL COMPARISON
    # =================================================

    print_header(
        "7. ML MODEL COMPARISON"
    )

    comparison = pd.DataFrame({

        "model": [
            "Isolation Forest",
            "Local Outlier Factor",
            "One-Class SVM"
        ],

        "anomaly_count": [

            isolation_results[
                "anomaly_count"
            ],

            lof_results[
                "anomaly_count"
            ],

            svm_results[
                "anomaly_count"
            ]
        ]
    })

    print(
        comparison.to_string(
            index=False
        )
    )

    # =================================================
    # 8. SAVE REPORT
    # =================================================

    print_header(
        "8. REPORT GENERATION"
    )

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    comparison.to_csv(
        REPORT_PATH,
        index=False
    )

    print(
        "ML anomaly report generated!"
    )

    print(
        f"Saved to: {REPORT_PATH}"
    )

    # =================================================
    # 9. FINAL SUMMARY
    # =================================================

    print_header(
        "PHASE 4 SUMMARY"
    )

    print(
        f"Rows analyzed        : "
        f"{len(df)}"
    )

    print(
        f"Features analyzed    : "
        f"{len(feature_columns)}"
    )

    print(
        f"Isolation Forest     : "
        f"{isolation_results['anomaly_count']}"
    )

    print(
        f"Local Outlier Factor : "
        f"{lof_results['anomaly_count']}"
    )

    print(
        f"One-Class SVM        : "
        f"{svm_results['anomaly_count']}"
    )

    print(
        "\nPhase 4 completed successfully! 🚀"
    )


# =====================================================
# ENTRY POINT
# =====================================================

if __name__ == "__main__":

    main()