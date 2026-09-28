"""
Telemetry Exporter: Exports live journey snapshots and delay events to CSV and JSON formats.
"""

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import EXPORTS_DIR
from storage.telemetry_db import TelemetryDatabase

logger = logging.getLogger("live_tracker")


class TelemetryExporter:
    """Exports SQLite telemetry records to CSV and JSON."""

    def __init__(self, db: Optional[TelemetryDatabase] = None, export_dir: Optional[Path] = None):
        self.db = db or TelemetryDatabase()
        self.export_dir = export_dir or EXPORTS_DIR
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_snapshots_to_csv(self, filename: str = "live_status.csv") -> Path:
        """Export latest train fleet snapshots to CSV."""
        snapshots = self.db.get_fleet_snapshots(limit=1000)
        out_path = self.export_dir / filename

        fieldnames = [
            "train_number", "train_name", "train_type",
            "current_station_code", "current_station_name",
            "latest_delay_minutes", "next_station_code",
            "distance_covered_km", "total_distance_km",
            "progress_percent", "delay_trend", "delay_drift_rate", "captured_at"
        ]

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for s in snapshots:
                row = {k: s.get(k, "") for k in fieldnames}
                writer.writerow(row)

        logger.info(f"Exported {len(snapshots)} fleet snapshots to {out_path}")
        return out_path

    def export_snapshots_to_json(self, filename: str = "live_telemetry.json") -> Path:
        """Export latest fleet snapshots to JSON."""
        snapshots = self.db.get_fleet_snapshots(limit=1000)
        out_path = self.export_dir / filename

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(snapshots, f, ensure_ascii=False, indent=2)

        logger.info(f"Exported {len(snapshots)} fleet snapshots to {out_path}")
        return out_path

    def export_all(self) -> Dict[str, Path]:
        """Export all telemetry datasets."""
        return {
            "live_status_csv": self.export_snapshots_to_csv(),
            "live_telemetry_json": self.export_snapshots_to_json(),
        }
