import pandas as pd


def calculate_quality_score(df):

    total_rows = len(df)

    total_columns = len(df.columns)

    # -------------------------------------------------
    # MISSING VALUES
    # -------------------------------------------------

    missing_values = int(
        df.isnull().sum().sum()
    )

    total_cells = (
        total_rows * total_columns
    )

    if total_cells > 0:
        missing_rate = (
            missing_values / total_cells
        )
    else:
        missing_rate = 0

    missing_score = (
        100 * (1 - missing_rate)
    )

    # -------------------------------------------------
    # DUPLICATES
    # -------------------------------------------------

    duplicate_rows = int(
        df.duplicated().sum()
    )

    if total_rows > 0:
        duplicate_rate = (
            duplicate_rows / total_rows
        )
    else:
        duplicate_rate = 0

    duplicate_score = (
        100 * (1 - duplicate_rate)
    )

    # -------------------------------------------------
    # COLUMN COMPLETENESS
    # -------------------------------------------------

    columns_with_missing = int(
        df.isnull()
        .any()
        .sum()
    )

    if total_columns > 0:

        completeness_score = (
            100
            * (
                1
                - (
                    columns_with_missing
                    / total_columns
                )
            )
        )

    else:

        completeness_score = 100

    # -------------------------------------------------
    # OVERALL SCORE
    # -------------------------------------------------

    overall_score = (
        missing_score * 0.40
        +
        duplicate_score * 0.25
        +
        completeness_score * 0.35
    )

    overall_score = round(
        max(
            0,
            min(
                100,
                overall_score
            )
        ),
        2
    )

    return {

        "total_rows":
            total_rows,

        "total_columns":
            total_columns,

        "missing_values":
            missing_values,

        "missing_rate":
            round(
                missing_rate * 100,
                2
            ),

        "missing_score":
            round(
                missing_score,
                2
            ),

        "duplicate_rows":
            duplicate_rows,

        "duplicate_rate":
            round(
                duplicate_rate * 100,
                2
            ),

        "duplicate_score":
            round(
                duplicate_score,
                2
            ),

        "columns_with_missing":
            columns_with_missing,

        "completeness_score":
            round(
                completeness_score,
                2
            ),

        "overall_score":
            overall_score
    }