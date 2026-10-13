import time

import pandas as pd

from .metrics import calculate_metrics


def evaluate_model(
    model_name,
    actual_labels,
    predicted_labels,
    start_time
):
    """
    Evaluate a single anomaly detection model.
    """

    execution_time = (
        time.perf_counter()
        - start_time
    )

    metrics = calculate_metrics(
        actual_labels,
        predicted_labels
    )

    anomaly_count = int(
        sum(predicted_labels)
    )

    result = {
        "model": model_name,

        "anomaly_count":
            anomaly_count,

        "execution_time_seconds":
            round(
                execution_time,
                6
            ),

        **metrics
    }

    return result


def create_evaluation_dataframe(
    results
):
    """
    Convert model results into
    a pandas DataFrame.
    """

    return pd.DataFrame(
        results
    )