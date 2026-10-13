import pandas as pd


def create_anomaly_summary(
    df: pd.DataFrame,
    iqr_results: dict,
    zscore_results: dict
) -> pd.DataFrame:
    """
    Combine IQR and Z-Score results
    into a single DataFrame.
    """

    columns = set()

    columns.update(
        iqr_results["columns"].keys()
    )

    columns.update(
        zscore_results["columns"].keys()
    )

    rows = []

    for column in sorted(columns):

        iqr_data = iqr_results[
            "columns"
        ].get(column, {})

        zscore_data = zscore_results[
            "columns"
        ].get(column, {})

        iqr_count = iqr_data.get(
            "anomaly_count",
            0
        )

        zscore_count = zscore_data.get(
            "anomaly_count",
            0
        )

        rows.append({

            "column": column,

            "iqr_anomalies": iqr_count,

            "zscore_anomalies":
                zscore_count,

            "total_detections":
                iqr_count + zscore_count
        })

    return pd.DataFrame(rows)