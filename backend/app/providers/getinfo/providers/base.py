"""
Base Provider interface for transit scrapers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from models.schemas import (
    CoachRakeResponse,
    ExceptionsResponse,
    LiveStatusResponse,
    PNRResponse,
    TimelineResponse,
)


class BaseProvider(ABC):
    """Abstract base class for information extraction providers."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier for the provider."""
        pass

    def get_live_status(
        self, train_number: str, date: Optional[str] = None
    ) -> Optional[LiveStatusResponse]:
        """Fetch real-time running status and delay."""
        return None

    def get_pnr_status(self, pnr: str) -> Optional[PNRResponse]:
        """Fetch PNR booking and current passenger status."""
        return None

    def get_coach_position(self, train_number: str) -> Optional[CoachRakeResponse]:
        """Fetch rake composition and coach sequence."""
        return None

    def get_timeline(
        self, train_number: str, date: Optional[str] = None
    ) -> Optional[TimelineResponse]:
        """Fetch full scheduled vs actual journey timeline."""
        return None

    def get_exceptions(
        self, date: Optional[str] = None, exception_type: str = "RescheduledTrains"
    ) -> Optional[ExceptionsResponse]:
        """Fetch operational disruptions (rescheduled, diverted, cancelled)."""
        return None
