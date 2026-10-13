from sklearn.svm import OneClassSVM


def detect_one_class_svm(
    X,
    nu=0.05,
    kernel="rbf"
) -> dict:
    """
    Detect anomalies using One-Class SVM.

    Output:
        1  = normal
       -1  = anomaly
    """

    model = OneClassSVM(
        kernel=kernel,
        nu=nu
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
        "model": "One-Class SVM",

        "predictions": predictions,

        "scores": scores,

        "anomaly_count":
            len(anomaly_indices),

        "anomalies":
            anomaly_indices
    }