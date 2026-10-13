import pandas as pd
import numpy as np
from scipy.stats import ks_2samp


# ============================================================
# CONFIGURATION
# ============================================================

EXCLUDED_FEATURES = {
    "id",
    "is_anomaly"
}


# ============================================================
# LOAD DATASETS
# ============================================================

def load_datasets(reference_path, current_path):

    reference = pd.read_csv(reference_path)
    current = pd.read_csv(current_path)

    return reference, current


# ============================================================
# DATA QUALITY ANALYSIS
# ============================================================

def calculate_quality_metrics(df):

    rows = len(df)
    columns = len(df.columns)

    missing_values = int(
        df.isnull().sum().sum()
    )

    duplicate_rows = int(
        df.duplicated().sum()
    )

    total_cells = rows * columns

    if total_cells > 0:

        completeness = (
            1 -
            (
                missing_values /
                total_cells
            )
        ) * 100

    else:

        completeness = 0

    return {

        "rows": rows,

        "columns": columns,

        "missing_values":
            missing_values,

        "duplicate_rows":
            duplicate_rows,

        "completeness":
            round(
                completeness,
                2
            )
    }


# ============================================================
# ANOMALY DETECTION
# ============================================================

def detect_anomalies(df):

    numeric_columns = (
        df.select_dtypes(
            include="number"
        )
        .columns
        .tolist()
    )

    # Remove metadata / ground-truth columns

    numeric_columns = [
        column
        for column in numeric_columns
        if column not in EXCLUDED_FEATURES
    ]

    anomalies = []

    # Store unique rows that contain
    # at least one anomaly

    anomalous_rows = set()

    for column in numeric_columns:

        mean = df[column].mean()

        std = df[column].std()

        if (
            pd.isna(std)
            or std == 0
        ):
            continue

        z_scores = (
            (
                df[column] -
                mean
            )
            /
            std
        )

        anomaly_mask = (
            abs(z_scores) >= 3
        )

        count = int(
            anomaly_mask.sum()
        )

        # Store row indexes

        detected_indexes = (
            df.index[
                anomaly_mask
            ]
            .tolist()
        )

        for index in detected_indexes:

            anomalous_rows.add(
                index
            )

        anomalies.append({

            "feature":
                column,

            "anomalies":
                count,

            "max_z_score":
                round(
                    float(
                        abs(
                            z_scores
                        ).max()
                    ),
                    4
                )
        })

    # IMPORTANT:
    # Count unique anomalous rows,
    # not feature-level anomaly count.

    total_anomalies = len(
        anomalous_rows
    )

    return (
        anomalies,
        total_anomalies
    )


# ============================================================
# PSI CALCULATION
# ============================================================

def calculate_psi(
    reference,
    current
):

    reference = np.asarray(
        reference.dropna()
    )

    current = np.asarray(
        current.dropna()
    )

    if (
        len(reference) == 0
        or
        len(current) == 0
    ):

        return 0.0

    minimum = min(
        reference.min(),
        current.min()
    )

    maximum = max(
        reference.max(),
        current.max()
    )

    if minimum == maximum:

        return 0.0

    bins = np.linspace(
        minimum,
        maximum,
        11
    )

    ref_counts, _ = (
        np.histogram(
            reference,
            bins=bins
        )
    )

    cur_counts, _ = (
        np.histogram(
            current,
            bins=bins
        )
    )

    ref_percent = (
        ref_counts /
        max(
            len(reference),
            1
        )
    )

    cur_percent = (
        cur_counts /
        max(
            len(current),
            1
        )
    )

    # Prevent log(0)

    ref_percent = np.where(
        ref_percent == 0,
        0.0001,
        ref_percent
    )

    cur_percent = np.where(
        cur_percent == 0,
        0.0001,
        cur_percent
    )

    psi = np.sum(
        (
            cur_percent -
            ref_percent
        )
        *
        np.log(
            cur_percent /
            ref_percent
        )
    )

    return round(
        float(psi),
        4
    )


# ============================================================
# DRIFT ANALYSIS
# ============================================================

def analyze_drift(
    reference,
    current
):

    numeric_reference = (
        reference
        .select_dtypes(
            include="number"
        )
    )

    numeric_current = (
        current
        .select_dtypes(
            include="number"
        )
    )

    # Find common numeric features

    common_features = (
        set(
            numeric_reference.columns
        )
        &
        set(
            numeric_current.columns
        )
    )

    # Remove metadata / ground-truth columns

    common_features = [
        feature
        for feature in common_features
        if feature not in EXCLUDED_FEATURES
    ]

    # Sort features so output is consistent

    common_features = sorted(
        common_features
    )

    results = []

    for feature in common_features:

        ref = (
            numeric_reference[
                feature
            ]
            .dropna()
        )

        cur = (
            numeric_current[
                feature
            ]
            .dropna()
        )

        if (
            len(ref) == 0
            or
            len(cur) == 0
        ):
            continue

        # --------------------------------------------
        # PSI
        # --------------------------------------------

        psi = calculate_psi(
            ref,
            cur
        )

        # --------------------------------------------
        # KS TEST
        # --------------------------------------------

        (
            ks_statistic,
            ks_pvalue
        ) = ks_2samp(
            ref,
            cur
        )

        # --------------------------------------------
        # MEANS
        # --------------------------------------------

        reference_mean = float(
            ref.mean()
        )

        current_mean = float(
            cur.mean()
        )

        # --------------------------------------------
        # MEAN CHANGE
        # --------------------------------------------

        if reference_mean != 0:

            mean_change = (
                abs(
                    current_mean -
                    reference_mean
                )
                /
                abs(
                    reference_mean
                )
            ) * 100

        else:

            mean_change = 0

        # --------------------------------------------
        # DRIFT STATUS
        # --------------------------------------------

        if psi >= 0.25:

            status = "HIGH DRIFT"

            risk = "HIGH"

        elif psi >= 0.10:

            status = "MODERATE DRIFT"

            risk = "MEDIUM"

        else:

            status = "NO DRIFT"

            risk = "LOW"

        results.append({

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

            "mean_change_percent":
                round(
                    mean_change,
                    2
                ),

            "psi":
                psi,

            "ks_statistic":
                round(
                    float(
                        ks_statistic
                    ),
                    4
                ),

            "ks_pvalue":
                round(
                    float(
                        ks_pvalue
                    ),
                    4
                ),

            "status":
                status,

            "risk":
                risk
        })

    return results


# ============================================================
# QUALITY SCORE
# ============================================================

def calculate_quality_score(
    quality,
    anomaly_count
):

    score = 100.0

    # ========================================================
    # ROW COUNT
    # ========================================================

    row_count = quality[
        "rows"
    ]

    column_count = quality[
        "columns"
    ]

    # ========================================================
    # MISSING-VALUE PENALTY
    # ========================================================

    total_cells = (
        row_count *
        column_count
    )

    if total_cells > 0:

        missing_rate = (
            quality[
                "missing_values"
            ]
            /
            total_cells
        ) * 100

        score -= min(
            missing_rate * 2,
            30
        )

    # ========================================================
    # DUPLICATE PENALTY
    # ========================================================

    if row_count > 0:

        duplicate_rate = (
            quality[
                "duplicate_rows"
            ]
            /
            row_count
        ) * 100

        score -= min(
            duplicate_rate * 2,
            20
        )

    # ========================================================
    # ANOMALY PENALTY
    # ========================================================

    if row_count > 0:

        anomaly_rate = (
            anomaly_count /
            row_count
        )

        score -= min(
            anomaly_rate * 20,
            30
        )

    return round(
        max(
            score,
            0
        ),
        2
    )