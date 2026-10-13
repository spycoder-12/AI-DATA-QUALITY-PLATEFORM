import pandas as pd


def check_missing_values(df: pd.DataFrame) -> dict:
    """
    Analyze missing values in every column.
    """

    total_rows = len(df)

    results = {}

    for column in df.columns:

        missing_count = int(df[column].isna().sum())

        if total_rows > 0:
            missing_percentage = round(
                (missing_count / total_rows) * 100,
                2
            )
        else:
            missing_percentage = 0.0

        if missing_percentage == 0:
            severity = "GOOD"

        elif missing_percentage < 5:
            severity = "LOW"

        elif missing_percentage < 20:
            severity = "MEDIUM"

        else:
            severity = "HIGH"

        results[column] = {
            "missing_count": missing_count,
            "missing_percentage": missing_percentage,
            "severity": severity
        }

    total_missing = int(df.isna().sum().sum())

    return {
        "total_missing": total_missing,
        "columns": results
    }