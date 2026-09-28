"""
SQLite Database module for Live Journey & Telemetry Tracker.
Manages live snapshots, station delay events, and intermediate track points.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from config import DEFAULT_DB_PATH

logger = logging.getLogger("live_tracker")


class TelemetryDatabase:
    """Manages SQLite storage for real-time train telemetry and delay monitoring."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Create telemetry database tables and performance indices."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Live Train Snapshots Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS live_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    train_number TEXT NOT NULL,
                    train_name TEXT,
                    train_type TEXT,
                    current_station_code TEXT,
                    current_station_name TEXT,
                    latest_delay_minutes INTEGER DEFAULT 0,
                    next_station_code TEXT,
                    distance_covered_km REAL,
                    total_distance_km REAL,
                    progress_percent REAL,
                    delay_trend TEXT,
                    delay_drift_rate REAL,
                    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. Journey Stop Telemetry Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS journey_stop_telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    train_number TEXT NOT NULL,
                    station_code TEXT NOT NULL,
                    station_name TEXT,
                    stop_number INTEGER,
                    scheduled_arrival TEXT,
                    scheduled_departure TEXT,
                    arrival_delay_mins INTEGER DEFAULT 0,
                    departure_delay_mins INTEGER DEFAULT 0,
                    platform TEXT,
                    distance_km REAL,
                    latitude REAL,
                    longitude REAL,
                    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(train_number, station_code, scheduled_arrival, scheduled_departure) ON CONFLICT REPLACE
                );
            """)

            # 3. Intermediate Signaling Cabins & Track Points
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS intermediate_track_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    train_number TEXT NOT NULL,
                    station_code TEXT,
                    station_name TEXT,
                    parent_station TEXT,
                    distance_km REAL,
                    latitude REAL,
                    longitude REAL,
                    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Indices
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_snap_train ON live_snapshots(train_number);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_snap_cur_stn ON live_snapshots(current_station_code);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_snap_delay ON live_snapshots(latest_delay_minutes);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stop_tel_train ON journey_stop_telemetry(train_number);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_track_train ON intermediate_track_points(train_number);")

            conn.commit()
            logger.info(f"Initialized Telemetry database schema at {self.db_path}")

    def save_telemetry(self, raw_telemetry: Dict[str, Any], analyzed: Dict[str, Any]) -> int:
        """Persist full telemetry snapshot, stop delays, and intermediate track points."""
        train_num = raw_telemetry.get("train_number", "")
        if not train_num:
            return 0

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cur_stn = analyzed.get("current_station", {})
            next_stn = analyzed.get("next_station") or {}

            # Insert live snapshot
            cursor.execute("""
                INSERT INTO live_snapshots (
                    train_number, train_name, train_type,
                    current_station_code, current_station_name,
                    latest_delay_minutes, next_station_code,
                    distance_covered_km, total_distance_km,
                    progress_percent, delay_trend, delay_drift_rate, captured_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                train_num,
                raw_telemetry.get("train_name"),
                raw_telemetry.get("train_type"),
                cur_stn.get("code"),
                cur_stn.get("name"),
                analyzed.get("instantaneous_delay_mins", 0),
                next_stn.get("code"),
                cur_stn.get("distance_from_origin_km", 0.0),
                analyzed.get("total_journey_distance_km", 0.0),
                analyzed.get("journey_progress_pct", 0.0),
                analyzed.get("delay_trend"),
                analyzed.get("delay_drift_rate_per_100km"),
            ))
            snapshot_id = cursor.lastrowid

            # Insert stops
            stops = raw_telemetry.get("schedule", [])
            for stop in stops:
                cursor.execute("""
                    INSERT INTO journey_stop_telemetry (
                        train_number, station_code, station_name,
                        stop_number, scheduled_arrival, scheduled_departure,
                        arrival_delay_mins, departure_delay_mins,
                        platform, distance_km, latitude, longitude, captured_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(train_number, station_code, scheduled_arrival, scheduled_departure) DO UPDATE SET
                        arrival_delay_mins = excluded.arrival_delay_mins,
                        departure_delay_mins = excluded.departure_delay_mins,
                        platform = COALESCE(excluded.platform, journey_stop_telemetry.platform),
                        captured_at = CURRENT_TIMESTAMP
                """, (
                    train_num,
                    stop.get("station_code"),
                    stop.get("station_name"),
                    stop.get("stop_number"),
                    stop.get("scheduled_arrival"),
                    stop.get("scheduled_departure"),
                    stop.get("arrival_delay_mins", 0),
                    stop.get("departure_delay_mins", 0),
                    stop.get("expected_platform"),
                    stop.get("distance_km"),
                    stop.get("latitude"),
                    stop.get("longitude"),
                ))

            # Insert intermediate track points / block cabins
            cabins = raw_telemetry.get("intermediate_cabins", [])
            for cabin in cabins:
                cursor.execute("""
                    INSERT INTO intermediate_track_points (
                        train_number, station_code, station_name,
                        parent_station, distance_km, latitude, longitude, captured_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    train_num,
                    cabin.get("station_code"),
                    cabin.get("station_name"),
                    cabin.get("parent_station"),
                    cabin.get("distance_km"),
                    cabin.get("latitude"),
                    cabin.get("longitude"),
                ))

            conn.commit()
            logger.info(f"Saved live telemetry for train {train_num} ({len(stops)} stops, {len(cabins)} cabins).")
            return snapshot_id

    def get_latest_snapshot(self, train_number: str) -> Optional[Dict[str, Any]]:
        """Get latest telemetry snapshot for a train."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM live_snapshots
                WHERE train_number = ?
                ORDER BY captured_at DESC LIMIT 1
            """, (train_number.strip(),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_fleet_snapshots(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get most recent snapshots for monitored trains."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.* FROM live_snapshots s
                INNER JOIN (
                    SELECT train_number, MAX(captured_at) as max_time
                    FROM live_snapshots
                    GROUP BY train_number
                ) latest ON s.train_number = latest.train_number AND s.captured_at = latest.max_time
                ORDER BY s.latest_delay_minutes DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_stops_telemetry(self, train_number: str) -> List[Dict[str, Any]]:
        """Get station delay records for a train."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM journey_stop_telemetry
                WHERE train_number = ?
                ORDER BY stop_number ASC
            """, (train_number.strip(),))
            return [dict(row) for row in cursor.fetchall()]

    def get_intermediate_cabins(self, train_number: str) -> List[Dict[str, Any]]:
        """Get intermediate track cabins for a train."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM intermediate_track_points
                WHERE train_number = ?
                ORDER BY distance_km ASC
            """, (train_number.strip(),))
            return [dict(row) for row in cursor.fetchall()]

    def get_outer_signal_delays(self, min_delay_surge: int = 15) -> List[Dict[str, Any]]:
        """Find trains experiencing sharp delay spikes right before stations (outer signals)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT train_number, station_code, station_name,
                       arrival_delay_mins, departure_delay_mins,
                       (departure_delay_mins - arrival_delay_mins) as delay_surge,
                       platform
                FROM journey_stop_telemetry
                WHERE (departure_delay_mins - arrival_delay_mins) >= ?
                  AND departure_delay_mins > 0
                ORDER BY delay_surge DESC
            """, (min_delay_surge,))
            return [dict(row) for row in cursor.fetchall()]

    def get_summary_stats(self) -> Dict[str, Any]:
        """Aggregate statistics of live monitored trains."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(DISTINCT train_number) FROM live_snapshots")
            total_monitored_trains = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM live_snapshots")
            total_snapshots = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM journey_stop_telemetry")
            total_stop_records = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM intermediate_track_points")
            total_cabin_points = cursor.fetchone()[0]

            # Average delay
            cursor.execute("""
                SELECT AVG(latest_delay_minutes) FROM (
                    SELECT train_number, latest_delay_minutes
                    FROM live_snapshots
                    GROUP BY train_number
                    HAVING MAX(captured_at)
                )
            """)
            avg_delay_val = cursor.fetchone()[0]
            avg_delay = round(avg_delay_val, 1) if avg_delay_val is not None else 0.0

            # On-time vs delayed
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN latest_delay_minutes <= 15 THEN 1 ELSE 0 END) as on_time,
                    SUM(CASE WHEN latest_delay_minutes > 15 AND latest_delay_minutes <= 60 THEN 1 ELSE 0 END) as moderate_delay,
                    SUM(CASE WHEN latest_delay_minutes > 60 THEN 1 ELSE 0 END) as severe_delay
                FROM (
                    SELECT train_number, latest_delay_minutes
                    FROM live_snapshots
                    GROUP BY train_number
                    HAVING MAX(captured_at)
                )
            """)
            punctuality = cursor.fetchone()

            return {
                "total_monitored_trains": total_monitored_trains,
                "total_snapshots": total_snapshots,
                "total_stop_records": total_stop_records,
                "total_cabin_points": total_cabin_points,
                "average_delay_mins": avg_delay,
                "on_time_trains": punctuality[0] if punctuality and punctuality[0] else 0,
                "moderately_delayed_trains": punctuality[1] if punctuality and punctuality[1] else 0,
                "severely_delayed_trains": punctuality[2] if punctuality and punctuality[2] else 0,
            }
