from pathlib import Path

import pandas as pd

from models.zscore import (
    detect_zscore
)

from models.iqr import (
    detect_iqr
)

from models.isolation_forest import (
    detect_isolation_forest
)

from evaluation.model_comparison import (
    compare_models
)


# =====================================================
# PATH CONFIGURATION
# =====================================================

BASE_DIR = Path(
    __file__
).resolve().parent

DATA_FILE = (
    BASE_DIR
    / "data"
    / "evaluation_dataset.csv"
)

REPORT_DIR = (
    BASE_DIR
    / "reports"
)

REPORT_DIR.mkdir(
    exist_ok=True
)


# =====================================================
# MAIN
# =====================================================

def main():

    print("=" * 70)

    print(
        "AI DATA QUALITY & "
        "ANOMALY DETECTION ENGINE"
    )

    print("=" * 70)

    print(
        "PHASE 9 - ADVANCED ML "
        "ANOMALY DETECTION"
    )

    print("=" * 70)


    # -------------------------------------------------
    # LOAD DATASET
    # -------------------------------------------------

    print(
        "\n1. DATASET LOADING"
    )

    if not DATA_FILE.exists():

        print(
            f"Dataset not found:\n"
            f"{DATA_FILE}"
        )

        return

    df = pd.read_csv(
        DATA_FILE
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


    # -------------------------------------------------
    # Z-SCORE
    # -------------------------------------------------

    print(
        "\n2. Z-SCORE DETECTION"
    )

    zscore_results = detect_zscore(
        df
    )

    print(
        f"Anomalies detected: "
        f"{len(zscore_results)}"
    )


    # -------------------------------------------------
    # IQR
    # -------------------------------------------------

    print(
        "\n3. IQR DETECTION"
    )

    iqr_results = detect_iqr(
        df
    )

    print(
        f"Anomalies detected: "
        f"{len(iqr_results)}"
    )


    # -------------------------------------------------
    # ISOLATION FOREST
    # -------------------------------------------------

    print(
        "\n4. ISOLATION FOREST"
    )

    isolation_results = (
        detect_isolation_forest(
            df
        )
    )

    print(
        f"Anomalies detected: "
        f"{len(isolation_results)}"
    )


    # -------------------------------------------------
    # MODEL COMPARISON
    # -------------------------------------------------

    print(
        "\n5. MODEL COMPARISON"
    )

    comparison = compare_models(

        zscore_results,

        iqr_results,

        isolation_results
    )

    print()

    print(
        comparison.to_string(
            index=False
        )
    )


    # -------------------------------------------------
    # SAVE REPORTS
    # -------------------------------------------------

    zscore_results.to_csv(

        REPORT_DIR
        / "zscore_results.csv",

        index=False
    )

    iqr_results.to_csv(

        REPORT_DIR
        / "iqr_results.csv",

        index=False
    )

    isolation_results.to_csv(

        REPORT_DIR
        / "isolation_forest_results.csv",

        index=False
    )

    comparison.to_csv(

        REPORT_DIR
        / "model_comparison.csv",

        index=False
    )


    # -------------------------------------------------
    # SUMMARY
    # -------------------------------------------------

    print(
        "\n6. PHASE 9 SUMMARY"
    )

    print(
        "--------------------------------------"
    )

    print(
        f"Z-Score: "
        f"{len(zscore_results)} anomalies"
    )

    print(
        f"IQR: "
        f"{len(iqr_results)} anomalies"
    )

    print(
        f"Isolation Forest: "
        f"{len(isolation_results)} anomalies"
    )

    print(
        "--------------------------------------"
    )

    print(
        "Reports saved successfully."
    )

    print(
        "\nPhase 9 completed successfully! 🚀"
    )


if __name__ == "__main__":

    main()