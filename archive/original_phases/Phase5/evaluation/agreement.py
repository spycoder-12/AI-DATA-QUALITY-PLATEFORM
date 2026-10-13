import pandas as pd


def create_agreement_matrix(
    predictions
):
    """
    Create a model agreement matrix.

    predictions format:

    {
        "IQR": [0, 1, 0, ...],
        "Z-Score": [0, 1, 0, ...],
        ...
    }
    """

    model_names = list(
        predictions.keys()
    )

    matrix = pd.DataFrame(
        index=model_names,
        columns=model_names,
        dtype=float
    )

    for model_a in model_names:

        for model_b in model_names:

            values_a = predictions[
                model_a
            ]

            values_b = predictions[
                model_b
            ]

            agreement = sum(
                a == b
                for a, b in zip(
                    values_a,
                    values_b
                )
            ) / len(values_a)

            matrix.loc[
                model_a,
                model_b
            ] = round(
                agreement,
                4
            )

    return matrix