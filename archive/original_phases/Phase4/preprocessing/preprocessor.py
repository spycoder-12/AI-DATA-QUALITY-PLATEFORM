import pandas as pd

from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler


def prepare_features(
    df: pd.DataFrame,
    columns: list[str]
):
    """
    Prepare numerical features for ML anomaly detection.

    Steps:
    1. Select required columns
    2. Convert values to numeric
    3. Handle missing values
    4. Standardize features
    """

    data = df[columns].copy()

    # Make sure all values are numeric
    for column in columns:

        data[column] = pd.to_numeric(
            data[column],
            errors="coerce"
        )

    # Replace missing values
    imputer = SimpleImputer(
        strategy="median"
    )

    imputed_data = imputer.fit_transform(
        data
    )

    # Standardize features
    scaler = StandardScaler()

    scaled_data = scaler.fit_transform(
        imputed_data
    )

    return scaled_data