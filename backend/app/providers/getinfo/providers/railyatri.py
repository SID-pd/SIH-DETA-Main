"""
RailYatri Provider.
Secondary fallback for PNR status and live running status.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from client.http import http_client
from config import RAILYATRI_BASE_URL
from models.schemas import (
    LiveStatusResponse,
    PassengerRecord,
    PNRResponse,
)
from providers.base import BaseProvider

logger = logging.getLogger("getinfo.providers.railyatri")


class RailYatriProvider(BaseProvider):
    """RailYatri fallback provider for PNR status and live running positions."""

    @property
    def provider_id(self) -> str:
        return "railyatri"

    def get_pnr_status(self, pnr: str) -> Optional[PNRResponse]:
        """Queries RailYatri AJAX PNR gateway."""
        cleaned_pnr = re.sub(r"\D", "", pnr)
        if len(cleaned_pnr) != 10:
            return None

        url = f"{RAILYATRI_BASE_URL}/get-status/{cleaned_pnr}"
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{RAILYATRI_BASE_URL}/pnr-status/{cleaned_pnr}",
        }

        try:
            data = http_client.get_json(url, headers=headers, provider_name="railyatri_pnr")
        except Exception as e:
            logger.warning(f"RailYatri PNR error: {e}")
            return None

        if not data or not data.get("status"):
            # status: false indicates invalid or flushed PNR
            return PNRResponse(
                success=False,
                pnr=cleaned_pnr,
                error_message="PNR flushed or invalid.",
                provider=self.provider_id,
            )

        pnr_data = data.get("pnr_data")
        if not pnr_data or not pnr_data.get("train_number"):
            return None

        passengers: List[PassengerRecord] = []
        raw_passengers = pnr_data.get("passengers") or []

        for idx, p in enumerate(raw_passengers, start=1):
            b_stat = str(p.get("booking_status") or "")
            c_stat = str(p.get("current_status") or "")
            coach = str(p.get("coach") or "") or None
            berth_raw = p.get("berth_no")
            berth = int(berth_raw) if berth_raw and str(berth_raw).isdigit() else None
            b_type = str(p.get("berth_type") or "") or None

            passengers.append(
                PassengerRecord(
                    passenger_no=idx,
                    booking_status=b_stat,
                    current_status=c_stat,
                    coach=coach,
                    berth=berth,
                    berth_type=b_type,
                )
            )

        return PNRResponse(
            success=True,
            pnr=cleaned_pnr,
            train_number=str(pnr_data.get("train_number") or ""),
            train_name=pnr_data.get("train_name"),
            doj=pnr_data.get("doj"),
            from_station=pnr_data.get("from_station_code"),
            to_station=pnr_data.get("to_station_code"),
            boarding_station=pnr_data.get("boarding_point"),
            reservation_upto=pnr_data.get("reservation_upto"),
            travel_class=pnr_data.get("journey_class"),
            quota=pnr_data.get("quota"),
            chart_prepared=bool(pnr_data.get("chart_prepared")),
            passenger_count=len(passengers),
            passengers=passengers,
            provider=self.provider_id,
        )
