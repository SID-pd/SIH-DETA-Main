"""
Live Engine.
Cascades across multiple providers to fetch real-time train running status with sub-minute caching.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from client.cache import cache
from config import TTL_LIVE_STATUS_SEC
from models.schemas import LiveStatusResponse
from providers.base import BaseProvider
from providers.confirmtkt import ConfirmTktProvider
from providers.erail import ErailProvider
from providers.ntes import NtesProvider

logger = logging.getLogger("getinfo.engines.live")


class LiveEngine:
    """Manages real-time running status queries with multi-provider failover."""

    def __init__(self, providers: Optional[List[BaseProvider]] = None):
        self.providers = providers or [
            ConfirmTktProvider(),
            NtesProvider(),
            ErailProvider(),
        ]

    def get_live_status(
        self, train_number: str, date: Optional[str] = None, use_cache: bool = True
    ) -> LiveStatusResponse:
        """Queries live status across providers with automatic cascade and caching."""
        cleaned_train = train_number.strip().zfill(5)
        cache_key = f"live:{cleaned_train}:{date or 'today'}"

        if use_cache:
            cached_val = cache.get(cache_key)
            if cached_val:
                resp = LiveStatusResponse(**cached_val)
                resp.cached = True
                return resp

        # Cascade through providers
        for provider in self.providers:
            try:
                res = provider.get_live_status(cleaned_train, date=date)
                if res and res.success:
                    # Store in cache
                    cache.set(cache_key, res.to_dict(), TTL_LIVE_STATUS_SEC)
                    return res
            except Exception as e:
                logger.warning(
                    f"Provider '{provider.provider_id}' failed for live status of {cleaned_train}: {e}"
                )

        # Graceful fallback: return a synthesized response rather than crashing
        fallback_resp = LiveStatusResponse(
            success=False,
            train_number=cleaned_train,
            train_name=f"Train {cleaned_train}",
            status_text="Live status temporarily unavailable from all upstream providers.",
            provider="none",
        )
        return fallback_resp
