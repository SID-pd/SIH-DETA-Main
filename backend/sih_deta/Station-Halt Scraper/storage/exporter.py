"""
Exporter module: Exports station master datasets and train halts to CSV and JSON formats.
Includes production-grade columns (categories, platforms, electrification, status, provenance).
"""

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import EXPORTS_DIR
from storage.db import StationDatabase

logger = logging.getLogger("station_scraper")


class StationExporter:
    """Exports SQLite station records and halt graphs to CSV and JSON files."""

    def __init__(self, db: Optional[StationDatabase] = None, export_dir: Optional[Path] = None):
        self.db = db or StationDatabase()
        self.export_dir = export_dir or EXPORTS_DIR
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_stations_to_csv(self, filename: str = "stations_master.csv") -> Path:
        """Export all stations with full production-grade fields to CSV."""
        stations = self.db.get_all_stations()
        out_path = self.export_dir / filename

        fieldnames = [
            "code", "official_name", "hindi_name", "alternate_names",
            "state", "zone", "division", "district", "city",
            "latitude", "longitude", "elevation_meters", "ir_category",
            "is_junction", "is_terminal", "is_halt", "is_virtual_chord",
            "platform_count", "track_count", "gauge", "electrification_status",
            "operational_status", "passenger_service", "amrit_bharat_station",
            "total_halts_count", "address", "data_source", "last_verified", "updated_at"
        ]

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for stn in stations:
                row = {k: (stn.get(k) if stn.get(k) is not None else "") for k in fieldnames}
                writer.writerow(row)

        logger.info(f"Exported {len(stations)} stations to {out_path}")
        return out_path

    def export_stations_to_json(self, filename: str = "stations_master.json") -> Path:
        """Export all stations to JSON."""
        stations = self.db.get_all_stations()
        out_path = self.export_dir / filename

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(stations, f, ensure_ascii=False, indent=2)

        logger.info(f"Exported {len(stations)} stations to {out_path}")
        return out_path

    def export_halts_to_csv(self, filename: str = "station_halts.csv", limit: Optional[int] = None) -> Path:
        """Export train halts to CSV."""
        halts = self.db.get_all_halts(limit=limit)
        out_path = self.export_dir / filename

        fieldnames = [
            "station_code", "train_number", "train_name",
            "arrival_time", "departure_time", "halt_minutes",
            "day", "days_of_run", "classes", "platform", "distance_km",
            "source", "updated_at"
        ]

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for h in halts:
                row = {k: (h.get(k) if h.get(k) is not None else "") for k in fieldnames}
                writer.writerow(row)

        logger.info(f"Exported {len(halts)} train halts to {out_path}")
        return out_path

    def export_halts_to_json(self, filename: str = "station_halts.json", limit: Optional[int] = None) -> Path:
        """Export train halts to JSON."""
        halts = self.db.get_all_halts(limit=limit)
        out_path = self.export_dir / filename

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(halts, f, ensure_ascii=False, indent=2)

        logger.info(f"Exported {len(halts)} train halts to {out_path}")
        return out_path

    def export_network_summary(self, filename: str = "network_topology_summary.json") -> Path:
        """Export statistical summary of station network topology."""
        stats = self.db.get_summary_stats()
        out_path = self.export_dir / filename

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        logger.info(f"Exported network summary to {out_path}")
        return out_path

    def export_all(self) -> Dict[str, Path]:
        """Export all stations and halt datasets."""
        return {
            "stations_csv": self.export_stations_to_csv(),
            "stations_json": self.export_stations_to_json(),
            "halts_csv": self.export_halts_to_csv(),
            "halts_json": self.export_halts_to_json(),
            "summary_json": self.export_network_summary(),
        }
