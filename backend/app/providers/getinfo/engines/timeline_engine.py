"""
Timeline Engine.
Extracts full journey schedule vs actual timetable with intermediate halts and delays.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from client.cache import cache
from config import TTL_TIMELINE_SEC
from models.schemas import TimelineResponse, TimelineStop
from providers.base import BaseProvider
from providers.confirmtkt import ConfirmTktProvider

logger = logging.getLogger("getinfo.engines.timeline")


class TimelineEngine:
    """Manages complete train journey timeline compilation."""

    def __init__(self, providers: Optional[List[BaseProvider]] = None):
        self.providers = providers or [
            ConfirmTktProvider(),
        ]

    def get_timeline(
        self, train_number: str, date: Optional[str] = None, use_cache: bool = True
    ) -> TimelineResponse:
        """Resolves complete station-by-station scheduled vs actual timeline."""
        cleaned_train = train_number.strip().zfill(5)
        cache_key = f"timeline:{cleaned_train}:{date or 'default'}"

        if use_cache:
            cached_val = cache.get(cache_key)
            if cached_val:
                d = dict(cached_val)
                raw_stops = d.pop("stops", [])
                stops = [TimelineStop(**s) for s in raw_stops]
                resp = TimelineResponse(**d, stops=stops)
                resp.cached = True
                return resp

        for provider in self.providers:
            try:
                res = provider.get_timeline(cleaned_train, date=date)
                if res and res.success and res.stops:
                    cache.set(cache_key, res.to_dict(), TTL_TIMELINE_SEC)
                    return res
            except Exception as e:
                logger.warning(
                    f"Provider '{provider.provider_id}' failed for timeline of {cleaned_train}: {e}"
                )

        return TimelineResponse(
            success=False,
            train_number=cleaned_train,
            train_name=f"Train {cleaned_train}",
            source="UNKNOWN",
            destination="UNKNOWN",
            total_stops=0,
            stops=[],
            provider="none",
        )
