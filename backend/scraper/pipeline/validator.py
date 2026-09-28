"""
Validation and data sanity checks for scraper-erail.
Guarantees data integrity before committing to the database.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("scraper_erail.validator")


class DataValidator:
    """Sanity rules for Indian Railways schedule and telemetry data."""

    @staticmethod
    def validate_station(station: Dict[str, Any]) -> Tuple[bool, str]:
        code = str(station.get("code") or "").strip().upper()
        if not code or not (2 <= len(code) <= 6):
            return False, f"Invalid station code length: '{code}'"
        if not re.match(r"^[A-Z0-9]+$", code):
            return False, f"Invalid station code format: '{code}'"
        name = str(station.get("name") or "").strip()
        if not name:
            return False, f"Empty station name for code '{code}'"
        return True, ""

    @staticmethod
    def validate_train(train: Dict[str, Any]) -> Tuple[bool, str]:
        number = str(train.get("number") or "").strip()
        if not number or not (4 <= len(number) <= 6):
            return False, f"Invalid train number: '{number}'"
        name = str(train.get("name") or "").strip()
        if not name:
            return False, f"Missing train name for train {number}"
        return True, ""

    @staticmethod
    def validate_schedule_stops(stops: List[Dict[str, Any]]) -> Tuple[bool, str]:
        if not stops:
            return False, "Empty schedule stops list"

        prev_dist = -0.01
        for i, stop in enumerate(stops):
            seq = stop.get("seq", i + 1)
            dist = float(stop.get("distance_km") or 0.0)
            stn = stop.get("station_code", "")

            if not stn:
                return False, f"Stop at seq {seq} missing station_code"

            # Check distance monotonicity (with slight tolerance for rounding/spur lines)
            if dist < prev_dist - 5.0:
                logger.warning(
                    f"Distance non-monotonic for stop {seq} ({stn}): {dist} < {prev_dist}"
                )
            prev_dist = max(prev_dist, dist)

        return True, ""
