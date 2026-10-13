import pandas as pd


def check_range(
    df: pd.DataFrame,
    column: str,
    minimum=None,
    maximum=None
) -> list:
    """
    Check whether values fall inside a valid range.
    """

    if column not in df.columns:
        return []

    invalid_rows = []

    for index, value in df[column].items():

        # Missing values are handled separately
        if pd.isna(value):
            continue

        invalid = False

        if minimum is not None and value < minimum:
            invalid = True

        if maximum is not None and value > maximum:
            invalid = True

        if invalid:
            invalid_rows.append({
                "row": int(index) + 2,
                "value": value
            })

    return invalid_rows


def check_validity(df: pd.DataFrame) -> dict:
    """
    Check predefined numerical validity rules.
    """

    results = {}

    # Age
    if "age" in df.columns:

        results["age"] = check_range(
            df,
            "age",
            minimum=0,
            maximum=120
        )

    # Score
    if "score" in df.columns:

        results["score"] = check_range(
            df,
            "score",
            minimum=0,
            maximum=100
        )

    # Income
    if "income" in df.columns:

        results["income"] = check_range(
            df,
            "income",
            minimum=0
        )

    total_invalid = sum(
        len(values)
        for values in results.values()
    )

    return {
        "total_invalid": total_invalid,
        "columns": results
    }