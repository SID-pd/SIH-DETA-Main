"""
PNR Engine.
Multi-provider PNR resolver with automatic berth layout deduction and caching.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from client.cache import cache
from config import TTL_PNR_SEC
from models.schemas import PassengerRecord, PNRResponse
from providers.base import BaseProvider
from providers.confirmtkt import ConfirmTktProvider
from providers.offline_fallback import OfflineFallbackProvider
from providers.railyatri import RailYatriProvider

logger = logging.getLogger("getinfo.engines.pnr")


class PNREngine:
    """Manages PNR inquiries with failover and passenger layout enrichment."""

    def __init__(self, providers: Optional[List[BaseProvider]] = None):
        self.providers = providers or [
            ConfirmTktProvider(),
            RailYatriProvider(),
        ]

    def get_pnr_status(self, pnr: str, use_cache: bool = True) -> PNRResponse:
        """Resolves 10-digit PNR status across providers."""
        cleaned_pnr = re.sub(r"\D", "", pnr.strip())
        if len(cleaned_pnr) != 10:
            return PNRResponse(
                success=False,
                pnr=pnr,
                error_message="Invalid PNR number. Indian Railways PNR must contain exactly 10 digits.",
                provider="validator",
            )

        cache_key = f"pnr:{cleaned_pnr}"
        if use_cache:
            cached_val = cache.get(cache_key)
            if cached_val:
                d = dict(cached_val)
                raw_passengers = d.pop("passengers", [])
                passengers = [PassengerRecord(**p) for p in raw_passengers]
                resp = PNRResponse(**d, passengers=passengers)
                resp.cached = True
                return resp

        # Cascade through providers
        for provider in self.providers:
            try:
                res = provider.get_pnr_status(cleaned_pnr)
                if res:
                    # If valid response (whether booked or explicitly flushed)
                    # Enrich passengers with berth type if missing
                    if res.success and res.passengers:
                        for p in res.passengers:
                            if not p.berth_type and p.coach and p.berth:
                                layout = OfflineFallbackProvider.calculate_seat_layout(
                                    p.coach[:2], p.berth
                                )
                                p.berth_type = layout.berth_type

                    # Cache successful lookups with valid train data
                    if res.success and res.train_number:
                        cache.set(cache_key, res.to_dict(), TTL_PNR_SEC)
                    return res
            except Exception as e:
                logger.warning(
                    f"Provider '{provider.provider_id}' failed for PNR {cleaned_pnr}: {e}"
                )

        return PNRResponse(
            success=False,
            pnr=cleaned_pnr,
            error_message="Unable to fetch PNR status from all upstream providers.",
            provider="none",
        )
