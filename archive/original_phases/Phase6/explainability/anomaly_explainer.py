import pandas as pd


def calculate_z_scores(
    df: pd.DataFrame,
    feature_columns: list[str]
) -> pd.DataFrame:

    result = df.copy()

    for column in feature_columns:

        mean = df[column].mean()

        std = df[column].std()

        if std == 0 or pd.isna(std):

            result[
                f"{column}_zscore"
            ] = 0

        else:

            result[
                f"{column}_zscore"
            ] = (
                df[column] - mean
            ) / std

    return result


def explain_row(
    df: pd.DataFrame,
    row_index: int,
    feature_columns: list[str]
) -> dict:

    row = df.loc[row_index]

    explanations = []

    strongest_feature = None

    strongest_score = 0

    for column in feature_columns:

        mean = df[column].mean()

        std = df[column].std()

        if std == 0 or pd.isna(std):

            continue

        value = row[column]

        z_score = (
            value - mean
        ) / std

        absolute_score = abs(
            z_score
        )

        if absolute_score > strongest_score:

            strongest_score = (
                absolute_score
            )

            strongest_feature = column

        if absolute_score >= 3:

            direction = (
                "higher"
                if z_score > 0
                else "lower"
            )

            explanations.append({
                "feature": column,
                "value": round(
                    float(value),
                    4
                ),
                "z_score": round(
                    float(z_score),
                    4
                ),
                "reason":
                    f"{column} is unusually "
                    f"{direction} than the "
                    f"normal dataset range."
            })

    return {
        "row": row_index + 2,

        "strongest_feature":
            strongest_feature,

        "strongest_z_score":
            round(
                float(strongest_score),
                4
            ),

        "explanations":
            explanations
    }