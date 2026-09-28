"""
SQLite Database module for Indian Railways stations, halt networks, and topology.
Supports production-grade schemas with NSG/SG/HG categories, physical infrastructure,
operational status, multi-attribute classification, and nationwide halt tracking.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from config import DEFAULT_DB_PATH

logger = logging.getLogger("station_scraper")


class StationDatabase:
    """Manages SQLite storage for station master data and train halts."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Create database tables and performance indices if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check if stations table exists and check its columns
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stations';")
            table_exists = cursor.fetchone()

            if table_exists:
                cursor.execute("PRAGMA table_info(stations);")
                cols = {row["name"] for row in cursor.fetchall()}
                if "division" not in cols:
                    # Drop obsolete schema to rebuild with production columns
                    cursor.execute("DROP TABLE IF EXISTS stations;")

            # 1. Stations Master Table (Production Grade Schema)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stations (
                    code TEXT PRIMARY KEY,
                    official_name TEXT NOT NULL,
                    hindi_name TEXT,
                    alternate_names TEXT,
                    state TEXT,
                    zone TEXT,
                    division TEXT,
                    district TEXT,
                    city TEXT,
                    latitude REAL,
                    longitude REAL,
                    elevation_meters REAL,
                    ir_category TEXT,
                    is_junction INTEGER DEFAULT 0,
                    is_terminal INTEGER DEFAULT 0,
                    is_halt INTEGER DEFAULT 0,
                    is_virtual_chord INTEGER DEFAULT 0,
                    platform_count INTEGER DEFAULT 2,
                    track_count INTEGER DEFAULT 2,
                    gauge TEXT DEFAULT 'Broad (1676mm)',
                    electrification_status TEXT DEFAULT '25kV AC Electrified',
                    operational_status TEXT DEFAULT 'Active Passenger Station',
                    passenger_service INTEGER DEFAULT 1,
                    amrit_bharat_station INTEGER DEFAULT 0,
                    total_halts_count INTEGER DEFAULT 0,
                    address TEXT,
                    data_source TEXT DEFAULT 'CRIS / Datameet / ConfirmTkt',
                    last_verified DATE,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. Station Halts Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS station_halts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    station_code TEXT NOT NULL,
                    train_number TEXT NOT NULL,
                    train_name TEXT,
                    arrival_time TEXT,
                    departure_time TEXT,
                    halt_minutes INTEGER DEFAULT 0,
                    day INTEGER DEFAULT 1,
                    days_of_run TEXT,
                    classes TEXT,
                    platform TEXT,
                    distance_km REAL,
                    source TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (station_code) REFERENCES stations(code) ON DELETE CASCADE,
                    UNIQUE(station_code, train_number, arrival_time, departure_time) ON CONFLICT REPLACE
                );
            """)

            # Performance Indices
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stations_zone ON stations(zone);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stations_division ON stations(division);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stations_state ON stations(state);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stations_ir_category ON stations(ir_category);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stations_is_junction ON stations(is_junction);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stations_is_terminal ON stations(is_terminal);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stations_is_halt ON stations(is_halt);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stations_op_status ON stations(operational_status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stations_passenger ON stations(passenger_service);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_halts_station ON station_halts(station_code);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_halts_train ON station_halts(train_number);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_halts_halt_mins ON station_halts(halt_minutes);")

            conn.commit()
            logger.info(f"Initialized Station database schema at {self.db_path}")

    def upsert_stations(self, stations: List[Dict[str, Any]]) -> int:
        """Insert or replace multiple production-grade station records."""
        if not stations:
            return 0

        query = """
            INSERT INTO stations (
                code, official_name, hindi_name, alternate_names,
                state, zone, division, district, city,
                latitude, longitude, elevation_meters, ir_category,
                is_junction, is_terminal, is_halt, is_virtual_chord,
                platform_count, track_count, gauge, electrification_status,
                operational_status, passenger_service, amrit_bharat_station,
                total_halts_count, address, data_source, last_verified, updated_at
            ) VALUES (
                :code, :official_name, :hindi_name, :alternate_names,
                :state, :zone, :division, :district, :city,
                :latitude, :longitude, :elevation_meters, :ir_category,
                :is_junction, :is_terminal, :is_halt, :is_virtual_chord,
                :platform_count, :track_count, :gauge, :electrification_status,
                :operational_status, :passenger_service, :amrit_bharat_station,
                :total_halts_count, :address, :data_source, :last_verified, CURRENT_TIMESTAMP
            )
            ON CONFLICT(code) DO UPDATE SET
                official_name = excluded.official_name,
                hindi_name = COALESCE(excluded.hindi_name, stations.hindi_name),
                alternate_names = COALESCE(excluded.alternate_names, stations.alternate_names),
                state = CASE WHEN excluded.state IS NOT NULL AND excluded.state != '' AND excluded.state != 'None' THEN excluded.state ELSE stations.state END,
                zone = CASE WHEN excluded.zone IS NOT NULL AND excluded.zone != '' AND excluded.zone != 'NONE' THEN excluded.zone ELSE stations.zone END,
                division = CASE WHEN excluded.division IS NOT NULL AND excluded.division != '' THEN excluded.division ELSE stations.division END,
                district = CASE WHEN excluded.district IS NOT NULL AND excluded.district != '' THEN excluded.district ELSE stations.district END,
                city = CASE WHEN excluded.city IS NOT NULL AND excluded.city != '' THEN excluded.city ELSE stations.city END,
                latitude = COALESCE(excluded.latitude, stations.latitude),
                longitude = COALESCE(excluded.longitude, stations.longitude),
                elevation_meters = COALESCE(excluded.elevation_meters, stations.elevation_meters),
                ir_category = excluded.ir_category,
                is_junction = excluded.is_junction,
                is_terminal = excluded.is_terminal,
                is_halt = excluded.is_halt,
                is_virtual_chord = excluded.is_virtual_chord,
                platform_count = excluded.platform_count,
                track_count = excluded.track_count,
                gauge = excluded.gauge,
                electrification_status = excluded.electrification_status,
                operational_status = excluded.operational_status,
                passenger_service = excluded.passenger_service,
                amrit_bharat_station = excluded.amrit_bharat_station,
                address = CASE WHEN excluded.address IS NOT NULL AND excluded.address != '' AND excluded.address != 'None' THEN excluded.address ELSE stations.address END,
                data_source = excluded.data_source,
                last_verified = excluded.last_verified,
                updated_at = CURRENT_TIMESTAMP;
        """

        # Normalize field dictionaries
        clean_stations = []
        for s in stations:
            item = dict(s)
            item.setdefault("official_name", item.get("name", ""))
            item.setdefault("hindi_name", None)
            item.setdefault("alternate_names", None)
            item.setdefault("state", None)
            item.setdefault("zone", None)
            item.setdefault("division", None)
            item.setdefault("district", None)
            item.setdefault("city", None)
            item.setdefault("latitude", None)
            item.setdefault("longitude", None)
            item.setdefault("elevation_meters", None)
            item.setdefault("ir_category", "Regular Station")
            item.setdefault("is_junction", 0)
            item.setdefault("is_terminal", 0)
            item.setdefault("is_halt", 0)
            item.setdefault("is_virtual_chord", 0)
            item.setdefault("platform_count", 2)
            item.setdefault("track_count", 2)
            item.setdefault("gauge", "Broad (1676mm)")
            item.setdefault("electrification_status", "25kV AC Electrified")
            item.setdefault("operational_status", "Active Passenger Station")
            item.setdefault("passenger_service", 1)
            item.setdefault("amrit_bharat_station", 0)
            item.setdefault("total_halts_count", 0)
            item.setdefault("address", None)
            item.setdefault("data_source", "CRIS / Datameet / ConfirmTkt")
            item.setdefault("last_verified", "2026-09-08")
            clean_stations.append(item)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, clean_stations)
            conn.commit()
            logger.info(f"Upserted {len(clean_stations)} stations into database.")
            return cursor.rowcount

    def upsert_halts(self, halts: List[Dict[str, Any]], update_counts: bool = True) -> int:
        """Insert or update train halts for stations."""
        if not halts:
            return 0

        query = """
            INSERT INTO station_halts (
                station_code, train_number, train_name,
                arrival_time, departure_time, halt_minutes,
                day, days_of_run, classes, platform, distance_km,
                source, updated_at
            ) VALUES (
                :station_code, :train_number, :train_name,
                :arrival_time, :departure_time, :halt_minutes,
                :day, :days_of_run, :classes, :platform, :distance_km,
                :source, CURRENT_TIMESTAMP
            )
            ON CONFLICT(station_code, train_number, arrival_time, departure_time) DO UPDATE SET
                train_name = excluded.train_name,
                halt_minutes = excluded.halt_minutes,
                day = excluded.day,
                days_of_run = CASE WHEN excluded.days_of_run != '' THEN excluded.days_of_run ELSE station_halts.days_of_run END,
                classes = CASE WHEN excluded.classes != '' THEN excluded.classes ELSE station_halts.classes END,
                platform = COALESCE(excluded.platform, station_halts.platform),
                distance_km = COALESCE(excluded.distance_km, station_halts.distance_km),
                source = excluded.source,
                updated_at = CURRENT_TIMESTAMP;
        """

        clean_halts = []
        for h in halts:
            item = dict(h)
            item.setdefault("platform", None)
            item.setdefault("distance_km", None)
            item.setdefault("days_of_run", "")
            item.setdefault("classes", "")
            item.setdefault("source", "manual")
            item.setdefault("day", 1)
            item.setdefault("halt_minutes", 0)
            clean_halts.append(item)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, clean_halts)
            conn.commit()

            if update_counts:
                # Update total_halts_count for affected stations
                unique_stns = list(set(h["station_code"] for h in clean_halts))
                cursor.execute(f"""
                    UPDATE stations
                    SET total_halts_count = (
                        SELECT COUNT(*) FROM station_halts WHERE station_halts.station_code = stations.code
                    )
                    WHERE code IN ({','.join('?' for _ in unique_stns)});
                """, unique_stns)
                conn.commit()

            logger.info(f"Upserted {len(clean_halts)} station halts into database.")
            return cursor.rowcount

    def update_all_station_halt_counts(self):
        """Recalculate total_halts_count across all stations from station_halts."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE stations
                SET total_halts_count = (
                    SELECT COUNT(*) FROM station_halts WHERE station_halts.station_code = stations.code
                );
            """)
            conn.commit()
            logger.info("Updated total_halts_count for all stations in database.")

    def get_station(self, code: str) -> Optional[Dict[str, Any]]:
        """Retrieve single station by code."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stations WHERE code = ? COLLATE NOCASE", (code.strip(),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def search_stations(self, query_text: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Search stations by code, official name, division, city, district, or state."""
        q = f"%{query_text.strip()}%"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM stations
                WHERE code LIKE ? OR official_name LIKE ? OR state LIKE ?
                   OR division LIKE ? OR district LIKE ? OR city LIKE ? OR address LIKE ?
                ORDER BY
                    CASE WHEN code = ? THEN 1
                         WHEN code LIKE ? THEN 2
                         WHEN official_name LIKE ? THEN 3
                         ELSE 4 END,
                    is_terminal DESC,
                    is_junction DESC,
                    total_halts_count DESC,
                    code ASC
                LIMIT ?
            """, (q, q, q, q, q, q, q, query_text.strip().upper(), f"{query_text.strip().upper()}%", f"{query_text.strip()}%", limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_station_halts(self, station_code: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all train halts for a station."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM station_halts
                WHERE station_code = ? COLLATE NOCASE
                ORDER BY arrival_time ASC, departure_time ASC
                LIMIT ?
            """, (station_code.strip(), limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_train_halts(self, train_number: str) -> List[Dict[str, Any]]:
        """Get all station halts along a train's journey."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sh.*, s.official_name as station_full_name, s.state, s.zone, s.division, s.platform_count
                FROM station_halts sh
                LEFT JOIN stations s ON sh.station_code = s.code
                WHERE sh.train_number = ?
                ORDER BY sh.day ASC, sh.arrival_time ASC
            """, (train_number.strip(),))
            return [dict(row) for row in cursor.fetchall()]

    def get_junctions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get railway junctions across India."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM stations
                WHERE is_junction = 1
                ORDER BY is_terminal DESC, total_halts_count DESC, code ASC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_all_stations(self) -> List[Dict[str, Any]]:
        """Get all stations from database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stations ORDER BY code ASC")
            return [dict(row) for row in cursor.fetchall()]

    def get_all_halts(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all halts from database."""
        query = "SELECT * FROM station_halts ORDER BY station_code ASC, train_number ASC"
        if limit:
            query += f" LIMIT {int(limit)}"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]

    def get_summary_stats(self) -> Dict[str, Any]:
        """Aggregate statistical summary of stations and halts."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM stations")
            total_stations = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM stations WHERE passenger_service = 1")
            passenger_stations = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM stations WHERE is_virtual_chord = 1 OR passenger_service = 0")
            freight_chord_stations = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM stations WHERE is_junction = 1")
            total_junctions = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM stations WHERE is_terminal = 1")
            total_terminals = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM stations WHERE is_halt = 1")
            total_halts_stations = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM stations WHERE amrit_bharat_station = 1")
            amrit_bharat_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM stations WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
            geocoded_stations = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM station_halts")
            total_train_halts = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT train_number) FROM station_halts")
            trains_with_halts = cursor.fetchone()[0]

            # IR Category breakdown
            cursor.execute("""
                SELECT ir_category, COUNT(*) as count FROM stations
                WHERE ir_category IS NOT NULL AND ir_category != ''
                GROUP BY ir_category ORDER BY count DESC
            """)
            category_distribution = [dict(row) for row in cursor.fetchall()]

            # Top zones
            cursor.execute("""
                SELECT zone, COUNT(*) as count FROM stations
                WHERE zone IS NOT NULL AND zone != '' AND zone != 'NONE'
                GROUP BY zone ORDER BY count DESC LIMIT 10
            """)
            zone_distribution = [dict(row) for row in cursor.fetchall()]

            # Top divisions
            cursor.execute("""
                SELECT division, COUNT(*) as count FROM stations
                WHERE division IS NOT NULL AND division != ''
                GROUP BY division ORDER BY count DESC LIMIT 10
            """)
            division_distribution = [dict(row) for row in cursor.fetchall()]

            # Top states
            cursor.execute("""
                SELECT state, COUNT(*) as count FROM stations
                WHERE state IS NOT NULL AND state != '' AND state != 'None'
                GROUP BY state ORDER BY count DESC LIMIT 10
            """)
            state_distribution = [dict(row) for row in cursor.fetchall()]

            # Stations with most halts
            cursor.execute("""
                SELECT s.code, s.official_name, s.ir_category, s.platform_count, COUNT(sh.id) as halt_count
                FROM stations s
                JOIN station_halts sh ON s.code = sh.station_code
                GROUP BY s.code, s.official_name, s.ir_category, s.platform_count
                ORDER BY halt_count DESC LIMIT 10
            """)
            busiest_stations = [dict(row) for row in cursor.fetchall()]

            return {
                "total_stations": total_stations,
                "passenger_stations": passenger_stations,
                "freight_chord_stations": freight_chord_stations,
                "total_junctions": total_junctions,
                "total_terminals": total_terminals,
                "total_halt_stations": total_halts_stations,
                "amrit_bharat_count": amrit_bharat_count,
                "geocoded_stations": geocoded_stations,
                "total_train_halts": total_train_halts,
                "trains_with_halts": trains_with_halts,
                "category_distribution": category_distribution,
                "zone_distribution": zone_distribution,
                "division_distribution": division_distribution,
                "state_distribution": state_distribution,
                "busiest_stations": busiest_stations,
            }
