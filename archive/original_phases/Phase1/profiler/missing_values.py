import pandas as pd


def analyze_missing_values(df: pd.DataFrame) -> dict:
    """
    Analyze missing values in every column.
    """

    missing_count = df.isnull().sum()

    missing_percentage = (
        df.isnull().mean() * 100
    ).round(2)

    columns = {}

    for column in df.columns:

        columns[column] = {
            "missing_count": int(
                missing_count[column]
            ),
            "missing_percentage": float(
                missing_percentage[column]
            )
        }

    total_missing = int(
        df.isnull().sum().sum()
    )

    return {
        "total_missing_values": total_missing,
        "columns": columns
    }