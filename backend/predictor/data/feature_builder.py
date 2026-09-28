"""
Feature Builder for 31-Feature Machine Learning ETA Dataset.
Assembles the complete feature matrix (X) and prediction labels (Y)
from static railway topology, historical delays, environmental factors, and live telemetry.
"""

import math
import logging
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from predictor.config import (
    DARPAN_DB_PATH,
    FEATURE_COLUMNS_31,
    PRIMARY_LABEL,
    SECONDARY_LABEL,
)
from predictor.scrapers.etrain_scraper import EtrainScraper
from predictor.scrapers.weather_client import WeatherClient

logger = logging.getLogger("predictor.data.feature_builder")


def time_to_minutes(t_str: Optional[str]) -> int:
    """Converts 'HH:MM' or 'HH:MM:SS' time string to minutes from midnight."""
    if not t_str or not isinstance(t_str, str) or ":" not in t_str:
        return 0
    try:
        parts = t_str.strip().split(":")
        hh = int(parts[0]) % 24
        mm = int(parts[1]) if len(parts) > 1 else 0
        return hh * 60 + mm
    except Exception:
        return 0


def minutes_to_time_str(mins: int) -> str:
    """Converts minutes from midnight to 'HH:MM' string."""
    mins = int(mins) % 1440
    hh = mins // 60
    mm = mins % 60
    return f"{hh:02d}:{mm:02d}"


def get_month_season(month: int) -> str:
    """Returns the climatic season for an Indian calendar month."""
    if month in (12, 1, 2):
        return "Winter"
    elif month in (3, 4, 5):
        return "Summer"
    elif month in (6, 7, 8, 9):
        return "Monsoon"
    else:
        return "Autumn"


def is_peak_hour(dep_minutes: int) -> int:
    """Peak commute hours: 06:00-10:00 (360-600) and 17:00-21:00 (1020-1260)."""
    return 1 if (360 <= dep_minutes <= 600) or (1020 <= dep_minutes <= 1260) else 0


class FeatureBuilder:
    """Constructs the exact 31 Features (X) and 2 Labels (Y) for station-level prediction."""

    def __init__(self, darpan_db_path=DARPAN_DB_PATH):
        self.darpan_db_path = darpan_db_path
        self.etrain_scraper = EtrainScraper()
        self.weather_client = WeatherClient()
        self._station_coords: Dict[str, Tuple[float, float]] = {}
        self._load_station_coordinates()

    def _load_station_coordinates(self):
        """Loads lat/lon for stations from darpan.sqlite."""
        if not self.darpan_db_path.exists():
            return
        try:
            conn = sqlite3.connect(self.darpan_db_path)
            cursor = conn.cursor()
            rows = cursor.execute("SELECT code, lat, lon FROM stations WHERE lat IS NOT NULL AND lon IS NOT NULL").fetchall()
            for code, lat, lon in rows:
                if code and lat and lon:
                    self._station_coords[code.strip().upper()] = (float(lat), float(lon))
            conn.close()
            logger.info(f"Loaded {len(self._station_coords)} station coordinates into memory.")
        except Exception as exc:
            logger.warning(f"Failed to load station coordinates from {self.darpan_db_path}: {exc}")

    def get_coordinates(self, station_code: str) -> Tuple[float, float]:
        """Returns (latitude, longitude) for a station code or default coordinates."""
        stn = str(station_code).strip().upper()
        if stn in self._station_coords:
            return self._station_coords[stn]
        # Central India default coordinate
        return (23.5, 78.5)

    def infer_train_type(self, train_id: str, train_name: Optional[str] = None) -> str:
        """Categorizes train into Vande Bharat, Rajdhani, Shatabdi, Superfast, Mail/Express, Passenger."""
        name = (train_name or "").upper()
        num = str(train_id)

        if "VANDE BHARAT" in name or num.startswith("206") or num.startswith("224"):
            return "Vande Bharat"
        elif "RAJDHANI" in name or num in ("12301", "12302", "12305", "12306", "12423", "12424"):
            return "Rajdhani"
        elif "SHATABDI" in name or num in ("12001", "12002", "12003", "12004"):
            return "Shatabdi"
        elif "DURONTO" in name or "GARIB RATH" in name:
            return "Duronto/Garib Rath"
        elif "SF" in name or "SUPERFAST" in name or (len(num) == 5 and num.startswith("12") or num.startswith("22")):
            return "Superfast"
        elif "PASSENGER" in name or "MEMU" in name or "DEMU" in name or (len(num) == 5 and num.startswith("5")):
            return "Passenger"
        else:
            return "Mail/Express"

    def estimate_zone_congestion(self, train_route: str) -> float:
        """High Density Networks (e.g. Delhi-Howrah, Delhi-Mumbai) have higher congestion index."""
        route = (train_route or "").upper()
        if any(h in route for h in ("NDLS", "CNB", "PRYJ", "DDU", "HWH", "GZB", "MGS")):
            return 0.85  # Northern / North-Central trunk line
        elif any(h in route for h in ("BCT", "MMCT", "BSR", "BRC", "ST")):
            return 0.75  # Western trunk line
        elif any(h in route for h in ("MAS", "SBC", "SC", "KCG")):
            return 0.55  # Southern / South-Central line
        return 0.60

    def build_feature_row(
        self,
        train_id: str,
        train_name: str,
        train_route: str,
        current_station: str,
        next_station: str,
        distance_to_next: float,
        scheduled_arr_next_min: int,
        scheduled_dep_curr_min: int,
        actual_arr_curr_min: int,
        actual_dep_curr_min: int,
        current_delay: float,
        prev_delay: float,
        scheduled_halt_duration: float,
        number_of_prev_halts: int,
        number_of_rem_stations: int,
        remaining_distance: float,
        time_since_start_min: int,
        day_of_week: int = 2,
        month: int = 9,
        live_speed: Optional[float] = None,
        date_str: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Constructs a complete single-row feature dictionary with all 31 features.
        """
        curr_lat, curr_lon = self.get_coordinates(current_station)
        train_type = self.infer_train_type(train_id, train_name)

        # Halt duration
        actual_halt = max(0.0, float(actual_dep_curr_min - actual_arr_curr_min))
        unscheduled_halt = 1 if (scheduled_halt_duration == 0 and actual_halt > 2.0) else 0

        # Section transit kinematics
        sched_travel_time = max(1.0, float((scheduled_arr_next_min - scheduled_dep_curr_min) % 1440))
        hist_avg_delay = self.etrain_scraper.get_historical_delay_for_station(train_id, next_station)

        # Speed estimations
        avg_speed = (distance_to_next / (sched_travel_time / 60.0)) if sched_travel_time > 0 else 65.0
        avg_speed = min(130.0, max(25.0, avg_speed))
        current_speed = live_speed if live_speed is not None else avg_speed * 0.95

        # Delay change between stations (proxy for signal/operational friction)
        signal_operational_delay = current_delay - prev_delay

        # Route congestion & environmental weather
        congestion = self.estimate_zone_congestion(train_route)
        hour = (actual_dep_curr_min // 60) % 24
        weather_info = self.weather_client.get_weather(curr_lat, curr_lon, date_str=date_str, hour=hour)
        weather_severity = weather_info.get("weather_severity_score", 0.1)

        season = get_month_season(month)
        peak_indicator = is_peak_hour(scheduled_dep_curr_min)

        row = {
            # 1. Train attributes
            "train_id": str(train_id).zfill(5),
            "train_type": train_type,
            "train_route": train_route,
            # 2. Topological
            "current_station": str(current_station).upper(),
            "next_station": str(next_station).upper(),
            "distance_to_next_station": round(float(distance_to_next), 2),
            # 3. Telemetry
            "current_latitude": round(float(curr_lat), 4),
            "current_longitude": round(float(curr_lon), 4),
            "current_speed": round(float(current_speed), 2),
            "average_speed": round(float(avg_speed), 2),
            # 4. Timings & Delays
            "scheduled_arrival_time": int(scheduled_arr_next_min),
            "scheduled_departure_time": int(scheduled_dep_curr_min),
            "actual_arrival_time": int(actual_arr_curr_min),
            "actual_departure_time": int(actual_dep_curr_min),
            "current_delay": round(float(current_delay), 2),
            "previous_station_delay": round(float(prev_delay), 2),
            # 5. Historical Priors
            "historical_average_delay": round(float(hist_avg_delay), 2),
            "historical_section_travel_time": round(float(sched_travel_time), 2),
            # 6. Halt Dynamics
            "number_of_previous_halts": int(number_of_prev_halts),
            "current_halt_duration": round(float(actual_halt), 2),
            "scheduled_halt_duration": round(float(scheduled_halt_duration), 2),
            "unscheduled_halt_flag": int(unscheduled_halt),
            # 7. Operational Realities
            "signal_operational_delay": round(float(signal_operational_delay), 2),
            "route_congestion_level": round(float(congestion), 2),
            "weather": round(float(weather_severity), 3),
            # 8. Calendar
            "day_of_week": int(day_of_week),
            "month_season": season,
            "peak_off_peak_indicator": int(peak_indicator),
            "time_since_journey_start": int(time_since_start_min),
            # 9. Remaining
            "remaining_distance": round(float(remaining_distance), 2),
            "number_of_remaining_stations": int(number_of_rem_stations),
        }
        return row
