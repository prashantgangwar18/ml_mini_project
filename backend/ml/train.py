import json
from datetime import datetime, timezone
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import ML_ARTIFACTS_DIR, ML_DATA_DIR
from ml.features import FEATURE_COLUMNS, LATE_CLASS_NAMES
from ml.generate_data import generate_synthetic_dataset


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def train_and_evaluate(regenerate_data: bool = False) -> dict:
    """Train TOA regressor, delay regressor, and late classifier; save artifacts and metrics."""
    data_path = ML_DATA_DIR / "historical_trips.csv"
    if regenerate_data or not data_path.exists():
        generate_synthetic_dataset(output_path=data_path)

    df = pd.read_csv(data_path)

    # Chronological split by trip_id to prevent same-trip data leakage
    unique_trips = np.sort(df["trip_id"].unique())
    n_trips = len(unique_trips)
    train_cutoff = unique_trips[int(n_trips * 0.70)]
    val_cutoff = unique_trips[int(n_trips * 0.85)]

    train_df = df[df["trip_id"] <= train_cutoff]
    val_df = df[(df["trip_id"] > train_cutoff) & (df["trip_id"] <= val_cutoff)]
    test_df = df[df["trip_id"] > val_cutoff]

    X_train, X_val, X_test = (
        train_df[FEATURE_COLUMNS],
        val_df[FEATURE_COLUMNS],
        test_df[FEATURE_COLUMNS],
    )

    y_toa_train = train_df["actual_remaining_min"].values
    y_toa_val = val_df["actual_remaining_min"].values
    y_toa_test = test_df["actual_remaining_min"].values

    y_delay_train = train_df["actual_delay_min"].values
    y_delay_test = test_df["actual_delay_min"].values

    y_cls_train = train_df["late_label"].values
    y_cls_test = test_df["late_label"].values

    # 1. Heuristic baseline: distance / rolling_speed + stop dwell
    baseline_pred = (
        (test_df["remaining_route_km"].values / np.maximum(test_df["rolling_speed_kmh"].values, 12.0))
        * 60.0
        + test_df["stops_remaining"].values * 0.65
    )

    # 2. Ridge Regression baseline
    ridge_pipe = Pipeline([("scaler", StandardScaler()), ("ridge", Ridge(alpha=1.0))])
    ridge_pipe.fit(X_train, y_toa_train)
    ridge_pred = np.maximum(0.2, ridge_pipe.predict(X_test))

    # 3. LightGBM TOA Regressor
    toa_model = LGBMRegressor(
        n_estimators=260,
        learning_rate=0.05,
        num_leaves=31,
        subsample_for_bin=50000,
        random_state=42,
        verbose=-1,
    )
    toa_model.fit(
        X_train,
        y_toa_train,
        eval_set=[(X_val, y_toa_val)],
    )
    toa_pred = np.maximum(0.2, toa_model.predict(X_test))

    # 4. LightGBM Delay Regressor
    delay_model = LGBMRegressor(
        n_estimators=240,
        learning_rate=0.05,
        num_leaves=31,
        random_state=42,
        verbose=-1,
    )
    delay_model.fit(X_train, y_delay_train)
    delay_pred = delay_model.predict(X_test)

    # 5. LightGBM Late Classifier (On Time / Slightly Late / Late)
    late_clf = LGBMClassifier(
        n_estimators=240,
        learning_rate=0.05,
        num_leaves=31,
        class_weight="balanced",
        random_state=42,
        verbose=-1,
    )
    late_clf.fit(X_train, y_cls_train)
    cls_pred = late_clf.predict(X_test)

    # Feature importance (normalized %)
    raw_imp = toa_model.feature_importances_.astype(float)
    total_imp = max(float(raw_imp.sum()), 1.0)
    feature_importance = sorted(
        [
            {"feature": col, "importance": round(float(val / total_imp * 100.0), 2)}
            for col, val in zip(FEATURE_COLUMNS, raw_imp)
        ],
        key=lambda x: x["importance"],
        reverse=True,
    )

    class_counts = {
        LATE_CLASS_NAMES[int(k)]: int(v)
        for k, v in zip(*np.unique(df["late_label"].values, return_counts=True))
    }

    metrics = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "total_samples": int(len(df)),
            "total_trips": int(n_trips),
            "train_samples": int(len(train_df)),
            "val_samples": int(len(val_df)),
            "test_samples": int(len(test_df)),
            "class_distribution": class_counts,
        },
        "toa_models": {
            "heuristic_baseline": {
                "mae_min": round(float(mean_absolute_error(y_toa_test, baseline_pred)), 3),
                "rmse_min": round(_rmse(y_toa_test, baseline_pred), 3),
                "r2": round(float(r2_score(y_toa_test, baseline_pred)), 4),
            },
            "ridge_regression": {
                "mae_min": round(float(mean_absolute_error(y_toa_test, ridge_pred)), 3),
                "rmse_min": round(_rmse(y_toa_test, ridge_pred), 3),
                "r2": round(float(r2_score(y_toa_test, ridge_pred)), 4),
            },
            "lightgbm_toa": {
                "mae_min": round(float(mean_absolute_error(y_toa_test, toa_pred)), 3),
                "rmse_min": round(_rmse(y_toa_test, toa_pred), 3),
                "r2": round(float(r2_score(y_toa_test, toa_pred)), 4),
            },
        },
        "delay_regression": {
            "mae_min": round(float(mean_absolute_error(y_delay_test, delay_pred)), 3),
            "rmse_min": round(_rmse(y_delay_test, delay_pred), 3),
            "r2": round(float(r2_score(y_delay_test, delay_pred)), 4),
        },
        "late_classification": {
            "accuracy": round(float(accuracy_score(y_cls_test, cls_pred)), 4),
            "macro_f1": round(float(f1_score(y_cls_test, cls_pred, average="macro")), 4),
        },
        "feature_importance": feature_importance[:10],
    }

    ML_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(toa_model, ML_ARTIFACTS_DIR / "toa_model.joblib")
    joblib.dump(delay_model, ML_ARTIFACTS_DIR / "delay_model.joblib")
    joblib.dump(late_clf, ML_ARTIFACTS_DIR / "late_classifier.joblib")
    (ML_ARTIFACTS_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    return metrics


if __name__ == "__main__":
    result = train_and_evaluate(regenerate_data=True)
    print(json.dumps(result, indent=2))
