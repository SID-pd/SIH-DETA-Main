"""
RunningStatus.in Scraper.
Extracts live train position, station arrival/departure times, and delays from runningstatus.in.
Includes anti-bot bypass headers and diagnostic fallbacks.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from predictor.config import RUNNINGSTATUS_BASE_URL
from predictor.scrapers.base_scraper import BaseScraper

logger = logging.getLogger("predictor.scrapers.runningstatus")


class RunningStatusScraper(BaseScraper):
    """Scrapes runningstatus.in status pages."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_train_status(self, train_number: str, date_str: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Fetches status from runningstatus.in.
        URL format: https://runningstatus.in/status/{train_number}-on-{YYYYMMDD}
        """
        cleaned_train = str(train_number).strip()
        if date_str:
            clean_date = date_str.replace("-", "").strip()
            url = f"{RUNNINGSTATUS_BASE_URL}/{cleaned_train}-on-{clean_date}"
        else:
            url = f"{RUNNINGSTATUS_BASE_URL}/{cleaned_train}"

        custom_headers = {
            "Host": "runningstatus.in",
            "Referer": "https://runningstatus.in/",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

        html = self.fetch_text(url, custom_headers=custom_headers)
        if not html:
            logger.warning(
                f"RunningStatus.in request failed for {cleaned_train}. "
                "Cloudflare Turnstile or IP rate-limiting may have blocked the request."
            )
            return None

        return self._parse_html(html, cleaned_train)

    def _parse_html(self, html: str, train_number: str) -> Dict[str, Any]:
        """Parses HTML table for station timings and delays."""
        soup = BeautifulSoup(html, "html.parser")
        stops: List[Dict[str, Any]] = []

        # Find schedule table
        table = soup.find("table", class_=re.compile(r"table|running-status", re.I))
        if not table:
            # Look for any table with station rows
            tables = soup.find_all("table")
            for t in tables:
                if "Station" in t.get_text():
                    table = t
                    break

        if table:
            rows = table.find_all("tr")
            for idx, tr in enumerate(rows):
                cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if len(cols) < 5 or "Station" in cols[0]:
                    continue

                stn_name = cols[0]
                sch_arr = cols[1] if len(cols) > 1 else ""
                act_arr = cols[2] if len(cols) > 2 else sch_arr
                sch_dep = cols[3] if len(cols) > 3 else ""
                act_dep = cols[4] if len(cols) > 4 else sch_dep
                delay_str = cols[5] if len(cols) > 5 else "0"

                delay_match = re.search(r"[-+]?\d+", delay_str)
                delay_min = int(delay_match.group(0)) if delay_match else 0

                stops.append({
                    "seq": idx,
                    "station_name": stn_name,
                    "scheduled_arrival": sch_arr,
                    "actual_arrival": act_arr,
                    "scheduled_departure": sch_dep,
                    "actual_departure": act_dep,
                    "delay_minutes": delay_min,
                })

        return {
            "train_number": train_number,
            "source": "runningstatus.in",
            "stops_count": len(stops),
            "stops": stops,
        }
