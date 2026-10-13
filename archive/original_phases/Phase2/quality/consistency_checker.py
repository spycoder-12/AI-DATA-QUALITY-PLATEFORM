import pandas as pd


ALLOWED_VALUES = {

    "gender": {
        "M",
        "F"
    },

    "city": {
        "Lucknow",
        "Delhi",
        "Kanpur"
    }
}


def check_consistency(df: pd.DataFrame) -> dict:
    """
    Check categorical columns against allowed values.
    """

    results = {}

    for column, allowed_values in ALLOWED_VALUES.items():

        if column not in df.columns:
            continue

        invalid_values = []

        for index, value in df[column].items():

            if pd.isna(value):
                continue

            if value not in allowed_values:

                invalid_values.append({
                    "row": int(index) + 2,
                    "value": value
                })

        results[column] = {
            "allowed_values": list(allowed_values),
            "invalid_values": invalid_values,
            "invalid_count": len(invalid_values)
        }

    total_invalid = sum(
        result["invalid_count"]
        for result in results.values()
    )

    return {
        "total_invalid": total_invalid,
        "columns": results
    }