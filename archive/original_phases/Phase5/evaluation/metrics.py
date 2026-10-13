import numpy as np

from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    accuracy_score
)


def calculate_metrics(
    actual,
    predicted
):
    """
    Calculate classification metrics
    for anomaly detection.

    Actual:
        0 = normal
        1 = anomaly

    Predicted:
        0 = normal
        1 = anomaly
    """

    actual = np.asarray(actual)
    predicted = np.asarray(predicted)

    return {
        "accuracy": round(
            accuracy_score(
                actual,
                predicted
            ),
            4
        ),

        "precision": round(
            precision_score(
                actual,
                predicted,
                zero_division=0
            ),
            4
        ),

        "recall": round(
            recall_score(
                actual,
                predicted,
                zero_division=0
            ),
            4
        ),

        "f1_score": round(
            f1_score(
                actual,
                predicted,
                zero_division=0
            ),
            4
        )
    }