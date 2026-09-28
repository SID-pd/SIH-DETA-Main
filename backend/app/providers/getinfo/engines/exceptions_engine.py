"""
Exceptions Engine.
Extracts operational disruptions: rescheduled trains, diverted routes, and cancellations.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from client.cache import cache
from config import TTL_EXCEPTIONS_SEC
from models.schemas import (
    CancelledTrain,
    DivertedTrain,
    ExceptionsResponse,
    RescheduledTrain,
)
from providers.base import BaseProvider
from providers.ntes import NtesProvider

logger = logging.getLogger("getinfo.engines.exceptions")


class ExceptionsEngine:
    """Manages operational train exception feeds."""

    def __init__(self, providers: Optional[List[BaseProvider]] = None):
        self.providers = providers or [
            NtesProvider(),
        ]

    def get_exceptions(
        self,
        date: Optional[str] = None,
        exception_type: str = "RescheduledTrains",
        use_cache: bool = True,
    ) -> ExceptionsResponse:
        """
        Retrieves official operational exceptions for a given date.
        Accepted types: 'rescheduled', 'diverted', 'cancelled' or NTES formal names.
        """
        type_norm = exception_type.lower()
        if "resched" in type_norm:
            formal_type = "RescheduledTrains"
        elif "divert" in type_norm:
            formal_type = "DivertedTrains"
        elif "cancel" in type_norm:
            formal_type = "CancelledTrains"
        else:
            formal_type = exception_type

        cache_key = f"exceptions:{date or 'today'}:{formal_type}"
        if use_cache:
            cached_val = cache.get(cache_key)
            if cached_val:
                d = dict(cached_val)
                resched = [
                    RescheduledTrain(**r) for r in d.pop("rescheduled", [])
                ]
                divert = [
                    DivertedTrain(**dv) for dv in d.pop("diverted", [])
                ]
                cancel = [
                    CancelledTrain(**c) for c in d.pop("cancelled", [])
                ]
                resp = ExceptionsResponse(
                    **d,
                    rescheduled=resched,
                    diverted=divert,
                    cancelled=cancel,
                )
                resp.cached = True
                return resp

        for provider in self.providers:
            try:
                res = provider.get_exceptions(date=date, exception_type=formal_type)
                if res and res.success:
                    cache.set(cache_key, res.to_dict(), TTL_EXCEPTIONS_SEC)
                    return res
            except Exception as e:
                logger.warning(
                    f"Provider '{provider.provider_id}' failed for exceptions ({formal_type}): {e}"
                )

        return ExceptionsResponse(
            success=False,
            journey_date=date or "today",
            exception_type=formal_type,
            provider="none",
        )
