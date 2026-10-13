import numpy as np
import pandas as pd

from scipy.stats import ks_2samp


# =====================================================
# FEATURE SELECTION
# =====================================================

def select_numeric_features(
    reference_df,
    current_df
):

    reference_features = set(
        reference_df
        .select_dtypes(
            include="number"
        )
        .columns
    )

    current_features = set(
        current_df
        .select_dtypes(
            include="number"
        )
        .columns
    )

    common_features = (
        reference_features
        .intersection(
            current_features
        )
    )

    # ID and ground-truth columns should
    # not participate in drift detection.

    excluded_columns = {
        "id",
        "is_anomaly"
    }

    features = [
        feature
        for feature in common_features
        if feature not in excluded_columns
    ]

    return sorted(features)


# =====================================================
# PSI CALCULATION
# =====================================================

def calculate_psi(
    reference,
    current,
    bins=10
):

    reference = pd.Series(
        reference
    ).dropna()

    current = pd.Series(
        current
    ).dropna()

    if len(reference) == 0:
        return 0.0

    if len(current) == 0:
        return 0.0

    # Combine datasets to create stable bins.

    combined = np.concatenate(
        [
            reference.to_numpy(),
            current.to_numpy()
        ]
    )

    # Remove infinite values.

    combined = combined[
        np.isfinite(combined)
    ]

    if len(combined) == 0:
        return 0.0

    minimum = np.min(
        combined
    )

    maximum = np.max(
        combined
    )

    # If both datasets have effectively
    # identical constant values there is
    # no distribution drift.

    if np.isclose(
        minimum,
        maximum
    ):

        return 0.0

    breakpoints = np.linspace(
        minimum,
        maximum,
        bins + 1
    )

    reference_counts, _ = np.histogram(
        reference,
        bins=breakpoints
    )

    current_counts, _ = np.histogram(
        current,
        bins=breakpoints
    )

    # Convert counts to percentages.

    reference_percentage = (
        reference_counts
        / max(
            reference_counts.sum(),
            1
        )
    )

    current_percentage = (
        current_counts
        / max(
            current_counts.sum(),
            1
        )
    )

    # Avoid division by zero.

    epsilon = 0.0001

    reference_percentage = np.where(
        reference_percentage == 0,
        epsilon,
        reference_percentage
    )

    current_percentage = np.where(
        current_percentage == 0,
        epsilon,
        current_percentage
    )

    psi = np.sum(
        (
            current_percentage
            - reference_percentage
        )
        *
        np.log(
            current_percentage
            /
            reference_percentage
        )
    )

    return round(
        float(psi),
        6
    )


# =====================================================
# PSI INTERPRETATION
# =====================================================

def classify_psi(
    psi
):

    if psi < 0.10:

        return {
            "status": "NO DRIFT",
            "risk": "LOW"
        }

    elif psi < 0.25:

        return {
            "status": "MODERATE DRIFT",
            "risk": "MEDIUM"
        }

    else:

        return {
            "status": "SIGNIFICANT DRIFT",
            "risk": "HIGH"
        }


# =====================================================
# KS TEST
# =====================================================

def calculate_ks_test(
    reference,
    current
):

    reference = (
        pd.Series(reference)
        .dropna()
    )

    current = (
        pd.Series(current)
        .dropna()
    )

    if (
        len(reference) == 0
        or len(current) == 0
    ):

        return 0.0, 1.0

    statistic, p_value = (
        ks_2samp(
            reference,
            current
        )
    )

    return (
        round(
            float(statistic),
            6
        ),
        round(
            float(p_value),
            6
        )
    )


# =====================================================
# FEATURE DRIFT ANALYSIS
# =====================================================

def analyze_feature_drift(
    reference_df,
    current_df,
    feature
):

    reference = (
        reference_df[feature]
        .dropna()
    )

    current = (
        current_df[feature]
        .dropna()
    )

    psi = calculate_psi(
        reference,
        current
    )

    ks_statistic, p_value = (
        calculate_ks_test(
            reference,
            current
        )
    )

    classification = (
        classify_psi(
            psi
        )
    )

    reference_mean = (
        float(
            reference.mean()
        )
    )

    current_mean = (
        float(
            current.mean()
        )
    )

    reference_median = (
        float(
            reference.median()
        )
    )

    current_median = (
        float(
            current.median()
        )
    )

    reference_std = (
        float(
            reference.std()
        )
    )

    current_std = (
        float(
            current.std()
        )
    )

    mean_change_percentage = 0.0

    if not np.isclose(
        reference_mean,
        0
    ):

        mean_change_percentage = (
            (
                (
                    current_mean
                    - reference_mean
                )
                /
                abs(reference_mean)
            )
            * 100
        )

    return {

        "feature":
            feature,

        "reference_mean":
            round(
                reference_mean,
                4
            ),

        "current_mean":
            round(
                current_mean,
                4
            ),

        "mean_change_percentage":
            round(
                mean_change_percentage,
                2
            ),

        "reference_median":
            round(
                reference_median,
                4
            ),

        "current_median":
            round(
                current_median,
                4
            ),

        "reference_std":
            round(
                reference_std,
                4
            ),

        "current_std":
            round(
                current_std,
                4
            ),

        "psi":
            psi,

        "ks_statistic":
            ks_statistic,

        "ks_p_value":
            p_value,

        "drift_status":
            classification["status"],

        "risk":
            classification["risk"]
    }


# =====================================================
# DATASET DRIFT ANALYSIS
# =====================================================

def detect_dataset_drift(
    reference_df,
    current_df
):

    features = (
        select_numeric_features(
            reference_df,
            current_df
        )
    )

    results = []

    for feature in features:

        result = (
            analyze_feature_drift(
                reference_df,
                current_df,
                feature
            )
        )

        results.append(
            result
        )

    return results


# =====================================================
# OVERALL DRIFT SCORE
# =====================================================

def calculate_overall_drift(
    results
):

    if not results:

        return {
            "drift_score": 0.0,
            "drifted_features": 0,
            "total_features": 0,
            "overall_status": "NO DATA",
            "overall_risk": "UNKNOWN"
        }

    psi_values = [
        result["psi"]
        for result in results
    ]

    average_psi = (
        np.mean(
            psi_values
        )
    )

    drifted_features = sum(
        result["psi"] >= 0.10
        for result in results
    )

    significant_features = sum(
        result["psi"] >= 0.25
        for result in results
    )

    if average_psi < 0.10:

        overall_status = (
            "NO SIGNIFICANT DRIFT"
        )

        overall_risk = "LOW"

    elif average_psi < 0.25:

        overall_status = (
            "MODERATE DRIFT"
        )

        overall_risk = "MEDIUM"

    else:

        overall_status = (
            "SIGNIFICANT DRIFT"
        )

        overall_risk = "HIGH"

    # Convert PSI into a 0-100 drift score.

    drift_score = min(
        100,
        average_psi * 100
    )

    return {

        "drift_score":
            round(
                float(
                    drift_score
                ),
                2
            ),

        "average_psi":
            round(
                float(
                    average_psi
                ),
                6
            ),

        "drifted_features":
            int(
                drifted_features
            ),

        "significant_features":
            int(
                significant_features
            ),

        "total_features":
            len(results),

        "overall_status":
            overall_status,

        "overall_risk":
            overall_risk
    }