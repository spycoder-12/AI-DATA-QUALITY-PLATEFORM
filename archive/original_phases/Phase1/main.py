from profiler.loader import load_dataset
from profiler.dataset_info import get_dataset_info
from profiler.missing_values import analyze_missing_values
from profiler.duplicates import analyze_duplicates
from profiler.statistics import get_descriptive_statistics


DATASET_PATH = "data/sample.csv"


def print_header(title: str):
    print("\n" + "=" * 65)
    print(title)
    print("=" * 65)


def main():

    print_header(
        "AI DATA QUALITY & ANOMALY DETECTION ENGINE"
    )

    print("PHASE 1 - DATASET PROFILER")

    # ==================================================
    # 1. Load Dataset
    # ==================================================

    print_header("1. DATASET LOADING")

    try:

        df = load_dataset(DATASET_PATH)

        print("Dataset loaded successfully!")

    except Exception as error:

        print(f"ERROR: {error}")
        return

    # ==================================================
    # 2. Dataset Information
    # ==================================================

    print_header("2. DATASET INFORMATION")

    info = get_dataset_info(df)

    print(f"Rows              : {info['rows']}")
    print(f"Columns           : {info['columns']}")
    print(
        f"Memory Usage      : "
        f"{info['memory_usage_mb']} MB"
    )

    print(
        f"Numerical Columns : "
        f"{len(info['numerical_columns'])}"
    )

    print(
        f"Categorical Columns: "
        f"{len(info['categorical_columns'])}"
    )

    print("\nColumn Data Types:")

    for column, dtype in info["data_types"].items():

        print(
            f"  {column:<15} → {dtype}"
        )

    # ==================================================
    # 3. Missing Values
    # ==================================================

    print_header("3. MISSING VALUE ANALYSIS")

    missing = analyze_missing_values(df)

    print(
        f"Total Missing Values: "
        f"{missing['total_missing_values']}"
    )

    for column, result in missing["columns"].items():

        if result["missing_count"] > 0:

            print(
                f"  {column:<15} → "
                f"{result['missing_count']} "
                f"({result['missing_percentage']}%)"
            )

    # ==================================================
    # 4. Duplicate Analysis
    # ==================================================

    print_header("4. DUPLICATE ANALYSIS")

    duplicates = analyze_duplicates(df)

    print(
        f"Duplicate Rows      : "
        f"{duplicates['duplicate_count']}"
    )

    print(
        f"Duplicate Percentage: "
        f"{duplicates['duplicate_percentage']}%"
    )

    # ==================================================
    # 5. Descriptive Statistics
    # ==================================================

    print_header("5. DESCRIPTIVE STATISTICS")

    statistics = get_descriptive_statistics(df)

    if statistics.empty:

        print("No numerical columns found.")

    else:

        print(statistics.to_string())

    # ==================================================
    # 6. Dataset Preview
    # ==================================================

    print_header("6. DATASET PREVIEW")

    print(df.head().to_string(index=False))

    # ==================================================
    # 7. Final Summary
    # ==================================================

    print_header("PHASE 1 SUMMARY")

    print(
        f"Dataset Rows       : {info['rows']}"
    )

    print(
        f"Dataset Columns    : {info['columns']}"
    )

    print(
        f"Missing Values     : "
        f"{missing['total_missing_values']}"
    )

    print(
        f"Duplicate Rows     : "
        f"{duplicates['duplicate_count']}"
    )

    print("\nPhase 1 completed successfully! 🚀")


if __name__ == "__main__":
    main()