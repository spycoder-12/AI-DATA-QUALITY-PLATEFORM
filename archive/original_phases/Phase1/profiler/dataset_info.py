import pandas as pd


def get_dataset_info(df: pd.DataFrame) -> dict:
    """
    Get basic information about the dataset.
    """

    data_types = {
        column: str(dtype)
        for column, dtype in df.dtypes.items()
    }

    numerical_columns = df.select_dtypes(
        include="number"
    ).columns.tolist()

    categorical_columns = df.select_dtypes(
        include=["object", "category"]
    ).columns.tolist()

    return {
        "rows": df.shape[0],
        "columns": df.shape[1],
        "memory_usage_mb": round(
            df.memory_usage(deep=True).sum()
            / (1024 * 1024),
            2
        ),
        "column_names": df.columns.tolist(),
        "data_types": data_types,
        "numerical_columns": numerical_columns,
        "categorical_columns": categorical_columns,
    }