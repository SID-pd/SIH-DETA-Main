"""
Parsers for CRIS NTES (enquiry.indianrail.gov.in) feeds.
Handles live running telemetry, operational exception lists (rescheduled, cancelled, diverted),
and official working timetables.
"""

from __future__ import annotations

import datetime
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from core.parser_erail import clean_time, parse_halt_minutes

logger = logging.getLogger("scraper_erail.parser_ntes")


class NtesParser:
    """Specialized parser for CRIS NTES web and API responses."""

    @staticmethod
    def parse_live_status(raw: str, train_number: str, journey_date: str) -> List[Dict[str, Any]]:
        """
        Parses NTES Spot Your Train running status.
        Extracts per-station live observation records:
        sched_arrival, actual_arrival, arrival_delay_mins, sched_dep, actual_dep,
        platform, status, current location.
        """
        observations: List[Dict[str, Any]] = []
        if not raw or not raw.strip():
            return observations

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        current_loc_str = "In Transit"

        # Check if JSON payload (mobile / ajax)
        if raw.strip().startswith("{") and "stations" in raw:
            import json
            try:
                data = json.loads(raw)
                current_loc_str = data.get("currentLocation") or data.get("curStn") or "In Transit"
                stn_list = data.get("stations") or data.get("halts") or []
                for stn in stn_list:
                    stn_code = (stn.get("stationCode") or stn.get("code") or "").upper()
                    if not stn_code:
                        continue

                    arr_delay = int(stn.get("arrDelay") or stn.get("delay") or 0)
                    dep_delay = int(stn.get("depDelay") or arr_delay)

                    observations.append({
                        "train_number": train_number,
                        "journey_date": journey_date,
                        "station_code": stn_code,
                        "observed_at": now_iso,
                        "sched_arrival": clean_time(stn.get("schArr")),
                        "actual_arrival": clean_time(stn.get("actArr")),
                        "arrival_delay_mins": arr_delay,
                        "sched_departure": clean_time(stn.get("schDep")),
                        "actual_departure": clean_time(stn.get("actDep")),
                        "departure_delay_mins": dep_delay,
                        "platform": str(stn.get("platform") or ""),
                        "status": str(stn.get("status") or "Unknown"),
                        "current_location": current_loc_str,
                        "source": "ntes",
                    })
                return observations
            except Exception:
                pass

        # HTML Table Parsing
        soup = BeautifulSoup(raw, "html.parser")

        # Check header status message (e.g. "Train departed NDLS at 17:15")
        status_banner = soup.find(class_=re.compile(r"status|banner|current", re.I))
        if status_banner:
            current_loc_str = status_banner.get_text(strip=True)[:200]

        table = soup.find("table")
        if not table:
            return observations

        for tr in table.find_all("tr"):
            cols = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cols) < 5:
                continue

            # Check header
            if "Station" in cols[0] or "Code" in cols[0]:
                continue

            # Format in NTES: Station (Code) | Sch Arr | Act Arr | Sch Dep | Act Dep | Delay | PF
            stn_text = cols[0]
            code_match = re.search(r"\(([A-Z0-9]{2,6})\)", stn_text)
            stn_code = code_match.group(1).upper() if code_match else stn_text.split()[0].upper()

            sch_arr = clean_time(cols[1]) if len(cols) > 1 else None
            act_arr = clean_time(cols[2]) if len(cols) > 2 else None
            sch_dep = clean_time(cols[3]) if len(cols) > 3 else None
            act_dep = clean_time(cols[4]) if len(cols) > 4 else None

            delay_mins = 0
            if len(cols) > 5:
                delay_str = cols[5]
                nums = re.findall(r"\d+", delay_str)
                if nums:
                    delay_mins = int(nums[0])
                    if "early" in delay_str.lower():
                        delay_mins = -delay_mins

            platform = cols[6].strip() if len(cols) > 6 else None
            status = "In Transit"
            if act_dep:
                status = "Departed"
            elif act_arr:
                status = "Arrived"

            observations.append({
                "train_number": train_number,
                "journey_date": journey_date,
                "station_code": stn_code,
                "observed_at": now_iso,
                "sched_arrival": sch_arr,
                "actual_arrival": act_arr,
                "arrival_delay_mins": delay_mins,
                "sched_departure": sch_dep,
                "actual_departure": act_dep,
                "departure_delay_mins": delay_mins,
                "platform": platform,
                "status": status,
                "current_location": current_loc_str,
                "source": "ntes",
            })

        return observations

    @staticmethod
    def parse_train_exceptions(raw: str, journey_date: str, default_type: str = "RESCHEDULED") -> List[Dict[str, Any]]:
        """
        Parses NTES Train Exception Info (Rescheduled, Cancelled, Diverted).
        """
        exceptions: List[Dict[str, Any]] = []
        if not raw or not raw.strip():
            return exceptions

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        soup = BeautifulSoup(raw, "html.parser")
        tables = soup.find_all("table")

        for table in tables:
            for tr in table.find_all("tr"):
                cols = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(cols) < 3:
                    continue

                # Detect train number
                t_num_match = re.search(r"\b\d{5}\b", cols[0])
                if not t_num_match and len(cols) > 1:
                    t_num_match = re.search(r"\b\d{5}\b", cols[1])
                if not t_num_match:
                    continue

                train_number = t_num_match.group(0)
                orig_dep = None
                resched_dep = None
                delay_origin = 0
                diverted_via = None
                reason = None

                ex_type = default_type.upper()
                if "CANCEL" in raw.upper() or "CANCEL" in cols[0].upper():
                    ex_type = "CANCELLED"
                elif "DIVERT" in raw.upper() or "DIVERT" in cols[0].upper():
                    ex_type = "DIVERTED"

                # Parse times if available
                times = re.findall(r"\d{1,2}:\d{2}", " ".join(cols))
                if len(times) >= 2 and ex_type == "RESCHEDULED":
                    orig_dep = clean_time(times[0])
                    resched_dep = clean_time(times[1])
                elif len(times) == 1:
                    resched_dep = clean_time(times[0])

                delays = re.findall(r"(\d+)\s*(?:hrs?|mins?|m|h)", " ".join(cols), re.I)
                if delays:
                    delay_origin = int(delays[0])

                if ex_type == "DIVERTED":
                    diverted_via = cols[-1] if len(cols) > 2 else None

                exceptions.append({
                    "train_number": train_number,
                    "journey_date": journey_date,
                    "exception_type": ex_type,
                    "original_departure": orig_dep,
                    "rescheduled_departure": resched_dep,
                    "delay_at_origin_mins": delay_origin,
                    "diverted_via": diverted_via,
                    "reason": reason,
                    "source": "ntes",
                    "recorded_at": now_iso,
                })

        return exceptions
