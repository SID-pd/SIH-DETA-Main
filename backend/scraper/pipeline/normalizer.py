"""
Normalizer for scraper-erail.
Standardizes entity formats and derives topological segments for DARPAN ETA engine.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("scraper_erail.normalizer")


def parse_time_to_minutes(time_str: str) -> int:
    """Converts HH:MM:SS or HH:MM to minutes from midnight."""
    parts = [int(p) for p in time_str.split(":")[:2]]
    return parts[0] * 60 + parts[1]


def calculate_transit_minutes(
    dep_time: str, arr_time: str, dep_day: int = 1, arr_day: int = 1
) -> float:
    """Calculates elapsed transit minutes considering overnight rollover."""
    t_dep = parse_time_to_minutes(dep_time)
    t_arr = parse_time_to_minutes(arr_time)
    day_diff = max(0, arr_day - dep_day)

    diff = (t_arr + day_diff * 1440) - t_dep
    if diff < 0:
        diff += 1440
    return float(diff)


class DataNormalizer:
    """Converts scraped records to canonical DARPAN DTOs and route graph segments."""

    @staticmethod
    def normalize_train_number(number: str) -> str:
        s = str(number).strip()
        if s.isdigit() and len(s) == 4:
            return f"0{s}"
        return s

    @staticmethod
    def derive_segments_from_stops(stops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Derives directed segment graph edges between consecutive stops for the ETA engine.
        Each segment represents (from_code -> to_code) with distance and scheduled runtime.
        """
        segments: List[Dict[str, Any]] = []
        if len(stops) < 2:
            return segments

        for i in range(len(stops) - 1):
            s_from = stops[i]
            s_to = stops[i + 1]

            from_code = s_from["station_code"]
            to_code = s_to["station_code"]

            dist_from = float(s_from.get("distance_km") or 0.0)
            dist_to = float(s_to.get("distance_km") or 0.0)
            seg_dist = max(0.0, dist_to - dist_from)

            dep = s_from.get("departure") or s_from.get("arrival")
            arr = s_to.get("arrival") or s_to.get("departure")

            sched_mins = None
            if dep and arr:
                try:
                    sched_mins = calculate_transit_minutes(
                        dep, arr, s_from.get("day", 1), s_to.get("day", 1)
                    )
                except Exception:
                    pass

            segments.append({
                "from_code": from_code,
                "to_code": to_code,
                "sched_minutes_p50": sched_mins,
                "sched_minutes_min": sched_mins,
                "distance_km": seg_dist,
                "n_timetables": 1,
                "hist_delay_added_p50": None,
                "hist_delay_added_p90": None,
                "n_obs": 0,
                "source": "scraped_schedule",
            })

        return segments
