"""Isolation Forest wrapper."""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest


def parse_contamination(value):
    """'auto' or a float in (0, 0.5]."""
    if isinstance(value, str) and value.strip().lower() == "auto":
        return "auto"
    try:
        return min(max(float(value), 1e-4), 0.5)
    except (TypeError, ValueError):
        return "auto"


def run(X_fit: np.ndarray, X_all: np.ndarray, contamination="auto", random_state: int = 42):
    """Fit on ``X_fit`` and score every row of ``X_all``.

    Returns (flags: bool ndarray, scores: ndarray where higher = more anomalous, params).
    """
    contamination = parse_contamination(contamination)
    model = IsolationForest(n_estimators=200, contamination=contamination,
                            random_state=random_state, n_jobs=1)
    model.fit(X_fit)
    flags = model.predict(X_all) == -1
    scores = -model.decision_function(X_all)
    return flags, scores, {"n_estimators": 200, "contamination": contamination,
                           "random_state": random_state}
