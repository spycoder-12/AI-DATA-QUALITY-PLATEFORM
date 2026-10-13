import pandas as pd


def compare_models(
    zscore_results: pd.DataFrame,
    iqr_results: pd.DataFrame,
    isolation_results: pd.DataFrame
) -> pd.DataFrame:

    comparison = [

        {
            "model": "Z-Score",

            "anomalies_detected":
                len(zscore_results)
        },

        {
            "model": "IQR",

            "anomalies_detected":
                len(iqr_results)
        },

        {
            "model": "Isolation Forest",

            "anomalies_detected":
                len(isolation_results)
        }

    ]

    return pd.DataFrame(
        comparison
    )