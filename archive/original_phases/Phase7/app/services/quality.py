import pandas as pd


def analyze_quality(
    df: pd.DataFrame
) -> dict:

    rows = len(df)

    columns = len(df.columns)

    missing_values = int(
        df.isnull()
        .sum()
        .sum()
    )

    duplicate_rows = int(
        df.duplicated()
        .sum()
    )

    return {
        "rows": rows,

        "columns": columns,

        "missing_values":
            missing_values,

        "duplicate_rows":
            duplicate_rows
    }