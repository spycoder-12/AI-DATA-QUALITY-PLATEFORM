import pandas as pd


def check_duplicates(df: pd.DataFrame) -> dict:
    """
    Detect duplicate rows.
    """

    duplicate_mask = df.duplicated()

    duplicate_count = int(duplicate_mask.sum())

    total_rows = len(df)

    if total_rows > 0:
        duplicate_percentage = round(
            (duplicate_count / total_rows) * 100,
            2
        )
    else:
        duplicate_percentage = 0.0

    if duplicate_count == 0:
        severity = "GOOD"

    elif duplicate_percentage < 5:
        severity = "LOW"

    elif duplicate_percentage < 15:
        severity = "MEDIUM"

    else:
        severity = "HIGH"

    return {
        "duplicate_count": duplicate_count,
        "duplicate_percentage": duplicate_percentage,
        "severity": severity
    }