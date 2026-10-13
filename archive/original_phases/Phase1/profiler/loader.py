from pathlib import Path
import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def load_dataset(file_path: str) -> pd.DataFrame:
    """
    Load a CSV or Excel dataset.

    Parameters:
        file_path: Path of the dataset.

    Returns:
        Pandas DataFrame.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {file_path}"
        )

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {extension}. "
            f"Supported: {SUPPORTED_EXTENSIONS}"
        )

    try:

        if extension == ".csv":
            df = pd.read_csv(path)

        else:
            df = pd.read_excel(path)

    except Exception as error:
        raise RuntimeError(
            f"Failed to load dataset: {error}"
        )

    if df.empty:
        raise ValueError("The dataset is empty.")

    return df