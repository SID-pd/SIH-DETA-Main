"""
Model Evaluation and Feature Importance Analysis.
Analyzes error distributions across train types, seasons, and generates feature importance rankings.
"""

import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from predictor.config import FEATURE_COLUMNS_31, PRIMARY_LABEL, SECONDARY_LABEL

logger = logging.getLogger("predictor.models.evaluate")


def evaluate_models(
    model_bundle: Dict[str, Any],
    X_test: pd.DataFrame,
    y_delay_test: pd.Series,
    y_time_test: Optional[pd.Series] = None,
) -> Dict[str, Any]:
    """
    Evaluates the trained model bundle and produces feature importances and segment segmentations.
    """
    preprocessor = model_bundle["preprocessor"]
    delay_model = model_bundle["delay_model_p50"]
    travel_time_model = model_bundle.get("travel_time_model")

    from predictor.config import CATEGORICAL_FEATURES
    X_test_copy = X_test.copy()
    for col in CATEGORICAL_FEATURES:
        if col in X_test_copy.columns:
            X_test_copy[col] = X_test_copy[col].astype(str)

    X_test_proc = preprocessor.transform(X_test_copy)
    pred_delay = delay_model.predict(X_test_proc)

    delay_mae = mean_absolute_error(y_delay_test, pred_delay)
    delay_rmse = np.sqrt(mean_squared_error(y_delay_test, pred_delay))
    delay_r2 = r2_score(y_delay_test, pred_delay)

    # Compute Feature Importances safely
    try:
        feature_names = preprocessor.get_feature_names_out()
    except Exception:
        feature_names = [f"feat_{i}" for i in range(X_test_proc.shape[1])]

    if hasattr(delay_model, "feature_importances_"):
        importances = delay_model.feature_importances_
    else:
        from sklearn.inspection import permutation_importance
        sub_n = min(400, len(y_delay_test))
        perm = permutation_importance(
            delay_model, X_test_proc[:sub_n], y_delay_test.values[:sub_n], n_repeats=2, random_state=42
        )
        importances = perm.importances_mean

    feat_imp_df = pd.DataFrame({
        "feature": feature_names,
        "importance": importances,
    }).sort_values("importance", ascending=False)

    top_15_features = feat_imp_df.head(15).to_dict(orient="records")

    # Segment Performance by Train Type
    eval_df = X_test.copy()
    eval_df["true_delay"] = y_delay_test.values
    eval_df["pred_delay"] = pred_delay
    eval_df["abs_error"] = np.abs(eval_df["true_delay"] - eval_df["pred_delay"])

    by_type = {}
    if "train_type" in eval_df.columns:
        for t_type, group in eval_df.groupby("train_type"):
            by_type[str(t_type)] = {
                "count": int(len(group)),
                "mae_minutes": round(float(group["abs_error"].mean()), 2),
            }

    # Segment Performance by Season
    by_season = {}
    if "month_season" in eval_df.columns:
        for season, group in eval_df.groupby("month_season"):
            by_season[str(season)] = {
                "count": int(len(group)),
                "mae_minutes": round(float(group["abs_error"].mean()), 2),
            }

    report = {
        "overall_metrics": {
            "delay_mae_minutes": round(float(delay_mae), 2),
            "delay_rmse_minutes": round(float(delay_rmse), 2),
            "delay_r2_score": round(float(delay_r2), 3),
            "test_samples": len(X_test),
        },
        "top_feature_importances": top_15_features,
        "mae_by_train_type": by_type,
        "mae_by_season": by_season,
    }

    return report
