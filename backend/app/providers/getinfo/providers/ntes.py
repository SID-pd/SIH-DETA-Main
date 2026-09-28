"""
CRIS NTES Provider.
Official government source for train telemetry, live passages, and operational exceptions.
"""

from __future__ import annotations

import datetime
import logging
import re
from typing import Any, Dict, List, Optional

from client.http import http_client
from config import NTES_BASE_URL
from models.schemas import (
    CancelledTrain,
    DivertedTrain,
    ExceptionsResponse,
    LiveStatusResponse,
    RescheduledTrain,
    TimelineResponse,
    TimelineStop,
)
from providers.base import BaseProvider

logger = logging.getLogger("getinfo.providers.ntes")


class NtesProvider(BaseProvider):
    """CRIS NTES provider for live passage telemetry and operational exception feeds."""

    @property
    def provider_id(self) -> str:
        return "ntes"

    def _get_today_date_str(self) -> str:
        today_ist = datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        )
        return today_ist.strftime("%d-%m-%Y")

    def get_live_status(
        self, train_number: str, date: Optional[str] = None
    ) -> Optional[LiveStatusResponse]:
        """Scrapes official NTES live running status."""
        journey_date = date or self._get_today_date_str()
        cleaned_train = train_number.strip().zfill(5)

        url = f"{NTES_BASE_URL}/q"
        params = {
            "opt": "TrainRunning",
            "subOpt": "FindTrain",
            "trainNo": cleaned_train,
            "dt": journey_date,
        }

        try:
            html = http_client.get_text(url, params=params, provider_name="ntes_live")
        except Exception as e:
            logger.warning(f"NTES live request error for {cleaned_train}: {e}")
            return None

        # Parse current station and delay from NTES HTML table
        # Look for table rows with station passage info
        m_train_name = re.search(r"<h3[^>]*>(.*?)</h3>", html)
        train_title = m_train_name.group(1).strip() if m_train_name else f"Train {cleaned_train}"

        # Search for status announcement box
        m_status = re.search(r'<div[^>]+class=[\'"][^\'"]*status[^\'"]*[\'"][^>]*>(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
        status_text = ""
        if m_status:
            status_text = re.sub(r"<[^>]+>", " ", m_status.group(1)).strip()

        # Extract last passed station
        last_station_code = None
        last_station_name = None
        delay_min = 0

        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
        for r in rows:
            cols = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.DOTALL)]
            if len(cols) >= 6:
                # Typical NTES row: Station, Sch Arr, Act Arr, Sch Dep, Act Dep, Delay
                s_name = cols[0]
                m_code = re.search(r"\(([A-Z]{2,5})\)", s_name)
                s_code = m_code.group(1) if m_code else s_name[:4]
                delay_str = cols[-1]

                # If station has actual arrival/departure time recorded, it has passed
                if cols[2] and cols[2] != "-" or (cols[4] and cols[4] != "-"):
                    last_station_code = s_code
                    last_station_name = s_name
                    m_del = re.search(r"(\d+)", delay_str)
                    if m_del:
                        delay_min = int(m_del.group(1))
                        if "Early" in delay_str or "before" in delay_str.lower():
                            delay_min = -delay_min

        if not last_station_code and not status_text:
            return None

        return LiveStatusResponse(
            success=True,
            train_number=cleaned_train,
            train_name=train_title,
            current_station_code=last_station_code,
            current_station_name=last_station_name,
            delay_minutes=delay_min,
            status_text=status_text or f"At/Passed {last_station_name or last_station_code} (Delay: {delay_min}m)",
            provider=self.provider_id,
        )

    def get_exceptions(
        self, date: Optional[str] = None, exception_type: str = "RescheduledTrains"
    ) -> Optional[ExceptionsResponse]:
        """Scrapes official operational exceptions (Rescheduled, Diverted, Cancelled)."""
        journey_date = date or self._get_today_date_str()

        url = f"{NTES_BASE_URL}/q"
        params = {
            "opt": "TrainException",
            "subOpt": exception_type,
            "dt": journey_date,
        }

        try:
            html = http_client.get_text(url, params=params, provider_name="ntes_exceptions")
        except Exception as e:
            logger.warning(f"NTES exception fetch error: {e}")
            return None

        rescheduled_list: List[RescheduledTrain] = []
        diverted_list: List[DivertedTrain] = []
        cancelled_list: List[CancelledTrain] = []

        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
        for r in rows:
            cols = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.DOTALL)]
            if len(cols) < 4:
                continue

            t_num_match = re.search(r"\b(\d{5})\b", cols[0])
            if not t_num_match:
                continue
            t_num = t_num_match.group(1)
            t_name = cols[1] if len(cols) > 1 else f"Train {t_num}"

            if exception_type == "RescheduledTrains":
                # Rescheduled: Train, Name, Source, Dest, Sch Dep, Resch Dep, Delay
                orig_dep = cols[4] if len(cols) > 4 else ""
                resch_dep = cols[5] if len(cols) > 5 else ""
                delay_str = cols[6] if len(cols) > 6 else ""
                rescheduled_list.append(
                    RescheduledTrain(
                        train_number=t_num,
                        train_name=t_name,
                        source=cols[2] if len(cols) > 2 else "",
                        destination=cols[3] if len(cols) > 3 else "",
                        original_departure=orig_dep,
                        rescheduled_departure=resch_dep,
                        delay_hours_mins=delay_str,
                    )
                )
            elif exception_type == "DivertedTrains":
                # Diverted: Train, Name, Source, Dest, Diverted From, Diverted To, Skipped
                div_from = cols[4] if len(cols) > 4 else ""
                div_to = cols[5] if len(cols) > 5 else ""
                skipped_str = cols[6] if len(cols) > 6 else ""
                skipped = [s.strip() for s in skipped_str.split(",") if s.strip()]
                diverted_list.append(
                    DivertedTrain(
                        train_number=t_num,
                        train_name=t_name,
                        source=cols[2] if len(cols) > 2 else "",
                        destination=cols[3] if len(cols) > 3 else "",
                        diverted_from=div_from,
                        diverted_to=div_to,
                        stations_skipped=skipped,
                    )
                )
            elif exception_type == "CancelledTrains":
                # Cancelled: Train, Name, Type (Full/Partial), From, To
                c_type = cols[2] if len(cols) > 2 else "FULL"
                from_stn = cols[3] if len(cols) > 3 else ""
                to_stn = cols[4] if len(cols) > 4 else ""
                cancelled_list.append(
                    CancelledTrain(
                        train_number=t_num,
                        train_name=t_name,
                        cancellation_type="PARTIAL" if "part" in c_type.lower() else "FULL",
                        from_station=from_stn,
                        to_station=to_stn,
                    )
                )

        return ExceptionsResponse(
            success=True,
            journey_date=journey_date,
            exception_type=exception_type,
            rescheduled=rescheduled_list,
            diverted=diverted_list,
            cancelled=cancelled_list,
            provider=self.provider_id,
        )
