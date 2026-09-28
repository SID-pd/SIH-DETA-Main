"""
Live Snapshot Harvester Daemon.
Continuously records periodic running status snapshots of trains into SQLite/CSV.
Builds an empirical, rolling ground-truth historical dataset.
"""

import datetime
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from predictor.config import SNAPSHOTS_DB_PATH
from predictor.scrapers.confirmtkt_scraper import ConfirmTktScraper

logger = logging.getLogger("predictor.scrapers.daemon")


class LiveSnapshotDaemon:
    """Harvests live running status snapshots for continuous historical dataset creation."""

    def __init__(self, db_path: Path = SNAPSHOTS_DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.scraper = ConfirmTktScraper()
        self._init_db()

    def _init_db(self):
        """Initializes the snapshots SQLite schema."""
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS live_train_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    train_id TEXT NOT NULL,
                    train_name TEXT,
                    captured_at TEXT NOT NULL,
                    current_station TEXT,
                    next_station TEXT,
                    distance_to_next REAL,
                    current_delay_min INTEGER,
                    scheduled_arr_next TEXT,
                    actual_arr_current TEXT,
                    stops_passed INTEGER,
                    stops_remaining INTEGER,
                    status_raw TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_train_time ON live_train_snapshots (train_id, captured_at)")
        conn.close()

    def capture_snapshot(self, train_number: str) -> Optional[Dict[str, Any]]:
        """Polls live status for a train and persists snapshot."""
        data = self.scraper.get_live_status(train_number)
        if not data:
            return None

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        train_id = str(train_number).zfill(5)
        curr_stn = data.get("current_station_code")
        next_stn = data.get("next_station_code")
        dist_next = data.get("distance_to_next_station_km", 0.0)
        curr_delay = data.get("current_delay_minutes", 0)

        stops = data.get("stops", [])
        passed = 0
        rem = len(stops)
        if curr_stn:
            for idx, s in enumerate(stops):
                if s["station_code"] == curr_stn:
                    passed = idx + 1
                    rem = len(stops) - passed
                    break

        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("""
                INSERT INTO live_train_snapshots (
                    train_id, train_name, captured_at, current_station, next_station,
                    distance_to_next, current_delay_min, scheduled_arr_next,
                    actual_arr_current, stops_passed, stops_remaining, status_raw
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                train_id,
                data.get("train_name"),
                now_iso,
                curr_stn,
                next_stn,
                dist_next,
                curr_delay,
                stops[passed]["scheduled_arrival"] if passed < len(stops) else None,
                stops[passed - 1]["actual_arrival"] if passed > 0 else None,
                passed,
                rem,
                "RUNNING" if curr_stn else "SCHEDULED",
            ))
        conn.close()
        logger.info(f"Recorded snapshot for Train {train_id} at station {curr_stn} (delay: {curr_delay}m)")
        return data

    def harvest_batch(self, train_numbers: List[str]) -> int:
        """Polls multiple trains in sequence."""
        success = 0
        for t in train_numbers:
            res = self.capture_snapshot(t)
            if res:
                success += 1
        return success

    def count_snapshots(self) -> int:
        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM live_train_snapshots").fetchone()[0]
        conn.close()
        return count
