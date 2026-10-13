import pandas as pd


def analyze_problems(df):

    problems = {
        "missing_values": int(
            df.isnull().sum().sum()
        ),

        "duplicate_rows": int(
            df.duplicated().sum()
        ),

        "numeric_columns": (
            df.select_dtypes(
                include="number"
            )
            .columns
            .tolist()
        )
    }

    return problems


def clean_missing_values(df):

    df = df.copy()

    changes = []

    numeric_columns = (
        df.select_dtypes(
            include="number"
        )
        .columns
        .tolist()
    )

    for column in numeric_columns:

        missing_count = int(
            df[column].isnull().sum()
        )

        if missing_count > 0:

            median_value = df[column].median()

            df[column] = (
                df[column]
                .fillna(median_value)
            )

            changes.append({
                "type":
                    "Missing Value",

                "column":
                    column,

                "affected_rows":
                    missing_count,

                "action":
                    f"Filled with median "
                    f"value {median_value}"
            })

    # Handle remaining non-numeric columns

    categorical_columns = (
        df.select_dtypes(
            exclude="number"
        )
        .columns
        .tolist()
    )

    for column in categorical_columns:

        missing_count = int(
            df[column].isnull().sum()
        )

        if missing_count > 0:

            mode = df[column].mode()

            if not mode.empty:

                replacement = mode.iloc[0]

                df[column] = (
                    df[column]
                    .fillna(replacement)
                )

                changes.append({
                    "type":
                        "Missing Value",

                    "column":
                        column,

                    "affected_rows":
                        missing_count,

                    "action":
                        f"Filled with mode "
                        f"'{replacement}'"
                })

    return df, changes


def remove_duplicates(df):

    df = df.copy()

    duplicate_count = int(
        df.duplicated().sum()
    )

    if duplicate_count > 0:

        df = (
            df.drop_duplicates()
            .reset_index(drop=True)
        )

    changes = []

    if duplicate_count > 0:

        changes.append({
            "type":
                "Duplicate Rows",

            "column":
                "ALL",

            "affected_rows":
                duplicate_count,

            "action":
                "Duplicate rows removed"
        })

    return df, changes


def detect_invalid_numeric_values(df):

    changes = []

    numeric_columns = (
        df.select_dtypes(
            include="number"
        )
        .columns
        .tolist()
    )

    # Ground-truth / identifier columns
    excluded_columns = {
        "id",
        "is_anomaly"
    }

    for column in numeric_columns:

        if column in excluded_columns:
            continue

        negative_count = int(
            (df[column] < 0).sum()
        )

        if negative_count > 0:

            changes.append({
                "type":
                    "Invalid Value",

                "column":
                    column,

                "affected_rows":
                    negative_count,

                "action":
                    "Negative numeric values detected; "
                    "manual verification recommended"
            })

    return changes


def calculate_quality_score(df):

    total_cells = (
        len(df) * len(df.columns)
    )

    if total_cells == 0:
        return 0

    missing_values = int(
        df.isnull().sum().sum()
    )

    duplicate_rows = int(
        df.duplicated().sum()
    )

    missing_rate = (
        missing_values / total_cells
    )

    duplicate_rate = (
        duplicate_rows / len(df)
        if len(df) > 0
        else 0
    )

    score = (
        100
        - (missing_rate * 60)
        - (duplicate_rate * 40)
    )

    return round(
        max(0, min(100, score)),
        2
    )


def perform_remediation(df):

    original_score = (
        calculate_quality_score(df)
    )

    all_changes = []

    # -------------------------------------------------
    # STEP 1: MISSING VALUES
    # -------------------------------------------------

    df, changes = (
        clean_missing_values(df)
    )

    all_changes.extend(
        changes
    )

    # -------------------------------------------------
    # STEP 2: DUPLICATES
    # -------------------------------------------------

    df, changes = (
        remove_duplicates(df)
    )

    all_changes.extend(
        changes
    )

    # -------------------------------------------------
    # STEP 3: INVALID VALUES
    # -------------------------------------------------

    invalid_changes = (
        detect_invalid_numeric_values(df)
    )

    all_changes.extend(
        invalid_changes
    )

    # -------------------------------------------------
    # FINAL SCORE
    # -------------------------------------------------

    final_score = (
        calculate_quality_score(df)
    )

    return (
        df,
        all_changes,
        original_score,
        final_score
    )