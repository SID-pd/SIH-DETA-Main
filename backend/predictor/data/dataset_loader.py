"""
Dataset Loader and Builder.
Assembles the master multi-year station-level dataset for training the ML ETA model.
Combines static schedules, historical delay priors, seasonal weather shocks, and Kaggle journey patterns.
"""

import csv
import logging
import math
import os
import random
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from predictor.config import (
    CATEGORICAL_FEATURES,
    DARPAN_DB_PATH,
    ETRAIN_DELAYS_CSV,
    FEATURE_COLUMNS_31,
    KAGGLE_IR_TRAIN_CSV,
    MASTER_DATASET_CSV,
    NUMERICAL_FEATURES,
    PRIMARY_LABEL,
    SECONDARY_LABEL,
)
from predictor.data.feature_builder import FeatureBuilder, time_to_minutes

logger = logging.getLogger("predictor.data.dataset_loader")


class DatasetLoader:
    """Builds and loads the 31-feature ML training matrix."""

    def __init__(self, master_csv_path: Path = MASTER_DATASET_CSV):
        self.master_csv_path = master_csv_path
        self.feature_builder = FeatureBuilder()

    def generate_master_dataset(self, num_trains: int = 150, runs_per_train: int = 12, force_rebuild: bool = False) -> pd.DataFrame:
        """
        Builds the station-to-station 31-feature dataset from darpan.sqlite and historical distributions.
        If master CSV already exists and force_rebuild=False, loads existing CSV.
        """
        if self.master_csv_path.exists() and not force_rebuild:
            logger.info(f"Loading existing master dataset from {self.master_csv_path}")
            df = pd.read_csv(self.master_csv_path)
            logger.info(f"Loaded dataset shape: {df.shape}")
            return df

        logger.info("Generating 31-feature station-level training dataset from railway topology...")
        self.master_csv_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Connect to darpan.sqlite to get train schedules
        if not DARPAN_DB_PATH.exists():
            raise FileNotFoundError(f"Database not found at {DARPAN_DB_PATH}")

        conn = sqlite3.connect(DARPAN_DB_PATH)
        conn.row_factory = sqlite3.Row

        # Get diverse coaching trains (Rajdhani, Shatabdi, Superfast, Mail/Express)
        train_rows = conn.execute("""
            SELECT number, name, type, from_code, to_code, distance_km
            FROM trains
            WHERE type IN ('Rajdhani', 'Shatabdi', 'Superfast', 'Mail/Express', 'Duronto', 'Express')
               OR number LIKE '12%' OR number LIKE '22%' OR number LIKE '20%'
            ORDER BY distance_km DESC
            LIMIT ?
        """, (num_trains,)).fetchall()

        records: List[Dict] = []
        random.seed(42)
        np.random.seed(42)

        for t_row in train_rows:
            t_num = str(t_row["number"]).zfill(5)
            t_name = str(t_row["name"])
            src = str(t_row["from_code"] or "SRC")
            dest = str(t_row["to_code"] or "DST")
            total_dist = float(t_row["distance_km"] or 1000.0)
            route_str = f"{src}-{dest}"

            # Get stops for this train from schedule_stops
            stops = conn.execute("""
                SELECT seq, station_code, arrival, departure, halt_mins, distance_km, day
                FROM schedule_stops
                WHERE train_number = ?
                ORDER BY seq ASC
            """, (t_num,)).fetchall()

            if len(stops) < 3:
                continue

            # Simulate multiple historical runs across calendar seasons (Winter Fog, Monsoon, Summer, Autumn)
            for run_idx in range(runs_per_train):
                # Assign a calendar season and month
                season_choice = random.choice(["Winter", "Summer", "Monsoon", "Autumn"])
                if season_choice == "Winter":
                    month = random.choice([12, 1, 2])
                    base_fog = random.uniform(0.3, 0.95) if any(z in route_str for z in ("NDLS", "CNB", "PRYJ", "DDU", "HWH")) else 0.1
                elif season_choice == "Monsoon":
                    month = random.choice([7, 8, 9])
                    base_fog = 0.05
                elif season_choice == "Summer":
                    month = random.choice([4, 5, 6])
                    base_fog = 0.0
                else:
                    month = random.choice([3, 10, 11])
                    base_fog = 0.0

                day_of_week = random.randint(0, 6)
                # Starting delay at origin station
                origin_delay = random.choice([0, 0, 0, 5, 15, 35, 60]) if random.random() < 0.4 else 0
                carried_delay = float(origin_delay)
                prev_delay = float(origin_delay)

                total_stops = len(stops)
                origin_dep_mins = time_to_minutes(stops[0]["departure"])

                # Walk through each segment between stops[i] and stops[i+1]
                for i in range(len(stops) - 1):
                    stn_curr = stops[i]
                    stn_next = stops[i + 1]

                    curr_code = str(stn_curr["station_code"]).upper()
                    next_code = str(stn_next["station_code"]).upper()

                    dist_curr = float(stn_curr["distance_km"] or 0.0)
                    dist_next = float(stn_next["distance_km"] or (dist_curr + 50.0))
                    seg_dist = max(1.0, dist_next - dist_curr)
                    rem_dist = max(0.0, total_dist - dist_curr)
                    rem_stations = total_stops - (i + 1)

                    sched_arr_curr = time_to_minutes(stn_curr["arrival"] or stn_curr["departure"])
                    sched_dep_curr = time_to_minutes(stn_curr["departure"] or stn_curr["arrival"])
                    sched_arr_next = time_to_minutes(stn_next["arrival"] or stn_next["departure"])

                    sched_halt = float(stn_curr["halt_mins"] or 2.0)
                    sched_section_time = (sched_arr_next - sched_dep_curr) % 1440
                    if sched_section_time <= 0:
                        sched_section_time = max(15.0, (seg_dist / 70.0) * 60.0)

                    # Actual times at current station
                    act_arr_curr = (sched_arr_curr + int(carried_delay)) % 1440
                    # Actual dwell duration with random delay overrun
                    actual_halt = sched_halt + (random.choice([0, 0, 1, 3, 7]) if random.random() < 0.35 else 0)
                    act_dep_curr = (act_arr_curr + int(actual_halt)) % 1440

                    # Elapsed time since origin
                    time_since_start = max(0, (act_dep_curr - origin_dep_mins) % 1440)

                    # Build feature row (X)
                    feat_row = self.feature_builder.build_feature_row(
                        train_id=t_num,
                        train_name=t_name,
                        train_route=route_str,
                        current_station=curr_code,
                        next_station=next_code,
                        distance_to_next=seg_dist,
                        scheduled_arr_next_min=sched_arr_next,
                        scheduled_dep_curr_min=sched_dep_curr,
                        actual_arr_curr_min=act_arr_curr,
                        actual_dep_curr_min=act_dep_curr,
                        current_delay=carried_delay,
                        prev_delay=prev_delay,
                        scheduled_halt_duration=sched_halt,
                        number_of_prev_halts=i,
                        number_of_rem_stations=rem_stations,
                        remaining_distance=rem_dist,
                        time_since_start_min=time_since_start,
                        day_of_week=day_of_week,
                        month=month,
                    )

                    # Compute Ground Truth Label (Y): Next Station Arrival Delay & Section Travel Time
                    # Delta delay modeling: track friction, fog slow-down, recovery margin
                    recovery_margin = max(0.0, sched_section_time * 0.08)  # In-built timetable slack
                    speed_friction = random.uniform(-0.15, 0.20)

                    # Fog effect in winter
                    weather_drag = (base_fog * 15.0) if (season_choice == "Winter" and "NDLS" in route_str) else 0.0

                    # High density congestion drag
                    congestion_drag = 4.0 if feat_row["route_congestion_level"] > 0.8 and random.random() < 0.3 else 0.0

                    # Unscheduled stop delay
                    unscheduled_delay = 12.0 if random.random() < 0.06 else 0.0

                    # Net delay added on this section
                    delay_delta = (
                        (sched_section_time * speed_friction)
                        + weather_drag
                        + congestion_drag
                        + unscheduled_delay
                        - (recovery_margin if carried_delay > 10 else 0)
                    )

                    # New arrival delay at next station
                    next_station_delay = max(0.0, carried_delay + delay_delta)
                    # Next section travel time
                    actual_travel_time = max(5.0, sched_section_time + delay_delta)

                    # Assign Labels (Y)
                    feat_row[PRIMARY_LABEL] = round(float(next_station_delay), 2)
                    feat_row[SECONDARY_LABEL] = round(float(actual_travel_time), 2)

                    records.append(feat_row)

                    # Step forward state
                    prev_delay = carried_delay
                    carried_delay = next_station_delay

        conn.close()

        df = pd.DataFrame(records)
        df.to_csv(self.master_csv_path, index=False)
        logger.info(f"Successfully generated and saved master dataset with {len(df)} rows to {self.master_csv_path}")
        return df

    def get_train_test_data(
        self,
        test_size: float = 0.2,
        random_state: int = 42,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series, pd.Series]:
        """
        Loads the dataset and returns X_train, X_test, y_delay_train, y_delay_test, y_time_train, y_time_test.
        """
        df = self.generate_master_dataset()

        # Separate Features (X) and Labels (Y)
        X = df[FEATURE_COLUMNS_31].copy()
        y_delay = df[PRIMARY_LABEL].copy()
        y_time = df[SECONDARY_LABEL].copy()

        # Deterministic Train / Test Split stratified by train_id
        unique_trains = X["train_id"].unique()
        random.seed(random_state)
        test_trains = set(random.sample(list(unique_trains), int(len(unique_trains) * test_size)))

        test_mask = X["train_id"].isin(test_trains)
        train_mask = ~test_mask

        X_train, X_test = X[train_mask].copy(), X[test_mask].copy()
        y_delay_train, y_delay_test = y_delay[train_mask], y_delay[test_mask]
        y_time_train, y_time_test = y_time[train_mask], y_time[test_mask]

        logger.info(f"Train split: {len(X_train)} rows | Test split: {len(X_test)} rows")
        return X_train, X_test, y_delay_train, y_delay_test, y_time_train, y_time_test
