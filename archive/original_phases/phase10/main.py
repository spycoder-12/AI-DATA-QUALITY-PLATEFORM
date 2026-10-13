from pathlib import Path
import sys
import time

import pandas as pd

from sklearn.ensemble import (
    IsolationForest
)

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix
)


# =====================================================
# PATH CONFIGURATION
# =====================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
)

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
# FEATURE SELECTION
# =====================================================

def select_features(df):

    numeric_df = df.select_dtypes(
        include="number"
    ).copy()

    numeric_df = numeric_df.drop(
        columns=[
            "id",
            "is_anomaly"
        ],
        errors="ignore"
    )

    numeric_df = numeric_df.loc[
        :,
        numeric_df.nunique() > 1
    ]

    return numeric_df


# =====================================================
# Z-SCORE
# =====================================================

def zscore_prediction(
    df,
    threshold=3.0
):

    features = select_features(
        df
    )

    predictions = pd.Series(
        0,
        index=df.index
    )

    for column in features.columns:

        mean = features[
            column
        ].mean()

        std = features[
            column
        ].std()

        if pd.isna(std) or std == 0:
            continue

        z_scores = (
            (
                features[column]
                - mean
            )
            / std
        )

        predictions[
            z_scores.abs() >= threshold
        ] = 1

    return predictions


# =====================================================
# IQR
# =====================================================

def iqr_prediction(df):

    features = select_features(
        df
    )

    predictions = pd.Series(
        0,
        index=df.index
    )

    for column in features.columns:

        q1 = features[
            column
        ].quantile(0.25)

        q3 = features[
            column
        ].quantile(0.75)

        iqr = q3 - q1

        if iqr == 0:
            continue

        lower = (
            q1 - 1.5 * iqr
        )

        upper = (
            q3 + 1.5 * iqr
        )

        mask = (
            (features[column] < lower)
            |
            (features[column] > upper)
        )

        predictions[mask] = 1

    return predictions


# =====================================================
# ISOLATION FOREST
# =====================================================

def isolation_forest_prediction(
    df
):

    features = select_features(
        df
    )

    features = features.fillna(
        features.median()
    )

    model = IsolationForest(
        n_estimators=200,
        contamination="auto",
        random_state=42
    )

    predictions = model.fit_predict(
        features
    )

    return pd.Series(
        (predictions == -1).astype(int),
        index=df.index
    )


# =====================================================
# METRICS
# =====================================================

def calculate_metrics(
    actual,
    predicted
):

    accuracy = accuracy_score(
        actual,
        predicted
    )

    precision = precision_score(
        actual,
        predicted,
        zero_division=0
    )

    recall = recall_score(
        actual,
        predicted,
        zero_division=0
    )

    f1 = f1_score(
        actual,
        predicted,
        zero_division=0
    )

    matrix = confusion_matrix(
        actual,
        predicted
    )

    return {

        "accuracy": round(
            accuracy,
            4
        ),

        "precision": round(
            precision,
            4
        ),

        "recall": round(
            recall,
            4
        ),

        "f1_score": round(
            f1,
            4
        ),

        "true_negative": int(
            matrix[0][0]
        ),

        "false_positive": int(
            matrix[0][1]
        ),

        "false_negative": int(
            matrix[1][0]
        ),

        "true_positive": int(
            matrix[1][1]
        )
    }


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
        "PHASE 10 - AI MODEL "
        "EVALUATION & PERFORMANCE ANALYSIS"
    )

    print("=" * 70)


    # -------------------------------------------------
    # LOAD DATA
    # -------------------------------------------------

    print(
        "\n1. DATASET LOADING"
    )

    if not DATA_FILE.exists():

        print(
            "Dataset not found!"
        )

        print(
            DATA_FILE
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
    # CHECK GROUND TRUTH
    # -------------------------------------------------

    print(
        "\n2. GROUND TRUTH CHECK"
    )

    if "is_anomaly" not in df.columns:

        print(
            "\nWARNING:"
        )

        print(
            "The dataset does not contain "
            "'is_anomaly' ground-truth labels."
        )

        print(
            "Precision, Recall and F1-score "
            "cannot be scientifically calculated."
        )

        print(
            "\nPhase 10 requires an "
            "'is_anomaly' column."
        )

        return


    actual = (
        df["is_anomaly"]
        .astype(int)
    )

    print(
        "Ground truth column found!"
    )

    print(
        f"Known anomalies: "
        f"{actual.sum()}"
    )


    # -------------------------------------------------
    # Z-SCORE
    # -------------------------------------------------

    print(
        "\n3. Z-SCORE EVALUATION"
    )

    start_time = time.perf_counter()

    z_predictions = (
        zscore_prediction(df)
    )

    z_time = (
        time.perf_counter()
        - start_time
    )

    z_metrics = calculate_metrics(
        actual,
        z_predictions
    )

    print(
        f"Anomalies detected: "
        f"{z_predictions.sum()}"
    )

    print(
        f"Execution time: "
        f"{z_time:.6f} seconds"
    )


    # -------------------------------------------------
    # IQR
    # -------------------------------------------------

    print(
        "\n4. IQR EVALUATION"
    )

    start_time = time.perf_counter()

    iqr_predictions = (
        iqr_prediction(df)
    )

    iqr_time = (
        time.perf_counter()
        - start_time
    )

    iqr_metrics = calculate_metrics(
        actual,
        iqr_predictions
    )

    print(
        f"Anomalies detected: "
        f"{iqr_predictions.sum()}"
    )

    print(
        f"Execution time: "
        f"{iqr_time:.6f} seconds"
    )


    # -------------------------------------------------
    # ISOLATION FOREST
    # -------------------------------------------------

    print(
        "\n5. ISOLATION FOREST EVALUATION"
    )

    start_time = time.perf_counter()

    isolation_predictions = (
        isolation_forest_prediction(
            df
        )
    )

    isolation_time = (
        time.perf_counter()
        - start_time
    )

    isolation_metrics = (
        calculate_metrics(
            actual,
            isolation_predictions
        )
    )

    print(
        f"Anomalies detected: "
        f"{isolation_predictions.sum()}"
    )

    print(
        f"Execution time: "
        f"{isolation_time:.6f} seconds"
    )


    # -------------------------------------------------
    # COMPARISON
    # -------------------------------------------------

    print(
        "\n6. MODEL COMPARISON"
    )

    results = [

        {
            "model": "Z-Score",

            **z_metrics,

            "execution_time":
                round(
                    z_time,
                    6
                )
        },

        {
            "model": "IQR",

            **iqr_metrics,

            "execution_time":
                round(
                    iqr_time,
                    6
                )
        },

        {
            "model":
                "Isolation Forest",

            **isolation_metrics,

            "execution_time":
                round(
                    isolation_time,
                    6
                )
        }

    ]

    comparison = pd.DataFrame(
        results
    )

    print()

    print(
        comparison.to_string(
            index=False
        )
    )


    # -------------------------------------------------
    # FIND BEST MODEL
    # -------------------------------------------------

    best_model = (
        comparison.sort_values(
            by="f1_score",
            ascending=False
        )
        .iloc[0]
    )

    print(
        "\n7. BEST MODEL"
    )

    print(
        f"Model: "
        f"{best_model['model']}"
    )

    print(
        f"F1-Score: "
        f"{best_model['f1_score']}"
    )


    # -------------------------------------------------
    # SAVE REPORT
    # -------------------------------------------------

    report_file = (
        REPORT_DIR
        / "model_performance.csv"
    )

    comparison.to_csv(
        report_file,
        index=False
    )


    # -------------------------------------------------
    # CONFUSION MATRICES
    # -------------------------------------------------

    matrices = []

    model_predictions = {

        "Z-Score":
            z_predictions,

        "IQR":
            iqr_predictions,

        "Isolation Forest":
            isolation_predictions
    }

    for model_name, predictions in (
        model_predictions.items()
    ):

        matrix = confusion_matrix(
            actual,
            predictions
        )

        matrices.append({

            "model":
                model_name,

            "true_negative":
                matrix[0][0],

            "false_positive":
                matrix[0][1],

            "false_negative":
                matrix[1][0],

            "true_positive":
                matrix[1][1]

        })

    matrix_df = pd.DataFrame(
        matrices
    )

    matrix_df.to_csv(
        REPORT_DIR
        / "confusion_matrices.csv",
        index=False
    )


    # -------------------------------------------------
    # FINAL SUMMARY
    # -------------------------------------------------

    print(
        "\n8. PHASE 10 SUMMARY"
    )

    print(
        "--------------------------------------"
    )

    for _, row in comparison.iterrows():

        print(
            f"{row['model']}: "
            f"F1 = {row['f1_score']}, "
            f"Precision = {row['precision']}, "
            f"Recall = {row['recall']}"
        )

    print(
        "--------------------------------------"
    )

    print(
        f"Best model: "
        f"{best_model['model']}"
    )

    print(
        "\nReports saved to:"
    )

    print(
        REPORT_DIR
    )

    print(
        "\nPhase 10 completed successfully! 🚀"
    )


if __name__ == "__main__":

    main()