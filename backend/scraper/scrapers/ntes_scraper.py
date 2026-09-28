"""
High-level scraper for CRIS NTES (enquiry.indianrail.gov.in).
Extracts official live running status, delays, passage times, and exceptions.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any, Dict, List, Optional

from config.settings import (
    NTES_BASE_URL,
    NTES_CONCURRENCY,
    NTES_RPS_LIMIT,
)
from core.http_client import ResilientHttpClient
from core.parser_ntes import NtesParser
from core.state_manager import StateManager
from storage.database import Database

logger = logging.getLogger("scraper_erail.ntes")


class NtesScraper:
    def __init__(
        self,
        db: Optional[Database] = None,
        state_mgr: Optional[StateManager] = None,
        base_url: str = NTES_BASE_URL,
    ):
        self.db = db or Database()
        self.state_mgr = state_mgr or StateManager()
        self.base_url = base_url.rstrip("/")

    async def fetch_live_running_status(
        self,
        train_number: str,
        journey_date: Optional[str] = None,
        client: Optional[ResilientHttpClient] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scrapes real-time running status and delay telemetry for a train on a given date.
        Date format: DD-MM-YYYY or defaults to today IST.
        """
        if not journey_date:
            today_ist = datetime.datetime.now(
                datetime.timezone(datetime.timedelta(hours=5, minutes=30))
            )
            journey_date = today_ist.strftime("%d-%m-%Y")

        url = f"{self.base_url}/q"
        params = {
            "opt": "TrainRunning",
            "subOpt": "FindTrain",
            "trainNo": train_number,
            "dt": journey_date,
        }

        should_close = False
        if client is None:
            client = ResilientHttpClient(
                rate_limit_rps=NTES_RPS_LIMIT, concurrency_limit=NTES_CONCURRENCY
            )
            await client.__aenter__()
            should_close = True

        try:
            raw = await client.get_text(url, params=params)
            observations = NtesParser.parse_live_status(raw, train_number, journey_date)

            if observations:
                self.db.insert_live_observations(observations)
                logger.info(
                    f"Recorded {len(observations)} live stops for train {train_number} ({journey_date})"
                )
            return observations
        finally:
            if should_close:
                await client.__aexit__(None, None, None)

    async def fetch_train_exceptions(
        self,
        journey_date: Optional[str] = None,
        exception_type: str = "RescheduledTrains",
    ) -> List[Dict[str, Any]]:
        """
        Scrapes official operational exceptions from NTES.
        Types: 'RescheduledTrains', 'CancelledTrains', 'DivertedTrains'.
        """
        if not journey_date:
            today_ist = datetime.datetime.now(
                datetime.timezone(datetime.timedelta(hours=5, minutes=30))
            )
            journey_date = today_ist.strftime("%d-%m-%Y")

        url = f"{self.base_url}/q"
        params = {
            "opt": "TrainException",
            "subOpt": exception_type,
            "dt": journey_date,
        }

        async with ResilientHttpClient(
            rate_limit_rps=NTES_RPS_LIMIT, concurrency_limit=NTES_CONCURRENCY
        ) as client:
            raw = await client.get_text(url, params=params)

        type_map = {
            "RescheduledTrains": "RESCHEDULED",
            "CancelledTrains": "CANCELLED",
            "DivertedTrains": "DIVERTED",
        }
        category = type_map.get(exception_type, "EXCEPTION")
        exceptions = NtesParser.parse_train_exceptions(raw, journey_date, category)

        if exceptions:
            self.db.insert_train_exceptions(exceptions)
            logger.info(
                f"Saved {len(exceptions)} {category} exceptions for date {journey_date}."
            )

        return exceptions

    async def scrape_batch_live(
        self, train_numbers: List[str], journey_date: Optional[str] = None
    ) -> int:
        """Batch captures live running status for active trains."""
        total_obs = 0
        async with ResilientHttpClient(
            rate_limit_rps=NTES_RPS_LIMIT, concurrency_limit=NTES_CONCURRENCY
        ) as client:
            for t_num in train_numbers:
                try:
                    obs = await self.fetch_live_running_status(
                        t_num, journey_date=journey_date, client=client
                    )
                    total_obs += len(obs)
                except Exception as exc:
                    logger.warning(f"Error checking live status for {t_num}: {exc}")

        return total_obs
