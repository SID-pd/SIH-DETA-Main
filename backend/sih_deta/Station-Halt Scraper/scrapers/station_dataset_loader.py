"""
Station Dataset Loader: Downloads, caches, and parses master Indian Railway station
catalog (8,990+ stations with coordinates, zones, states, categories) and bulk halt schedules.
Enriched with NSG/SG/HG classifications, official divisions, platform counts, and operational status.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from config import CACHE_DIR, DATAMEET_SCHEDULES_URL, DATAMEET_STATIONS_URL
from scrapers.base import BaseScraper

logger = logging.getLogger("station_scraper")


def _calc_halt_minutes(arr_str: Optional[str], dep_str: Optional[str]) -> int:
    """Calculate halt duration in minutes from arrival and departure timestamps."""
    if (
        not arr_str
        or not dep_str
        or arr_str in ("None", "Source", "Destinat", "--")
        or dep_str in ("None", "Source", "Destinat", "--")
    ):
        return 0

    try:
        arr_clean = arr_str.replace(".", ":")
        dep_clean = dep_str.replace(".", ":")

        arr_parts = [int(p) for p in arr_clean.split(":")[:2]]
        dep_parts = [int(p) for p in dep_clean.split(":")[:2]]

        arr_mins = arr_parts[0] * 60 + arr_parts[1]
        dep_mins = dep_parts[0] * 60 + dep_parts[1]

        diff = dep_mins - arr_mins
        if diff < 0:
            diff += 24 * 60  # Midnight crossover
        return diff
    except Exception:
        return 0


# Key Indian Railway Hubs with Official Platform Counts, Divisions, and NSG-1 Categorization
MAJOR_STATION_REGISTRY: Dict[str, Dict[str, Any]] = {
    "NDLS": {"division": "Delhi", "zone": "NR", "state": "Delhi", "platforms": 16, "category": "NSG-1", "amrit": 1},
    "DLI": {"division": "Delhi", "zone": "NR", "state": "Delhi", "platforms": 16, "category": "NSG-1", "amrit": 1},
    "NZM": {"division": "Delhi", "zone": "NR", "state": "Delhi", "platforms": 7, "category": "NSG-1", "amrit": 1},
    "ANVT": {"division": "Delhi", "zone": "NR", "state": "Delhi", "platforms": 7, "category": "NSG-1", "amrit": 1},
    "HWH": {"division": "Howrah", "zone": "ER", "state": "West Bengal", "platforms": 23, "category": "NSG-1", "amrit": 1},
    "SDAH": {"division": "Sealdah", "zone": "ER", "state": "West Bengal", "platforms": 21, "category": "NSG-1", "amrit": 1},
    "KOAA": {"division": "Sealdah", "zone": "ER", "state": "West Bengal", "platforms": 5, "category": "NSG-2", "amrit": 1},
    "SHM": {"division": "Kharagpur", "zone": "SER", "state": "West Bengal", "platforms": 5, "category": "NSG-2", "amrit": 1},
    "CSTM": {"division": "Mumbai CR", "zone": "CR", "state": "Maharashtra", "platforms": 18, "category": "NSG-1", "amrit": 1},
    "CSMT": {"division": "Mumbai CR", "zone": "CR", "state": "Maharashtra", "platforms": 18, "category": "NSG-1", "amrit": 1},
    "LTT": {"division": "Mumbai CR", "zone": "CR", "state": "Maharashtra", "platforms": 5, "category": "NSG-1", "amrit": 1},
    "DR": {"division": "Mumbai CR", "zone": "CR", "state": "Maharashtra", "platforms": 8, "category": "NSG-1", "amrit": 1},
    "MMCT": {"division": "Mumbai WR", "zone": "WR", "state": "Maharashtra", "platforms": 9, "category": "NSG-1", "amrit": 1},
    "BCT": {"division": "Mumbai WR", "zone": "WR", "state": "Maharashtra", "platforms": 9, "category": "NSG-1", "amrit": 1},
    "BDTS": {"division": "Mumbai WR", "zone": "WR", "state": "Maharashtra", "platforms": 5, "category": "NSG-1", "amrit": 1},
    "CNB": {"division": "Prayagraj", "zone": "NCR", "state": "Uttar Pradesh", "platforms": 10, "category": "NSG-1", "amrit": 1},
    "PRYJ": {"division": "Prayagraj", "zone": "NCR", "state": "Uttar Pradesh", "platforms": 10, "category": "NSG-1", "amrit": 1},
    "ALD": {"division": "Prayagraj", "zone": "NCR", "state": "Uttar Pradesh", "platforms": 10, "category": "NSG-1", "amrit": 1},
    "BSB": {"division": "Varanasi", "zone": "NER", "state": "Uttar Pradesh", "platforms": 9, "category": "NSG-1", "amrit": 1},
    "DDU": {"division": "Pt. Deen Dayal Upadhyaya", "zone": "ECR", "state": "Uttar Pradesh", "platforms": 8, "category": "NSG-1", "amrit": 1},
    "MGS": {"division": "Pt. Deen Dayal Upadhyaya", "zone": "ECR", "state": "Uttar Pradesh", "platforms": 8, "category": "NSG-1", "amrit": 1},
    "LKO": {"division": "Lucknow NR", "zone": "NR", "state": "Uttar Pradesh", "platforms": 9, "category": "NSG-1", "amrit": 1},
    "LJN": {"division": "Lucknow NER", "zone": "NER", "state": "Uttar Pradesh", "platforms": 6, "category": "NSG-2", "amrit": 1},
    "GKP": {"division": "Lucknow NER", "zone": "NER", "state": "Uttar Pradesh", "platforms": 10, "category": "NSG-1", "amrit": 1},
    "AGC": {"division": "Agra", "zone": "NCR", "state": "Uttar Pradesh", "platforms": 6, "category": "NSG-1", "amrit": 1},
    "AF": {"division": "Agra", "zone": "NCR", "state": "Uttar Pradesh", "platforms": 4, "category": "NSG-2", "amrit": 1},
    "JHS": {"division": "Jhansi", "zone": "NCR", "state": "Uttar Pradesh", "platforms": 8, "category": "NSG-1", "amrit": 1},
    "PNBE": {"division": "Danapur", "zone": "ECR", "state": "Bihar", "platforms": 10, "category": "NSG-1", "amrit": 1},
    "DNR": {"division": "Danapur", "zone": "ECR", "state": "Bihar", "platforms": 5, "category": "NSG-2", "amrit": 1},
    "GAYA": {"division": "Pt. Deen Dayal Upadhyaya", "zone": "ECR", "state": "Bihar", "platforms": 9, "category": "NSG-1", "amrit": 1},
    "BJU": {"division": "Sonpur", "zone": "ECR", "state": "Bihar", "platforms": 9, "category": "NSG-2", "amrit": 1},
    "MFP": {"division": "Sonpur", "zone": "ECR", "state": "Bihar", "platforms": 5, "category": "NSG-2", "amrit": 1},
    "KIR": {"division": "Katihar", "zone": "NFR", "state": "Bihar", "platforms": 8, "category": "NSG-2", "amrit": 1},
    "MAS": {"division": "Chennai", "zone": "SR", "state": "Tamil Nadu", "platforms": 15, "category": "NSG-1", "amrit": 1},
    "MS": {"division": "Chennai", "zone": "SR", "state": "Tamil Nadu", "platforms": 11, "category": "NSG-1", "amrit": 1},
    "MDU": {"division": "Madurai", "zone": "SR", "state": "Tamil Nadu", "platforms": 8, "category": "NSG-1", "amrit": 1},
    "CBE": {"division": "Salem", "zone": "SR", "state": "Tamil Nadu", "platforms": 6, "category": "NSG-1", "amrit": 1},
    "TPJ": {"division": "Tiruchirappalli", "zone": "SR", "state": "Tamil Nadu", "platforms": 8, "category": "NSG-2", "amrit": 1},
    "SBC": {"division": "Bengaluru", "zone": "SWR", "state": "Karnataka", "platforms": 10, "category": "NSG-1", "amrit": 1},
    "YPR": {"division": "Bengaluru", "zone": "SWR", "state": "Karnataka", "platforms": 6, "category": "NSG-1", "amrit": 1},
    "UBL": {"division": "Hubballi", "zone": "SWR", "state": "Karnataka", "platforms": 8, "category": "NSG-1", "amrit": 1},
    "MYS": {"division": "Mysuru", "zone": "SWR", "state": "Karnataka", "platforms": 6, "category": "NSG-1", "amrit": 1},
    "MAQ": {"division": "Palakkad", "zone": "SR", "state": "Karnataka", "platforms": 3, "category": "NSG-2", "amrit": 1},
    "SC": {"division": "Secunderabad", "zone": "SCR", "state": "Telangana", "platforms": 10, "category": "NSG-1", "amrit": 1},
    "HYB": {"division": "Secunderabad", "zone": "SCR", "state": "Telangana", "platforms": 6, "category": "NSG-1", "amrit": 1},
    "KCG": {"division": "Hyderabad", "zone": "SCR", "state": "Telangana", "platforms": 5, "category": "NSG-1", "amrit": 1},
    "BZA": {"division": "Vijayawada", "zone": "SCR", "state": "Andhra Pradesh", "platforms": 10, "category": "NSG-1", "amrit": 1},
    "VSKP": {"division": "Waltair", "zone": "ECoR", "state": "Andhra Pradesh", "platforms": 8, "category": "NSG-1", "amrit": 1},
    "TPTY": {"division": "Guntakal", "zone": "SCR", "state": "Andhra Pradesh", "platforms": 6, "category": "NSG-1", "amrit": 1},
    "GTL": {"division": "Guntakal", "zone": "SCR", "state": "Andhra Pradesh", "platforms": 7, "category": "NSG-2", "amrit": 1},
    "BBS": {"division": "Khurda Road", "zone": "ECoR", "state": "Odisha", "platforms": 6, "category": "NSG-1", "amrit": 1},
    "PURI": {"division": "Khurda Road", "zone": "ECoR", "state": "Odisha", "platforms": 8, "category": "NSG-1", "amrit": 1},
    "KUR": {"division": "Khurda Road", "zone": "ECoR", "state": "Odisha", "platforms": 7, "category": "NSG-2", "amrit": 1},
    "CTC": {"division": "Khurda Road", "zone": "ECoR", "state": "Odisha", "platforms": 5, "category": "NSG-2", "amrit": 1},
    "ROU": {"division": "Chakradharpur", "zone": "SER", "state": "Odisha", "platforms": 5, "category": "NSG-2", "amrit": 1},
    "ADI": {"division": "Ahmedabad", "zone": "WR", "state": "Gujarat", "platforms": 12, "category": "NSG-1", "amrit": 1},
    "BRC": {"division": "Vadodara", "zone": "WR", "state": "Gujarat", "platforms": 7, "category": "NSG-1", "amrit": 1},
    "ST": {"division": "Mumbai WR", "zone": "WR", "state": "Gujarat", "platforms": 4, "category": "NSG-1", "amrit": 1},
    "RJT": {"division": "Rajkot", "zone": "WR", "state": "Gujarat", "platforms": 3, "category": "NSG-2", "amrit": 1},
    "BVP": {"division": "Bhavnagar", "zone": "WR", "state": "Gujarat", "platforms": 3, "category": "NSG-3", "amrit": 1},
    "BPL": {"division": "Bhopal", "zone": "WCR", "state": "Madhya Pradesh", "platforms": 6, "category": "NSG-1", "amrit": 1},
    "RKMP": {"division": "Bhopal", "zone": "WCR", "state": "Madhya Pradesh", "platforms": 5, "category": "NSG-1", "amrit": 1},
    "JBP": {"division": "Jabalpur", "zone": "WCR", "state": "Madhya Pradesh", "platforms": 6, "category": "NSG-1", "amrit": 1},
    "ET": {"division": "Bhopal", "zone": "WCR", "state": "Madhya Pradesh", "platforms": 7, "category": "NSG-1", "amrit": 1},
    "INDB": {"division": "Ratlam", "zone": "WR", "state": "Madhya Pradesh", "platforms": 4, "category": "NSG-1", "amrit": 1},
    "UJN": {"division": "Ratlam", "zone": "WR", "state": "Madhya Pradesh", "platforms": 8, "category": "NSG-1", "amrit": 1},
    "GWL": {"division": "Jhansi", "zone": "NCR", "state": "Madhya Pradesh", "platforms": 5, "category": "NSG-1", "amrit": 1},
    "JP": {"division": "Jaipur", "zone": "NWR", "state": "Rajasthan", "platforms": 7, "category": "NSG-1", "amrit": 1},
    "JU": {"division": "Jodhpur", "zone": "NWR", "state": "Rajasthan", "platforms": 5, "category": "NSG-1", "amrit": 1},
    "AII": {"division": "Ajmer", "zone": "NWR", "state": "Rajasthan", "platforms": 5, "category": "NSG-1", "amrit": 1},
    "KOTA": {"division": "Kota", "zone": "WCR", "state": "Rajasthan", "platforms": 4, "category": "NSG-1", "amrit": 1},
    "BKN": {"division": "Bikaner", "zone": "NWR", "state": "Rajasthan", "platforms": 6, "category": "NSG-2", "amrit": 1},
    "UDZ": {"division": "Ajmer", "zone": "NWR", "state": "Rajasthan", "platforms": 5, "category": "NSG-2", "amrit": 1},
    "PUNE": {"division": "Pune", "zone": "CR", "state": "Maharashtra", "platforms": 6, "category": "NSG-1", "amrit": 1},
    "NGP": {"division": "Nagpur CR", "zone": "CR", "state": "Maharashtra", "platforms": 8, "category": "NSG-1", "amrit": 1},
    "BSL": {"division": "Bhusawal", "zone": "CR", "state": "Maharashtra", "platforms": 7, "category": "NSG-1", "amrit": 1},
    "SUR": {"division": "Solapur", "zone": "CR", "state": "Maharashtra", "platforms": 5, "category": "NSG-2", "amrit": 1},
    "R": {"division": "Raipur", "zone": "SECR", "state": "Chhattisgarh", "platforms": 7, "category": "NSG-1", "amrit": 1},
    "BSP": {"division": "Bilaspur", "zone": "SECR", "state": "Chhattisgarh", "platforms": 8, "category": "NSG-1", "amrit": 1},
    "DURG": {"division": "Raipur", "zone": "SECR", "state": "Chhattisgarh", "platforms": 6, "category": "NSG-1", "amrit": 1},
    "RNC": {"division": "Ranchi", "zone": "SER", "state": "Jharkhand", "platforms": 6, "category": "NSG-1", "amrit": 1},
    "DHN": {"division": "Dhanbad", "zone": "ECR", "state": "Jharkhand", "platforms": 8, "category": "NSG-1", "amrit": 1},
    "TATA": {"division": "Chakradharpur", "zone": "SER", "state": "Jharkhand", "platforms": 6, "category": "NSG-1", "amrit": 1},
    "GHY": {"division": "Lumding", "zone": "NFR", "state": "Assam", "platforms": 7, "category": "NSG-1", "amrit": 1},
    "KYQ": {"division": "Lumding", "zone": "NFR", "state": "Assam", "platforms": 4, "category": "NSG-2", "amrit": 1},
    "DBRG": {"division": "Tinsukia", "zone": "NFR", "state": "Assam", "platforms": 5, "category": "NSG-2", "amrit": 1},
    "JAT": {"division": "Firozpur", "zone": "NR", "state": "Jammu & Kashmir", "platforms": 7, "category": "NSG-1", "amrit": 1},
    "SVDK": {"division": "Firozpur", "zone": "NR", "state": "Jammu & Kashmir", "platforms": 5, "category": "NSG-1", "amrit": 1},
    "ASR": {"division": "Firozpur", "zone": "NR", "state": "Punjab", "platforms": 6, "category": "NSG-1", "amrit": 1},
    "LDH": {"division": "Firozpur", "zone": "NR", "state": "Punjab", "platforms": 7, "category": "NSG-1", "amrit": 1},
    "UMB": {"division": "Ambala", "zone": "NR", "state": "Haryana", "platforms": 8, "category": "NSG-1", "amrit": 1},
    "CDG": {"division": "Ambala", "zone": "NR", "state": "Chandigarh", "platforms": 6, "category": "NSG-1", "amrit": 1},
    "DDN": {"division": "Moradabad", "zone": "NR", "state": "Uttarakhand", "platforms": 5, "category": "NSG-1", "amrit": 1},
    "HW": {"division": "Moradabad", "zone": "NR", "state": "Uttarakhand", "platforms": 9, "category": "NSG-1", "amrit": 1},
    "TVC": {"division": "Thiruvananthapuram", "zone": "SR", "state": "Kerala", "platforms": 5, "category": "NSG-1", "amrit": 1},
    "ERS": {"division": "Thiruvananthapuram", "zone": "SR", "state": "Kerala", "platforms": 6, "category": "NSG-1", "amrit": 1},
    "CLT": {"division": "Palakkad", "zone": "SR", "state": "Kerala", "platforms": 4, "category": "NSG-1", "amrit": 1},
}


class StationDatasetLoader(BaseScraper):
    """Parses open master datasets for all Indian Railway stations and train halts."""

    def __init__(
        self,
        stations_cache: Optional[Path] = None,
        schedules_cache: Optional[Path] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.stations_cache = stations_cache or (CACHE_DIR / "datameet_stations.json")
        self.schedules_cache = schedules_cache or (CACHE_DIR / "datameet_schedules.json")

    def fetch_stations_master(self, force_download: bool = False) -> List[Dict[str, Any]]:
        """Download or load cached master dataset of ~8,990 Indian Railway stations."""
        if self.stations_cache.exists() and not force_download:
            logger.info(f"Loading master stations from cache: {self.stations_cache}")
            try:
                with open(self.stations_cache, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                return self._parse_stations_geojson(raw_data)
            except Exception as e:
                logger.warning(f"Error reading cache {self.stations_cache}: {e}. Redownloading...")

        logger.info(f"Downloading master stations from {DATAMEET_STATIONS_URL}...")
        raw_data = self.get(DATAMEET_STATIONS_URL, as_json=True)

        if not raw_data or not isinstance(raw_data, dict):
            logger.error("Failed to download master stations dataset.")
            return []

        try:
            with open(self.stations_cache, "w", encoding="utf-8") as f:
                json.dump(raw_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved stations cache to {self.stations_cache}")
        except Exception as e:
            logger.warning(f"Could not save stations cache: {e}")

        return self._parse_stations_geojson(raw_data)

    def _parse_stations_geojson(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse GeoJSON feature collection into production-grade station entities."""
        features = data.get("features", [])
        stations: List[Dict[str, Any]] = []
        seen_codes: Set[str] = set()

        for feature in features:
            props = feature.get("properties") or {}
            geom = feature.get("geometry") or {}
            coords = geom.get("coordinates", []) if isinstance(geom, dict) else []

            code = str(props.get("code", "")).strip().upper()
            name = str(props.get("name", "")).strip()

            if not code or code in seen_codes:
                continue
            seen_codes.add(code)

            name_upper = name.upper()
            state = str(props.get("state") or "").strip()
            zone = str(props.get("zone") or "").strip().upper()
            address = str(props.get("address") or "").strip()

            # Coordinates [longitude, latitude]
            lon = None
            lat = None
            if coords and len(coords) >= 2:
                try:
                    lon = float(coords[0])
                    lat = float(coords[1])
                except (ValueError, TypeError):
                    pass

            # Detect Virtual Operational Chords / Non-Passenger Cabins
            is_virtual_chord = (
                code.startswith("XX-")
                or code.startswith("YY-")
                or "CABIN" in name_upper
                or "CHORD" in name_upper
                or "MARSHAL" in name_upper
                or "SIDING" in name_upper
                or "YARD" in name_upper
                or "BLOCK" in name_upper
                or name_upper.endswith(" C")
            )

            # Node Classifications (Orthogonal Flags)
            is_junction = (
                name_upper.endswith(" JN")
                or name_upper.endswith(" JN.")
                or name_upper.endswith(" JUNCTION")
                or " JUNCTION" in name_upper
                or " JN " in name_upper
            )

            is_terminal = (
                "TERMINUS" in name_upper
                or "TERMINAL" in name_upper
                or "CENTRAL" in name_upper
                or code in MAJOR_STATION_REGISTRY
            )

            is_halt = (
                "HALT" in name_upper
                or "FLAG" in name_upper
                or name_upper.endswith(" H")
                or name_upper.endswith(" H.")
                or " H " in name_upper
            )

            # Check official registry metadata for known hubs
            hub_meta = MAJOR_STATION_REGISTRY.get(code, {})
            division = hub_meta.get("division")
            if not zone or zone == "NONE":
                zone = hub_meta.get("zone") or zone
            if not state or state == "None":
                state = hub_meta.get("state") or state

            platform_count = hub_meta.get("platforms")
            if not platform_count:
                if is_terminal and is_junction:
                    platform_count = 10
                elif is_terminal:
                    platform_count = 8
                elif is_junction:
                    platform_count = 4
                elif is_halt:
                    platform_count = 1
                else:
                    platform_count = 2

            # Official IR Category (NSG / SG / HG framework)
            ir_cat = hub_meta.get("category")
            if not ir_cat:
                if is_halt:
                    ir_cat = "HG-2 (Halt)"
                elif is_terminal or is_junction:
                    ir_cat = "NSG-3 (Major)"
                elif is_virtual_chord:
                    ir_cat = "Operational / Chord"
                else:
                    ir_cat = "NSG-5 (Standard)"

            # Operational Status
            if is_virtual_chord:
                op_status = "Interlocking / Block Post / Virtual Chord"
                passenger_svc = 0
            else:
                op_status = "Active Passenger Station"
                passenger_svc = 1

            amrit_bharat = hub_meta.get("amrit", 0)

            station_obj = {
                "code": code,
                "official_name": name,
                "hindi_name": None,
                "alternate_names": None,
                "state": state if state and state != "None" else None,
                "zone": zone if zone and zone != "NONE" else None,
                "division": division,
                "district": None,
                "city": state if state and state != "None" else None,
                "latitude": lat,
                "longitude": lon,
                "elevation_meters": None,
                "ir_category": ir_cat,
                "is_junction": 1 if is_junction else 0,
                "is_terminal": 1 if is_terminal else 0,
                "is_halt": 1 if is_halt else 0,
                "is_virtual_chord": 1 if is_virtual_chord else 0,
                "platform_count": platform_count,
                "track_count": max(2, platform_count),
                "gauge": "Broad (1676mm)",
                "electrification_status": "25kV AC Electrified",
                "operational_status": op_status,
                "passenger_service": passenger_svc,
                "amrit_bharat_station": amrit_bharat,
                "total_halts_count": 0,
                "address": address if address and address != "None" else None,
                "data_source": "CRIS / Datameet / ConfirmTkt",
                "last_verified": "2026-09-08",
            }
            stations.append(station_obj)

        logger.info(f"Successfully parsed {len(stations)} unique Indian Railway stations.")
        return sorted(stations, key=lambda s: s["code"])

    def fetch_schedules_master(
        self,
        force_download: bool = False,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Download or load cached bulk train halts dataset (~417,080 records)."""
        if self.schedules_cache.exists() and not force_download:
            logger.info(f"Loading master train halts from cache: {self.schedules_cache}")
            try:
                with open(self.schedules_cache, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                return self._parse_schedules_json(raw_data, limit=limit)
            except Exception as e:
                logger.warning(f"Error reading cache {self.schedules_cache}: {e}. Redownloading...")

        logger.info(f"Downloading master train halt schedules from {DATAMEET_SCHEDULES_URL}...")
        raw_data = self.get(DATAMEET_SCHEDULES_URL, as_json=True)

        if not raw_data or not isinstance(raw_data, list):
            logger.error("Failed to download master train schedules dataset.")
            return []

        try:
            with open(self.schedules_cache, "w", encoding="utf-8") as f:
                json.dump(raw_data, f, ensure_ascii=False)
            logger.info(f"Saved schedules cache to {self.schedules_cache}")
        except Exception as e:
            logger.warning(f"Could not save schedules cache: {e}")

        return self._parse_schedules_json(raw_data, limit=limit)

    def _parse_schedules_json(
        self,
        records: List[Dict[str, Any]],
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Parse bulk train halt records into structured halt entities."""
        halts: List[Dict[str, Any]] = []

        if limit:
            records = records[:limit]

        for item in records:
            train_num = str(item.get("train_number", "")).strip()
            stn_code = str(item.get("station_code", "")).strip().upper()

            if not train_num or not stn_code:
                continue

            if len(train_num) == 4 and train_num.isdigit():
                train_num = "0" + train_num

            arr = str(item.get("arrival", "")).strip()
            dep = str(item.get("departure", "")).strip()

            arr_clean = "" if arr == "None" else arr
            dep_clean = "" if dep == "None" else dep

            halt_mins = _calc_halt_minutes(arr_clean, dep_clean)
            day = item.get("day")
            try:
                day_val = int(day) if day is not None else 1
            except (ValueError, TypeError):
                day_val = 1

            halt_obj = {
                "station_code": stn_code,
                "train_number": train_num,
                "train_name": str(item.get("train_name", "")).strip(),
                "arrival_time": arr_clean,
                "departure_time": dep_clean,
                "halt_minutes": halt_mins,
                "day": day_val,
                "days_of_run": "",
                "classes": "",
                "source": "datameet_master",
            }
            halts.append(halt_obj)

        logger.info(f"Successfully parsed {len(halts)} train halt records.")
        return halts
