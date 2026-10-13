"""ML anomaly detection: preprocessing + Isolation Forest, LOF, One-Class SVM.

Preprocessing (done ONCE and shared by all three models):
  1. features come from the shared selector (no ids / constants / labels);
  2. features with more than 50 % missing values are dropped (imputing them
     would mostly invent data);
  3. remaining missing values -> median imputation;
  4. optional frequency-encoding of low-cardinality categoricals (off by default);
  5. StandardScaler; zero-variance columns are removed after imputation.

The detectors never raise: an unsuitable dataset produces ``SKIPPED`` results
with a plain-language message instead of an exception.
"""
from __future__ import annotations

import time
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from app.config import AnalysisConfig
from app.ml import isolation_forest, local_outlier_factor, one_class_svm
from app.services.anomaly import DetectorResult
from app.utils.helpers import is_text_series, rnd

MODEL_NAMES = ["Isolation Forest", "Local Outlier Factor", "One-Class SVM"]


def prepare_features(df: pd.DataFrame, features: List[str], cfg: AnalysisConfig,
                     kinds: Dict[str, str] | None = None, stats: Dict[str, dict] | None = None) -> Tuple[np.ndarray | None, List[str], List[str]]:
    """Return (scaled matrix | None, used_feature_names, notes)."""
    notes: List[str] = []
    frame = pd.DataFrame(index=df.index)
    for f in features:
        col = (stats[f]["values"] if stats and f in stats
               else pd.to_numeric(df[f], errors="coerce").replace([np.inf, -np.inf], np.nan))
        if col.isna().mean() > 0.5:
            notes.append(f"'{f}' was left out of ML analysis (more than 50% missing).")
            continue
        frame[f] = col
    if cfg.ml_include_categorical:
        for c in df.columns:
            if (is_text_series(df[c]) and (kinds or {}).get(c) == "categorical"
                    and 2 <= df[c].nunique() <= 20 and df[c].isna().mean() <= 0.5):
                freq = df[c].map(df[c].value_counts(normalize=True))
                frame[f"{c} (frequency)"] = freq
                notes.append(f"Categorical column '{c}' was frequency-encoded so rare categories stand out.")
    if frame.shape[1] > cfg.ml_max_features:
        keep = frame.var().sort_values(ascending=False).index[:cfg.ml_max_features]
        notes.append(f"Only the {cfg.ml_max_features} highest-variance features were used.")
        frame = frame[list(keep)]
    if frame.shape[1] == 0:
        return None, [], notes
    imputed = SimpleImputer(strategy="median").fit_transform(frame)
    imputed = pd.DataFrame(imputed, columns=frame.columns, index=frame.index)
    nonconst = imputed.columns[imputed.nunique() > 1]
    if len(nonconst) < imputed.shape[1]:
        notes.append("Features that became constant after imputation were removed.")
    imputed = imputed[list(nonconst)]
    if imputed.shape[1] == 0:
        return None, [], notes
    scaled = StandardScaler().fit_transform(imputed)
    return scaled, list(imputed.columns), notes


def run_ml_detection(df: pd.DataFrame, features: List[str], cfg: AnalysisConfig,
                     kinds: Dict[str, str] | None = None, stats: Dict[str, dict] | None = None) -> Tuple[List[DetectorResult], dict]:
    n = len(df)
    results: List[DetectorResult] = []
    public = {"status": "OK", "message": "", "features_used": [], "preprocessing": [], "models": []}

    def skip_all(message: str) -> Tuple[List[DetectorResult], dict]:
        skipped = [DetectorResult(name, "machine_learning", status="SKIPPED", message=message)
                   for name in MODEL_NAMES]
        public.update(status="SKIPPED", message=message,
                      models=[r.summary(n) for r in skipped])
        return skipped, public

    if n < cfg.ml_min_rows:
        return skip_all(f"Too few rows ({n}) for reliable ML anomaly detection "
                        f"(minimum {cfg.ml_min_rows}).")
    if not features:
        return skip_all("No suitable numerical features for ML anomaly detection "
                        "(the dataset has no non-constant, non-identifier numeric columns).")
    try:
        X, used, notes = prepare_features(df, features, cfg, kinds, stats)
    except Exception as exc:  # noqa: BLE001
        return skip_all(f"ML preprocessing failed ({type(exc).__name__}). "
                        f"The dataset may contain unsupported values.")
    logged = [f for f in used if stats and f in stats and stats[f].get("transform")]
    public["preprocessing"] = ["Median imputation", "Standard scaling"] + (
        [f"Log transform for skewed features: {', '.join(logged)}"] if logged else []) + notes
    if X is None:
        return skip_all("No usable features remained after ML preprocessing.")
    public["features_used"] = used

    # large data: fit on a random sample, score all rows
    if n > cfg.ml_max_fit_rows:
        rng = np.random.default_rng(cfg.random_state)
        fit_idx = np.sort(rng.choice(n, cfg.ml_max_fit_rows, replace=False))
        X_fit = X[fit_idx]
        public["preprocessing"].append(
            f"Models were fitted on a random sample of {cfg.ml_max_fit_rows:,} rows and applied to all rows.")
    else:
        X_fit = X

    runners = [
        ("Isolation Forest", lambda: isolation_forest.run(X_fit, X, cfg.if_contamination, cfg.random_state)),
        ("Local Outlier Factor",
         lambda: local_outlier_factor.run(X_fit, X, cfg.lof_neighbors, "auto")),
        ("One-Class SVM", lambda: one_class_svm.run(X_fit, X, cfg.svm_nu)),
    ]
    for name, runner in runners:
        result = DetectorResult(name, "machine_learning")
        start = time.perf_counter()
        try:
            flags, scores, params = runner()
            result.row_flags = pd.Series(np.asarray(flags, dtype=bool), index=df.index)
            result.scores = pd.Series(np.asarray(scores, dtype=float), index=df.index)
            result.params = params
        except Exception as exc:  # noqa: BLE001
            result.status = "FAILED"
            result.message = f"{name} could not run on this dataset ({type(exc).__name__})."
        result.seconds = time.perf_counter() - start
        results.append(result)

    public["models"] = [r.summary(n) for r in results]
    if not any(r.ok for r in results):
        public["status"], public["message"] = "FAILED", "None of the ML models could run on this dataset."
    return results, public
