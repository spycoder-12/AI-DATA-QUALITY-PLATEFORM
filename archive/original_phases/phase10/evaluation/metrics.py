import pandas as pd

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix
)


def calculate_metrics(
    actual,
    predicted
):
    """
    Calculate classification metrics
    for anomaly detection.
    """

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


def create_comparison_table(
    results
):

    return pd.DataFrame(
        results
    )