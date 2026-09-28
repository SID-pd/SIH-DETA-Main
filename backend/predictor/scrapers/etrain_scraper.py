"""
eTrain Historical Delay Scraper and Profiler.
Extracts 1-year to 3-year historical station punctuality distributions and delay statistics.
"""

import csv
import logging
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from predictor.config import ETRAIN_BASE_URL, ETRAIN_DELAYS_CSV
from predictor.scrapers.base_scraper import BaseScraper

logger = logging.getLogger("predictor.scrapers.etrain")


class EtrainScraper(BaseScraper):
    """Scrapes and indexes historical station delay distributions from etrain.info."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._delay_cache: Dict[str, Dict[str, float]] = {}
        self._load_local_csv_cache()

    def _load_local_csv_cache(self):
        """Loads pre-scraped historical delays from Datasets/etrain_delays.csv if present."""
        if not ETRAIN_DELAYS_CSV.exists():
            return
        try:
            with open(ETRAIN_DELAYS_CSV, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    t_num = str(row.get("train_number") or "").strip().zfill(5)
                    stn = str(row.get("station_code") or "").strip().upper()
                    avg_delay = row.get("average_delay_minutes")
                    if t_num and stn and avg_delay:
                        try:
                            val = float(avg_delay)
                            if t_num not in self._delay_cache:
                                self._delay_cache[t_num] = {}
                            self._delay_cache[t_num][stn] = val
                            count += 1
                        except ValueError:
                            pass
            logger.info(f"Loaded {count} historical delay records from {ETRAIN_DELAYS_CSV.name}")
        except Exception as exc:
            logger.warning(f"Failed to load local etrain delays cache: {exc}")

    def get_historical_delay_for_station(self, train_number: str, station_code: str) -> float:
        """Returns the 1-year trailing average delay for a train at a specific station."""
        t_num = str(train_number).strip().zfill(5)
        stn = str(station_code).strip().upper()

        if t_num in self._delay_cache and stn in self._delay_cache[t_num]:
            return self._delay_cache[t_num][stn]

        # Network-wide default if train/station has no specific entry
        return 12.0

    def scrape_train_history(self, train_name: str, train_number: str, duration: str = "1y") -> List[Dict[str, Any]]:
        """
        Scrapes historical delay table from:
        https://etrain.info/train/{train_name}-{train_number}/history?d={duration}
        """
        cleaned_train = str(train_number).strip()
        slug = f"{train_name.replace(' ', '-')}-{cleaned_train}"
        url = f"{ETRAIN_BASE_URL}/{slug}/history?d={duration}"

        html = self.fetch_text(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        records: List[Dict[str, Any]] = []

        table = soup.find("table")
        if not table:
            return records

        for row in table.find_all("tr"):
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) < 5:
                continue

            stn_code = cols[0].split("-")[0].strip().upper()
            avg_delay_m = re.findall(r"[-+]?\d*\.\d+|\d+", cols[1])
            avg_delay = float(avg_delay_m[0]) if avg_delay_m else 0.0

            records.append({
                "train_number": cleaned_train,
                "station_code": stn_code,
                "average_delay_minutes": avg_delay,
                "pct_right_time": float(cols[2]) if len(cols) > 2 and cols[2].replace(".", "", 1).isdigit() else 0.0,
                "pct_slight_delay": float(cols[3]) if len(cols) > 3 and cols[3].replace(".", "", 1).isdigit() else 0.0,
                "pct_significant_delay": float(cols[4]) if len(cols) > 4 and cols[4].replace(".", "", 1).isdigit() else 0.0,
            })

        return records
