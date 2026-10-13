def calculate_quality_score(
    total_rows: int,
    total_columns: int,
    total_missing: int,
    duplicate_count: int,
    total_invalid: int,
    constant_column_count: int
) -> dict:
    """
    Calculate an overall data quality score.

    This is a baseline scoring model for the research prototype.
    """

    if total_rows == 0 or total_columns == 0:

        return {
            "score": 0,
            "grade": "Poor",
            "components": {}
        }

    # ---------------------------------------------
    # Missing value score
    # ---------------------------------------------

    total_cells = total_rows * total_columns

    missing_rate = (
        total_missing / total_cells
    ) * 100

    missing_score = max(
        0,
        100 - missing_rate
    )

    # ---------------------------------------------
    # Duplicate score
    # ---------------------------------------------

    duplicate_rate = (
        duplicate_count / total_rows
    ) * 100

    duplicate_score = max(
        0,
        100 - duplicate_rate
    )

    # ---------------------------------------------
    # Validity score
    # ---------------------------------------------

    invalid_rate = (
        total_invalid / total_cells
    ) * 100

    validity_score = max(
        0,
        100 - invalid_rate
    )

    # ---------------------------------------------
    # Constant column score
    # ---------------------------------------------

    constant_rate = (
        constant_column_count / total_columns
    ) * 100

    constant_score = max(
        0,
        100 - constant_rate
    )

    # ---------------------------------------------
    # Weighted score
    # ---------------------------------------------

    final_score = (
        missing_score * 0.30
        + duplicate_score * 0.20
        + validity_score * 0.35
        + constant_score * 0.15
    )

    final_score = round(final_score, 2)

    # ---------------------------------------------
    # Grade
    # ---------------------------------------------

    if final_score >= 90:
        grade = "Excellent"

    elif final_score >= 75:
        grade = "Good"

    elif final_score >= 50:
        grade = "Moderate"

    else:
        grade = "Poor"

    return {
        "score": final_score,
        "grade": grade,
        "components": {
            "missing_score": round(
                missing_score,
                2
            ),

            "duplicate_score": round(
                duplicate_score,
                2
            ),

            "validity_score": round(
                validity_score,
                2
            ),

            "constant_score": round(
                constant_score,
                2
            )
        }
    }