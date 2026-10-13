from pathlib import Path

import pandas as pd

from explainability.anomaly_explainer import (
    explain_row
)

from explainability.severity import (
    calculate_severity
)

from recommendations.recommendation_engine import (
    generate_recommendation
)


# =====================================================
# CONFIGURATION
# =====================================================

DATASET_PATH = Path(
    "data/evaluation_dataset.csv"
)

REPORT_PATH = Path(
    "reports/ai_anomaly_explanations.csv"
)


# =====================================================
# HEADER
# =====================================================

def print_header(title):

    print(
        "\n" + "=" * 70
    )

    print(title)

    print(
        "=" * 70
    )


# =====================================================
# FEATURE SELECTION
# =====================================================

def select_features(df):

    numerical_columns = (
        df.select_dtypes(
            include="number"
        )
        .columns
        .tolist()
    )

    features = []

    for column in numerical_columns:

        if column in [
            "id",
            "is_anomaly"
        ]:

            continue

        if (
            df[column].nunique(
                dropna=True
            ) <= 1
        ):

            continue

        features.append(
            column
        )

    return features


# =====================================================
# MAIN
# =====================================================

def main():

    print_header(
        "AI DATA QUALITY & ANOMALY DETECTION ENGINE"
    )

    print(
        "PHASE 6 - AI RECOMMENDATION "
        "& EXPLAINABILITY ENGINE"
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
            f"Dataset not found: "
            f"{DATASET_PATH}"
        )

        return

    print(
        "Dataset loaded successfully!"
    )

    print(
        f"Rows: {len(df)}"
    )

    # =================================================
    # 2. FEATURE SELECTION
    # =================================================

    print_header(
        "2. FEATURE SELECTION"
    )

    feature_columns = (
        select_features(df)
    )

    print(
        "Features:"
    )

    for feature in feature_columns:

        print(
            f"  ✓ {feature}"
        )

    # =================================================
    # 3. FIND KNOWN ANOMALIES
    # =================================================

    print_header(
        "3. ANOMALY ANALYSIS"
    )

    anomaly_rows = df[
        df["is_anomaly"] == 1
    ].index.tolist()

    print(
        f"Known anomalies: "
        f"{len(anomaly_rows)}"
    )

    # =================================================
    # 4. EXPLAIN EACH ANOMALY
    # =================================================

    explanations = []

    for row_index in anomaly_rows:

        explanation = explain_row(
            df,
            row_index,
            feature_columns
        )

        strongest_feature = (
            explanation[
                "strongest_feature"
            ]
        )

        strongest_score = (
            explanation[
                "strongest_z_score"
            ]
        )

        # Determine severity
        severity = calculate_severity(
            strongest_score
        )

        # Get actual value
        value = df.loc[
            row_index,
            strongest_feature
        ]

        recommendation = (
            generate_recommendation(
                strongest_feature,
                severity,
                value,
                strongest_score
            )
        )

        # =================================================
        # DISPLAY
        # =================================================

        print(
            "\n" + "-" * 65
        )

        print(
            f"Anomaly Row: "
            f"{row_index + 2}"
        )

        print(
            f"Feature: "
            f"{strongest_feature}"
        )

        print(
            f"Value: "
            f"{value}"
        )

        print(
            f"Z-Score: "
            f"{strongest_score}"
        )

        print(
            f"Severity: "
            f"{severity}"
        )

        print(
            f"Recommendation:"
        )

        print(
            recommendation
        )

        # =================================================
        # SAVE RESULT
        # =================================================

        explanations.append({

            "row":
                row_index + 2,

            "feature":
                strongest_feature,

            "value":
                value,

            "z_score":
                strongest_score,

            "severity":
                severity,

            "recommendation":
                recommendation
        })

    # =================================================
    # 5. CREATE REPORT
    # =================================================

    print_header(
        "4. AI EXPLANATION REPORT"
    )

    report_df = pd.DataFrame(
        explanations
    )

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    report_df.to_csv(
        REPORT_PATH,
        index=False
    )

    print(
        report_df.to_string(
            index=False
        )
    )

    print(
        f"\nReport saved to:"
    )

    print(
        REPORT_PATH
    )

    # =================================================
    # 6. SUMMARY
    # =================================================

    print_header(
        "PHASE 6 SUMMARY"
    )

    if not report_df.empty:

        severity_counts = (
            report_df[
                "severity"
            ]
            .value_counts()
        )

        print(
            "Severity distribution:"
        )

        for severity, count in (
            severity_counts.items()
        ):

            print(
                f"  {severity}: {count}"
            )

    print(
        "\nAI explainability enabled."
    )

    print(
        "AI recommendations generated."
    )

    print(
        "\nPhase 6 completed successfully! 🚀"
    )


if __name__ == "__main__":

    main()