import pandas as pd


def detect_iqr_anomalies(
    df: pd.DataFrame,
    columns=None,
    multiplier: float = 1.5
) -> dict:
    """
    Detect numerical anomalies using the IQR method.

    Formula:

        Lower Bound = Q1 - multiplier * IQR
        Upper Bound = Q3 + multiplier * IQR

    Default multiplier = 1.5
    """

    if columns is None:
        columns = df.select_dtypes(
            include="number"
        ).columns.tolist()

    results = {}

    for column in columns:

        series = df[column].dropna()

        if series.empty:
            continue

        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)

        iqr = q3 - q1

        lower_bound = q1 - (
            multiplier * iqr
        )

        upper_bound = q3 + (
            multiplier * iqr
        )

        anomaly_mask = (
            (df[column] < lower_bound)
            |
            (df[column] > upper_bound)
        )

        anomaly_rows = []

        for index in df.index[anomaly_mask]:

            anomaly_rows.append({
                "row": int(index) + 2,
                "value": df.loc[index, column]
            })

        results[column] = {
            "q1": round(float(q1), 2),
            "q3": round(float(q3), 2),
            "iqr": round(float(iqr), 2),
            "lower_bound": round(
                float(lower_bound), 2
            ),
            "upper_bound": round(
                float(upper_bound), 2
            ),
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
        "method": "IQR",
        "total_anomalies": total_anomalies,
        "columns": results
    }