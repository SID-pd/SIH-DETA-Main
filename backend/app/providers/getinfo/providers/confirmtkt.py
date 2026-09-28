"""
ConfirmTkt Provider.
Delivers direct JSON PNR status, live running status, journey timeline, and coach positions.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from client.http import http_client
from config import CONFIRMTKT_LIVE_PAGE, CONFIRMTKT_PNR_API
from models.schemas import (
    CoachInfo,
    CoachRakeResponse,
    LiveStatusResponse,
    PassengerRecord,
    PNRResponse,
    TimelineResponse,
    TimelineStop,
)
from providers.base import BaseProvider

logger = logging.getLogger("getinfo.providers.confirmtkt")

COACH_CATEGORY_MAP = {
    "ENG": "Locomotive / Engine",
    "EN": "Locomotive / Engine",
    "EOG": "End On Generation / Generator Van",
    "SLR": "Seating-cum-Luggage Rake / Guard Van",
    "GS": "General Second Class (Unreserved)",
    "GEN": "General Second Class (Unreserved)",
    "UR": "General Unreserved",
    "DL": "Second Class Divyangjan / Guard",
    "SL": "Sleeper Class (Non-AC)",
    "3A": "AC 3-Tier (Air Conditioned)",
    "2A": "AC 2-Tier (Air Conditioned)",
    "1A": "First Class AC",
    "3E": "AC 3-Tier Economy",
    "CC": "AC Chair Car",
    "EC": "Executive Chair Car",
    "EA": "Executive Anubhuti Chair Car",
    "EV": "Vistadome AC Coach",
    "PC": "Pantry Car / Dining Car",
    "HA": "First AC + AC 2-Tier Composite",
    "AB": "AC 2-Tier + AC 3-Tier Composite",
}


class ConfirmTktProvider(BaseProvider):
    """Primary provider using direct REST API for PNR and rich embedded streams for Live/Timeline."""

    @property
    def provider_id(self) -> str:
        return "confirmtkt"

    def get_pnr_status(self, pnr: str) -> Optional[PNRResponse]:
        """Queries ConfirmTkt direct JSON PNR gateway."""
        cleaned_pnr = re.sub(r"\D", "", pnr)
        if len(cleaned_pnr) != 10:
            return PNRResponse(
                success=False,
                pnr=pnr,
                error_message="Invalid PNR format. Indian Railways PNR must be 10 digits.",
                provider=self.provider_id,
            )

        url = f"{CONFIRMTKT_PNR_API}/{cleaned_pnr}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.confirmtkt.com/",
        }
        try:
            resp = http_client.get(url, headers=headers, provider_name="confirmtkt_pnr")
            text = resp.text.strip()
            if text.startswith("<"):
                # Fallback XML parser
                import xml.etree.ElementTree as ET
                root = ET.fromstring(text)
                data = {}
                for elem in root:
                    tag = elem.tag.split("}")[-1]  # remove namespace
                    data[tag] = elem.text
            else:
                data = json.loads(text)
        except Exception as e:
            logger.warning(f"ConfirmTkt PNR request error: {e}")
            return None

        # Check for error or flushed PNR
        error_msg = data.get("Error")
        if error_msg and not data.get("TrainNo"):
            return PNRResponse(
                success=False,
                pnr=cleaned_pnr,
                error_message=error_msg,
                provider=self.provider_id,
            )

        # Parse Passengers
        passengers: List[PassengerRecord] = []
        raw_passengers = data.get("PassengerStatus") or []
        for idx, p in enumerate(raw_passengers, start=1):
            b_status = str(p.get("BookingStatus") or "").strip()
            c_status = str(p.get("CurrentStatus") or "").strip()
            coach = str(p.get("Coach") or "").strip() or None
            berth_raw = p.get("Berth")
            berth = int(berth_raw) if berth_raw and str(berth_raw).isdigit() else None
            b_type = str(p.get("BerthType") or p.get("CurrentBerthCode") or p.get("BookingBerthCode") or "").strip() or None

            passengers.append(
                PassengerRecord(
                    passenger_no=idx,
                    booking_status=b_status,
                    current_status=c_status,
                    coach=coach,
                    berth=berth,
                    berth_type=b_type,
                )
            )

        train_no_str = str(data.get("TrainNo") or "").strip()
        return PNRResponse(
            success=True,
            pnr=cleaned_pnr,
            train_number=train_no_str if train_no_str and train_no_str != "None" else None,
            train_name=data.get("TrainName"),
            doj=data.get("Doj"),
            booking_date=data.get("BookingDate"),
            from_station=data.get("From"),
            to_station=data.get("To"),
            boarding_station=data.get("BoardingPoint"),
            reservation_upto=data.get("ReservationUpto"),
            travel_class=data.get("Class"),
            quota=data.get("Quota"),
            chart_prepared=bool(data.get("ChartPrepared")),
            passenger_count=len(passengers) or int(data.get("PassengerCount") or 0),
            passengers=passengers,
            expected_platform=str(data.get("ExpectedPlatformNo") or "").strip() or None,
            coach_position=data.get("CoachPosition"),
            has_pantry=bool(data.get("HasPantry")),
            provider=self.provider_id,
        )

    def _fetch_train_data_page(
        self, train_number: str, date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetches and extracts the embedded JSON `data` and live variables from ConfirmTkt page."""
        cleaned_train = train_number.strip().zfill(5)
        url = f"{CONFIRMTKT_LIVE_PAGE}/{cleaned_train}"
        params = {}
        if date:
            params["Date"] = date

        try:
            html = http_client.get_text(url, params=params, provider_name="confirmtkt_live")
        except Exception as e:
            logger.warning(f"ConfirmTkt page error for {cleaned_train}: {e}")
            return None

        # Extract `var data = {...};`
        m_data = re.search(r"var\s+data\s*=\s*(\{.*?\});\s*(?:var|\n|<)", html, re.DOTALL)
        if not m_data:
            return None

        try:
            payload = json.loads(m_data.group(1))
        except Exception as e:
            logger.warning(f"Failed to parse data JSON for {cleaned_train}: {e}")
            return None

        # Extract live running variables from the script
        m_curr_code = re.search(r'var\s+currentStnCode\s*=\s*"(.*?)";', html)
        m_curr_name = re.search(r'var\s+currentStnName\s*=\s*"(.*?)";', html)
        m_delay = re.search(r"var\s+latestDelay\s*=\s*([0-9\-]+);", html)

        curr_code = m_curr_code.group(1).strip() if m_curr_code else None
        curr_name = m_curr_name.group(1).strip() if m_curr_name else None
        delay_min = int(m_delay.group(1)) if m_delay and m_delay.group(1) != "null" else 0

        payload["_live_current_code"] = curr_code
        payload["_live_current_name"] = curr_name
        payload["_live_delay_min"] = delay_min
        return payload

    def get_live_status(
        self, train_number: str, date: Optional[str] = None
    ) -> Optional[LiveStatusResponse]:
        """Extracts real-time position, next station, delay and travel progress."""
        payload = self._fetch_train_data_page(train_number, date)
        if not payload:
            return None

        curr_code = payload.get("_live_current_code")
        curr_name = payload.get("_live_current_name")
        delay_min = payload.get("_live_delay_min", 0)

        # Status text synthesis
        if not curr_code:
            status_text = "Scheduled to start from source station"
        elif delay_min == 0:
            status_text = f"At/Departed {curr_name or curr_code} Right Time"
        elif delay_min > 0:
            status_text = f"At/Departed {curr_name or curr_code} {delay_min} mins late"
        else:
            status_text = f"At/Departed {curr_name or curr_code} {abs(delay_min)} mins early"

        # Determine next station and distance from schedule
        schedules = payload.get("Schedule") or []
        total_distance = 0.0
        distance_covered = 0.0
        next_station_code = None
        next_station_name = None

        if schedules:
            # Last station distance is total distance
            last_stop = schedules[-1]
            try:
                total_distance = float(last_stop.get("Distance") or 0.0)
            except ValueError:
                total_distance = 0.0

            # Find matching current station (either as a booked halt or in intermediateStations)
            matched = False
            for idx, stop in enumerate(schedules):
                s_code = stop.get("StationCode")
                if s_code and curr_code and s_code.upper() == curr_code.upper():
                    try:
                        distance_covered = float(stop.get("Distance") or 0.0)
                    except ValueError:
                        pass
                    if idx + 1 < len(schedules):
                        next_stop = schedules[idx + 1]
                        next_station_code = next_stop.get("StationCode")
                        next_station_name = next_stop.get("StationName")
                    matched = True
                    break

                # Check intermediate passing stations between halts
                for inter in (stop.get("intermediateStations") or []):
                    inter_code = inter.get("StationCode")
                    inter_name = inter.get("StationName")
                    if (inter_code and curr_code and inter_code.upper() == curr_code.upper()) or (
                        inter_name and curr_name and inter_name.upper() == curr_name.upper()
                    ):
                        try:
                            distance_covered = float(inter.get("Distance") or stop.get("Distance") or 0.0)
                        except ValueError:
                            pass
                        if idx + 1 < len(schedules):
                            next_stop = schedules[idx + 1]
                            next_station_code = next_stop.get("StationCode")
                            next_station_name = next_stop.get("StationName")
                        matched = True
                        break
                if matched:
                    break

        progress_pct = None
        if total_distance > 0 and distance_covered >= 0:
            progress_pct = round((distance_covered / total_distance) * 100, 1)

        return LiveStatusResponse(
            success=True,
            train_number=str(payload.get("TrainNo")),
            train_name=payload.get("TrainName", ""),
            current_station_code=curr_code,
            current_station_name=curr_name,
            next_station_code=next_station_code,
            next_station_name=next_station_name,
            delay_minutes=delay_min,
            status_text=status_text,
            distance_covered_km=distance_covered,
            total_distance_km=total_distance,
            journey_percentage=progress_pct,
            last_updated_time=payload.get("CacheTime"),
            provider=self.provider_id,
        )

    def get_coach_position(self, train_number: str) -> Optional[CoachRakeResponse]:
        """Extracts complete coach sequence and identifies rake type."""
        payload = self._fetch_train_data_page(train_number)
        if not payload:
            return None

        raw_coaches_str = payload.get("CoachPosition", "")
        if not raw_coaches_str:
            return None

        # Parse coach string: e.g. ",En:B1,3A:B2,3A:B3,3A:PC:H1,1A:A1,2A:"
        coaches: List[CoachInfo] = []
        tokens = [t.strip() for t in raw_coaches_str.split(":") if t.strip()]

        idx = 1
        for token in tokens:
            parts = token.split(",")
            coach_code = parts[0].strip()
            class_code = parts[1].strip() if len(parts) > 1 else None

            if not coach_code or coach_code in ("-", ""):
                continue

            # Determine category
            category = "Passenger Coach"
            upper_code = coach_code.upper()
            if upper_code in COACH_CATEGORY_MAP:
                category = COACH_CATEGORY_MAP[upper_code]
            elif class_code and class_code.upper() in COACH_CATEGORY_MAP:
                category = COACH_CATEGORY_MAP[class_code.upper()]
            elif upper_code.startswith("B"):
                category = "AC 3-Tier (Air Conditioned)"
                class_code = class_code or "3A"
            elif upper_code.startswith("A"):
                category = "AC 2-Tier (Air Conditioned)"
                class_code = class_code or "2A"
            elif upper_code.startswith("H"):
                category = "First Class AC"
                class_code = class_code or "1A"
            elif upper_code.startswith("S") and not upper_code.startswith("SLR"):
                category = "Sleeper Class (Non-AC)"
                class_code = class_code or "SL"
            elif upper_code.startswith("M"):
                category = "AC 3-Tier Economy"
                class_code = class_code or "3E"
            elif upper_code.startswith("C"):
                category = "AC Chair Car"
                class_code = class_code or "CC"
            elif upper_code.startswith("E"):
                category = "Executive Chair Car"
                class_code = class_code or "EC"

            coaches.append(
                CoachInfo(
                    position_index=idx,
                    coach_code=coach_code,
                    coach_category=category,
                    class_code=class_code,
                )
            )
            idx += 1

        # Detect Rake Type
        all_codes = [c.coach_code.upper() for c in coaches]
        if any(c.startswith("EOG") for c in all_codes) or any(c.startswith("B") for c in all_codes):
            rake_type = "LHB"
        elif any("VANDE" in payload.get("TrainName", "").upper() for _ in [1]):
            rake_type = "Vande Bharat"
        else:
            rake_type = "ICF / Conventional"

        return CoachRakeResponse(
            success=True,
            train_number=str(payload.get("TrainNo")),
            train_name=payload.get("TrainName"),
            rake_type=rake_type,
            total_coaches=len(coaches),
            coach_sequence=coaches,
            provider=self.provider_id,
        )

    def get_timeline(
        self, train_number: str, date: Optional[str] = None
    ) -> Optional[TimelineResponse]:
        """Extracts complete station-by-station schedule vs actual/estimated timeline."""
        payload = self._fetch_train_data_page(train_number, date)
        if not payload:
            return None

        schedules = payload.get("Schedule") or []
        stops: List[TimelineStop] = []

        # Determine distance covered from live station code or intermediate stations
        curr_code = payload.get("_live_current_code")
        curr_name = payload.get("_live_current_name")
        dist_covered = 0.0
        if curr_code:
            for s_item in schedules:
                if s_item.get("StationCode") and s_item.get("StationCode").upper() == curr_code.upper():
                    try:
                        dist_covered = float(s_item.get("Distance") or 0.0)
                    except ValueError:
                        pass
                    break
                for inter in (s_item.get("intermediateStations") or []):
                    if (inter.get("StationCode") and inter.get("StationCode").upper() == curr_code.upper()) or (
                        inter.get("StationName") and curr_name and inter.get("StationName").upper() == curr_name.upper()
                    ):
                        try:
                            dist_covered = float(inter.get("Distance") or s_item.get("Distance") or 0.0)
                        except ValueError:
                            pass
                        break
                if dist_covered > 0:
                    break

        for idx, item in enumerate(schedules, start=1):
            s_code = item.get("StationCode", "")
            s_name = item.get("StationName", "")
            sta = item.get("ArrivalTime") or None
            std = item.get("DepartureTime") or None
            halt = item.get("HaltMinutes")
            halt_min = int(halt) if halt and str(halt).isdigit() else None

            dist = 0.0
            try:
                dist = float(item.get("Distance") or 0.0)
            except ValueError:
                pass

            day = int(item.get("Day") or 1)
            plat = str(item.get("ExpectedPlatformNo") or "").strip() or None

            # Delays
            arr_delay_str = str(item.get("arrivalDelay") or "").strip()
            dep_delay_str = str(item.get("departureDelay") or "").strip()
            arr_delay = int(arr_delay_str) if arr_delay_str.isdigit() or (arr_delay_str.startswith("-") and arr_delay_str[1:].isdigit()) else None
            dep_delay = int(dep_delay_str) if dep_delay_str.isdigit() or (dep_delay_str.startswith("-") and dep_delay_str[1:].isdigit()) else None

            lat = float(item.get("Latitude")) if item.get("Latitude") is not None else None
            lon = float(item.get("Longitude")) if item.get("Longitude") is not None else None
            has_dep = bool(dist_covered > 0 and dist < dist_covered)

            stops.append(
                TimelineStop(
                    stop_number=idx,
                    station_code=s_code,
                    station_name=s_name,
                    scheduled_arrival=sta,
                    scheduled_departure=std,
                    actual_arrival=None,
                    actual_departure=None,
                    arrival_delay_min=arr_delay,
                    departure_delay_min=dep_delay,
                    halt_minutes=halt_min,
                    distance_km=dist,
                    day=day,
                    platform=plat,
                    latitude=lat,
                    longitude=lon,
                    has_departed=has_dep,
                )
            )

        return TimelineResponse(
            success=True,
            train_number=str(payload.get("TrainNo")),
            train_name=payload.get("TrainName", ""),
            source=payload.get("SourceCode", ""),
            destination=payload.get("DestinationCode", ""),
            total_stops=len(stops),
            stops=stops,
            provider=self.provider_id,
        )
