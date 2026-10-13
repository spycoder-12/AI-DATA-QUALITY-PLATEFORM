import pandas as pd

from sklearn.ensemble import IsolationForest


def detect_isolation_forest(
    X,
    contamination="auto",
    random_state=42
) -> dict:
    """
    Detect anomalies using Isolation Forest.

    Output:
        1  = normal
       -1  = anomaly
    """

    model = IsolationForest(
        contamination=contamination,
        random_state=random_state
    )

    predictions = model.fit_predict(X)

    scores = model.decision_function(X)

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
        "model": "Isolation Forest",

        "predictions": predictions,

        "scores": scores,

        "anomaly_count":
            len(anomaly_indices),

        "anomalies":
            anomaly_indices
    }