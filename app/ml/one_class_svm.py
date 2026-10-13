"""One-Class SVM wrapper."""
from __future__ import annotations

import numpy as np
from sklearn.svm import OneClassSVM


def run(X_fit: np.ndarray, X_all: np.ndarray, nu: float = 0.05, kernel: str = "rbf"):
    nu = float(min(max(nu, 0.001), 0.5))
    model = OneClassSVM(kernel=kernel, nu=nu, gamma="scale")
    model.fit(X_fit)
    flags = model.predict(X_all) == -1
    scores = -model.decision_function(X_all)
    return flags, scores, {"nu": nu, "kernel": kernel, "gamma": "scale"}
