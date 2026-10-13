import pandas as pd


def check_constant_columns(df: pd.DataFrame) -> dict:
    """
    Detect columns containing only one unique value.
    """

    constant_columns = []

    for column in df.columns:

        unique_count = df[column].nunique(
            dropna=False
        )

        if unique_count <= 1:
            constant_columns.append(column)

    return {
        "constant_columns": constant_columns,
        "count": len(constant_columns)
    }