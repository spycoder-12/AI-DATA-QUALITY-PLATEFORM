import pandas as pd


def select_numeric_features(
    df: pd.DataFrame
) -> list:

    numerical_columns = (
        df.select_dtypes(
            include="number"
        )
        .columns
        .tolist()
    )

    features = []

    for column in numerical_columns:

        if column in [
            "id",
            "is_anomaly"
        ]:

            continue

        if (
            df[column].nunique(
                dropna=True
            ) <= 1
        ):

            continue

        features.append(
            column
        )

    return features


def detect_anomalies(
    df: pd.DataFrame
) -> list:

    features = (
        select_numeric_features(df)
    )

    anomalies = []

    for index, row in df.iterrows():

        strongest_feature = None

        strongest_z_score = 0

        strongest_value = 0

        for feature in features:

            mean = df[
                feature
            ].mean()

            std = df[
                feature
            ].std()

            if (
                pd.isna(std)
                or std == 0
            ):

                continue

            value = row[
                feature
            ]

            z_score = (
                value - mean
            ) / std

            if abs(z_score) > abs(
                strongest_z_score
            ):

                strongest_z_score = (
                    z_score
                )

                strongest_feature = (
                    feature
                )

                strongest_value = (
                    value
                )

        if (
            abs(strongest_z_score)
            >= 3
        ):

            anomalies.append({

                "row":
                    index + 2,

                "feature":
                    strongest_feature,

                "value":
                    float(
                        strongest_value
                    ),

                "z_score":
                    round(
                        float(
                            strongest_z_score
                        ),
                        4
                    )
            })

    return anomalies