import pandas as pd


def analyze_duplicates(df: pd.DataFrame) -> dict:
    """
    Analyze duplicate rows.
    """

    duplicate_mask = df.duplicated()

    duplicate_count = int(
        duplicate_mask.sum()
    )

    total_rows = len(df)

    if total_rows > 0:
        duplicate_percentage = round(
            (duplicate_count / total_rows) * 100,
            2
        )
    else:
        duplicate_percentage = 0.0

    return {
        "duplicate_count": duplicate_count,
        "duplicate_percentage": duplicate_percentage
    }