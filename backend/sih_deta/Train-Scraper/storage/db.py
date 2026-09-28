"""
SQLite database management for Indian Railways train records and timetables.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import DEFAULT_DB_PATH


class Database:
    """Manages SQLite storage for trains and detailed stop timetables."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Create tables and indexes if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Trains master table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trains (
                    number TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT,
                    zone TEXT,
                    route TEXT,
                    from_station_code TEXT,
                    from_station_name TEXT,
                    to_station_code TEXT,
                    to_station_name TEXT,
                    departure TEXT,
                    arrival TEXT,
                    travel_time TEXT,
                    distance TEXT,
                    service_days TEXT,
                    total_stops INTEGER DEFAULT 0,
                    classes TEXT,
                    pantry TEXT,
                    source TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Train stops / timetable table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS train_stops (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    train_number TEXT NOT NULL,
                    sno INTEGER NOT NULL,
                    station_code TEXT,
                    station_name TEXT,
                    arrival TEXT,
                    departure TEXT,
                    halt TEXT,
                    distance TEXT,
                    avg_delay TEXT,
                    day TEXT,
                    FOREIGN KEY (train_number) REFERENCES trains(number) ON DELETE CASCADE,
                    UNIQUE(train_number, sno)
                );
            """)

            # Indexes for fast search and joins
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trains_name ON trains(name);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trains_from ON trains(from_station_code);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trains_to ON trains(to_station_code);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stops_train ON train_stops(train_number);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stops_station ON train_stops(station_code);")

            conn.commit()

    def upsert_train(self, train: Dict[str, Any]):
        """Insert or update a single train record."""
        self.upsert_trains([train])

    def upsert_trains(self, trains: List[Dict[str, Any]]) -> int:
        """Batch insert or update train records."""
        if not trains:
            return 0

        now = datetime.utcnow().isoformat()
        records = []
        for t in trains:
            records.append((
                str(t.get("number", "")).strip(),
                str(t.get("name", "")).strip(),
                t.get("type", ""),
                t.get("zone", ""),
                t.get("route", ""),
                t.get("from_station_code", ""),
                t.get("from_station_name", ""),
                t.get("to_station_code", ""),
                t.get("to_station_name", ""),
                t.get("departure", ""),
                t.get("arrival", ""),
                t.get("travel_time", ""),
                str(t.get("distance", "")),
                t.get("service_days", ""),
                t.get("total_stops", 0),
                t.get("classes", ""),
                t.get("pantry", ""),
                t.get("source", ""),
                now
            ))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO trains (
                    number, name, type, zone, route, from_station_code, from_station_name,
                    to_station_code, to_station_name, departure, arrival, travel_time,
                    distance, service_days, total_stops, classes, pantry, source, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(number) DO UPDATE SET
                    name = coalesce(nullif(excluded.name, ''), trains.name),
                    type = coalesce(nullif(excluded.type, ''), trains.type),
                    zone = coalesce(nullif(excluded.zone, ''), trains.zone),
                    route = coalesce(nullif(excluded.route, ''), trains.route),
                    from_station_code = coalesce(nullif(excluded.from_station_code, ''), trains.from_station_code),
                    from_station_name = coalesce(nullif(excluded.from_station_name, ''), trains.from_station_name),
                    to_station_code = coalesce(nullif(excluded.to_station_code, ''), trains.to_station_code),
                    to_station_name = coalesce(nullif(excluded.to_station_name, ''), trains.to_station_name),
                    departure = coalesce(nullif(excluded.departure, ''), trains.departure),
                    arrival = coalesce(nullif(excluded.arrival, ''), trains.arrival),
                    travel_time = coalesce(nullif(excluded.travel_time, ''), trains.travel_time),
                    distance = coalesce(nullif(excluded.distance, ''), trains.distance),
                    service_days = coalesce(nullif(excluded.service_days, ''), trains.service_days),
                    total_stops = max(excluded.total_stops, trains.total_stops),
                    classes = coalesce(nullif(excluded.classes, ''), trains.classes),
                    pantry = coalesce(nullif(excluded.pantry, ''), trains.pantry),
                    source = coalesce(nullif(excluded.source, ''), trains.source),
                    updated_at = excluded.updated_at;
            """, records)
            conn.commit()
            return len(records)

    def save_schedule(self, schedule: Dict[str, Any]):
        """Save a complete train schedule including stops."""
        train_num = str(schedule.get("number", "")).strip()
        if not train_num:
            return

        # Upsert train header
        self.upsert_train(schedule)

        stops = schedule.get("stops", [])
        if not stops:
            return

        stop_records = []
        for s in stops:
            stop_records.append((
                train_num,
                s.get("sno", 0),
                s.get("station_code", ""),
                s.get("station_name", ""),
                s.get("arrival", ""),
                s.get("departure", ""),
                s.get("halt", ""),
                s.get("distance", ""),
                s.get("avg_delay", ""),
                str(s.get("day", "1"))
            ))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Replace existing stops for this train
            cursor.execute("DELETE FROM train_stops WHERE train_number = ?;", (train_num,))
            cursor.executemany("""
                INSERT INTO train_stops (
                    train_number, sno, station_code, station_name, arrival,
                    departure, halt, distance, avg_delay, day
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, stop_records)
            conn.commit()

    def get_train(self, train_number: str) -> Optional[Dict[str, Any]]:
        """Retrieve a train by number with its stops."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trains WHERE number = ?;", (train_number,))
            row = cursor.fetchone()
            if not row:
                return None

            train_dict = dict(row)
            cursor.execute("SELECT * FROM train_stops WHERE train_number = ? ORDER BY sno ASC;", (train_number,))
            stops = [dict(r) for r in cursor.fetchall()]
            train_dict["stops"] = stops
            return train_dict

    def get_all_trains(self) -> List[Dict[str, Any]]:
        """Get all train records without stops."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trains ORDER BY number ASC;")
            return [dict(r) for r in cursor.fetchall()]

    def search_trains(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search trains by number, name, or station code."""
        pattern = f"%{query}%"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM trains
                WHERE number LIKE ? OR name LIKE ? OR from_station_code LIKE ? OR to_station_code LIKE ?
                ORDER BY number ASC
                LIMIT ?;
            """, (pattern, pattern, pattern, pattern, limit))
            return [dict(r) for r in cursor.fetchall()]

    def count_trains(self) -> int:
        """Return total count of trains in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trains;")
            return cursor.fetchone()[0]

    def count_stops(self) -> int:
        """Return total count of stops in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM train_stops;")
            return cursor.fetchone()[0]
