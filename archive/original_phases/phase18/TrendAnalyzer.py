import pandas as pd
import numpy as np


# ============================================================
# LOAD HISTORICAL DATA
# ============================================================

def load_historical_data(path):

    df = pd.read_csv(path)

    if df.empty:
        raise ValueError(
            "Historical monitoring dataset is empty."
        )

    if "date" not in df.columns:
        raise ValueError(
            "Historical dataset must contain a date column."
        )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["date"]
    )

    df = df.sort_values(
        "date"
    ).reset_index(
        drop=True
    )

    return df


# ============================================================
# TREND CALCULATION
# ============================================================

def calculate_trend(
    values
):

    values = np.asarray(
        values,
        dtype=float
    )

    if len(values) < 2:

        return {
            "slope": 0.0,
            "trend": "INSUFFICIENT DATA"
        }

    x = np.arange(
        len(values)
    )

    slope = np.polyfit(
        x,
        values,
        1
    )[0]

    if slope > 0.05:

        trend = "IMPROVING"

    elif slope < -0.05:

        trend = "DECLINING"

    else:

        trend = "STABLE"

    return {

        "slope": round(
            float(slope),
            4
        ),

        "trend": trend
    }


# ============================================================
# QUALITY TREND
# ============================================================

def analyze_quality_trend(
    df
):

    result = calculate_trend(
        df["quality_score"]
    )

    return result


# ============================================================
# ANOMALY TREND
# ============================================================

def analyze_anomaly_trend(
    df
):

    result = calculate_trend(
        df["anomalies"]
    )

    return result


# ============================================================
# DRIFT TREND
# ============================================================

def analyze_drift_trend(
    df
):

    result = calculate_trend(
        df["drifted_features"]
    )

    return result


# ============================================================
# ALERT TREND
# ============================================================

def analyze_alert_trend(
    df
):

    result = calculate_trend(
        df["alerts"]
    )

    return result


# ============================================================
# OVERALL TREND
# ============================================================

def determine_overall_trend(
    quality_trend,
    anomaly_trend,
    drift_trend
):

    if quality_trend == "DECLINING":

        return "DECLINING"

    if (
        anomaly_trend == "IMPROVING"
        and
        drift_trend == "IMPROVING"
    ):

        return "IMPROVING"

    if (
        quality_trend == "IMPROVING"
        and
        anomaly_trend != "DECLINING"
    ):

        return "IMPROVING"

    return "STABLE"