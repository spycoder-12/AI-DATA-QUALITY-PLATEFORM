from sklearn.neighbors import LocalOutlierFactor


def detect_lof(
    X,
    n_neighbors=20,
    contamination="auto"
) -> dict:
    """
    Detect anomalies using Local Outlier Factor.

    LOF compares the local density
    of each observation with its neighbors.

    Output:
        1  = normal
       -1  = anomaly
    """

    model = LocalOutlierFactor(
        n_neighbors=n_neighbors,
        contamination=contamination
    )

    predictions = model.fit_predict(X)

    scores = model.negative_outlier_factor_

    anomaly_indices = []

    for index, prediction in enumerate(
        predictions
    ):

        if prediction == -1:

            anomaly_indices.append({
                "row": index + 2,
                "score": round(
                    float(scores[index]),
                    4
                )
            })

    return {
        "model": "Local Outlier Factor",

        "predictions": predictions,

        "scores": scores,

        "anomaly_count":
            len(anomaly_indices),

        "anomalies":
            anomaly_indices
    }