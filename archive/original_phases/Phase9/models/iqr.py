import pandas as pd


def detect_iqr(
    df: pd.DataFrame
) -> pd.DataFrame:

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

    results = []

    for column in numeric_df.columns:

        q1 = numeric_df[
            column
        ].quantile(0.25)

        q3 = numeric_df[
            column
        ].quantile(0.75)

        iqr = q3 - q1

        if iqr == 0:
            continue

        lower_bound = (
            q1 - 1.5 * iqr
        )

        upper_bound = (
            q3 + 1.5 * iqr
        )

        anomaly_indices = (
            (numeric_df[column] < lower_bound)
            |
            (numeric_df[column] > upper_bound)
        )

        for index in numeric_df[
            anomaly_indices
        ].index:

            value = numeric_df.loc[
                index,
                column
            ]

            results.append({

                "row": int(index + 2),

                "feature": column,

                "value": float(value),

                "score": round(
                    float(
                        value
                    ),
                    4
                )

            })

    return pd.DataFrame(
        results
    )