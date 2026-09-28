"""
Station Live Scraper: Scrapes live station timetable from ConfirmTkt (passing and halting trains,
arrival/departure times, classes, operating days, and halt durations).
"""

import logging
import re
from typing import Any, Dict, List, Optional

from config import CONFIRMTKT_STATION_URL
from scrapers.base import BaseScraper
from scrapers.station_dataset_loader import _calc_halt_minutes

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

logger = logging.getLogger("station_scraper")


class StationLiveScraper(BaseScraper):
    """Scrapes live train halt schedules for specific railway stations."""

    def scrape_station_timetable(self, station_code: str) -> Dict[str, Any]:
        """
        Scrape live timetable of all trains halting/passing through a station.
        """
        stn_code = station_code.strip().upper()
        url = f"{CONFIRMTKT_STATION_URL}{stn_code}"
        logger.info(f"Scraping live station timetable from {url}...")

        html = self.get(url)
        if not html or not isinstance(html, str):
            logger.warning(f"No response received for station {stn_code}")
            return {"station_code": stn_code, "total_trains": 0, "trains": []}

        if HAS_BS4:
            return self._parse_with_bs4(stn_code, html)
        else:
            return self._parse_with_regex(stn_code, html)

    def _parse_with_bs4(self, stn_code: str, html: str) -> Dict[str, Any]:
        """Parse station table with BeautifulSoup."""
        soup = BeautifulSoup(html, "html.parser")
        trains: List[Dict[str, Any]] = []

        table = soup.find("table")
        if not table:
            logger.warning(f"No trains table found on station page for {stn_code}")
            return {"station_code": stn_code, "total_trains": 0, "trains": []}

        rows = table.find_all("tr")
        for tr in rows:
            # Skip heading row
            if "heading" in tr.get("class", []):
                continue

            tds = tr.find_all("td")
            if len(tds) < 5:
                continue

            train_num = tds[0].get_text(strip=True)
            if not train_num or not any(c.isdigit() for c in train_num):
                continue

            # Standardize 5-digit train numbers
            if len(train_num) == 4 and train_num.isdigit():
                train_num = "0" + train_num

            train_name = tds[1].get_text(strip=True)
            classes = tds[2].get_text(strip=True) if len(tds) > 2 else ""

            # Days of run
            days_of_run = ""
            if len(tds) > 3:
                day_lis = tds[3].find_all("li")
                if day_lis:
                    active_days = []
                    day_names = ["M", "T", "W", "T", "F", "S", "S"]
                    for idx, li in enumerate(day_lis):
                        # Check opacity style (opacity: 1 means runs on this day)
                        style = li.get("style", "")
                        text = li.get_text(strip=True)
                        if "opacity: 1" in style or "opacity:1" in style:
                            active_days.append(text or (day_names[idx] if idx < len(day_names) else ""))
                    days_of_run = " ".join(active_days) if active_days else tds[3].get_text(strip=True)
                else:
                    days_of_run = tds[3].get_text(strip=True)

            arr = tds[4].get_text(strip=True) if len(tds) > 4 else ""
            dep = tds[5].get_text(strip=True) if len(tds) > 5 else ""

            # Clean placeholder values
            arr_clean = "" if arr in ("--", "-", "None") else arr
            dep_clean = "" if dep in ("--", "-", "None") else dep

            halt_mins = _calc_halt_minutes(arr_clean, dep_clean)

            trains.append({
                "station_code": stn_code,
                "train_number": train_num,
                "train_name": train_name,
                "arrival_time": arr_clean,
                "departure_time": dep_clean,
                "halt_minutes": halt_mins,
                "days_of_run": days_of_run,
                "classes": classes,
                "day": 1,
                "source": "confirmtkt_live",
            })

        logger.info(f"Extracted {len(trains)} trains passing through {stn_code}")
        return {
            "station_code": stn_code,
            "total_trains": len(trains),
            "trains": trains,
        }

    def _parse_with_regex(self, stn_code: str, html: str) -> Dict[str, Any]:
        """Lightweight regex parser fallback when BeautifulSoup is unavailable."""
        trains: List[Dict[str, Any]] = []

        # Find rows
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE)
        for row in rows:
            if "thColor" in row or "TRAIN No" in row:
                continue

            tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
            if len(tds) < 5:
                continue

            def clean_text(cell: str) -> str:
                return re.sub(r"<[^>]+>", " ", cell).strip()

            train_num = clean_text(tds[0])
            if not train_num or not any(c.isdigit() for c in train_num):
                continue

            if len(train_num) == 4 and train_num.isdigit():
                train_num = "0" + train_num

            train_name = clean_text(tds[1])
            classes = clean_text(tds[2]) if len(tds) > 2 else ""
            days_raw = clean_text(tds[3]) if len(tds) > 3 else ""
            days_of_run = re.sub(r"\s+", " ", days_raw).strip()

            arr = clean_text(tds[4]) if len(tds) > 4 else ""
            dep = clean_text(tds[5]) if len(tds) > 5 else ""

            arr_clean = "" if arr in ("--", "-", "None") else arr
            dep_clean = "" if dep in ("--", "-", "None") else dep

            halt_mins = _calc_halt_minutes(arr_clean, dep_clean)

            trains.append({
                "station_code": stn_code,
                "train_number": train_num,
                "train_name": train_name,
                "arrival_time": arr_clean,
                "departure_time": dep_clean,
                "halt_minutes": halt_mins,
                "days_of_run": days_of_run,
                "classes": classes,
                "day": 1,
                "source": "confirmtkt_live",
            })

        logger.info(f"Regex extracted {len(trains)} trains passing through {stn_code}")
        return {
            "station_code": stn_code,
            "total_trains": len(trains),
            "trains": trains,
        }
