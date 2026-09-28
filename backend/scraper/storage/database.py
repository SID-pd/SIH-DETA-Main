"""
Database layer for scraper-erail.
Manages connections and batch upserts into the SQLite database.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from config.settings import DEFAULT_DARPAN_DB_PATH, SCRAPER_DIR

logger = logging.getLogger("scraper_erail.storage")

SCHEMA_FILE = SCRAPER_DIR / "storage" / "schema.sql"


class Database:
    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.is_memory = str(db_path) == ":memory:"
        self.db_path = Path(db_path) if db_path and not self.is_memory else (Path(":memory:") if self.is_memory else DEFAULT_DARPAN_DB_PATH)
        if not self.is_memory:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._mem_conn: Optional[sqlite3.Connection] = None
        if self.is_memory:
            self._mem_conn = sqlite3.connect(":memory:")
            self._mem_conn.row_factory = sqlite3.Row
        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        if self.is_memory and self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        """Applies schema.sql to the target database and safely migrates missing columns."""
        if not SCHEMA_FILE.exists():
            logger.warning(f"Schema file {SCHEMA_FILE} not found; skipping init.")
            return

        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            sql = f.read()

        with self.get_connection() as conn:
            conn.executescript(sql)
            self._migrate_existing_tables(conn)
            conn.commit()
        logger.info(f"Initialized and migrated database schema at {self.db_path}")

    def _migrate_existing_tables(self, conn: sqlite3.Connection) -> None:
        """Safely adds missing columns to pre-existing DARPAN tables without data loss."""
        def get_existing_cols(tbl: str) -> set[str]:
            cur = conn.execute(f"PRAGMA table_info({tbl});")
            return {row[1] for row in cur.fetchall()}

        # 1. trains
        train_cols = get_existing_cols("trains")
        if train_cols:
            missing_trains = {
                "running_days": "TEXT",
                "rake_type": "TEXT",
                "total_coaches": "INTEGER",
                "pantry_status": "TEXT",
                "source": "TEXT DEFAULT 'erail'",
                "updated_at": "TEXT",
            }
            for col, col_type in missing_trains.items():
                if col not in train_cols:
                    try:
                        conn.execute(f"ALTER TABLE trains ADD COLUMN {col} {col_type};")
                    except Exception:
                        pass

        # 2. stations
        stn_cols = get_existing_cols("stations")
        if stn_cols and "updated_at" not in stn_cols:
            try:
                conn.execute("ALTER TABLE stations ADD COLUMN updated_at TEXT;")
            except Exception:
                pass

        # 3. schedule_stops
        stop_cols = get_existing_cols("schedule_stops")
        if stop_cols:
            missing_stops = {
                "distance_km": "REAL DEFAULT 0.0",
                "halt_mins": "INTEGER DEFAULT 0",
                "platform": "TEXT",
                "speed_kmph": "REAL",
                "is_commercial_halt": "INTEGER DEFAULT 1",
                "source": "TEXT DEFAULT 'erail'",
                "updated_at": "TEXT",
            }
            for col, col_type in missing_stops.items():
                if col not in stop_cols:
                    try:
                        conn.execute(f"ALTER TABLE schedule_stops ADD COLUMN {col} {col_type};")
                    except Exception:
                        pass

    def upsert_stations(self, stations: List[Dict[str, Any]]) -> int:
        if not stations:
            return 0
        keys = ["code", "name", "state", "zone", "address", "lat", "lon", "updated_at"]
        sanitized = [{k: s.get(k, None) for k in keys} for s in stations]
        sql = """
        INSERT INTO stations (code, name, state, zone, address, lat, lon, updated_at)
        VALUES (:code, :name, :state, :zone, :address, :lat, :lon, :updated_at)
        ON CONFLICT(code) DO UPDATE SET
            name=COALESCE(excluded.name, stations.name),
            state=COALESCE(excluded.state, stations.state),
            zone=COALESCE(excluded.zone, stations.zone),
            lat=COALESCE(excluded.lat, stations.lat),
            lon=COALESCE(excluded.lon, stations.lon),
            updated_at=excluded.updated_at;
        """
        with self.get_connection() as conn:
            conn.executemany(sql, sanitized)
            conn.commit()
        return len(sanitized)

    def upsert_trains(self, trains: List[Dict[str, Any]]) -> int:
        if not trains:
            return 0
        keys = [
            "number", "name", "type", "from_code", "from_name", "to_code", "to_name",
            "departure", "arrival", "duration_min", "distance_km", "zone", "classes",
            "running_days", "rake_type", "total_coaches", "pantry_status", "return_train",
            "source", "updated_at"
        ]
        sanitized = [{k: t.get(k, None) for k in keys} for t in trains]
        sql = """
        INSERT INTO trains (
            number, name, type, from_code, from_name, to_code, to_name,
            departure, arrival, duration_min, distance_km, zone, classes,
            running_days, rake_type, total_coaches, pantry_status, return_train,
            source, updated_at
        )
        VALUES (
            :number, :name, :type, :from_code, :from_name, :to_code, :to_name,
            :departure, :arrival, :duration_min, :distance_km, :zone, :classes,
            :running_days, :rake_type, :total_coaches, :pantry_status, :return_train,
            :source, :updated_at
        )
        ON CONFLICT(number) DO UPDATE SET
            name=COALESCE(excluded.name, trains.name),
            type=COALESCE(excluded.type, trains.type),
            from_code=COALESCE(excluded.from_code, trains.from_code),
            from_name=COALESCE(excluded.from_name, trains.from_name),
            to_code=COALESCE(excluded.to_code, trains.to_code),
            to_name=COALESCE(excluded.to_name, trains.to_name),
            departure=COALESCE(excluded.departure, trains.departure),
            arrival=COALESCE(excluded.arrival, trains.arrival),
            duration_min=COALESCE(excluded.duration_min, trains.duration_min),
            distance_km=COALESCE(excluded.distance_km, trains.distance_km),
            zone=COALESCE(excluded.zone, trains.zone),
            classes=COALESCE(excluded.classes, trains.classes),
            running_days=COALESCE(excluded.running_days, trains.running_days),
            rake_type=COALESCE(excluded.rake_type, trains.rake_type),
            total_coaches=COALESCE(excluded.total_coaches, trains.total_coaches),
            pantry_status=COALESCE(excluded.pantry_status, trains.pantry_status),
            return_train=COALESCE(excluded.return_train, trains.return_train),
            source=COALESCE(excluded.source, trains.source),
            updated_at=excluded.updated_at;
        """
        with self.get_connection() as conn:
            conn.executemany(sql, sanitized)
            conn.commit()
        return len(sanitized)

    def upsert_schedule_stops(self, stops: List[Dict[str, Any]]) -> int:
        if not stops:
            return 0
        keys = [
            "train_number", "seq", "station_code", "station_name", "day", "arrival",
            "departure", "halt_mins", "distance_km", "platform", "speed_kmph",
            "is_commercial_halt", "source", "updated_at"
        ]
        sanitized = [{k: s.get(k, None) for k in keys} for s in stops]
        sql = """
        INSERT INTO schedule_stops (
            train_number, seq, station_code, station_name, day, arrival,
            departure, halt_mins, distance_km, platform, speed_kmph,
            is_commercial_halt, source, updated_at
        )
        VALUES (
            :train_number, :seq, :station_code, :station_name, :day, :arrival,
            :departure, :halt_mins, :distance_km, :platform, :speed_kmph,
            :is_commercial_halt, :source, :updated_at
        )
        ON CONFLICT(train_number, seq) DO UPDATE SET
            station_code=excluded.station_code,
            station_name=COALESCE(excluded.station_name, schedule_stops.station_name),
            day=excluded.day,
            arrival=excluded.arrival,
            departure=excluded.departure,
            halt_mins=excluded.halt_mins,
            distance_km=excluded.distance_km,
            platform=COALESCE(excluded.platform, schedule_stops.platform),
            speed_kmph=COALESCE(excluded.speed_kmph, schedule_stops.speed_kmph),
            is_commercial_halt=excluded.is_commercial_halt,
            source=COALESCE(excluded.source, schedule_stops.source),
            updated_at=excluded.updated_at;
        """
        with self.get_connection() as conn:
            conn.executemany(sql, sanitized)
            conn.commit()
        return len(sanitized)

    def upsert_coach_compositions(self, coaches: List[Dict[str, Any]]) -> int:
        if not coaches:
            return 0
        sql = """
        INSERT INTO coach_compositions (train_number, position, coach_code, coach_type, class_type, rake_type, updated_at)
        VALUES (:train_number, :position, :coach_code, :coach_type, :class_type, :rake_type, :updated_at)
        ON CONFLICT(train_number, position) DO UPDATE SET
            coach_code=excluded.coach_code,
            coach_type=excluded.coach_type,
            class_type=excluded.class_type,
            rake_type=excluded.rake_type,
            updated_at=excluded.updated_at;
        """
        with self.get_connection() as conn:
            conn.executemany(sql, coaches)
            conn.commit()
        return len(coaches)

    def upsert_historical_delays(self, delays: List[Dict[str, Any]]) -> int:
        if not delays:
            return 0
        sql = """
        INSERT INTO historical_station_delays (
            train_number, station_code, avg_delay_mins, pct_on_time,
            pct_slight_delay, pct_moderate_delay, pct_severe_delay,
            sample_days, source, scraped_at
        )
        VALUES (
            :train_number, :station_code, :avg_delay_mins, :pct_on_time,
            :pct_slight_delay, :pct_moderate_delay, :pct_severe_delay,
            :sample_days, :source, :scraped_at
        )
        ON CONFLICT(train_number, station_code) DO UPDATE SET
            avg_delay_mins=excluded.avg_delay_mins,
            pct_on_time=excluded.pct_on_time,
            pct_slight_delay=excluded.pct_slight_delay,
            pct_moderate_delay=excluded.pct_moderate_delay,
            pct_severe_delay=excluded.pct_severe_delay,
            sample_days=excluded.sample_days,
            source=excluded.source,
            scraped_at=excluded.scraped_at;
        """
        with self.get_connection() as conn:
            conn.executemany(sql, delays)
            conn.commit()
        return len(delays)

    def insert_live_observations(self, observations: List[Dict[str, Any]]) -> int:
        if not observations:
            return 0
        sql = """
        INSERT OR IGNORE INTO live_observations (
            train_number, journey_date, station_code, observed_at,
            sched_arrival, actual_arrival, arrival_delay_mins,
            sched_departure, actual_departure, departure_delay_mins,
            platform, status, current_location, source
        )
        VALUES (
            :train_number, :journey_date, :station_code, :observed_at,
            :sched_arrival, :actual_arrival, :arrival_delay_mins,
            :sched_departure, :actual_departure, :departure_delay_mins,
            :platform, :status, :current_location, :source
        );
        """
        with self.get_connection() as conn:
            conn.executemany(sql, observations)
            conn.commit()
        return len(observations)

    def insert_train_exceptions(self, exceptions: List[Dict[str, Any]]) -> int:
        if not exceptions:
            return 0
        sql = """
        INSERT INTO train_exceptions (
            train_number, journey_date, exception_type, original_departure,
            rescheduled_departure, delay_at_origin_mins, diverted_via,
            reason, source, recorded_at
        )
        VALUES (
            :train_number, :journey_date, :exception_type, :original_departure,
            :rescheduled_departure, :delay_at_origin_mins, :diverted_via,
            :reason, :source, :recorded_at
        );
        """
        with self.get_connection() as conn:
            conn.executemany(sql, exceptions)
            conn.commit()
        return len(exceptions)
