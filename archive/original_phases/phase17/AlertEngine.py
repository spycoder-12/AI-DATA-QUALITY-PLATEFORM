# ============================================================
# ALERT ENGINE
# ============================================================

def generate_alerts(
    quality,
    anomaly_count,
    drift_results,
    quality_score
):

    alerts = []

    # --------------------------------------------------------
    # QUALITY SCORE
    # --------------------------------------------------------

    if quality_score < 60:

        alerts.append({

            "type": "QUALITY_SCORE",

            "severity": "CRITICAL",

            "message":
                "Overall data quality score is critically low."
        })

    elif quality_score < 80:

        alerts.append({

            "type": "QUALITY_SCORE",

            "severity": "WARNING",

            "message":
                "Overall data quality score requires attention."
        })


    # --------------------------------------------------------
    # MISSING VALUES
    # --------------------------------------------------------

    if quality["missing_values"] > 0:

        alerts.append({

            "type": "MISSING_VALUES",

            "severity": "WARNING",

            "message":
                f"{quality['missing_values']} missing values detected."
        })


    # --------------------------------------------------------
    # DUPLICATES
    # --------------------------------------------------------

    if quality["duplicate_rows"] > 0:

        alerts.append({

            "type": "DUPLICATES",

            "severity": "WARNING",

            "message":
                f"{quality['duplicate_rows']} duplicate rows detected."
        })


    # --------------------------------------------------------
    # ANOMALIES
    # --------------------------------------------------------

    if anomaly_count >= 10:

        alerts.append({

            "type": "ANOMALIES",

            "severity": "CRITICAL",

            "message":
                f"{anomaly_count} anomalies detected."
        })

    elif anomaly_count > 0:

        alerts.append({

            "type": "ANOMALIES",

            "severity": "WARNING",

            "message":
                f"{anomaly_count} anomalies detected."
        })


    # --------------------------------------------------------
    # DATA DRIFT
    # --------------------------------------------------------

    for item in drift_results:

        if item["risk"] == "HIGH":

            alerts.append({

                "type": "DATA_DRIFT",

                "severity": "CRITICAL",

                "message":
                    f"High distribution drift detected in "
                    f"{item['feature']}."
            })

        elif item["risk"] == "MEDIUM":

            alerts.append({

                "type": "DATA_DRIFT",

                "severity": "WARNING",

                "message":
                    f"Moderate distribution drift detected in "
                    f"{item['feature']}."
            })


    return alerts


# ============================================================
# OVERALL SYSTEM STATUS
# ============================================================

def determine_status(alerts):

    if any(
        alert["severity"] == "CRITICAL"
        for alert in alerts
    ):

        return "CRITICAL"

    if any(
        alert["severity"] == "WARNING"
        for alert in alerts
    ):

        return "WARNING"

    return "HEALTHY"


# ============================================================
# RISK LEVEL
# ============================================================

def determine_risk(status):

    if status == "CRITICAL":

        return "HIGH"

    if status == "WARNING":

        return "MEDIUM"

    return "LOW"