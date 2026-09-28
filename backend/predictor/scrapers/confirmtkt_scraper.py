"""
ConfirmTkt Scraper.
Scrapes live train status, intermediate stations, schedules, delays, and current location.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from predictor.config import CONFIRMTKT_LIVE_URL
from predictor.scrapers.base_scraper import BaseScraper

logger = logging.getLogger("predictor.scrapers.confirmtkt")


class ConfirmTktScraper(BaseScraper):
    """Scrapes live train running status from ConfirmTkt."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_live_status(self, train_number: str, date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Fetches live train running status for a 5-digit train number.
        Returns parsed dictionary with current station, next station, delay, and full station timeline.
        """
        cleaned_train = str(train_number).strip().zfill(5)
        url = f"{CONFIRMTKT_LIVE_URL}/{cleaned_train}"
        params = {}
        if date:
            params["Date"] = date

        custom_headers = {
            "Referer": "https://www.confirmtkt.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        html = self.fetch_text(url, params=params, custom_headers=custom_headers)
        if not html:
            return None

        # Extract embedded `var data = {...};`
        m_data = re.search(r"var\s+data\s*=\s*(\{.*?\});\s*(?:var|\n|<)", html, re.DOTALL)
        if not m_data:
            logger.warning(f"Could not find data payload in ConfirmTkt response for {cleaned_train}")
            return None

        try:
            payload = json.loads(m_data.group(1))
        except Exception as exc:
            logger.warning(f"Error parsing JSON payload for {cleaned_train}: {exc}")
            return None

        # Extract live state variables from JS
        m_curr_code = re.search(r'var\s+currentStnCode\s*=\s*"(.*?)";', html)
        m_curr_name = re.search(r'var\s+currentStnName\s*=\s*"(.*?)";', html)
        m_delay = re.search(r"var\s+latestDelay\s*=\s*([0-9\-]+);", html)

        curr_code = m_curr_code.group(1).strip() if m_curr_code else None
        curr_name = m_curr_name.group(1).strip() if m_curr_name else None
        delay_min = int(m_delay.group(1)) if m_delay and m_delay.group(1) != "null" else 0

        # Parse schedule stops
        raw_schedules = payload.get("Schedule") or []
        stops: List[Dict[str, Any]] = []

        for idx, stop in enumerate(raw_schedules, start=1):
            stn_code = str(stop.get("StationCode") or "").strip().upper()
            stn_name = str(stop.get("StationName") or "").strip()
            dist = float(stop.get("Distance") or 0.0)
            sch_arr = str(stop.get("ArrivalTime") or stop.get("ScheduleArrival") or "").strip()
            sch_dep = str(stop.get("DepartureTime") or stop.get("ScheduleDeparture") or "").strip()
            act_arr = str(stop.get("ActualArrival") or sch_arr).strip()
            act_dep = str(stop.get("ActualDeparture") or sch_dep).strip()
            def _safe_int(val, default=0):
                if not val:
                    return default
                m = re.search(r"[-+]?\d+", str(val))
                return int(m.group(0)) if m else default

            halt = _safe_int(stop.get("HaltMinutes") or stop.get("Halt"))
            day = _safe_int(stop.get("Day"), default=1)
            lat = float(stop.get("Latitude") or 0.0) if stop.get("Latitude") else None
            lon = float(stop.get("Longitude") or 0.0) if stop.get("Longitude") else None
            arr_delay = _safe_int(stop.get("arrivalDelay"))
            dep_delay = _safe_int(stop.get("departureDelay"))

            stops.append({
                "seq": idx,
                "station_code": stn_code,
                "station_name": stn_name,
                "distance_km": dist,
                "scheduled_arrival": sch_arr,
                "scheduled_departure": sch_dep,
                "actual_arrival": act_arr,
                "actual_departure": act_dep,
                "halt_minutes": halt,
                "day": day,
                "latitude": lat,
                "longitude": lon,
                "arrival_delay": arr_delay,
                "departure_delay": dep_delay,
            })

        # Determine current and next stations
        current_idx = None
        if curr_code:
            for i, st in enumerate(stops):
                if st["station_code"] == curr_code.upper():
                    current_idx = i
                    break

        next_station = None
        if current_idx is not None and current_idx + 1 < len(stops):
            next_station = stops[current_idx + 1]
        elif stops:
            next_station = stops[0]

        return {
            "train_number": cleaned_train,
            "train_name": payload.get("TrainName") or f"Train {cleaned_train}",
            "source_code": stops[0]["station_code"] if stops else None,
            "destination_code": stops[-1]["station_code"] if stops else None,
            "total_distance_km": stops[-1]["distance_km"] if stops else 0.0,
            "current_station_code": curr_code,
            "current_station_name": curr_name,
            "current_delay_minutes": delay_min,
            "next_station_code": next_station["station_code"] if next_station else None,
            "next_station_name": next_station["station_name"] if next_station else None,
            "distance_to_next_station_km": (
                next_station["distance_km"] - (stops[current_idx]["distance_km"] if current_idx is not None else 0.0)
            ) if next_station else 0.0,
            "stops": stops,
            "raw_payload": payload,
        }
