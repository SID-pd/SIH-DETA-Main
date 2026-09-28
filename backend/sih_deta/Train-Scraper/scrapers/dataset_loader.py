"""
Dataset Loader: Fetches and parses the open master Indian Railways dataset (thousands of trains
with zones, source/destination stations, coordinates, and timings).
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import DATA_DIR, DATAMEET_TRAINS_URL
from scrapers.base import BaseScraper

logger = logging.getLogger("rail_scraper")


class DatasetLoader(BaseScraper):
    """Fetches master Indian Railways train records from verified open data sources."""

    def __init__(self, cache_file: Optional[Path] = None, **kwargs):
        super().__init__(**kwargs)
        self.cache_file = cache_file or (DATA_DIR / "datameet_trains.json")

    def fetch_master_dataset(self, force_download: bool = False) -> List[Dict[str, Any]]:
        """
        Download or load cached master dataset of all Indian Railways trains.
        """
        if self.cache_file.exists() and not force_download:
            logger.info(f"Loading master trains dataset from cache: {self.cache_file}")
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                return self._parse_geojson(raw_data)
            except Exception as e:
                logger.warning(f"Failed to read cache {self.cache_file}: {e}. Redownloading...")

        logger.info(f"Fetching master dataset from {DATAMEET_TRAINS_URL}...")
        raw_data = self.get(DATAMEET_TRAINS_URL, as_json=True)

        if not raw_data or not isinstance(raw_data, dict):
            logger.error("Failed to download master dataset.")
            return []

        # Save to local cache
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(raw_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved master dataset cache to {self.cache_file}")
        except Exception as e:
            logger.warning(f"Could not write cache file: {e}")

        return self._parse_geojson(raw_data)

    def _parse_geojson(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse GeoJSON feature collection into structured train records."""
        features = data.get("features", [])
        trains = []

        for feature in features:
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [])

            number = str(props.get("number", "")).strip()
            name = str(props.get("name", "")).strip()

            if not number:
                continue

            if len(number) == 4 and number.isdigit():
                number = "0" + number

            # Extract classes
            classes_available = []
            if props.get("first_ac"):
                classes_available.append("1A")
            if props.get("second_ac"):
                classes_available.append("2A")
            if props.get("third_ac"):
                classes_available.append("3A")
            if props.get("sleeper"):
                classes_available.append("SL")
            if props.get("chair_car"):
                classes_available.append("CC")
            if props.get("first_class"):
                classes_available.append("FC")

            classes_str = ", ".join(classes_available) or props.get("classes", "")

            # Travel duration
            duration_h = props.get("duration_h", 0)
            duration_m = props.get("duration_m", 0)
            travel_time = f"{duration_h}h {duration_m}m" if (duration_h or duration_m) else ""

            # Route description
            from_stn = props.get("from_station_name") or props.get("from_station_code", "")
            to_stn = props.get("to_station_name") or props.get("to_station_code", "")
            route = f"{from_stn} → {to_stn}" if (from_stn and to_stn) else ""

            train_obj = {
                "number": number,
                "name": name,
                "type": props.get("type", "Express"),
                "zone": props.get("zone", ""),
                "route": route,
                "from_station_code": props.get("from_station_code", ""),
                "from_station_name": props.get("from_station_name", ""),
                "to_station_code": props.get("to_station_code", ""),
                "to_station_name": props.get("to_station_name", ""),
                "departure": props.get("departure", ""),
                "arrival": props.get("arrival", ""),
                "travel_time": travel_time,
                "distance": props.get("distance", ""),
                "classes": classes_str,
                "return_train": props.get("return_train", ""),
                "source": "datameet_master",
                "coordinates_count": len(coords)
            }
            trains.append(train_obj)

        logger.info(f"Successfully parsed {len(trains)} trains from master dataset.")
        return sorted(trains, key=lambda x: x["number"])
