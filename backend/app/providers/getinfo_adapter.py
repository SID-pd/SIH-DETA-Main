"""
GetInfoAdapter: Adapts Get-info multi-provider cascading engine to DARPAN canonical DTOs.
Provides quota-free, zero-downtime live status, timeline, coach layout, and PNR data.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# Add getinfo directory to sys.path so its internal engine imports resolve seamlessly
_GETINFO_DIR = os.path.dirname(os.path.abspath(__file__))
_GETINFO_ROOT = os.path.join(_GETINFO_DIR, "getinfo")
if _GETINFO_ROOT not in sys.path:
    sys.path.insert(0, _GETINFO_ROOT)

from fetcher import InfoFetcher  # type: ignore

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist_iso() -> str:
    return datetime.now(IST).isoformat()


def _parse_time_to_iso(time_str: Optional[str], ref_date: Optional[str] = None) -> Optional[str]:
    """Convert HH:MM or DD-MM-YYYY HH:MM to ISO 8601 with +05:30 offset."""
    if not time_str or time_str.strip() in ("", "--", "-", "N/A"):
        return None
    time_str = time_str.strip()
    # If already ISO-like
    if "T" in time_str and "+" in time_str:
        return time_str
    
    # If just HH:MM (e.g. '16:50')
    if len(time_str) == 5 and ":" in time_str:
        today = datetime.now(IST).date()
        if ref_date:
            try:
                today = datetime.strptime(ref_date, "%d-%m-%Y").date()
            except ValueError:
                pass
        return f"{today.isoformat()}T{time_str}:00+05:30"
    
    # Try parsing common formats
    for fmt in ("%d-%m-%Y %H:%M", "%d-%b-%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(time_str, fmt).replace(tzinfo=IST)
            return dt.isoformat()
        except ValueError:
            continue
    return None


class GetInfoAdapter:
    """
    In-process provider adapter using the multi-provider cascading engine.
    Ensures zero external API quota dependency.
    """

    def __init__(self):
        self.fetcher = InfoFetcher()

    def live_status(self, train_number: str, date: Optional[str] = None) -> Dict[str, Any]:
        """Produce canonical live status DTO expected by DARPAN api."""
        date_param = date or datetime.now(IST).strftime("%d-%m-%Y")
        live_res = self.fetcher.get_live_status(train_number, date=date_param)
        timeline_res = self.fetcher.get_timeline(train_number, date=date_param)
        rake_res = self.fetcher.get_coach_position(train_number)

        unavailable: List[str] = ["position.speedKmph"]
        stops: List[Dict[str, Any]] = []
        
        # Build stops from timeline if available
        if timeline_res and timeline_res.stops:
            curr_code = (live_res.current_station_code if live_res else None) or ""
            dist_covered = float(live_res.distance_covered_km or 0.0) if live_res else 0.0

            for idx, s in enumerate(timeline_res.stops):
                s_dist = float(s.distance_km or 0.0)
                is_curr_stn = bool(curr_code and s.station_code.upper() == curr_code.upper())

                # Determine status
                if s.has_departed:
                    status = "passed"
                elif dist_covered > 0:
                    if is_curr_stn:
                        status = "current"
                    elif s_dist < dist_covered:
                        status = "passed"
                    else:
                        status = "upcoming"
                elif is_curr_stn:
                    status = "current"
                elif idx == 0 and dist_covered == 0:
                    status = "current"
                else:
                    status = "upcoming"
                
                sched_arr = _parse_time_to_iso(s.scheduled_arrival, date_param)
                act_arr = _parse_time_to_iso(s.actual_arrival, date_param)
                sched_dep = _parse_time_to_iso(s.scheduled_departure, date_param)
                act_dep = _parse_time_to_iso(s.actual_departure, date_param)

                stops.append({
                    "stationCode": s.station_code,
                    "stationName": s.station_name,
                    "status": status,
                    "distanceKm": s.distance_km,
                    "platform": s.platform,
                    "arrival": {
                        "scheduled": sched_arr,
                        "actual": act_arr,
                        "delayMinutes": s.arrival_delay_min,
                    },
                    "departure": {
                        "scheduled": sched_dep,
                        "actual": act_dep,
                        "delayMinutes": s.departure_delay_min,
                    },
                })
        
        # Build rake composition
        composition: List[Dict[str, Any]] = []
        if rake_res and rake_res.coach_sequence:
            for c in rake_res.coach_sequence:
                composition.append({
                    "position": c.position_index,
                    "label": c.coach_code,
                    "type": c.class_code or c.coach_category or "GEN",
                    "code": c.coach_code,
                    "category": c.coach_category,
                    "class": c.class_code,
                })

        current_delay = live_res.delay_minutes if live_res else 0
        train_display_name = (live_res.train_name if live_res else None) or (
            timeline_res.train_name if timeline_res else f"Train {train_number}"
        )

        return {
            "train": {
                "number": train_number,
                "name": train_display_name,
                "journeyDate": date_param,
            },
            "position": {
                "lastStationCode": live_res.current_station_code if live_res else None,
                "lastStationName": live_res.current_station_name if live_res else None,
                "currentStationCode": live_res.current_station_code if live_res else None,
                "nextStationCode": live_res.next_station_code if live_res else None,
                "nextStationName": live_res.next_station_name if live_res else None,
                "distanceCoveredKm": live_res.distance_covered_km if live_res else None,
                "totalDistanceKm": live_res.total_distance_km if live_res else None,
                "speedKmph": None,
                "delayMinutes": current_delay,
                "lastUpdateAt": (live_res.last_updated_time if live_res else None) or _now_ist_iso(),
            },
            "stops": stops,
            "passingPoints": [],
            "composition": composition,
            "unavailableFields": unavailable,
        }

    def train_info(self, train_number: str) -> Dict[str, Any]:
        """Produce canonical train info DTO."""
        timeline_res = self.fetcher.get_timeline(train_number)
        return {
            "train": {
                "number": train_number,
                "name": timeline_res.train_name if timeline_res else f"Train {train_number}",
                "from": {"code": timeline_res.source if timeline_res else None},
                "to": {"code": timeline_res.destination if timeline_res else None},
            },
            "route": [
                {"stationCode": s.station_code, "stationName": s.station_name, "distanceKm": s.distance_km}
                for s in (timeline_res.stops if timeline_res else [])
            ],
        }

    def pnr(self, pnr: str) -> Dict[str, Any]:
        """Produce canonical PNR DTO."""
        pnr_res = self.fetcher.get_pnr_status(pnr)
        if not pnr_res or not pnr_res.success:
            return {
                "pnr": pnr,
                "train": {"number": None, "name": None},
                "journeyDate": None,
                "from": {"code": None, "name": None},
                "to": {"code": None, "name": None},
                "reservationClass": None,
                "quota": None,
                "chartPrepared": None,
                "passengers": [],
                "error": pnr_res.error_message if pnr_res else "PNR lookup failed",
            }

        passengers: List[Dict[str, Any]] = []
        for p in pnr_res.passengers:
            passengers.append({
                "serial": p.passenger_no,
                "bookingStatus": p.booking_status,
                "currentStatus": p.current_status,
                "coach": p.coach,
                "berth": p.berth,
                "berthType": p.berth_type,
            })

        from_code = pnr_res.from_station
        to_code = pnr_res.to_station

        return {
            "pnr": pnr,
            "train": {
                "number": pnr_res.train_number,
                "name": pnr_res.train_name,
            },
            "journeyDate": pnr_res.doj,
            "from": {"code": from_code, "name": from_code},
            "to": {"code": to_code, "name": to_code},
            "fromStation": {"code": from_code, "name": from_code},
            "toStation": {"code": to_code, "name": to_code},
            "boardingPoint": pnr_res.boarding_station,
            "reservationClass": pnr_res.travel_class,
            "quota": pnr_res.quota,
            "chartPrepared": pnr_res.chart_prepared,
            "expectedPlatform": pnr_res.expected_platform,
            "passengers": passengers,
        }
