"""
Continuous live telemetry poller for active trains.
Harvests ground truth into live_observations without consuming vendor API key quota.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import sqlite3
from typing import List, Optional

from scrapers.ntes_scraper import NtesScraper
from storage.database import Database

logger = logging.getLogger("scraper_erail.live_poller")

# Priority high-signal long distance trains
DEFAULT_TRACKED_TRAINS = [
    "12301",  # Howrah Rajdhani (HWH-NDLS)
    "12302",  # Howrah Rajdhani (NDLS-HWH)
    "12002",  # New Delhi - Bhopal Shatabdi
    "22436",  # Vande Bharat (NDLS-BSB)
    "12951",  # Mumbai Rajdhani (MMCT-NDLS)
    "12952",  # Mumbai Rajdhani (NDLS-MMCT)
    "12259",  # Sealdah Bikaner Duronto
    "12621",  # Tamil Nadu Express (MAS-NDLS)
    "12841",  # Coromandel Express (HWH-MAS)
    "12423",  # Dibrugarh Rajdhani
]


class LivePoller:
    def __init__(self, db: Optional[Database] = None, interval_seconds: int = 600):
        self.db = db or Database()
        self.ntes_scraper = NtesScraper(db=self.db)
        self.interval_seconds = interval_seconds

    def get_active_trains(self, limit: int = 50) -> List[str]:
        """Fetches active train numbers from the local database or falls back to defaults."""
        try:
            with self.db.get_connection() as conn:
                cur = conn.execute(
                    "SELECT number FROM trains WHERE type LIKE '%Rajdhani%' OR type LIKE '%Vande%' OR type LIKE '%Superfast%' LIMIT ?;",
                    (limit,),
                )
                rows = cur.fetchall()
                if rows:
                    return [r["number"] for r in rows]
        except Exception:
            pass
        return DEFAULT_TRACKED_TRAINS

    async def run_poll_cycle(self, train_numbers: Optional[List[str]] = None) -> int:
        trains = train_numbers or self.get_active_trains()
        today_ist = datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        ).strftime("%d-%m-%Y")

        logger.info(
            f"Starting live poll cycle for {len(trains)} trains on date {today_ist}..."
        )
        total_obs = await self.ntes_scraper.scrape_batch_live(trains, journey_date=today_ist)
        logger.info(
            f"Poll cycle completed: recorded {total_obs} live station observations."
        )
        return total_obs

    async def run_forever(self, train_numbers: Optional[List[str]] = None) -> None:
        logger.info(
            f"Live poller started. Polling every {self.interval_seconds} seconds."
        )
        while True:
            try:
                await self.run_poll_cycle(train_numbers)
            except Exception as e:
                logger.error(f"Error in poll cycle: {e}")
            logger.info(f"Sleeping for {self.interval_seconds}s until next poll cycle...")
            await asyncio.sleep(self.interval_seconds)
