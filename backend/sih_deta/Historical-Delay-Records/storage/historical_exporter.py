"""
Dataset Exporter for Historical Delay Records: Generates CSV and JSON feature sets.
"""

import csv
import json
import logging
from pathlib import Path
from typing import Dict, Optional

from config import EXPORTS_DIR
from storage.historical_db import HistoricalDatabase

logger = logging.getLogger("historical_exporter")


class HistoricalExporter:
    """Exports historical delay datasets and ML feature sets to CSV and JSON."""

    def __init__(
        self,
        db: Optional[HistoricalDatabase] = None,
        export_dir: Optional[Path] = None,
    ):
        self.db = db or HistoricalDatabase()
        self.export_dir = export_dir or EXPORTS_DIR
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_sectional_history_csv(self) -> Path:
        """Export raw sectional delay records to CSV."""
        out_path = self.export_dir / "delay_history_15days.csv"
        records = self.db.get_all_sectional_records()

        fieldnames = [
            "train_number", "journey_date", "from_station", "to_station", "section_order",
            "departure_delay", "arrival_delay", "delay_delta", "status", "from_state", "to_state", "day_of_week"
        ]

        with open(out_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in records:
                writer.writerow(r)

        logger.info(f"Exported {len(records)} sectional delay records to {out_path}")
        return out_path

    def export_sectional_profiles_csv(self) -> Path:
        """Export pre-aggregated sectional profiles to CSV."""
        out_path = self.export_dir / "sectional_profiles.csv"
        profiles = self.db.get_all_profiles()

        fieldnames = [
            "train_number", "from_station", "to_station", "section_order", "sample_size_days",
            "mean_delay_delta", "std_delay_delta", "median_delay_delta", "min_delay_delta", "max_delay_delta",
            "absorption_rate_pct", "accumulation_rate_pct", "punctuality_rate_pct", "corridor_type"
        ]

        with open(out_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for p in profiles:
                writer.writerow(p)

        logger.info(f"Exported {len(profiles)} sectional profiles to {out_path}")
        return out_path

    def export_summary_json(self) -> Path:
        """Export overall database summary and stats to JSON."""
        out_path = self.export_dir / "historical_summary.json"
        stats = self.db.get_summary_stats()
        with open(out_path, mode="w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
        return out_path

    def export_all(self) -> Dict[str, Path]:
        """Run all export routines."""
        return {
            "delay_history_csv": self.export_sectional_history_csv(),
            "sectional_profiles_csv": self.export_sectional_profiles_csv(),
            "summary_json": self.export_summary_json(),
        }
