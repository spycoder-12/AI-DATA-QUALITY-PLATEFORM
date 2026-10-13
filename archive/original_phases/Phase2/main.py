from pathlib import Path

import pandas as pd

from quality.missing_checker import check_missing_values
from quality.duplicate_checker import check_duplicates
from quality.constant_checker import check_constant_columns
from quality.validity_checker import check_validity
from quality.consistency_checker import check_consistency
from quality.quality_score import calculate_quality_score


DATASET_PATH = Path("data/sample_quality.csv")


def print_header(title: str):
    print("\n" + "=" * 65)
    print(title)
    print("=" * 65)


def main():

    print_header(
        "AI DATA QUALITY & ANOMALY DETECTION ENGINE"
    )

    print("PHASE 2 - DATA QUALITY ANALYZER")

    # =================================================
    # 1. LOAD DATASET
    # =================================================

    print_header("1. DATASET LOADING")

    try:

        df = pd.read_csv(DATASET_PATH)

        if df.empty:
            print("ERROR: Dataset is empty.")
            return

        print("Dataset loaded successfully!")
        print(f"Rows    : {len(df)}")
        print(f"Columns : {len(df.columns)}")

    except FileNotFoundError:

        print(
            f"ERROR: Dataset not found: "
            f"{DATASET_PATH}"
        )

        return

    except Exception as error:

        print(f"ERROR: {error}")
        return

    # =================================================
    # 2. MISSING VALUES
    # =================================================

    print_header("2. MISSING VALUE ANALYSIS")

    missing = check_missing_values(df)

    print(
        f"Total Missing Values: "
        f"{missing['total_missing']}"
    )

    for column, result in missing["columns"].items():

        if result["missing_count"] > 0:

            print(
                f"{column:<15} "
                f"{result['missing_count']} missing "
                f"({result['missing_percentage']}%) "
                f"[{result['severity']}]"
            )

    # =================================================
    # 3. DUPLICATES
    # =================================================

    print_header("3. DUPLICATE ANALYSIS")

    duplicates = check_duplicates(df)

    print(
        f"Duplicate Rows      : "
        f"{duplicates['duplicate_count']}"
    )

    print(
        f"Duplicate Percentage: "
        f"{duplicates['duplicate_percentage']}%"
    )

    print(
        f"Severity            : "
        f"{duplicates['severity']}"
    )

    # =================================================
    # 4. CONSTANT COLUMNS
    # =================================================

    print_header("4. CONSTANT COLUMN ANALYSIS")

    constants = check_constant_columns(df)

    if constants["count"] == 0:

        print("No constant columns detected.")

    else:

        print(
            f"Constant Columns: "
            f"{constants['count']}"
        )

        for column in constants["constant_columns"]:

            print(f"  - {column}")

    # =================================================
    # 5. VALIDITY
    # =================================================

    print_header("5. VALIDITY ANALYSIS")

    validity = check_validity(df)

    print(
        f"Total Invalid Values: "
        f"{validity['total_invalid']}"
    )

    for column, invalid_values in (
        validity["columns"].items()
    ):

        if not invalid_values:
            continue

        print(f"\n{column}:")

        for item in invalid_values:

            print(
                f"  Row {item['row']} "
                f"→ {item['value']}"
            )

    # =================================================
    # 6. CONSISTENCY
    # =================================================

    print_header("6. CONSISTENCY ANALYSIS")

    consistency = check_consistency(df)

    print(
        f"Total Inconsistent Values: "
        f"{consistency['total_invalid']}"
    )

    for column, result in (
        consistency["columns"].items()
    ):

        if not result["invalid_values"]:
            continue

        print(f"\n{column}:")

        for item in result["invalid_values"]:

            print(
                f"  Row {item['row']} "
                f"→ {item['value']}"
            )

    # =================================================
    # 7. QUALITY SCORE
    # =================================================

    print_header("7. DATA QUALITY SCORE")

    total_problems = (
        validity["total_invalid"]
        + consistency["total_invalid"]
    )

    quality = calculate_quality_score(

        total_rows=len(df),

        total_columns=len(df.columns),

        total_missing=missing[
            "total_missing"
        ],

        duplicate_count=duplicates[
            "duplicate_count"
        ],

        total_invalid=total_problems,

        constant_column_count=constants[
            "count"
        ]
    )

    print(
        f"Overall Score : "
        f"{quality['score']} / 100"
    )

    print(
        f"Quality Grade : "
        f"{quality['grade']}"
    )

    print("\nScore Components:")

    for name, value in (
        quality["components"].items()
    ):

        print(
            f"  {name:<25}: {value}"
        )

    # =================================================
    # 8. FINAL SUMMARY
    # =================================================

    print_header("PHASE 2 SUMMARY")

    print(
        f"Missing Values      : "
        f"{missing['total_missing']}"
    )

    print(
        f"Duplicate Rows      : "
        f"{duplicates['duplicate_count']}"
    )

    print(
        f"Invalid Values      : "
        f"{validity['total_invalid']}"
    )

    print(
        f"Inconsistent Values : "
        f"{consistency['total_invalid']}"
    )

    print(
        f"Constant Columns    : "
        f"{constants['count']}"
    )

    print(
        f"Quality Score       : "
        f"{quality['score']} / 100"
    )

    print(
        f"Quality Grade       : "
        f"{quality['grade']}"
    )

    print("\nPhase 2 completed successfully! 🚀")


if __name__ == "__main__":
    main()