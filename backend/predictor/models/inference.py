"""
Real-time Station ETA & Delay Inference Engine.
Loads saved station_eta_model.joblib and computes continuous dynamic ETA,
delay predictions, and quantile confidence bounds (p10 to p90).
"""

import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import joblib
import pandas as pd
import numpy as np

from predictor.config import (
    FEATURE_COLUMNS_31,
    MODEL_ARTIFACT_PATH,
)
from predictor.data.feature_builder import FeatureBuilder, minutes_to_time_str, time_to_minutes

logger = logging.getLogger("predictor.models.inference")


class StationETAPredictor:
    """Predicts upcoming station arrival times, delay changes, and uncertainty intervals."""

    def __init__(self, model_path: Path = MODEL_ARTIFACT_PATH):
        self.model_path = model_path
        self.feature_builder = FeatureBuilder()
        self.model_bundle: Optional[Dict[str, Any]] = None
        self._load_model()

    def _load_model(self):
        """Loads trained model bundle if available."""
        if not self.model_path.exists():
            logger.warning(f"Model artifact not found at {self.model_path}. Train the model first.")
            return
        try:
            self.model_bundle = joblib.load(self.model_path)
            logger.info(f"Loaded Station ETA model bundle from {self.model_path}")
        except Exception as exc:
            logger.error(f"Failed to load model artifact: {exc}")

    def is_ready(self) -> bool:
        return self.model_bundle is not None

    def predict_next_station_eta(
        self,
        train_id: str,
        current_station: str,
        next_station: str,
        current_delay_minutes: float,
        scheduled_dep_curr: str,
        scheduled_arr_next: str,
        actual_dep_curr: Optional[str] = None,
        distance_to_next_km: Optional[float] = None,
        train_name: Optional[str] = None,
        train_route: Optional[str] = None,
        prev_station_delay: Optional[float] = None,
        scheduled_halt_min: float = 2.0,
        number_of_prev_halts: int = 4,
        number_of_rem_stations: int = 10,
        remaining_distance_km: float = 400.0,
        current_speed_kmph: Optional[float] = None,
        month: int = 9,
        day_of_week: int = 2,
    ) -> Dict[str, Any]:
        """
        Calculates dynamic ETA and predicted delay at the next station.
        Outputs expected delay, section transit time, arrival timestamp, and confidence interval.
        """
        sched_dep_min = time_to_minutes(scheduled_dep_curr)
        sched_arr_min = time_to_minutes(scheduled_arr_next)

        if actual_dep_curr:
            act_dep_min = time_to_minutes(actual_dep_curr)
        else:
            act_dep_min = (sched_dep_min + int(current_delay_minutes)) % 1440

        act_arr_min = (act_dep_min - int(scheduled_halt_min)) % 1440
        prev_delay = prev_station_delay if prev_station_delay is not None else current_delay_minutes
        route = train_route or f"{current_station}-{next_station}"
        dist_next = distance_to_next_km if distance_to_next_km is not None else 65.0

        # Build feature row (31 Features)
        feature_dict = self.feature_builder.build_feature_row(
            train_id=str(train_id),
            train_name=train_name or f"Train {train_id}",
            train_route=route,
            current_station=current_station,
            next_station=next_station,
            distance_to_next=dist_next,
            scheduled_arr_next_min=sched_arr_min,
            scheduled_dep_curr_min=sched_dep_min,
            actual_arr_curr_min=act_arr_min,
            actual_dep_curr_min=act_dep_min,
            current_delay=current_delay_minutes,
            prev_delay=prev_delay,
            scheduled_halt_duration=scheduled_halt_min,
            number_of_prev_halts=number_of_prev_halts,
            number_of_rem_stations=number_of_rem_stations,
            remaining_distance=remaining_distance_km,
            time_since_start_min=180,
            day_of_week=day_of_week,
            month=month,
            live_speed=current_speed_kmph,
        )

        df_input = pd.DataFrame([feature_dict])[FEATURE_COLUMNS_31]

        if not self.is_ready():
            # Heuristic fallback if model weights not yet trained
            sched_transit = (sched_arr_min - sched_dep_min) % 1440
            pred_delay = current_delay_minutes
            pred_travel_time = max(5.0, float(sched_transit))
            lower_bound_delay = max(0.0, current_delay_minutes - 5)
            upper_bound_delay = current_delay_minutes + 10
        else:
            preprocessor = self.model_bundle["preprocessor"]
            delay_model_p50 = self.model_bundle["delay_model_p50"]
            delay_model_p10 = self.model_bundle["delay_model_p10"]
            delay_model_p90 = self.model_bundle["delay_model_p90"]
            time_model = self.model_bundle.get("travel_time_model")

            from predictor.config import CATEGORICAL_FEATURES
            for col in CATEGORICAL_FEATURES:
                if col in df_input.columns:
                    df_input[col] = df_input[col].astype(str)

            X_proc = preprocessor.transform(df_input)
            pred_delay = float(delay_model_p50.predict(X_proc)[0])
            lower_bound_delay = max(0.0, float(delay_model_p10.predict(X_proc)[0]))
            upper_bound_delay = max(lower_bound_delay, float(delay_model_p90.predict(X_proc)[0]))

            if time_model:
                pred_travel_time = max(5.0, float(time_model.predict(X_proc)[0]))
            else:
                sched_transit = (sched_arr_min - sched_dep_min) % 1440
                pred_travel_time = max(5.0, float(sched_transit + (pred_delay - current_delay_minutes)))

        # Expected Arrival Time (Minutes from midnight)
        eta_minutes = (sched_arr_min + int(round(pred_delay))) % 1440
        eta_lower_min = (sched_arr_min + int(round(lower_bound_delay))) % 1440
        eta_upper_min = (sched_arr_min + int(round(upper_bound_delay))) % 1440

        eta_time_str = minutes_to_time_str(eta_minutes)
        eta_lower_str = minutes_to_time_str(eta_lower_min)
        eta_upper_str = minutes_to_time_str(eta_upper_min)

        # Delay trend analysis
        delay_change = pred_delay - current_delay_minutes
        if delay_change <= -2.0:
            trend = f"Recovering {abs(round(delay_change))} mins before arrival"
        elif delay_change >= 2.0:
            trend = f"Accumulating {round(delay_change)} additional mins due to section friction"
        else:
            trend = "Maintaining current delay (stable headway)"

        # Risk Factors
        risk_factors = []
        if feature_dict["weather"] > 0.4:
            risk_factors.append(f"Adverse Weather / Fog impact (severity index: {feature_dict['weather']:.2f})")
        if feature_dict["route_congestion_level"] > 0.75:
            risk_factors.append(f"High Density Route corridor (congestion: {feature_dict['route_congestion_level']:.2f})")
        if feature_dict["peak_off_peak_indicator"] == 1:
            risk_factors.append("Peak suburban commute slot congestion")

        return {
            "train_id": str(train_id),
            "train_type": feature_dict["train_type"],
            "current_station": current_station,
            "next_station": next_station,
            "distance_km": dist_next,
            "current_delay_minutes": round(current_delay_minutes, 1),
            "predicted_delay_at_next_station_minutes": round(pred_delay, 1),
            "delay_trend": trend,
            "predicted_section_travel_time_minutes": round(pred_travel_time, 1),
            "scheduled_arrival_time": scheduled_arr_next,
            "predicted_eta": eta_time_str,
            "eta_confidence_interval_90pct": f"{eta_lower_str} - {eta_upper_str} (+/-{round((upper_bound_delay - lower_bound_delay)/2)} mins)",
            "lower_bound_delay_min": round(lower_bound_delay, 1),
            "upper_bound_delay_min": round(upper_bound_delay, 1),
            "risk_factors": risk_factors,
            "feature_snapshot": feature_dict,
        }
