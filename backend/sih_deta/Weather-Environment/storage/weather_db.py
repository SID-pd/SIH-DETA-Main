"""
SQLite Storage Engine for Weather & Environmental Constraints
Persists station observations and spatial cluster definitions using WAL mode.
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from config import DEFAULT_DB_PATH


class WeatherDatabase:
    """
    Manages SQLite database schema and persistence for weather features.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_db(self):
        """Initializes tables and indexes."""
        with self._get_connection() as conn:
            cur = conn.cursor()

            # 1. Spatial clusters table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS weather_clusters (
                    cluster_id TEXT PRIMARY KEY,
                    grid_lat REAL NOT NULL,
                    grid_lon REAL NOT NULL,
                    centroid_lat REAL NOT NULL,
                    centroid_lon REAL NOT NULL,
                    station_count INTEGER NOT NULL,
                    stations_json TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. Station weather observations table (Live snapshots)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS station_weather_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    station_code TEXT NOT NULL,
                    observation_time TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    visibility_meters REAL NOT NULL,
                    is_foggy INTEGER NOT NULL,
                    fog_speed_cap INTEGER NOT NULL,
                    precipitation_mm REAL NOT NULL,
                    monsoon_active INTEGER NOT NULL,
                    monsoon_speed_cap INTEGER,
                    ambient_temp_c REAL NOT NULL,
                    estimated_rail_temp_c REAL NOT NULL,
                    heat_buckling_warning INTEGER NOT NULL,
                    nominal_mps INTEGER NOT NULL,
                    effective_mps_cap INTEGER NOT NULL,
                    throttle_reason TEXT NOT NULL,
                    data_source TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(station_code, observation_time)
                );
            """)

            # 3. Station Daily Weather Table (Synchronized 1y & 90d slots)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS station_daily_weather (
                    station_code TEXT NOT NULL,
                    observation_date TEXT NOT NULL,
                    horizon_type TEXT NOT NULL,
                    weather_code INTEGER NOT NULL,
                    is_foggy INTEGER NOT NULL,
                    fog_speed_cap INTEGER NOT NULL,
                    precipitation_mm REAL NOT NULL,
                    monsoon_active INTEGER NOT NULL,
                    monsoon_speed_cap INTEGER,
                    temp_max_c REAL NOT NULL,
                    temp_min_c REAL NOT NULL,
                    estimated_rail_temp_c REAL NOT NULL,
                    heat_buckling_warning INTEGER NOT NULL,
                    nominal_mps INTEGER NOT NULL,
                    effective_mps_cap INTEGER NOT NULL,
                    throttle_reason TEXT NOT NULL,
                    data_source TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (station_code, observation_date)
                );
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_weather_station_time
                ON station_weather_observations(station_code, observation_time);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_station_horizon
                ON station_daily_weather(station_code, horizon_type);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_date
                ON station_daily_weather(observation_date);
            """)
            conn.commit()

    def save_clusters(self, clusters: Dict[str, dict]):
        """Persists spatial cluster centroids."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            rows = [
                (
                    c["cluster_id"],
                    c["grid_lat"],
                    c["grid_lon"],
                    c["centroid_lat"],
                    c["centroid_lon"],
                    c["station_count"],
                    json.dumps(c["stations"]),
                )
                for c in clusters.values()
            ]
            cur.executemany("""
                INSERT OR REPLACE INTO weather_clusters
                (cluster_id, grid_lat, grid_lon, centroid_lat, centroid_lon, station_count, stations_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()

    def save_observation(self, obs: dict):
        """Saves a single evaluated weather observation."""
        self.save_observations_batch([obs])

    def save_observations_batch(self, observations: List[dict]):
        """Bulk upserts evaluated weather observations."""
        if not observations:
            return

        with self._get_connection() as conn:
            cur = conn.cursor()
            rows = [
                (
                    o["station_code"],
                    o["observation_time"],
                    o["latitude"],
                    o["longitude"],
                    o["visibility_meters"],
                    o["is_foggy"],
                    o["fog_speed_cap"],
                    o["precipitation_mm"],
                    o["monsoon_active"],
                    o.get("monsoon_speed_cap"),
                    o["ambient_temp_c"],
                    o["estimated_rail_temp_c"],
                    o["heat_buckling_warning"],
                    o["nominal_mps"],
                    o["effective_mps_cap"],
                    o["throttle_reason"],
                    o["data_source"],
                )
                for o in observations
            ]
            cur.executemany("""
                INSERT OR REPLACE INTO station_weather_observations (
                    station_code, observation_time, latitude, longitude,
                    visibility_meters, is_foggy, fog_speed_cap, precipitation_mm,
                    monsoon_active, monsoon_speed_cap, ambient_temp_c, estimated_rail_temp_c,
                    heat_buckling_warning, nominal_mps, effective_mps_cap, throttle_reason, data_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()

    def get_latest_observation(self, station_code: str) -> Optional[dict]:
        """Fetches the latest observation for a specific station."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM station_weather_observations
                WHERE station_code = ?
                ORDER BY observation_time DESC
                LIMIT 1
            """, (station_code.strip().upper(),))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_corridor_observations(self, station_codes: List[str]) -> List[dict]:
        """Fetches latest observations for an ordered sequence of stations along a route."""
        if not station_codes:
            return []

        results = []
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            for code in station_codes:
                cur.execute("""
                    SELECT * FROM station_weather_observations
                    WHERE station_code = ?
                    ORDER BY observation_time DESC
                    LIMIT 1
                """, (code.strip().upper(),))
                row = cur.fetchone()
                if row:
                    results.append(dict(row))
        return results

    def save_daily_weather_batch(self, daily_records: List[dict]):
        """Bulk upserts daily historical weather records."""
        if not daily_records:
            return

        with self._get_connection() as conn:
            cur = conn.cursor()
            rows = [
                (
                    r["station_code"],
                    r["observation_date"],
                    r["horizon_type"],
                    r["weather_code"],
                    r["is_foggy"],
                    r["fog_speed_cap"],
                    r["precipitation_mm"],
                    r["monsoon_active"],
                    r.get("monsoon_speed_cap"),
                    r["temp_max_c"],
                    r["temp_min_c"],
                    r["estimated_rail_temp_c"],
                    r["heat_buckling_warning"],
                    r["nominal_mps"],
                    r["effective_mps_cap"],
                    r["throttle_reason"],
                    r["data_source"],
                )
                for r in daily_records
            ]
            cur.executemany("""
                INSERT OR REPLACE INTO station_daily_weather (
                    station_code, observation_date, horizon_type, weather_code,
                    is_foggy, fog_speed_cap, precipitation_mm, monsoon_active,
                    monsoon_speed_cap, temp_max_c, temp_min_c, estimated_rail_temp_c,
                    heat_buckling_warning, nominal_mps, effective_mps_cap, throttle_reason, data_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()

    def get_total_daily_records_count(self) -> int:
        """Returns total count of historical daily weather records."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM station_daily_weather;")
            return cur.fetchone()[0]

    def get_total_observations_count(self) -> int:
        """Returns total count of recorded weather observations."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM station_weather_observations;")
            return cur.fetchone()[0]
