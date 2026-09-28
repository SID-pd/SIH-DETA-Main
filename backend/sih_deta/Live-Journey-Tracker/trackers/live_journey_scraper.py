"""
Live Journey Scraper: Extracts real-time GPS telemetry, instantaneous delay,
platform allocations, scheduled stops, and intermediate signaling cabins from live running feeds.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import CONFIRMTKT_RUNNING_STATUS_URL
from trackers.base_tracker import BaseTracker

logger = logging.getLogger("live_tracker")


def _parse_delay_mins(delay_str: Optional[str]) -> int:
    """Parse delay string like '07 Min', '08 Min', '-', or integer into signed minutes."""
    if not delay_str or delay_str in ("-", "--", "RT", "Right Time", "On Time"):
        return 0

    try:
        # Match digits in string
        match = re.search(r"(\d+)", str(delay_str))
        if match:
            mins = int(match.group(1))
            if "early" in str(delay_str).lower():
                return -mins
            return mins
        return int(delay_str)
    except (ValueError, TypeError):
        return 0


class LiveJourneyScraper(BaseTracker):
    """Scrapes and parses real-time train running status telemetry."""

    def fetch_live_status(
        self,
        train_number: str,
        journey_date: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch live running status for any Indian Railways train.
        
        Args:
            train_number: 5-digit train number (e.g. '12004', '12301')
            journey_date: Optional journey start date (e.g. 'today', 'yesterday', or 'YYYYMMDD')
        """
        train_clean = str(train_number).strip()
        if len(train_clean) == 4 and train_clean.isdigit():
            train_clean = "0" + train_clean

        url = f"{CONFIRMTKT_RUNNING_STATUS_URL}{train_clean}"
        if journey_date:
            url += f"?Date={journey_date}"

        logger.info(f"Fetching live journey status for train {train_clean} from {url}...")
        html = self.get(url)

        if not html or not isinstance(html, str):
            logger.warning(f"No response received for train {train_clean}")
            return None

        return self._parse_telemetry_html(train_clean, html)

    def _parse_telemetry_html(self, train_number: str, html: str) -> Optional[Dict[str, Any]]:
        """Extract JavaScript telemetry payload from HTML page."""
        # 1. Extract JSON data payload (var data = {...};)
        data_match = re.search(r"var\s+data\s*=\s*(\{.*?\});\s*(?:var|\n|$)", html, re.DOTALL)
        if not data_match:
            logger.warning(f"Could not locate live telemetry JSON payload in page for train {train_number}")
            return None

        try:
            raw_data = json.loads(data_match.group(1))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse live telemetry JSON for {train_number}: {e}")
            return None

        # 2. Extract current station and latest delay from script variables
        cur_stn_code_match = re.search(r'var\s+currentStnCode\s*=\s*["\']([^"\']*)["\']', html)
        cur_stn_name_match = re.search(r'var\s+currentStnName\s*=\s*["\']([^"\']*)["\']', html)
        latest_delay_match = re.search(r"var\s+latestDelay\s*=\s*(-?\d+)", html)

        current_station_code = cur_stn_code_match.group(1).strip().upper() if cur_stn_code_match else ""
        current_station_name = cur_stn_name_match.group(1).strip() if cur_stn_name_match else ""
        latest_delay_mins = int(latest_delay_match.group(1)) if latest_delay_match else 0

        # 3. Parse Station Schedule & Intermediate Cabins
        schedule_raw = raw_data.get("Schedule", [])
        stops: List[Dict[str, Any]] = []
        all_intermediate_cabins: List[Dict[str, Any]] = []

        has_passed_tracker = True

        for item in schedule_raw:
            stn_code = str(item.get("StationCode", "")).strip().upper()
            stn_name = str(item.get("StationName", "")).strip()
            arr_delay_str = str(item.get("arrivalDelay", "-"))
            dep_delay_str = str(item.get("departureDelay", "-"))
            platform = str(item.get("ExpectedPlatformNo", "")).strip()
            dist_str = str(item.get("Distance", "0.0"))

            try:
                dist_km = float(dist_str)
            except ValueError:
                dist_km = 0.0

            arr_delay_mins = _parse_delay_mins(arr_delay_str)
            dep_delay_mins = _parse_delay_mins(dep_delay_str)

            is_current = (stn_code == current_station_code)
            if is_current:
                # If this is the current station, subsequent stations haven't been reached
                has_passed = True
                has_passed_tracker = False
            else:
                has_passed = has_passed_tracker

            # Process intermediate cabins / block sections
            intermediate_raw = item.get("intermediateStations", [])
            cabins: List[Dict[str, Any]] = []
            for inter in intermediate_raw:
                c_code = str(inter.get("StationCode", "")).strip().upper()
                c_name = str(inter.get("StationName", "")).strip()
                c_dist = str(inter.get("Distance", "0.0"))
                try:
                    c_dist_km = float(c_dist)
                except ValueError:
                    c_dist_km = 0.0

                cabin_obj = {
                    "station_code": c_code,
                    "station_name": c_name,
                    "scheduled_arrival": inter.get("ArrivalTime", ""),
                    "scheduled_departure": inter.get("DepartureTime", ""),
                    "distance_km": c_dist_km,
                    "latitude": inter.get("Latitude"),
                    "longitude": inter.get("Longitude"),
                    "stop_number": inter.get("stopNumberDisplay"),
                    "parent_station": stn_code,
                }
                cabins.append(cabin_obj)
                all_intermediate_cabins.append(cabin_obj)

            stop_obj = {
                "station_code": stn_code,
                "station_name": stn_name,
                "stop_number": item.get("StopNumber", len(stops) + 1),
                "scheduled_arrival": item.get("ArrivalTime", ""),
                "scheduled_departure": item.get("DepartureTime", ""),
                "halt_minutes": item.get("HaltMinutes", ""),
                "expected_platform": platform if platform and platform != "null" else None,
                "distance_km": dist_km,
                "arrival_delay_mins": arr_delay_mins,
                "departure_delay_mins": dep_delay_mins,
                "day": item.get("Day", 1),
                "latitude": item.get("Latitude"),
                "longitude": item.get("Longitude"),
                "has_wifi": item.get("HasWifi", False),
                "has_passed": has_passed,
                "is_current": is_current,
                "intermediate_stations_count": len(cabins),
                "intermediate_stations": cabins,
            }
            stops.append(stop_obj)

        # Fallback for current station if not matched in script variable
        if not current_station_code and stops:
            current_station_code = stops[-1]["station_code"]
            current_station_name = stops[-1]["station_name"]

        status_summary = (
            f"Train {train_number} ({raw_data.get('TrainName', '')}): "
            f"At/Departed {current_station_name} ({current_station_code}) "
            f"with {latest_delay_mins}m delay."
        )

        return {
            "train_number": train_number,
            "train_name": raw_data.get("TrainName", ""),
            "train_type": raw_data.get("TrainType", "EXPRESS"),
            "source_code": raw_data.get("SourceCode", ""),
            "source_name": raw_data.get("Source", ""),
            "destination_code": raw_data.get("DestinationCode", ""),
            "destination_name": raw_data.get("Destination", ""),
            "total_duration": raw_data.get("TotalDuration", ""),
            "classes": raw_data.get("Classes", []),
            "days_of_run": raw_data.get("DaysOfRun", {}),
            "current_station_code": current_station_code,
            "current_station_name": current_station_name,
            "latest_delay_minutes": latest_delay_mins,
            "status_message": status_summary,
            "total_stops": len(stops),
            "total_intermediate_cabins": len(all_intermediate_cabins),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "schedule": stops,
            "intermediate_cabins": all_intermediate_cabins,
        }
