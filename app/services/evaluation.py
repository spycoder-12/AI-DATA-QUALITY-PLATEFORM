"""Model comparison.

Two clearly separated things:

1. Model-generated anomaly detection (always available): how many rows each
   detector flags, execution time, and how much detectors agree with each other.
2. Ground-truth evaluation (ONLY when the dataset contains a real label column
   such as ``is_anomaly``): precision, recall, F1, accuracy and confusion matrix.

No metric is ever fabricated - without labels the ground-truth section says so.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, precision_score,
                             recall_score)

from app.services.anomaly import DetectorResult
from app.utils.helpers import GROUND_TRUTH_NAMES, json_safe, rnd

_TRUE = {"1", "true", "yes", "y", "anomaly", "outlier"}
_FALSE = {"0", "false", "no", "n", "normal", "inlier"}


def find_ground_truth(df: pd.DataFrame) -> Optional[pd.Series]:
    """Return a 0/1 Series when the dataset carries an anomaly label column."""
    for column in df.columns:
        if column.lower() not in GROUND_TRUTH_NAMES:
            continue
        mapped = df[column].astype(str).str.strip().str.lower().map(
            lambda v: 1 if v in _TRUE or v == "1.0" else (0 if v in _FALSE or v == "0.0" else np.nan))
        if mapped.notna().all():
            return mapped.astype(int).rename(column)
    return None


def classification_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    cm = confusion_matrix(actual, predicted, labels=[0, 1])   # never fails on single-class input
    return {
        "accuracy": rnd(accuracy_score(actual, predicted)),
        "precision": rnd(precision_score(actual, predicted, zero_division=0)),
        "recall": rnd(recall_score(actual, predicted, zero_division=0)),
        "f1_score": rnd(f1_score(actual, predicted, zero_division=0)),
        "true_negative": int(cm[0][0]), "false_positive": int(cm[0][1]),
        "false_negative": int(cm[1][0]), "true_positive": int(cm[1][1]),
    }


def agreement(flags: Dict[str, pd.Series]) -> dict:
    """Pairwise agreement between detectors.

    ``percent_agreement`` = share of rows on which both detectors give the same
    answer (inflated when anomalies are rare); ``jaccard`` = overlap of the
    flagged sets, which is the more informative number.
    """
    names = list(flags)
    pct, jac = {}, {}
    for a in names:
        pct[a], jac[a] = {}, {}
        for b in names:
            fa, fb = flags[a].to_numpy(dtype=bool), flags[b].to_numpy(dtype=bool)
            pct[a][b] = rnd((fa == fb).mean() * 100, 2) if len(fa) else None
            union = (fa | fb).sum()
            jac[a][b] = rnd((fa & fb).sum() / union, 3) if union else None
    return {"models": names, "percent_agreement": pct, "jaccard": jac}


def evaluate(df: pd.DataFrame, detectors: List[DetectorResult], reported_rows: pd.Series,
             consensus_summary: dict) -> dict:
    n = len(df)
    ok = [d for d in detectors if d.ok]
    flags: Dict[str, pd.Series] = {d.name: d.row_flags for d in ok}
    flags["Consensus"] = reported_rows

    comparison = []
    for d in detectors:
        comparison.append(d.summary(n))
    comparison.append({
        "model": "Consensus (reported anomalies)", "type": "ensemble", "status": "OK" if ok else "SKIPPED",
        "message": "", "anomalies_flagged": int(reported_rows.sum()) if ok else None,
        "anomaly_pct": rnd(reported_rows.sum() / n * 100, 2) if (ok and n) else None,
        "execution_seconds": None, "params": {"min_votes": consensus_summary.get("min_votes")}})

    truth = find_ground_truth(df)
    ground_truth: dict
    if truth is None:
        ground_truth = {
            "available": False,
            "message": "Not available — insufficient data. No ground-truth anomaly label column "
                       "(e.g. 'is_anomaly') was found, so precision/recall/F1 cannot be computed. "
                       "The counts and agreement shown are model outputs, not accuracy measurements."}
    elif truth.nunique() < 2:
        ground_truth = {
            "available": False, "label_column": truth.name,
            "message": f"Not available — insufficient data. The label column '{truth.name}' contains "
                       f"only one class, so precision/recall/F1 are not meaningful."}
    else:
        actual = truth.reindex(df.index).to_numpy()
        metrics = []
        for name, series in flags.items():
            row = classification_metrics(actual, series.reindex(df.index).to_numpy(dtype=int))
            row["model"] = name if name != "Consensus" else "Consensus (reported anomalies)"
            row["anomalies_flagged"] = int(series.sum())
            metrics.append(row)
        ground_truth = {
            "available": True, "label_column": truth.name,
            "actual_anomalies": int(truth.sum()), "metrics": metrics,
            "note": "Metrics compare each detector with the labels in the uploaded dataset."}

    result = {
        "comparison": comparison,
        "agreement": agreement(flags) if len(flags) >= 2 and ok else
        {"models": [], "percent_agreement": {}, "jaccard": {},
         "message": "Not available — insufficient data (no detector produced results)."},
        "ground_truth": ground_truth,
    }
    return json_safe(result)
