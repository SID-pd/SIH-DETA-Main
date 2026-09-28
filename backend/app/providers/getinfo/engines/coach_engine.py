"""
Coach Engine.
Rake composition and exact seat/berth layout resolver.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from client.cache import cache
from config import TTL_COACH_SEC
from models.schemas import CoachInfo, CoachRakeResponse, SeatLayoutInfo
from providers.base import BaseProvider
from providers.confirmtkt import ConfirmTktProvider
from providers.erail import ErailProvider
from providers.offline_fallback import OfflineFallbackProvider

logger = logging.getLogger("getinfo.engines.coach")


class CoachEngine:
    """Manages coach sequence, rake composition, and seat layout calculations."""

    def __init__(self, providers: Optional[List[BaseProvider]] = None):
        self.providers = providers or [
            ConfirmTktProvider(),
            ErailProvider(),
            OfflineFallbackProvider(),  # Guarantees standard rake when scrapers fail
        ]

    def get_coach_position(
        self, train_number: str, use_cache: bool = True
    ) -> CoachRakeResponse:
        """Resolves coach sequence and rake composition."""
        cleaned_train = train_number.strip().zfill(5)
        cache_key = f"coach:{cleaned_train}"

        if use_cache:
            cached_val = cache.get(cache_key)
            if cached_val:
                d = dict(cached_val)
                raw_seq = d.pop("coach_sequence", [])
                coaches = [CoachInfo(**c) for c in raw_seq]
                resp = CoachRakeResponse(**d, coach_sequence=coaches)
                resp.cached = True
                return resp

        for provider in self.providers:
            try:
                res = provider.get_coach_position(cleaned_train)
                if res and res.success and res.coach_sequence:
                    cache.set(cache_key, res.to_dict(), TTL_COACH_SEC)
                    return res
            except Exception as e:
                logger.warning(
                    f"Provider '{provider.provider_id}' failed for coach layout of {cleaned_train}: {e}"
                )

        # Fallback to offline template
        return OfflineFallbackProvider().get_coach_position(cleaned_train)

    def get_seat_layout(self, coach_type: str, seat_number: int) -> SeatLayoutInfo:
        """Calculates exact berth type (LB, MB, UB, SL, SU, WS) and bay number."""
        return OfflineFallbackProvider.calculate_seat_layout(coach_type, seat_number)
