import pandas as pd


def detect_zscore_anomalies(
    df: pd.DataFrame,
    columns=None,
    threshold: float = 3.0
) -> dict:
    """
    Detect numerical anomalies using Z-Score.

    Z = (X - Mean) / Standard Deviation

    Default threshold = 3.
    """

    if columns is None:
        columns = df.select_dtypes(
            include="number"
        ).columns.tolist()

    results = {}

    for column in columns:

        series = df[column]

        mean = series.mean()
        std = series.std()

        # Prevent division by zero
        if pd.isna(std) or std == 0:

            results[column] = {
                "mean": round(
                    float(mean), 2
                ) if not pd.isna(mean) else None,

                "std": 0,

                "threshold": threshold,

                "anomaly_count": 0,

                "anomalies": []
            }

            continue

        z_scores = (
            (series - mean) / std
        )

        anomaly_mask = (
            z_scores.abs() > threshold
        )

        anomaly_rows = []

        for index in df.index[anomaly_mask]:

            anomaly_rows.append({
                "row": int(index) + 2,

                "value": df.loc[
                    index,
                    column
                ],

                "z_score": round(
                    float(z_scores.loc[index]),
                    3
                )
            })

        results[column] = {

            "mean": round(
                float(mean),
                2
            ),

            "std": round(
                float(std),
                2
            ),

            "threshold": threshold,

            "anomaly_count": len(
                anomaly_rows
            ),

            "anomalies": anomaly_rows
        }

    total_anomalies = sum(
        result["anomaly_count"]
        for result in results.values()
    )

    return {
        "method": "Z-Score",
        "total_anomalies": total_anomalies,
        "columns": results
    }