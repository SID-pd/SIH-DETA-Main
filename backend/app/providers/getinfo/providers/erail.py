"""
eRail.in Provider.
Fast timetable schedules, live running status streams, and coach layouts.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from client.http import http_client
from config import ERAIL_BASE_URL
from models.schemas import (
    CoachInfo,
    CoachRakeResponse,
    LiveStatusResponse,
    TimelineResponse,
    TimelineStop,
)
from providers.base import BaseProvider

logger = logging.getLogger("getinfo.providers.erail")


class ErailProvider(BaseProvider):
    """eRail.in provider for high-speed timetable routes and coach position feeds."""

    @property
    def provider_id(self) -> str:
        return "erail"

    def get_coach_position(self, train_number: str) -> Optional[CoachRakeResponse]:
        """Scrapes coach position layout from eRail getTrains feed."""
        cleaned_train = train_number.strip().lstrip("0")
        url = f"{ERAIL_BASE_URL}/rail/getTrains.aspx?TrainNo={cleaned_train}&Action=CoachPosition"

        try:
            raw = http_client.get_text(url, provider_name="erail_coach")
        except Exception as e:
            logger.warning(f"eRail coach fetch error for {cleaned_train}: {e}")
            return None

        if not raw or "Please try again" in raw:
            return None

        # Parse coach string from the raw response (e.g. ^12951~...~,,En:LPR,B1:3A,...)
        m_coaches = re.search(r",,(En:[^~]+|ENG:[^~]+)", raw)
        coach_str = m_coaches.group(1) if m_coaches else ""
        if not coach_str:
            # Fallback search for colon-separated coach tokens
            tokens_match = re.findall(r"([A-Z0-9]+:[A-Z0-9]+)", raw)
            if tokens_match:
                coach_str = ",".join(tokens_match)

        if not coach_str:
            return None

        coaches: List[CoachInfo] = []
        tokens = [t.strip() for t in coach_str.split(",") if t.strip()]

        for idx, token in enumerate(tokens, start=1):
            parts = token.split(":")
            c_code = parts[0].strip()
            c_class = parts[1].strip() if len(parts) > 1 else None

            # Category inference
            category = "Passenger Coach"
            u_code = c_code.upper()
            if u_code in ("EN", "ENG"):
                category = "Locomotive / Engine"
            elif u_code.startswith("B"):
                category = "AC 3-Tier"
                c_class = c_class or "3A"
            elif u_code.startswith("A"):
                category = "AC 2-Tier"
                c_class = c_class or "2A"
            elif u_code.startswith("H"):
                category = "First Class AC"
                c_class = c_class or "1A"
            elif u_code.startswith("S") and not u_code.startswith("SLR"):
                category = "Sleeper Class (Non-AC)"
                c_class = c_class or "SL"
            elif u_code in ("PC", "PANTRY"):
                category = "Pantry Car"
            elif u_code in ("SLR", "EOG"):
                category = "Brake / Generator Van"

            coaches.append(
                CoachInfo(
                    position_index=idx,
                    coach_code=c_code,
                    coach_category=category,
                    class_code=c_class,
                )
            )

        rake_type = "LHB" if any(c.coach_code.startswith("B") or c.coach_code == "EOG" for c in coaches) else "ICF"
        return CoachRakeResponse(
            success=True,
            train_number=cleaned_train,
            train_name=None,
            rake_type=rake_type,
            total_coaches=len(coaches),
            coach_sequence=coaches,
            provider=self.provider_id,
        )

    def get_live_status(
        self, train_number: str, date: Optional[str] = None
    ) -> Optional[LiveStatusResponse]:
        """Scrapes live running status HTML from eRail."""
        cleaned_train = train_number.strip().lstrip("0")
        url = f"{ERAIL_BASE_URL}/train-running-status/{cleaned_train}"

        try:
            html = http_client.get_text(url, provider_name="erail_live")
        except Exception as e:
            logger.warning(f"eRail live fetch error for {cleaned_train}: {e}")
            return None

        # Look for live status container or table
        m_delay = re.search(r"(\d+)\s*mins?\s*(late|early|delay)", html, re.IGNORECASE)
        delay_min = 0
        if m_delay:
            delay_min = int(m_delay.group(1))
            if m_delay.group(2).lower() == "early":
                delay_min = -delay_min

        m_stn = re.search(r'(?:Arrived|Departed|Crossed)\s+([A-Za-z\s]+)\s*(?:\(([A-Z]+)\))?', html, re.IGNORECASE)
        curr_name = m_stn.group(1).strip() if m_stn else None
        curr_code = m_stn.group(2).strip() if m_stn and m_stn.group(2) else None

        if not curr_name and not m_delay:
            return None

        return LiveStatusResponse(
            success=True,
            train_number=cleaned_train,
            train_name=f"Train {cleaned_train}",
            current_station_code=curr_code,
            current_station_name=curr_name,
            delay_minutes=delay_min,
            status_text=f"At/Departed {curr_name or curr_code or 'Unknown'} (Delay: {delay_min}m)",
            provider=self.provider_id,
        )
