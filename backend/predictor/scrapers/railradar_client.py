"""
RailRadar API Client.
Interfaces with official RailRadar developer REST API for live speed, coordinates, bearing, and segment progress.
"""

import logging
import os
from typing import Any, Dict, Optional

from predictor.config import RAILRADAR_API_URL
from predictor.scrapers.base_scraper import BaseScraper

logger = logging.getLogger("predictor.scrapers.railradar")


class RailRadarClient(BaseScraper):
    """Client for the official RailRadar API."""

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key or os.environ.get("RAILRADAR_API_KEY", "")

    def get_live_telemetry(self, train_number: str) -> Optional[Dict[str, Any]]:
        """
        Calls GET /v1/trains/{number}/live.
        Returns real-time speed, coordinates, bearing, segment progress, and delay.
        """
        cleaned_train = str(train_number).strip().zfill(5)
        url = f"{RAILRADAR_API_URL}/trains/{cleaned_train}/live"

        custom_headers = {}
        if self.api_key:
            custom_headers["Authorization"] = f"Bearer {self.api_key}"
            custom_headers["Accept"] = "application/json"
            res = self.fetch_json(url, custom_headers=custom_headers)
            if res:
                return res

        # Fallback simulation structure if API key is not configured
        logger.info(f"RailRadar API key not found or returned empty. Using fallback telemetry format for {cleaned_train}.")
        return {
            "trainNumber": cleaned_train,
            "status": "Running",
            "delayMinutes": 0,
            "currentLocation": {
                "latitude": 26.8467,
                "longitude": 80.9462,
                "speed": 85.5,
                "bearing": 115,
                "segmentProgress": 0.45,
            },
            "is_simulated": True,
        }
