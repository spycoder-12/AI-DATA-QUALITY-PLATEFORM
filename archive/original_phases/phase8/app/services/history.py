from sqlalchemy.orm import Session

from app.models import Analysis, Anomaly


# =====================================================
# SAVE ANALYSIS
# =====================================================

def save_analysis(
    db: Session,
    filename: str,
    result: dict
):
    """
    Save one complete dataset analysis
    and its detected anomalies to PostgreSQL.
    """

    quality = result.get(
        "quality",
        {}
    )

    # -------------------------------------------------
    # Create Analysis record
    # -------------------------------------------------

    analysis = Analysis(

        filename=filename,

        rows=result.get(
            "rows",
            0
        ),

        columns=result.get(
            "columns",
            0
        ),

        missing_values=quality.get(
            "missing_values",
            0
        ),

        duplicate_rows=quality.get(
            "duplicate_rows",
            0
        ),

        anomalies_detected=result.get(
            "anomalies_detected",
            0
        )
    )

    db.add(analysis)

    # Flush so PostgreSQL gives us analysis.id
    db.flush()

    # -------------------------------------------------
    # Save anomalies
    # -------------------------------------------------

    for item in result.get(
        "anomalies",
        []
    ):

        anomaly = Anomaly(

            analysis_id=analysis.id,

            row_number=item.get(
                "row",
                0
            ),

            feature=item.get(
                "feature",
                ""
            ),

            value=float(
                item.get(
                    "value",
                    0
                )
            ),

            z_score=float(
                item.get(
                    "z_score",
                    0
                )
            ),

            severity=item.get(
                "severity",
                "UNKNOWN"
            ),

            recommendation=item.get(
                "recommendation",
                ""
            )
        )

        db.add(anomaly)

    # -------------------------------------------------
    # Commit everything
    # -------------------------------------------------

    db.commit()

    # Refresh analysis from database
    db.refresh(analysis)

    return analysis


# =====================================================
# GET ANALYSIS HISTORY
# =====================================================

def get_analysis_history(
    db: Session
):

    return (
        db.query(Analysis)
        .order_by(
            Analysis.created_at.desc()
        )
        .all()
    )


# =====================================================
# GET SINGLE ANALYSIS
# =====================================================

def get_analysis_by_id(
    db: Session,
    analysis_id: int
):

    return (
        db.query(Analysis)
        .filter(
            Analysis.id == analysis_id
        )
        .first()
    )