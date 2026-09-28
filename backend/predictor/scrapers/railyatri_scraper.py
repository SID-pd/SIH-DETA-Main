"""
RailYatri Scraper.
Scrapes live train status, crowd-sourced GPS telemetry, and upcoming station ETAs.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from predictor.config import RAILYATRI_BASE_URL
from predictor.scrapers.base_scraper import BaseScraper

logger = logging.getLogger("predictor.scrapers.railyatri")


class RailYatriScraper(BaseScraper):
    """Scrapes RailYatri live train status and telemetry."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_live_status(self, train_number: str) -> Optional[Dict[str, Any]]:
        """
        Queries RailYatri live train status page.
        Extracts current station, GPS telemetry, delay, and upcoming halts.
        """
        cleaned_train = str(train_number).strip().zfill(5)
        url = f"{RAILYATRI_BASE_URL}/live-train-status/{cleaned_train}"

        custom_headers = {
            "Referer": "https://www.railyatri.in/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }

        html = self.fetch_text(url, custom_headers=custom_headers)
        if not html:
            logger.warning(f"Could not retrieve RailYatri status for {cleaned_train}")
            return None

        return self._parse_html(html, cleaned_train)

    def _parse_html(self, html: str, train_number: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        stops: List[Dict[str, Any]] = []

        # Check for embedded JSON state (e.g. window.__INITIAL_STATE__ or similar)
        m_state = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});", html, re.DOTALL)
        if m_state:
            try:
                state_data = json.loads(m_state.group(1))
                return {
                    "train_number": train_number,
                    "source": "railyatri_state",
                    "data": state_data,
                }
            except Exception:
                pass

        # Fallback to HTML table/cards
        curr_station = None
        current_delay = 0
        current_speed = 0.0

        # Look for speed & delay headers
        speed_match = re.search(r"(\d+(?:\.\d+)?)\s*km/h", html, re.I)
        if speed_match:
            current_speed = float(speed_match.group(1))

        delay_match = re.search(r"(\d+)\s*(?:mins?|hours?)\s*late", html, re.I)
        if delay_match:
            current_delay = int(delay_match.group(1))

        # Extract timeline stops
        stop_cards = soup.find_all("div", class_=re.compile(r"station|timeline-item|timetable", re.I))
        for idx, card in enumerate(stop_cards, start=1):
            text = card.get_text(separator=" ", strip=True)
            stn_code_m = re.search(r"\b([A-Z]{2,5})\b", text)
            if stn_code_m:
                stops.append({
                    "seq": idx,
                    "station_code": stn_code_m.group(1),
                    "text": text[:120],
                })

        return {
            "train_number": train_number,
            "source": "railyatri",
            "current_station": curr_station,
            "current_delay_min": current_delay,
            "current_speed_kmph": current_speed,
            "stops_count": len(stops),
            "stops": stops,
        }
