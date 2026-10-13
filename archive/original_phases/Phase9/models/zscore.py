import pandas as pd


def detect_zscore(
    df: pd.DataFrame,
    threshold: float = 3.0
) -> pd.DataFrame:

    numeric_df = df.select_dtypes(
        include="number"
    ).copy()

    # Remove ID-like columns
    numeric_df = numeric_df.drop(
        columns=[
            "id",
            "is_anomaly"
        ],
        errors="ignore"
    )

    results = []

    for column in numeric_df.columns:

        mean = numeric_df[column].mean()

        std = numeric_df[column].std()

        if pd.isna(std) or std == 0:
            continue

        z_scores = (
            numeric_df[column] - mean
        ) / std

        anomaly_indices = (
            z_scores.abs() >= threshold
        )

        for index in numeric_df[
            anomaly_indices
        ].index:

            results.append({

                "row": int(index + 2),

                "feature": column,

                "value": float(
                    numeric_df.loc[
                        index,
                        column
                    ]
                ),

                "score": round(
                    float(
                        z_scores.loc[index]
                    ),
                    4
                )

            })

    return pd.DataFrame(
        results
    )