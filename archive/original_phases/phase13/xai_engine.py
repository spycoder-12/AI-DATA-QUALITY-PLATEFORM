import pandas as pd
import numpy as np


def explain_anomalies(df: pd.DataFrame):

    explanations = []

    numeric_columns = (
        df.select_dtypes(include="number")
        .columns
        .tolist()
    )

    # Do not use ID or ground-truth label
    numeric_columns = [
        column
        for column in numeric_columns
        if column not in ["id", "is_anomaly"]
    ]

    for index, row in df.iterrows():

        strongest_feature = None
        strongest_z_score = 0
        strongest_value = None

        for feature in numeric_columns:

            mean = df[feature].mean()
            std = df[feature].std()

            if pd.isna(std) or std == 0:
                continue

            value = row[feature]

            if pd.isna(value):
                continue

            z_score = (
                (value - mean) / std
            )

            if abs(z_score) > abs(
                strongest_z_score
            ):

                strongest_z_score = z_score
                strongest_feature = feature
                strongest_value = value

        if abs(strongest_z_score) >= 3:

            if abs(strongest_z_score) >= 5:
                severity = "CRITICAL"

            elif abs(strongest_z_score) >= 4:
                severity = "HIGH"

            else:
                severity = "MEDIUM"

            if strongest_z_score > 0:
                direction = "higher"
            else:
                direction = "lower"

            reason = (
                f"{strongest_feature} has a value of "
                f"{strongest_value:.2f}, which is "
                f"{direction} than the normal dataset "
                f"distribution."
            )

            recommendation = (
                "Verify the original data source "
                "and investigate this record for "
                "possible data-entry or data-quality errors."
            )

            explanations.append({

                "row_number":
                    index + 2,

                "feature":
                    strongest_feature,

                "value":
                    float(strongest_value),

                "z_score":
                    round(
                        float(strongest_z_score),
                        4
                    ),

                "severity":
                    severity,

                "reason":
                    reason,

                "recommendation":
                    recommendation
            })

    return explanations