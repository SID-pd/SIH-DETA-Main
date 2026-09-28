"""
SQLite Persistence Engine for Network Anomalies & Disruptions
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from config import DEFAULT_DB_PATH
from models.incident_types import NetworkIncident


class AnomalyDatabase:
    """
    Manages SQLite storage for operational incidents and network disruptions.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        """Creates incident tables and indices."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS network_incidents (
                    incident_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    train_number TEXT NOT NULL,
                    section_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    detention_minutes REAL NOT NULL,
                    speed_restriction_kmh INTEGER,
                    description TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    severity TEXT NOT NULL DEFAULT 'MEDIUM',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. Junction outer queue profiles table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS junction_queue_profiles (
                    junction_code TEXT NOT NULL,
                    hour_ist INTEGER NOT NULL,
                    priority_tier INTEGER NOT NULL,
                    expected_wait_minutes REAL NOT NULL,
                    congestion_status TEXT NOT NULL,
                    platforms INTEGER NOT NULL,
                    PRIMARY KEY (junction_code, hour_ist, priority_tier)
                );
            """)

            cur.execute("CREATE INDEX IF NOT EXISTS idx_incident_section ON network_incidents(section_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_incident_train ON network_incidents(train_number);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_incident_active ON network_incidents(is_active);")
            conn.commit()

    def save_incident(self, incident):
        """Saves a single incident."""
        self.save_incidents_batch([incident])

    def save_incidents_batch(self, incidents: list):
        """Bulk upserts incidents (supports both dataclass objects and dicts)."""
        if not incidents:
            return

        with self._get_connection() as conn:
            cur = conn.cursor()
            rows = []
            for inc in incidents:
                if isinstance(inc, dict):
                    rows.append((
                        inc["incident_id"],
                        inc["timestamp"],
                        str(inc["train_number"]),
                        inc["section_id"],
                        inc["category"],
                        float(inc["detention_minutes"]),
                        inc.get("speed_restriction_kmh"),
                        inc.get("description", ""),
                        1 if inc.get("is_active", True) else 0,
                        inc.get("severity", "MEDIUM"),
                    ))
                else:
                    rows.append((
                        inc.incident_id,
                        inc.timestamp,
                        str(inc.train_number),
                        inc.section_id,
                        inc.category,
                        float(inc.detention_minutes),
                        inc.speed_restriction_kmh,
                        inc.description,
                        1 if inc.is_active else 0,
                        inc.severity,
                    ))

            cur.executemany("""
                INSERT OR REPLACE INTO network_incidents
                (incident_id, timestamp, train_number, section_id, category,
                 detention_minutes, speed_restriction_kmh, description, is_active, severity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()

    def save_queue_profiles_batch(self, profiles: List[dict]):
        """Bulk upserts junction queue profiles."""
        if not profiles:
            return

        with self._get_connection() as conn:
            cur = conn.cursor()
            rows = [
                (
                    p["junction_code"],
                    p["hour_ist"],
                    p["priority_tier"],
                    p["expected_wait_minutes"],
                    p["congestion_status"],
                    p["platforms"],
                )
                for p in profiles
            ]
            cur.executemany("""
                INSERT OR REPLACE INTO junction_queue_profiles
                (junction_code, hour_ist, priority_tier, expected_wait_minutes, congestion_status, platforms)
                VALUES (?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()

    def get_active_incidents(
        self,
        train_number: Optional[str] = None,
        section_id: Optional[str] = None,
    ) -> List[dict]:
        """Queries currently active disruptions, optionally filtered by train or section."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            query = "SELECT * FROM network_incidents WHERE is_active = 1"
            params = []

            if train_number:
                query += " AND (train_number = ? OR train_number = 'ALL')"
                params.append(train_number)

            if section_id:
                query += " AND section_id = ?"
                params.append(section_id.upper())

            query += " ORDER BY detention_minutes DESC;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]

    def get_total_incidents_count(self) -> int:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM network_incidents;")
            return cur.fetchone()[0]
