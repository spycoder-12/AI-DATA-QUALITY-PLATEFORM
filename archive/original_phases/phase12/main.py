from pathlib import Path

import pandas as pd

from Predictor import (
    prepare_features,
    create_training_data,
    train_model
)

from recommendation import (
    generate_recommendation
)


# =====================================================
# CONFIGURATION
# =====================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"

REPORT_DIR = BASE_DIR / "reports"


REPORT_DIR.mkdir(
    exist_ok=True
)


# =====================================================
# DATASET
# =====================================================

DATASET = (
    DATA_DIR /
    "evaluation_dataset.csv"
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
    "PHASE 12 - AI DATA QUALITY PREDICTION"
)

print("=" * 70)


# =====================================================
# LOAD DATASET
# =====================================================

print("\n1. DATASET LOADING")

df = pd.read_csv(
    DATASET
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
# FEATURE PREPARATION
# =====================================================

print("\n2. FEATURE ENGINEERING")

feature_df = prepare_features(
    df
)

print(
    f"Numeric features analyzed: "
    f"{len(feature_df)}"
)


# =====================================================
# TRAINING DATA
# =====================================================

print("\n3. TRAINING DATA PREPARATION")

X, y = create_training_data(
    feature_df
)

print(
    f"Training samples: {len(X)}"
)

print(
    f"Risky features: {int(y.sum())}"
)


# =====================================================
# MODEL TRAINING
# =====================================================
print("\n4. RANDOM FOREST MODEL")

model, metrics = train_model(
    X,
    y
)

if model is None:

    print(
        "Random Forest training skipped."
    )

    print(
        f"Reason: {metrics['reason']}"
    )

else:

    print(
        "Model trained successfully!"
    )
# =====================================================
# PERFORMANCE
# =====================================================
print("\n5. MODEL PERFORMANCE")

if model is None:

    print(
        "No supervised model was trained "
        "because the dataset contains only "
        "one quality-risk class."
    )

else:

    print(
        f"Accuracy : "
        f"{metrics['accuracy']:.4f}"
    )

    print(
        f"Precision: "
        f"{metrics['precision']:.4f}"
    )

    print(
        f"Recall   : "
        f"{metrics['recall']:.4f}"
    )

    print(
        f"F1 Score : "
        f"{metrics['f1_score']:.4f}"
    )
# =====================================================
# PREDICTION
# =====================================================

if model is not None:

    predictions = model.predict(
        X
    )

    feature_df[
        "quality_risk"
    ] = predictions

else:

    feature_df[
        "quality_risk"
    ] = y

# =====================================================
# RECOMMENDATIONS
# =====================================================

print("\n7. AI RECOMMENDATIONS")

recommendations = []

for _, row in feature_df.iterrows():

    recommendation = generate_recommendation(

        row["missing_rate"],

        row["std"],

        row["unique_values"]
    )

    recommendations.append(
        " ".join(recommendation)
    )


feature_df[
    "recommendation"
] = recommendations


# =====================================================
# DISPLAY RESULTS
# =====================================================

print(
    "\nFeature Risk Analysis:"
)

print(
    feature_df[
        [
            "feature",
            "quality_risk",
            "missing_rate",
            "recommendation"
        ]
    ].to_string(
        index=False
    )
)


# =====================================================
# SAVE REPORT
# =====================================================

report_file = (
    REPORT_DIR /
    "phase12_quality_prediction.csv"
)

feature_df.to_csv(
    report_file,
    index=False
)


print("\n8. REPORT")

print(
    f"Report saved to:\n"
    f"{report_file}"
)


print("\n" + "=" * 70)

print(
    "Phase 12 completed successfully! 🚀"
)

print("=" * 70)