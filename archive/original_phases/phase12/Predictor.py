import pandas as pd
import numpy as np

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score
)


def prepare_features(df):

    numeric_df = df.select_dtypes(
        include="number"
    ).copy()

    if numeric_df.empty:
        raise ValueError(
            "Dataset does not contain numeric features."
        )

    features = []

    for column in numeric_df.columns:

        series = numeric_df[column]

        std = series.std()

        if pd.isna(std):
            std = 0

        features.append({

            "feature": column,

            "missing_values":
                int(series.isnull().sum()),

            "missing_rate":
                float(series.isnull().mean()),

            "mean":
                float(series.mean()),

            "std":
                float(std),

            "min":
                float(series.min()),

            "max":
                float(series.max()),

            "unique_values":
                int(series.nunique())
        })

    return pd.DataFrame(features)


def create_training_data(feature_df):

    X = feature_df[
        [
            "missing_values",
            "missing_rate",
            "mean",
            "std",
            "min",
            "max",
            "unique_values"
        ]
    ].copy()

    # Quality-risk rule
    #
    # 1 = risky
    # 0 = healthy

    y = (

        (feature_df["missing_rate"] > 0.20)

        |

        (feature_df["std"] == 0)

        |

        (feature_df["unique_values"] <= 1)

    ).astype(int)

    return X, y


def train_model(X, y):

    # -------------------------------------------------
    # CHECK NUMBER OF CLASSES
    # -------------------------------------------------

    if y.nunique() < 2:

        return None, {

            "status":
                "SKIPPED",

            "reason":
                "Training data contains only one class.",

            "accuracy":
                None,

            "precision":
                None,

            "recall":
                None,

            "f1_score":
                None
        }


    # -------------------------------------------------
    # TRAIN TEST SPLIT
    # -------------------------------------------------

    X_train, X_test, y_train, y_test = train_test_split(

        X,

        y,

        test_size=0.30,

        random_state=42,

        stratify=y
    )


    # -------------------------------------------------
    # RANDOM FOREST
    # -------------------------------------------------

    model = RandomForestClassifier(

        n_estimators=100,

        random_state=42
    )


    model.fit(

        X_train,

        y_train
    )


    # -------------------------------------------------
    # PREDICTION
    # -------------------------------------------------

    predictions = model.predict(

        X_test
    )


    # -------------------------------------------------
    # METRICS
    # -------------------------------------------------

    metrics = {

        "status":
            "TRAINED",

        "accuracy":
            accuracy_score(
                y_test,
                predictions
            ),

        "precision":
            precision_score(
                y_test,
                predictions,
                zero_division=0
            ),

        "recall":
            recall_score(
                y_test,
                predictions,
                zero_division=0
            ),

        "f1_score":
            f1_score(
                y_test,
                predictions,
                zero_division=0
            )
    }


    return model, metrics