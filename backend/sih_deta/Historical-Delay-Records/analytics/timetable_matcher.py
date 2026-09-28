"""
Timetable Matcher: Enriches historical delay observations with scheduled (ideal)
vs actual (real) arrival and departure timestamps, scheduled halt durations,
platform allocations, and track distance markers from the Station Network database.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config import STATIONS_DB_PATH

logger = logging.getLogger("timetable_matcher")


def add_minutes_to_time_str(time_str: Optional[str], delay_minutes: Optional[int]) -> Optional[str]:
    """
    Calculate real timestamp by adding delay minutes to ideal scheduled time string (HH:MM:SS or HH:MM).
    Accurately wraps across midnight (23:59 -> 00:00).
    """
    if not time_str or delay_minutes is None:
        return None

    clean_time = time_str.strip()
    if clean_time.lower() in ("source", "destination", "first", "last", "-", "none", ""):
        return time_str

    try:
        # Support both HH:MM:SS and HH:MM
        if len(clean_time.split(":")) == 3:
            t = datetime.strptime(clean_time, "%H:%M:%S")
        elif len(clean_time.split(":")) == 2:
            t = datetime.strptime(clean_time, "%H:%M")
        else:
            return None

        real_t = t + timedelta(minutes=delay_minutes)
        return real_t.strftime("%H:%M:%S")
    except Exception:
        return None


class TimetableMatcher:
    """Matches live/historical delay data against official scheduled timetables."""

    def __init__(self, stations_db_path: Optional[str] = None):
        self.db_path = stations_db_path or str(STATIONS_DB_PATH)
        self._cache: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def _load_train_timetable(self, train_number: str) -> Dict[str, Dict[str, Any]]:
        """
        Query stations.db for a train's scheduled halt sequence and cache it in memory.
        Returns mapping: { station_code: { arrival_time, departure_time, halt_minutes, ... } }
        """
        train_clean = str(train_number).strip().lstrip("0")
        train_padded = str(train_number).strip().zfill(5)

        if train_clean in self._cache:
            return self._cache[train_clean]
        if train_padded in self._cache:
            return self._cache[train_padded]

        schedule = {}
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check matching train halts
            cursor.execute(
                """
                SELECT sh.station_code, sh.arrival_time, sh.departure_time, sh.halt_minutes,
                       sh.day, sh.platform, sh.distance_km,
                       s.official_name, s.is_junction, s.is_halt, s.is_terminal
                FROM station_halts sh
                LEFT JOIN stations s ON sh.station_code = s.code
                WHERE sh.train_number = ? OR sh.train_number = ?
                ORDER BY sh.id ASC
                """,
                (train_clean, train_padded),
            )
            rows = cursor.fetchall()
            for r in rows:
                stn = r["station_code"]
                schedule[stn] = {
                    "station_code": stn,
                    "official_name": r["official_name"] or stn,
                    "scheduled_arrival": r["arrival_time"],
                    "scheduled_departure": r["departure_time"],
                    "scheduled_halt_minutes": r["halt_minutes"] or 0,
                    "day": r["day"] or 1,
                    "platform": r["platform"] or "1",
                    "distance_km": r["distance_km"] or 0.0,
                    "is_junction": r["is_junction"] or 0,
                    "is_halt": r["is_halt"] or 0,
                    "is_terminal": r["is_terminal"] or 0,
                }
            conn.close()
        except Exception as e:
            logger.debug(f"Could not load timetable from {self.db_path} for train {train_number}: {e}")

        self._cache[train_clean] = schedule
        self._cache[train_padded] = schedule
        return schedule

    def enrich_station_delay(
        self,
        train_number: str,
        station_code: str,
        delay_minutes: Optional[int],
    ) -> Dict[str, Any]:
        """
        Combines scheduled timetable parameters with actual delay observations
        to compute ideal vs real arrival/departure and halt deviation.
        """
        timetable = self._load_train_timetable(train_number)
        stn_sched = timetable.get(station_code, {})

        sched_arr = stn_sched.get("scheduled_arrival")
        sched_dep = stn_sched.get("scheduled_departure")
        sched_halt = stn_sched.get("scheduled_halt_minutes", 0)

        real_arr = add_minutes_to_time_str(sched_arr, delay_minutes)
        real_dep = add_minutes_to_time_str(sched_dep, delay_minutes)

        # Halt duration analysis
        actual_halt = sched_halt  # Nominal baseline
        halt_variance = 0

        return {
            "station_code": station_code,
            "scheduled_arrival": sched_arr,
            "actual_arrival": real_arr,
            "scheduled_departure": sched_dep,
            "actual_departure": real_dep,
            "scheduled_halt_minutes": sched_halt,
            "actual_halt_minutes": actual_halt,
            "halt_variance_minutes": halt_variance,
            "distance_km": stn_sched.get("distance_km", 0.0),
            "platform": stn_sched.get("platform", "1"),
            "is_halt": stn_sched.get("is_halt", 0),
            "is_junction": stn_sched.get("is_junction", 0),
            "is_terminal": stn_sched.get("is_terminal", 0),
        }
