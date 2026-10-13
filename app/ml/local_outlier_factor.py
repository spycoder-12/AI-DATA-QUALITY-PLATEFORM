"""Local Outlier Factor wrapper."""
from __future__ import annotations

import numpy as np
from sklearn.neighbors import LocalOutlierFactor


def run(X_fit: np.ndarray, X_all: np.ndarray, n_neighbors: int = 20, contamination="auto"):
    """LOF compares each point's local density with its neighbours' density.

    When all rows were used for fitting we use the classic ``fit_predict``; when
    the fit set is a sample (very large data) LOF runs in *novelty* mode so the
    remaining rows can still be scored.
    """
    n_neighbors = int(max(2, min(n_neighbors, len(X_fit) - 1)))
    same = X_fit is X_all or len(X_fit) == len(X_all)
    if same:
        model = LocalOutlierFactor(n_neighbors=n_neighbors, contamination=contamination)
        flags = model.fit_predict(X_all) == -1
        scores = -model.negative_outlier_factor_
    else:
        model = LocalOutlierFactor(n_neighbors=n_neighbors, contamination=contamination, novelty=True)
        model.fit(X_fit)
        flags = model.predict(X_all) == -1
        scores = -model.score_samples(X_all)
    scores = np.nan_to_num(scores, nan=0.0, posinf=1e6, neginf=0.0)
    return flags, scores, {"n_neighbors": n_neighbors, "contamination": contamination,
                           "mode": "fit_predict" if same else "novelty"}
