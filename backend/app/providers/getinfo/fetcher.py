"""
InfoFetcher: Unified Developer Facade for Indian Railways Information Extraction.
Provides single-point access to live status, PNR, coach layouts, timelines, and operational exceptions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from client.cache import cache
from engines.coach_engine import CoachEngine
from engines.exceptions_engine import ExceptionsEngine
from engines.live_engine import LiveEngine
from engines.pnr_engine import PNREngine
from engines.timeline_engine import TimelineEngine
from models.schemas import (
    CoachRakeResponse,
    ExceptionsResponse,
    LiveStatusResponse,
    PNRResponse,
    SeatLayoutInfo,
    TimelineResponse,
)

logger = logging.getLogger("getinfo.fetcher")


class InfoFetcher:
    """
    High-level facade providing bulletproof transit information retrieval.
    Guaranteed uptime via multi-provider cascading failovers, two-tier caching,
    and deterministic offline heuristics.
    """

    def __init__(self):
        self.live_engine = LiveEngine()
        self.pnr_engine = PNREngine()
        self.coach_engine = CoachEngine()
        self.timeline_engine = TimelineEngine()
        self.exceptions_engine = ExceptionsEngine()

    def get_live_status(
        self, train_number: str, date: Optional[str] = None, use_cache: bool = True
    ) -> LiveStatusResponse:
        """
        Retrieves real-time train running status, current station, next station, delay, and progress.
        :param train_number: 5-digit Indian Railways train number (e.g. '12951')
        :param date: Optional journey date: 'today', 'yesterday', 'tomorrow', or 'DD-MM-YYYY'
        :param use_cache: If True, uses cached response within TTL
        """
        return self.live_engine.get_live_status(train_number, date=date, use_cache=use_cache)

    def get_pnr_status(self, pnr: str, use_cache: bool = True) -> PNRResponse:
        """
        Retrieves complete PNR journey details, passenger booking vs current status, coach, and berth.
        :param pnr: 10-digit Indian Railways PNR number
        :param use_cache: If True, uses cached response within TTL
        """
        return self.pnr_engine.get_pnr_status(pnr, use_cache=use_cache)

    def get_coach_position(
        self, train_number: str, use_cache: bool = True
    ) -> CoachRakeResponse:
        """
        Retrieves full engine-to-guard rake composition and coach positions.
        :param train_number: 5-digit train number
        :param use_cache: If True, uses cached response within TTL
        """
        return self.coach_engine.get_coach_position(train_number, use_cache=use_cache)

    def get_seat_layout(self, coach_type: str, seat_number: int) -> SeatLayoutInfo:
        """
        Calculates exact berth type (Lower, Middle, Upper, Side Lower, Side Upper, Window),
        bay number, and generates visual ASCII compartment diagram.
        :param coach_type: Class code or coach code (e.g. '3A', '2A', 'SL', '3E', 'B3', 'S2')
        :param seat_number: Seat / berth number (1-80)
        """
        return self.coach_engine.get_seat_layout(coach_type, seat_number)

    def get_timeline(
        self, train_number: str, date: Optional[str] = None, use_cache: bool = True
    ) -> TimelineResponse:
        """
        Retrieves complete station-by-station journey schedule vs actual timetable with delays and lat/long.
        :param train_number: 5-digit train number
        :param date: Optional journey date
        :param use_cache: If True, uses cached response within TTL
        """
        return self.timeline_engine.get_timeline(train_number, date=date, use_cache=use_cache)

    def get_exceptions(
        self,
        date: Optional[str] = None,
        exception_type: str = "RescheduledTrains",
        use_cache: bool = True,
    ) -> ExceptionsResponse:
        """
        Retrieves official operational disruptions (rescheduled, diverted, cancelled trains).
        :param date: Journey date (defaults to today IST)
        :param exception_type: 'rescheduled', 'diverted', or 'cancelled'
        :param use_cache: If True, uses cached response within TTL
        """
        return self.exceptions_engine.get_exceptions(
            date=date, exception_type=exception_type, use_cache=use_cache
        )

    def get_all_info(
        self, train_number: str, date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Consolidated query returning live status, coach sequence, and timeline in one call.
        """
        live = self.get_live_status(train_number, date=date)
        coach = self.get_coach_position(train_number)
        timeline = self.get_timeline(train_number, date=date)

        return {
            "train_number": train_number,
            "train_name": live.train_name or timeline.train_name,
            "live_status": live.to_dict(),
            "coach_rake": coach.to_dict(),
            "timeline": timeline.to_dict(),
        }

    def clear_cache(self) -> int:
        """Prunes expired cache entries."""
        return cache.clear_expired()

    def clear_all_cache(self) -> int:
        """Flushes all cached entries immediately."""
        return cache.clear_all()
