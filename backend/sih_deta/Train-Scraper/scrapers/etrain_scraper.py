"""
eTrain / Tripozo Scraper: Secondary fast autocomplete and lookup engine.
"""

import concurrent.futures
import logging
from typing import Dict, List, Optional

from config import DEFAULT_CONCURRENCY, ETRAIN_SUGGEST_API
from scrapers.base import BaseScraper

logger = logging.getLogger("rail_scraper")


class ETrainScraper(BaseScraper):
    """Scraper for eTrain.info train autocomplete suggestions."""

    def search_trains(self, query: str) -> List[Dict[str, str]]:
        """
        Search for trains using eTrain suggest endpoint.
        Returns a list of dicts with 'number' and 'name'.
        """
        url = f"{ETRAIN_SUGGEST_API}{query}"
        data = self.get(url, as_json=True)

        results = []
        if not data or not isinstance(data, list):
            return results

        for item in data:
            if not isinstance(item, dict):
                continue

            num = str(item.get("number", "")).strip()
            name = str(item.get("name", "")).strip()

            if num:
                # Normalise 4-digit numbers with leading 0
                if len(num) == 4 and num.isdigit():
                    num = "0" + num

                results.append({
                    "number": num,
                    "name": name,
                    "source": "etrain"
                })

        return results

    def discover_trains(
        self,
        prefixes: Optional[List[str]] = None,
        concurrency: int = DEFAULT_CONCURRENCY,
        limit: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Discover trains by querying eTrain autocomplete for prefixes.
        """
        if prefixes is None:
            prefixes = [f"{i:02d}" for i in range(100)]

        if limit and limit < len(prefixes):
            prefixes = prefixes[:limit]

        discovered: Dict[str, Dict[str, str]] = {}
        logger.info(f"[eTrain] Discovering across {len(prefixes)} prefixes with {concurrency} workers...")

        def worker(pfx: str):
            try:
                return pfx, self.search_trains(pfx)
            except Exception as e:
                logger.error(f"[eTrain] Error querying {pfx}: {e}")
                return pfx, []

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_pfx = {executor.submit(worker, pfx): pfx for pfx in prefixes}
            for future in concurrent.futures.as_completed(future_to_pfx):
                pfx, trains = future.result()
                for t in trains:
                    num = t["number"]
                    if num not in discovered:
                        discovered[num] = t

        logger.info(f"[eTrain] Discovery completed. Unique trains found: {len(discovered)}")
        return sorted(discovered.values(), key=lambda x: x["number"])
