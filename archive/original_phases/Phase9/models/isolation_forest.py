import pandas as pd

from sklearn.ensemble import (
    IsolationForest
)


def detect_isolation_forest(
    df: pd.DataFrame,
    contamination: float = "auto"
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

    # Remove columns with no useful variation
    numeric_df = numeric_df.loc[
        :,
        numeric_df.nunique() > 1
    ]

    if numeric_df.empty:

        return pd.DataFrame(
            columns=[
                "row",
                "feature",
                "value",
                "score"
            ]
        )

    # Fill missing numeric values
    numeric_df = numeric_df.fillna(
        numeric_df.median()
    )

    model = IsolationForest(

        contamination=contamination,

        random_state=42,

        n_estimators=200
    )

    predictions = model.fit_predict(
        numeric_df
    )

    scores = model.decision_function(
        numeric_df
    )

    results = []

    for position, prediction in enumerate(
        predictions
    ):

        if prediction == -1:

            row_index = numeric_df.index[
                position
            ]

            # Find the feature contributing
            # most strongly to this anomaly
            row = numeric_df.loc[
                row_index
            ]

            median_values = (
                numeric_df.median()
            )

            deviations = (
                (row - median_values)
                .abs()
            )

            strongest_feature = (
                deviations.idxmax()
            )

            results.append({

                "row": int(
                    row_index + 2
                ),

                "feature":
                    strongest_feature,

                "value": float(
                    row[
                        strongest_feature
                    ]
                ),

                "score": round(
                    float(
                        scores[position]
                    ),
                    4
                )

            })

    return pd.DataFrame(
        results
    )