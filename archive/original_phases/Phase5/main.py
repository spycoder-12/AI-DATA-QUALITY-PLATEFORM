from pathlib import Path

import time

import pandas as pd

from sklearn.ensemble import (
    IsolationForest
)

from sklearn.neighbors import (
    LocalOutlierFactor
)

from sklearn.svm import (
    OneClassSVM
)

from sklearn.impute import (
    SimpleImputer
)

from sklearn.preprocessing import (
    StandardScaler
)

from evaluation.metrics import (
    calculate_metrics
)

from evaluation.evaluator import (
    evaluate_model,
    create_evaluation_dataframe
)

from evaluation.agreement import (
    create_agreement_matrix
)


# =====================================================
# CONFIGURATION
# =====================================================

DATASET_PATH = Path(
    "data/evaluation_dataset.csv"
)

REPORT_PATH = Path(
    "reports/model_comparison.csv"
)

AGREEMENT_PATH = Path(
    "reports/model_agreement.csv"
)


# =====================================================
# HELPER
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
# FEATURE PREPARATION
# =====================================================

def prepare_data(df):

    numerical_columns = (
        df.select_dtypes(
            include="number"
        )
        .columns
        .tolist()
    )

    feature_columns = []

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

        feature_columns.append(
            column
        )

    X = df[
        feature_columns
    ].copy()

    # Convert to numeric
    for column in feature_columns:

        X[column] = pd.to_numeric(
            X[column],
            errors="coerce"
        )

    # Missing values
    imputer = SimpleImputer(
        strategy="median"
    )

    X_imputed = imputer.fit_transform(
        X
    )

    # Standardization
    scaler = StandardScaler()

    X_scaled = scaler.fit_transform(
        X_imputed
    )

    return (
        X_scaled,
        feature_columns
    )


# =====================================================
# IQR
# =====================================================

def detect_iqr(
    df,
    feature_columns
):

    predictions = []

    for index in df.index:

        row_is_anomaly = False

        for column in feature_columns:

            series = df[
                column
            ]

            q1 = series.quantile(
                0.25
            )

            q3 = series.quantile(
                0.75
            )

            iqr = q3 - q1

            lower = q1 - (
                1.5 * iqr
            )

            upper = q3 + (
                1.5 * iqr
            )

            value = df.loc[
                index,
                column
            ]

            if (
                value < lower
                or value > upper
            ):

                row_is_anomaly = True

                break

        predictions.append(
            1 if row_is_anomaly else 0
        )

    return predictions


# =====================================================
# Z-SCORE
# =====================================================

def detect_zscore(
    df,
    feature_columns,
    threshold=3.0
):

    predictions = []

    statistics = {}

    for column in feature_columns:

        mean = df[
            column
        ].mean()

        std = df[
            column
        ].std()

        statistics[column] = (
            mean,
            std
        )

    for index in df.index:

        row_is_anomaly = False

        for column in feature_columns:

            mean, std = statistics[
                column
            ]

            if pd.isna(std) or std == 0:

                continue

            value = df.loc[
                index,
                column
            ]

            z_score = (
                (value - mean)
                / std
            )

            if abs(z_score) > threshold:

                row_is_anomaly = True

                break

        predictions.append(
            1 if row_is_anomaly else 0
        )

    return predictions


# =====================================================
# MAIN
# =====================================================

def main():

    print_header(
        "AI DATA QUALITY & ANOMALY DETECTION ENGINE"
    )

    print(
        "PHASE 5 - MODEL COMPARISON & EVALUATION"
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
    # 2. PREPARE DATA
    # =================================================

    print_header(
        "2. DATA PREPROCESSING"
    )

    X, feature_columns = (
        prepare_data(df)
    )

    print(
        "Features used:"
    )

    for column in feature_columns:

        print(
            f"  ✓ {column}"
        )

    actual_labels = (
        df[
            "is_anomaly"
        ]
        .astype(int)
        .tolist()
    )

    # =================================================
    # 3. STORE PREDICTIONS
    # =================================================

    all_predictions = {}

    results = []

    # =================================================
    # 4. IQR
    # =================================================

    print_header(
        "3. IQR"
    )

    start = time.perf_counter()

    iqr_predictions = detect_iqr(
        df,
        feature_columns
    )

    iqr_result = evaluate_model(
        "IQR",
        actual_labels,
        iqr_predictions,
        start
    )

    all_predictions[
        "IQR"
    ] = iqr_predictions

    results.append(
        iqr_result
    )

    print(
        f"Anomalies: "
        f"{iqr_result['anomaly_count']}"
    )

    # =================================================
    # 5. Z-SCORE
    # =================================================

    print_header(
        "4. Z-SCORE"
    )

    start = time.perf_counter()

    zscore_predictions = (
        detect_zscore(
            df,
            feature_columns
        )
    )

    zscore_result = evaluate_model(
        "Z-Score",
        actual_labels,
        zscore_predictions,
        start
    )

    all_predictions[
        "Z-Score"
    ] = zscore_predictions

    results.append(
        zscore_result
    )

    print(
        f"Anomalies: "
        f"{zscore_result['anomaly_count']}"
    )

    # =================================================
    # 6. ISOLATION FOREST
    # =================================================

    print_header(
        "5. ISOLATION FOREST"
    )

    start = time.perf_counter()

    isolation_model = (
        IsolationForest(
            contamination=0.05,
            random_state=42
        )
    )

    isolation_output = (
        isolation_model.fit_predict(
            X
        )
    )

    isolation_predictions = [
        1 if value == -1
        else 0
        for value in isolation_output
    ]

    isolation_result = evaluate_model(
        "Isolation Forest",
        actual_labels,
        isolation_predictions,
        start
    )

    all_predictions[
        "Isolation Forest"
    ] = isolation_predictions

    results.append(
        isolation_result
    )

    print(
        f"Anomalies: "
        f"{isolation_result['anomaly_count']}"
    )

    # =================================================
    # 7. LOF
    # =================================================

    print_header(
        "6. LOCAL OUTLIER FACTOR"
    )

    start = time.perf_counter()

    n_neighbors = min(
        20,
        len(df) - 1
    )

    lof_model = (
        LocalOutlierFactor(
            n_neighbors=n_neighbors,
            contamination=0.05
        )
    )

    lof_output = (
        lof_model.fit_predict(
            X
        )
    )

    lof_predictions = [
        1 if value == -1
        else 0
        for value in lof_output
    ]

    lof_result = evaluate_model(
        "Local Outlier Factor",
        actual_labels,
        lof_predictions,
        start
    )

    all_predictions[
        "Local Outlier Factor"
    ] = lof_predictions

    results.append(
        lof_result
    )

    print(
        f"Anomalies: "
        f"{lof_result['anomaly_count']}"
    )

    # =================================================
    # 8. ONE-CLASS SVM
    # =================================================

    print_header(
        "7. ONE-CLASS SVM"
    )

    start = time.perf_counter()

    svm_model = OneClassSVM(
        kernel="rbf",
        nu=0.05
    )

    svm_output = (
        svm_model.fit_predict(
            X
        )
    )

    svm_predictions = [
        1 if value == -1
        else 0
        for value in svm_output
    ]

    svm_result = evaluate_model(
        "One-Class SVM",
        actual_labels,
        svm_predictions,
        start
    )

    all_predictions[
        "One-Class SVM"
    ] = svm_predictions

    results.append(
        svm_result
    )

    print(
        f"Anomalies: "
        f"{svm_result['anomaly_count']}"
    )

    # =================================================
    # 9. MODEL COMPARISON
    # =================================================

    print_header(
        "8. MODEL PERFORMANCE COMPARISON"
    )

    comparison_df = (
        create_evaluation_dataframe(
            results
        )
    )

    print(
        comparison_df.to_string(
            index=False
        )
    )

    # =================================================
    # 10. BEST MODEL
    # =================================================

    best_model = (
        comparison_df
        .sort_values(
            "f1_score",
            ascending=False
        )
        .iloc[0]
    )

    print_header(
        "9. BEST PERFORMING MODEL"
    )

    print(
        f"Model     : "
        f"{best_model['model']}"
    )

    print(
        f"Precision : "
        f"{best_model['precision']}"
    )

    print(
        f"Recall    : "
        f"{best_model['recall']}"
    )

    print(
        f"F1 Score  : "
        f"{best_model['f1_score']}"
    )

    # =================================================
    # 11. AGREEMENT
    # =================================================

    print_header(
        "10. MODEL AGREEMENT"
    )

    agreement_df = (
        create_agreement_matrix(
            all_predictions
        )
    )

    print(
        agreement_df.to_string()
    )

    # =================================================
    # 12. SAVE REPORTS
    # =================================================

    print_header(
        "11. REPORT GENERATION"
    )

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    comparison_df.to_csv(
        REPORT_PATH,
        index=False
    )

    agreement_df.to_csv(
        AGREEMENT_PATH
    )

    print(
        f"Performance report:"
    )

    print(
        REPORT_PATH
    )

    print(
        f"\nAgreement report:"
    )

    print(
        AGREEMENT_PATH
    )

    # =================================================
    # FINAL
    # =================================================

    print_header(
        "PHASE 5 SUMMARY"
    )

    print(
        "Models evaluated:"
    )

    for model in all_predictions:

        print(
            f"  ✓ {model}"
        )

    print(
        f"\nBest model: "
        f"{best_model['model']}"
    )

    print(
        "\nPhase 5 completed successfully! 🚀"
    )


if __name__ == "__main__":

    main()