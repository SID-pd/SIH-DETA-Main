"""
Data Exporter: Exports scraped train records to JSON and CSV formats.
"""

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("rail_scraper")

TRAIN_CSV_FIELDS = [
    "number",
    "name",
    "type",
    "zone",
    "route",
    "from_station_code",
    "from_station_name",
    "to_station_code",
    "to_station_name",
    "departure",
    "arrival",
    "travel_time",
    "distance",
    "service_days",
    "total_stops",
    "classes",
    "pantry",
    "source"
]

STOP_CSV_FIELDS = [
    "train_number",
    "sno",
    "station_code",
    "station_name",
    "arrival",
    "departure",
    "halt",
    "distance",
    "avg_delay",
    "day"
]


def export_to_json(data: Any, filepath: Path, indent: int = 2) -> Path:
    """Save python data structure to a JSON file."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)

    logger.info(f"Exported {len(data) if isinstance(data, list) else 1} records to JSON: {filepath}")
    return filepath


def export_to_csv(
    data: List[Dict[str, Any]],
    filepath: Path,
    fields: Optional[List[str]] = None
) -> Path:
    """Save a list of dictionary records to a CSV file."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if not data:
        logger.warning(f"No data to export to CSV: {filepath}")
        return filepath

    if not fields:
        # Infer fields from first record or use TRAIN_CSV_FIELDS
        fields = [f for f in TRAIN_CSV_FIELDS if any(f in item for item in data)]
        if not fields:
            fields = list(data[0].keys())

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            # Flatten any nested lists/dicts to strings
            clean_row = {}
            for k in fields:
                val = row.get(k, "")
                if isinstance(val, (list, dict)):
                    clean_row[k] = json.dumps(val)
                else:
                    clean_row[k] = val
            writer.writerow(clean_row)

    logger.info(f"Exported {len(data)} records to CSV: {filepath}")
    return filepath


def export_schedules_flattened_csv(
    schedules: List[Dict[str, Any]],
    filepath: Path
) -> Path:
    """Export detailed train stops for multiple schedules to a single CSV."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    all_stops = []
    for sched in schedules:
        train_no = sched.get("number", "")
        for stop in sched.get("stops", []):
            stop_copy = dict(stop)
            stop_copy["train_number"] = train_no
            all_stops.append(stop_copy)

    return export_to_csv(all_stops, filepath, fields=STOP_CSV_FIELDS)
