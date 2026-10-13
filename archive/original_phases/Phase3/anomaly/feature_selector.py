import pandas as pd


def select_numerical_features(
    df: pd.DataFrame
) -> tuple[list[str], list[str]]:
    """
    Select useful numerical features.

    Returns:

        usable_features
        excluded_features
    """

    numerical_columns = df.select_dtypes(
        include="number"
    ).columns.tolist()

    usable_features = []
    excluded_features = []

    for column in numerical_columns:

        column_lower = column.lower()

        # -----------------------------------------
        # Exclude ID-like columns
        # -----------------------------------------

        if (
            column_lower == "id"
            or column_lower.endswith("_id")
            or column_lower.startswith("id_")
        ):

            excluded_features.append(
                column
            )

            continue

        # -----------------------------------------
        # Exclude constant columns
        # -----------------------------------------

        if df[column].nunique(
            dropna=True
        ) <= 1:

            excluded_features.append(
                column
            )

            continue

        usable_features.append(
            column
        )

    return (
        usable_features,
        excluded_features
    )