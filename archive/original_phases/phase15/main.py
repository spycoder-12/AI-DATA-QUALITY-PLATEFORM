import os

import pandas as pd

from remediation import (
    analyze_problems,
    perform_remediation
)


# =====================================================
# CONFIGURATION
# =====================================================

DATASET_PATH = (
    "data/evaluation_dataset.csv"
)

CLEANED_DIRECTORY = (
    "cleaned"
)

REPORT_DIRECTORY = (
    "reports"
)


os.makedirs(
    CLEANED_DIRECTORY,
    exist_ok=True
)

os.makedirs(
    REPORT_DIRECTORY,
    exist_ok=True
)


# =====================================================
# HEADER
# =====================================================

print("=" * 70)

print(
    "AI DATA QUALITY & ANOMALY DETECTION ENGINE"
)

print("=" * 70)

print(
    "PHASE 15 - AUTOMATED DATA QUALITY "
    "REMEDIATION & CLEANING ENGINE"
)

print("=" * 70)


# =====================================================
# 1. DATASET LOADING
# =====================================================

print("\n1. DATASET LOADING")

df = pd.read_csv(
    DATASET_PATH
)

print(
    "Dataset loaded successfully!"
)

print(
    f"Rows: {len(df)}"
)

print(
    f"Columns: {len(df.columns)}"
)


# =====================================================
# 2. ORIGINAL DATA QUALITY
# =====================================================

print("\n2. ORIGINAL DATA QUALITY")

problems = analyze_problems(
    df
)

print(
    f"Missing values: "
    f"{problems['missing_values']}"
)

print(
    f"Duplicate rows: "
    f"{problems['duplicate_rows']}"
)


# =====================================================
# 3. AUTOMATED REMEDIATION
# =====================================================

print("\n3. AUTOMATED REMEDIATION")

(
    cleaned_df,
    changes,
    original_score,
    final_score
) = perform_remediation(df)


print(
    f"Remediation actions: "
    f"{len(changes)}"
)


if changes:

    for index, change in enumerate(
        changes,
        start=1
    ):

        print(
            f"\nAction {index}"
        )

        print(
            f"Type: "
            f"{change['type']}"
        )

        print(
            f"Column: "
            f"{change['column']}"
        )

        print(
            f"Affected rows: "
            f"{change['affected_rows']}"
        )

        print(
            f"Action: "
            f"{change['action']}"
        )

else:

    print(
        "No automatic cleaning "
        "actions were required."
    )


# =====================================================
# 4. BEFORE / AFTER ANALYSIS
# =====================================================

print("\n4. BEFORE / AFTER QUALITY")

print(
    f"Original Quality Score: "
    f"{original_score}/100"
)

print(
    f"Cleaned Quality Score: "
    f"{final_score}/100"
)

improvement = round(
    final_score - original_score,
    2
)

print(
    f"Quality Improvement: "
    f"{improvement} points"
)


# =====================================================
# 5. SAVE CLEANED DATA
# =====================================================

print("\n5. SAVING CLEANED DATA")

cleaned_path = (
    os.path.join(
        CLEANED_DIRECTORY,
        "cleaned_dataset.csv"
    )
)

cleaned_df.to_csv(
    cleaned_path,
    index=False
)

print(
    f"Cleaned dataset saved to:"
)

print(
    os.path.abspath(
        cleaned_path
    )
)


# =====================================================
# 6. REMEDIATION REPORT
# =====================================================

print("\n6. REMEDIATION REPORT")

report_rows = []

for change in changes:

    report_rows.append({

        "type":
            change["type"],

        "column":
            change["column"],

        "affected_rows":
            change["affected_rows"],

        "action":
            change["action"]
    })


if not report_rows:

    report_rows.append({

        "type":
            "No Issues",

        "column":
            "N/A",

        "affected_rows":
            0,

        "action":
            "No automatic remediation required."
    })


report_df = pd.DataFrame(
    report_rows
)


report_path = (
    os.path.join(
        REPORT_DIRECTORY,
        "phase15_remediation_report.csv"
    )
)


report_df.to_csv(
    report_path,
    index=False
)


print(
    f"Report saved to:"
)

print(
    os.path.abspath(
        report_path
    )
)


# =====================================================
# 7. VERIFICATION
# =====================================================

print("\n7. CLEANED DATA VERIFICATION")

remaining_missing = int(
    cleaned_df.isnull()
    .sum()
    .sum()
)

remaining_duplicates = int(
    cleaned_df.duplicated()
    .sum()
)

print(
    f"Remaining missing values: "
    f"{remaining_missing}"
)

print(
    f"Remaining duplicate rows: "
    f"{remaining_duplicates}"
)


# =====================================================
# 8. FINAL SUMMARY
# =====================================================

print("\n8. PHASE 15 SUMMARY")

print("-" * 70)

print(
    f"Original Score : "
    f"{original_score}/100"
)

print(
    f"Final Score    : "
    f"{final_score}/100"
)

print(
    f"Improvement    : "
    f"{improvement} points"
)

print(
    f"Actions        : "
    f"{len(changes)}"
)

print(
    f"Missing Values : "
    f"{remaining_missing}"
)

print(
    f"Duplicates     : "
    f"{remaining_duplicates}"
)

print("-" * 70)

print(
    "\nPhase 15 completed successfully! 🚀"
)

print("=" * 70)