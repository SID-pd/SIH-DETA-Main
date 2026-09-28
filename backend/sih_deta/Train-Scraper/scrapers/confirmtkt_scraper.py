"""
ConfirmTkt Scraper: Extracts train listings, search results, and deep timetable/route details.
"""

import concurrent.futures
import logging
import re
from typing import Any, Dict, List, Optional

from config import CONFIRMTKT_SCHEDULE_URL, CONFIRMTKT_SEARCH_API, DEFAULT_CONCURRENCY
from scrapers.base import BaseScraper

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

logger = logging.getLogger("rail_scraper")


class ConfirmTktScraper(BaseScraper):
    """Scraper for ConfirmTkt train directory and schedules."""

    def search_trains(self, query: str) -> List[Dict[str, str]]:
        """
        Search for trains by number prefix, name, or keyword.
        Returns a list of dictionaries with 'number' and 'name'.
        """
        url = f"{CONFIRMTKT_SEARCH_API}{query}"
        data = self.get(url, as_json=True)

        results = []
        if not data or not isinstance(data, list):
            return results

        for item in data:
            if not isinstance(item, dict):
                continue

            # ConfirmTkt returns items with 'Key' (train number) and 'Value' (train name)
            # or variations like 'TrainNo', 'name'
            train_no = str(item.get("Key") or item.get("TrainNo") or item.get("trainNo") or "").strip()
            train_name = str(item.get("Value") or item.get("Name") or item.get("name") or "").strip()

            if not train_no and "-" in train_name:
                parts = train_name.split("-", 1)
                if parts[0].strip().isdigit():
                    train_no = parts[0].strip()
                    train_name = parts[1].strip()

            if train_no:
                # Normalise train number (standard 5-digit representation in Indian Railways)
                if len(train_no) == 4 and train_no.isdigit():
                    train_no = "0" + train_no

                results.append({
                    "number": train_no,
                    "name": train_name,
                    "source": "confirmtkt"
                })

        return results

    def discover_all_trains(
        self,
        prefixes: Optional[List[str]] = None,
        concurrency: int = DEFAULT_CONCURRENCY,
        limit: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Traverse train number prefixes to discover all active Indian Railways trains.
        Indian Railways uses 5-digit numbers starting with 0-9:
          0xxxx: Specials
          1xxxx & 2xxxx: Mail / Express / Superfast / Rajdhani / Shatabdi / Vande Bharat
          5xxxx, 6xxxx, 7xxxx: Passenger / MEMU / DEMU
          8xxxx: Suvidha
          9xxxx: Suburban / Locals
        """
        if prefixes is None:
            # Generate 2-digit prefixes: 00 to 99
            prefixes = [f"{i:02d}" for i in range(100)]

        if limit and limit < len(prefixes):
            prefixes = prefixes[:limit]

        discovered: Dict[str, Dict[str, str]] = {}
        logger.info(f"Starting discovery across {len(prefixes)} prefixes using {concurrency} workers...")

        def fetch_prefix(pfx: str):
            try:
                trains = self.search_trains(pfx)
                return pfx, trains
            except Exception as e:
                logger.error(f"Error querying prefix {pfx}: {e}")
                return pfx, []

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_pfx = {executor.submit(fetch_prefix, pfx): pfx for pfx in prefixes}
            completed = 0
            for future in concurrent.futures.as_completed(future_to_pfx):
                pfx, trains = future.result()
                completed += 1

                new_count = 0
                for t in trains:
                    num = t["number"]
                    if num not in discovered:
                        discovered[num] = t
                        new_count += 1

                if completed % 10 == 0 or completed == len(prefixes):
                    logger.info(
                        f"[{completed}/{len(prefixes)}] Prefix '{pfx}': Found {len(trains)} trains ({new_count} new). Total unique trains: {len(discovered)}"
                    )

        logger.info(f"Discovery complete. Total unique trains found: {len(discovered)}")
        return sorted(discovered.values(), key=lambda x: x["number"])

    def scrape_schedule(self, train_number: str) -> Optional[Dict[str, Any]]:
        """
        Scrape complete route, halts, timings, and metadata for a specific train.
        """
        norm_no = str(train_number).strip()
        url = f"{CONFIRMTKT_SCHEDULE_URL}{norm_no}"
        html_content = self.get(url)

        if not html_content or isinstance(html_content, dict):
            return None

        if HAS_BS4:
            return self._parse_schedule_bs4(norm_no, html_content)
        else:
            return self._parse_schedule_regex(norm_no, html_content)

    def _parse_schedule_bs4(self, train_number: str, html: str) -> Optional[Dict[str, Any]]:
        """Parse timetable page using BeautifulSoup."""
        soup = BeautifulSoup(html, "html.parser")

        # Basic metadata
        meta: Dict[str, Any] = {
            "number": train_number,
            "name": "",
            "route": "",
            "type": "",
            "service_days": "",
            "departure": "",
            "arrival": "",
            "travel_time": "",
            "distance": "",
            "total_stops": 0,
            "classes": "",
            "pantry": "",
            "stops": []
        }

        # Extract title or description for fallback name
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            match = re.search(r"(\d+)\s+Train Route and Schedule of\s+([^|]+)", title_text, re.IGNORECASE)
            if match:
                meta["name"] = match.group(2).strip()

        # Parse the Train Info table (Route, Type, Service Days, Distance, etc.)
        info_table = soup.find("table", class_="train-info-table")
        if info_table:
            for row in info_table.find_all("tr"):
                label_td = row.find("td", class_="train-info-label")
                val_td = row.find("td", class_="train-info-value")
                if label_td and val_td:
                    label = label_td.get_text(strip=True).lower()
                    val = val_td.get_text(strip=True)
                    if "route" in label:
                        meta["route"] = val
                    elif "type" in label:
                        meta["type"] = val
                    elif "service days" in label or "days" in label:
                        meta["service_days"] = val
                    elif "departure" in label:
                        meta["departure"] = val
                    elif "arrival" in label:
                        meta["arrival"] = val
                    elif "travel time" in label:
                        meta["travel_time"] = val
                    elif "distance" in label:
                        meta["distance"] = val
                    elif "total stops" in label or "stops" in label:
                        try:
                            meta["total_stops"] = int(val)
                        except ValueError:
                            pass
                    elif "classes" in label:
                        meta["classes"] = val
                    elif "pantry" in label:
                        meta["pantry"] = val

        # Parse Stops Table
        stops_table = soup.find("table", class_="table")
        if stops_table:
            tbody = stops_table.find("tbody")
            rows = tbody.find_all("tr") if tbody else stops_table.find_all("tr")
            sno_counter = 1

            for tr in rows:
                tds = tr.find_all("td")
                if len(tds) < 6:
                    continue

                raw_sno = tds[0].get_text(strip=True)
                try:
                    sno = int(raw_sno)
                except ValueError:
                    sno = sno_counter

                stn_cell = tds[1].get_text(strip=True)
                station_name = stn_cell
                station_code = ""
                if "-" in stn_cell:
                    parts = stn_cell.rsplit("-", 1)
                    station_name = parts[0].strip()
                    station_code = parts[1].strip()

                arrival = tds[2].get_text(strip=True)
                departure = tds[3].get_text(strip=True)
                halt = tds[4].get_text(strip=True)
                distance = tds[5].get_text(strip=True)
                delay = tds[6].get_text(strip=True) if len(tds) > 6 else ""
                day = tds[7].get_text(strip=True) if len(tds) > 7 else "1"

                meta["stops"].append({
                    "sno": sno,
                    "station_name": station_name,
                    "station_code": station_code,
                    "arrival": arrival,
                    "departure": departure,
                    "halt": halt,
                    "distance": distance,
                    "avg_delay": delay,
                    "day": day
                })
                sno_counter += 1

        if not meta["total_stops"]:
            meta["total_stops"] = len(meta["stops"])

        return meta

    def _parse_schedule_regex(self, train_number: str, html: str) -> Optional[Dict[str, Any]]:
        """Fallback lightweight parser using regex when BeautifulSoup is not installed."""
        meta: Dict[str, Any] = {
            "number": train_number,
            "name": "",
            "route": "",
            "type": "",
            "service_days": "",
            "departure": "",
            "arrival": "",
            "travel_time": "",
            "distance": "",
            "total_stops": 0,
            "classes": "",
            "pantry": "",
            "stops": []
        }

        # Extract name from H1 or meta description or title
        h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL | re.IGNORECASE)
        if h1_m:
            h1_text = re.sub(r"<[^>]+>", "", h1_m.group(1)).strip()
            # Often "Ndls Moga Sht (12043)" or "12043 Ndls Moga Sht: Train Route..."
            cleaned_name = re.sub(rf"\b{train_number}\b", "", h1_text)
            cleaned_name = re.split(r"[:|-]\s*(?:Train Route|Schedule|Timetable)", cleaned_name, flags=re.IGNORECASE)[0]
            cleaned_name = cleaned_name.strip("() -")
            if cleaned_name:
                import html as html_lib
                meta["name"] = html_lib.unescape(cleaned_name)

        if not meta["name"]:
            desc_m = re.search(r'name="description"\s+content=".*?Schedule of\s+([^.]+?)\s+online', html, re.IGNORECASE)
            if desc_m:
                import html as html_lib
                meta["name"] = html_lib.unescape(desc_m.group(1).strip())

        if not meta["name"]:
            title_m = re.search(r"<title>.*?(\d+)\s+Train Route and Schedule(?:\s+of\s+([^|<]+))?", html, re.IGNORECASE)
            if title_m and title_m.group(2):
                import html as html_lib
                meta["name"] = html_lib.unescape(title_m.group(2).strip())

        # Extract info labels and values
        labels = re.findall(
            r'<td class="train-info-label">(.*?)</td>\s*<td class="train-info-value">(.*?)</td>',
            html,
            re.DOTALL
        )
        for lbl, val in labels:
            lbl_clean = re.sub(r"<[^>]+>", "", lbl, flags=re.DOTALL).strip().lower()
            val_clean = re.sub(r"<[^>]+>", "", val, flags=re.DOTALL).strip()
            if "route" in lbl_clean:
                meta["route"] = val_clean
            elif "type" in lbl_clean:
                meta["type"] = val_clean
            elif "service days" in lbl_clean:
                meta["service_days"] = val_clean
            elif "departure" in lbl_clean:
                meta["departure"] = val_clean
            elif "arrival" in lbl_clean:
                meta["arrival"] = val_clean
            elif "travel time" in lbl_clean:
                meta["travel_time"] = val_clean
            elif "distance" in lbl_clean:
                meta["distance"] = val_clean
            elif "classes" in lbl_clean:
                meta["classes"] = val_clean
            elif "pantry" in lbl_clean:
                meta["pantry"] = val_clean

        # Strip HTML comments to avoid commented-out <td> tags
        clean_html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)

        # Extract rows from timetable
        row_matches = re.findall(r"<tr>\s*<td[^>]*>\s*(\d+)\s*</td>(.*?)</tr>", clean_html, re.DOTALL)
        for sno_str, row_body in row_matches:
            cols = re.findall(r"<td[^>]*>(.*?)</td>", row_body, re.DOTALL)
            if len(cols) >= 5:
                stn_clean = re.sub(r"<[^>]+>", "", cols[0], flags=re.DOTALL).strip()
                stn_clean = re.sub(r"\s+", " ", stn_clean)
                stn_name, stn_code = stn_clean, ""
                if "-" in stn_clean:
                    p = stn_clean.rsplit("-", 1)
                    stn_name, stn_code = p[0].strip(), p[1].strip()

                arrival = re.sub(r"<[^>]+>", "", cols[1], flags=re.DOTALL).strip()
                departure = re.sub(r"<[^>]+>", "", cols[2], flags=re.DOTALL).strip()
                halt = re.sub(r"<[^>]+>", "", cols[3], flags=re.DOTALL).strip()
                distance = re.sub(r"<[^>]+>", "", cols[4], flags=re.DOTALL).strip()
                delay = re.sub(r"<[^>]+>", "", cols[5], flags=re.DOTALL).strip() if len(cols) > 5 else ""
                day = re.sub(r"<[^>]+>", "", cols[6], flags=re.DOTALL).strip() if len(cols) > 6 else "1"

                meta["stops"].append({
                    "sno": int(sno_str),
                    "station_name": stn_name,
                    "station_code": stn_code,
                    "arrival": arrival,
                    "departure": departure,
                    "halt": halt,
                    "distance": distance,
                    "avg_delay": delay,
                    "day": day
                })

        meta["total_stops"] = len(meta["stops"])
        return meta
