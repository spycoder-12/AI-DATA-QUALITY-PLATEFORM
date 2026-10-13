import pandas as pd


def get_descriptive_statistics(
    df: pd.DataFrame
) -> pd.DataFrame:
    """
    Generate descriptive statistics
    for numerical columns.
    """

    numerical_df = df.select_dtypes(
        include="number"
    )

    if numerical_df.empty:
        return pd.DataFrame()

    return numerical_df.describe().round(2)