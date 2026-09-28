"""
Training pipeline for dynamic station-level train ETA and delay prediction.
Trains Gradient Boosting Regressors with Quantile Estimation (p10, p50, p90) for confidence intervals.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from predictor.config import (
    ARTIFACTS_DIR,
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS_31,
    MODEL_ARTIFACT_PATH,
    NUMERICAL_FEATURES,
    PRIMARY_LABEL,
    SECONDARY_LABEL,
)
from predictor.data.dataset_loader import DatasetLoader

logger = logging.getLogger("predictor.models.train")


def build_preprocessor() -> ColumnTransformer:
    """Builds preprocessor for numerical and categorical features."""
    num_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    cat_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="UNKNOWN")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False, max_categories=30)),
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", num_pipeline, NUMERICAL_FEATURES),
            ("cat", cat_pipeline, CATEGORICAL_FEATURES),
        ],
        remainder="drop",
    )
    return preprocessor


def train_station_eta_models(
    dataset_loader: Optional[DatasetLoader] = None,
    save_path: Path = MODEL_ARTIFACT_PATH,
) -> Dict[str, Any]:
    """
    Trains:
    1. Primary Point Delay Regressor (delay_at_next_station_minutes - p50)
    2. Lower Bound Quantile Regressor (p10)
    3. Upper Bound Quantile Regressor (p90)
    4. Travel Time Regressor (travel_time_to_next_station_minutes)
    Uses HistGradientBoostingRegressor (LightGBM algorithm) for high performance.
    """
    loader = dataset_loader or DatasetLoader()
    save_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Loading training and testing data splits...")
    X_train, X_test, y_delay_train, y_delay_test, y_time_train, y_time_test = loader.get_train_test_data()

    # Subsample if dataset is very large (> 80k) for ultra-fast training
    if len(X_train) > 80000:
        logger.info(f"Subsampling {len(X_train)} train rows down to 80,000 for rapid training...")
        sample_idx = X_train.sample(n=80000, random_state=42).index
        X_train = X_train.loc[sample_idx]
        y_delay_train = y_delay_train.loc[sample_idx]
        y_time_train = y_time_train.loc[sample_idx]

    if len(X_test) > 20000:
        test_sample_idx = X_test.sample(n=20000, random_state=42).index
        X_test = X_test.loc[test_sample_idx]
        y_delay_test = y_delay_test.loc[test_sample_idx]
        y_time_test = y_time_test.loc[test_sample_idx]

    logger.info(f"Training on {len(X_train)} samples across {len(FEATURE_COLUMNS_31)} features...")

    # Ensure categorical features are uniformly strings
    for col in CATEGORICAL_FEATURES:
        if col in X_train.columns:
            X_train[col] = X_train[col].astype(str)
        if col in X_test.columns:
            X_test[col] = X_test[col].astype(str)

    # 1. Fit Preprocessor
    preprocessor = build_preprocessor()
    X_train_proc = preprocessor.fit_transform(X_train)
    X_test_proc = preprocessor.transform(X_test)

    # 2. Train Point Predictor for Delay (Mean / Median)
    logger.info("Training Primary Delay Regressor (p50 / squared_error)...")
    delay_regressor_p50 = HistGradientBoostingRegressor(
        loss="squared_error",
        max_iter=90,
        learning_rate=0.09,
        max_depth=6,
        random_state=42,
    )
    delay_regressor_p50.fit(X_train_proc, y_delay_train)

    # 3. Train Quantile Regressors for Confidence Bounds (p10 and p90)
    logger.info("Training Quantile Regressors (p10 and p90) for ETA Uncertainty Intervals...")
    delay_regressor_p10 = HistGradientBoostingRegressor(
        loss="quantile",
        quantile=0.10,
        max_iter=70,
        learning_rate=0.09,
        max_depth=5,
        random_state=42,
    )
    delay_regressor_p10.fit(X_train_proc, y_delay_train)

    delay_regressor_p90 = HistGradientBoostingRegressor(
        loss="quantile",
        quantile=0.90,
        max_iter=70,
        learning_rate=0.09,
        max_depth=5,
        random_state=42,
    )
    delay_regressor_p90.fit(X_train_proc, y_delay_train)

    # 4. Train Section Travel Time Regressor
    logger.info("Training Section Travel Time Regressor (minutes to next station)...")
    travel_time_regressor = HistGradientBoostingRegressor(
        loss="squared_error",
        max_iter=90,
        learning_rate=0.09,
        max_depth=6,
        random_state=42,
    )
    travel_time_regressor.fit(X_train_proc, y_time_train)

    # 5. Evaluate Performance on Test Set
    pred_delay_test = delay_regressor_p50.predict(X_test_proc)
    pred_time_test = travel_time_regressor.predict(X_test_proc)

    delay_mae = mean_absolute_error(y_delay_test, pred_delay_test)
    delay_rmse = np.sqrt(mean_squared_error(y_delay_test, pred_delay_test))
    delay_r2 = r2_score(y_delay_test, pred_delay_test)

    time_mae = mean_absolute_error(y_time_test, pred_time_test)
    time_rmse = np.sqrt(mean_squared_error(y_time_test, pred_time_test))
    time_r2 = r2_score(y_time_test, pred_time_test)

    metrics = {
        "primary_label": PRIMARY_LABEL,
        "delay_mae_minutes": round(float(delay_mae), 3),
        "delay_rmse_minutes": round(float(delay_rmse), 3),
        "delay_r2_score": round(float(delay_r2), 3),
        "secondary_label": SECONDARY_LABEL,
        "travel_time_mae_minutes": round(float(time_mae), 3),
        "travel_time_rmse_minutes": round(float(time_rmse), 3),
        "travel_time_r2_score": round(float(time_r2), 3),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "num_features": len(FEATURE_COLUMNS_31),
    }

    logger.info(f"--- Evaluation Results on Unseen Test Segments ---")
    logger.info(f"Delay MAE: {delay_mae:.2f} mins | RMSE: {delay_rmse:.2f} mins | R2: {delay_r2:.3f}")
    logger.info(f"Travel Time MAE: {time_mae:.2f} mins | RMSE: {time_rmse:.2f} mins | R2: {time_r2:.3f}")

    # 6. Save Complete Model Bundle
    bundle = {
        "preprocessor": preprocessor,
        "delay_model_p50": delay_regressor_p50,
        "delay_model_p10": delay_regressor_p10,
        "delay_model_p90": delay_regressor_p90,
        "travel_time_model": travel_time_regressor,
        "feature_columns": FEATURE_COLUMNS_31,
        "categorical_features": CATEGORICAL_FEATURES,
        "numerical_features": NUMERICAL_FEATURES,
        "metrics": metrics,
    }

    joblib.dump(bundle, save_path)
    logger.info(f"Saved trained station ETA model bundle to {save_path}")

    return {
        "bundle": bundle,
        "metrics": metrics,
        "X_test": X_test,
        "y_delay_test": y_delay_test,
        "pred_delay_test": pred_delay_test,
    }
