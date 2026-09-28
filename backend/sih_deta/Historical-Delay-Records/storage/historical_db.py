"""
SQLite Database engine for Indian Railways Historical Delay Records & Sectional Analytics.
Configured with WAL mode, busy timeouts, and atomic transactions to prevent database deadlocks.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import DEFAULT_DB_PATH

logger = logging.getLogger("historical_db")


class HistoricalDatabase:
    """SQLite database manager with deadlock prevention and rich halt-level analytics."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a SQLite connection with 60s busy timeout and performance pragmas."""
        conn = sqlite3.connect(str(self.db_path), timeout=60.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 60000")
        return conn

    def _init_db(self) -> None:
        """Initialize relational database schemas and performance indexes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Daily Station-by-Station Delays (with Scheduled Ideal vs Actual Real)
            # 1. Daily Station-by-Station Delays Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_station_delays (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    train_number TEXT NOT NULL,
                    journey_date TEXT NOT NULL,
                    station_code TEXT NOT NULL,
                    stop_order INTEGER NOT NULL,
                    delay_minutes INTEGER,
                    punctuality_bucket TEXT,
                    day_of_week INTEGER,
                    is_weekend INTEGER,
                    scheduled_arrival TEXT,
                    actual_arrival TEXT,
                    scheduled_departure TEXT,
                    actual_departure TEXT,
                    scheduled_halt_minutes INTEGER DEFAULT 0,
                    actual_halt_minutes INTEGER DEFAULT 0,
                    halt_variance_minutes INTEGER DEFAULT 0,
                    distance_km REAL DEFAULT 0.0,
                    platform TEXT DEFAULT '1',
                    window_tag TEXT DEFAULT '15d_w1',
                    horizon_type TEXT DEFAULT '90d',
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(train_number, journey_date, station_code, window_tag) ON CONFLICT REPLACE
                )
            """)

            # Auto-migrate daily_station_delays columns if table existed with older schema
            cursor.execute("PRAGMA table_info(daily_station_delays)")
            cols = {row["name"] for row in cursor.fetchall()}
            for col, col_type in [
                ("scheduled_arrival", "TEXT"),
                ("actual_arrival", "TEXT"),
                ("scheduled_departure", "TEXT"),
                ("actual_departure", "TEXT"),
                ("scheduled_halt_minutes", "INTEGER DEFAULT 0"),
                ("actual_halt_minutes", "INTEGER DEFAULT 0"),
                ("halt_variance_minutes", "INTEGER DEFAULT 0"),
                ("distance_km", "REAL DEFAULT 0.0"),
                ("platform", "TEXT DEFAULT '1'"),
                ("window_tag", "TEXT DEFAULT '15d_w1'"),
                ("horizon_type", "TEXT DEFAULT '90d'"),
            ]:
                if col not in cols:
                    try:
                        cursor.execute(f"ALTER TABLE daily_station_delays ADD COLUMN {col} {col_type}")
                    except Exception:
                        pass

            # Safe indexes for daily_station_delays (after migration)
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_stn_delays_lookup ON daily_station_delays(train_number, journey_date)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_stn_delays_stn ON daily_station_delays(station_code, journey_date)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_stn_delays_window ON daily_station_delays(train_number, window_tag)")
            except Exception as e:
                logger.debug(f"Index creation warning: {e}")

            # 2. Sectional Delay Transitions (S_i -> S_{i+1})
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sectional_delay_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    train_number TEXT NOT NULL,
                    journey_date TEXT NOT NULL,
                    from_station TEXT NOT NULL,
                    to_station TEXT NOT NULL,
                    section_order INTEGER NOT NULL,
                    departure_delay INTEGER,
                    arrival_delay INTEGER,
                    delay_delta INTEGER,
                    status TEXT,
                    from_state TEXT,
                    to_state TEXT,
                    day_of_week INTEGER,
                    window_tag TEXT DEFAULT '15d_w1',
                    horizon_type TEXT DEFAULT '90d',
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(train_number, journey_date, from_station, to_station, window_tag) ON CONFLICT REPLACE
                )
            """)

            # Auto-migrate sectional columns before creating indexes
            cursor.execute("PRAGMA table_info(sectional_delay_records)")
            sec_cols = {row["name"] for row in cursor.fetchall()}
            for col, col_type in [("window_tag", "TEXT DEFAULT '15d_w1'"), ("horizon_type", "TEXT DEFAULT '90d'")]:
                if col not in sec_cols:
                    try:
                        cursor.execute(f"ALTER TABLE sectional_delay_records ADD COLUMN {col} {col_type}")
                    except Exception:
                        pass

            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sec_delays_corridor ON sectional_delay_records(from_station, to_station)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sec_delays_train ON sectional_delay_records(train_number, journey_date)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sec_delays_win ON sectional_delay_records(train_number, window_tag)")
            except Exception as e:
                logger.debug(f"Sectional index warning: {e}")

            # 3. Sectional Profiles (Aggregated Feature Store by Sub-Window)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sectional_profiles (
                    train_number TEXT NOT NULL,
                    from_station TEXT NOT NULL,
                    to_station TEXT NOT NULL,
                    window_tag TEXT NOT NULL DEFAULT 'macro',
                    horizon_type TEXT NOT NULL DEFAULT '90d',
                    section_order INTEGER NOT NULL,
                    sample_size_days INTEGER NOT NULL,
                    mean_delay_delta REAL NOT NULL,
                    std_delay_delta REAL NOT NULL,
                    median_delay_delta INTEGER NOT NULL,
                    min_delay_delta INTEGER NOT NULL,
                    max_delay_delta INTEGER NOT NULL,
                    absorption_rate_pct REAL NOT NULL,
                    accumulation_rate_pct REAL NOT NULL,
                    punctuality_rate_pct REAL NOT NULL,
                    corridor_type TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (train_number, from_station, to_station, window_tag, horizon_type)
                )
            """)

            # Auto-migrate sectional_profiles columns
            cursor.execute("PRAGMA table_info(sectional_profiles)")
            prof_cols = {row["name"] for row in cursor.fetchall()}
            for col, col_type in [("window_tag", "TEXT DEFAULT 'macro'"), ("horizon_type", "TEXT DEFAULT '90d'")]:
                if col not in prof_cols:
                    try:
                        cursor.execute(f"ALTER TABLE sectional_profiles ADD COLUMN {col} {col_type}")
                    except Exception:
                        pass

            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sec_profiles_stns ON sectional_profiles(from_station, to_station)")
            except Exception as e:
                logger.debug(f"Profiles index warning: {e}")

            # 4. Scraping Checkpoint & State Table (Enables Interruption & Safe Resume)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scraping_checkpoints (
                    train_number TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    status TEXT NOT NULL,
                    runs_retrieved INTEGER DEFAULT 0,
                    stations_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (train_number, phase)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_phase ON scraping_checkpoints(phase, status)")

            conn.commit()

    def save_train_history(
        self,
        history: Dict[str, Any],
        sectional_records: List[Dict[str, Any]],
        sectional_profiles: List[Dict[str, Any]],
        timetable_matcher: Optional[Any] = None,
    ) -> None:
        """
        Persist parsed train runs, enriched timetable records, sectional transitions,
        and profiles in a single atomic database transaction.
        """
        train_number = history["train_number"]
        horizon = history.get("horizon", "3m")
        horizon_type = "90d" if horizon == "3m" else ("1y" if horizon == "1y" else "macro")
        station_sequence = history["station_sequence"]
        daily_runs = history.get("daily_runs", [])

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Insert daily station delays
            station_rows = []
            for run in daily_runs:
                j_date = run["journey_date"]
                dow = run["day_of_week"]
                is_wknd = run["is_weekend"]
                w_tag = run.get("window_tag", "15d_w1")
                delays = run.get("delays", {})

                for idx, stn in enumerate(station_sequence):
                    d_mins = delays.get(stn)
                    if d_mins is None:
                        continue

                    # Bucket classification
                    if d_mins <= 5:
                        p_bucket = "RIGHT_TIME"
                    elif d_mins <= 15:
                        p_bucket = "SLIGHT_DELAY"
                    elif d_mins <= 45:
                        p_bucket = "SIGNIFICANT_DELAY"
                    else:
                        p_bucket = "SEVERE_DELAY"

                    # Enrich with timetable values if matcher available
                    if timetable_matcher:
                        enriched = timetable_matcher.enrich_station_delay(train_number, stn, d_mins)
                        sched_arr = enriched["scheduled_arrival"]
                        real_arr = enriched["actual_arrival"]
                        sched_dep = enriched["scheduled_departure"]
                        real_dep = enriched["actual_departure"]
                        sched_halt = enriched["scheduled_halt_minutes"]
                        real_halt = enriched["actual_halt_minutes"]
                        halt_var = enriched["halt_variance_minutes"]
                        dist = enriched["distance_km"]
                        plat = enriched["platform"]
                    else:
                        sched_arr = real_arr = sched_dep = real_dep = None
                        sched_halt = real_halt = halt_var = 0
                        dist = 0.0
                        plat = "1"

                    station_rows.append((
                        train_number, j_date, stn, idx + 1, d_mins, p_bucket, dow, is_wknd,
                        sched_arr, real_arr, sched_dep, real_dep, sched_halt, real_halt,
                        halt_var, dist, plat, w_tag, horizon_type
                    ))

            if station_rows:
                cursor.executemany("""
                    INSERT OR REPLACE INTO daily_station_delays (
                        train_number, journey_date, station_code, stop_order, delay_minutes,
                        punctuality_bucket, day_of_week, is_weekend, scheduled_arrival,
                        actual_arrival, scheduled_departure, actual_departure,
                        scheduled_halt_minutes, actual_halt_minutes, halt_variance_minutes,
                        distance_km, platform, window_tag, horizon_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, station_rows)

            # 2. Insert sectional transition records
            sec_rows = []
            for r in sectional_records:
                sec_rows.append((
                    r["train_number"], r["journey_date"], r["from_station"], r["to_station"],
                    r["section_order"], r["departure_delay"], r["arrival_delay"],
                    r["delay_delta"], r["status"], r["from_state"], r["to_state"],
                    r["day_of_week"], r.get("window_tag", "15d_w1"), r.get("horizon_type", horizon_type)
                ))

            if sec_rows:
                cursor.executemany("""
                    INSERT OR REPLACE INTO sectional_delay_records (
                        train_number, journey_date, from_station, to_station, section_order,
                        departure_delay, arrival_delay, delay_delta, status, from_state,
                        to_state, day_of_week, window_tag, horizon_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, sec_rows)

            # 3. Insert pre-aggregated sectional profiles
            prof_rows = []
            for p in sectional_profiles:
                prof_rows.append((
                    p["train_number"], p["from_station"], p["to_station"],
                    p.get("window_tag", "macro"), p.get("horizon_type", horizon_type),
                    p["section_order"], p["sample_size_days"], p["mean_delay_delta"],
                    p["std_delay_delta"], p["median_delay_delta"], p["min_delay_delta"],
                    p["max_delay_delta"], p["absorption_rate_pct"], p["accumulation_rate_pct"],
                    p["punctuality_rate_pct"], p["corridor_type"]
                ))

            if prof_rows:
                cursor.executemany("""
                    INSERT OR REPLACE INTO sectional_profiles (
                        train_number, from_station, to_station, window_tag, horizon_type,
                        section_order, sample_size_days, mean_delay_delta, std_delay_delta,
                        median_delay_delta, min_delay_delta, max_delay_delta,
                        absorption_rate_pct, accumulation_rate_pct, punctuality_rate_pct,
                        corridor_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, prof_rows)

            # 4. Update checkpoint entry in database
            cursor.execute("""
                INSERT OR REPLACE INTO scraping_checkpoints (
                    train_number, phase, status, runs_retrieved, stations_count, updated_at
                ) VALUES (?, ?, 'SUCCESS', ?, ?, CURRENT_TIMESTAMP)
            """, (train_number, horizon_type, len(daily_runs), len(station_sequence)))

            conn.commit()

    def mark_train_failed(self, train_number: str, phase: str, error_message: str) -> None:
        """Record train crawl failure in database checkpoint table."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO scraping_checkpoints (
                    train_number, phase, status, error_message, updated_at
                ) VALUES (?, ?, 'FAILED', ?, CURRENT_TIMESTAMP)
            """, (train_number, phase, error_message[:255]))
            conn.commit()

    def mark_train_skipped(self, train_number: str, phase: str, reason: str) -> None:
        """Record train skipped (e.g. 404 Not Found) in checkpoint table."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO scraping_checkpoints (
                    train_number, phase, status, error_message, updated_at
                ) VALUES (?, ?, 'SKIPPED', ?, CURRENT_TIMESTAMP)
            """, (train_number, phase, reason[:255]))
            conn.commit()

    def get_all_sectional_records(self) -> List[Dict[str, Any]]:
        """Retrieve all sectional transition records."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sectional_delay_records ORDER BY train_number, journey_date, section_order")
            return [dict(row) for row in cursor.fetchall()]

    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """Retrieve all pre-aggregated sectional profiles."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sectional_profiles ORDER BY train_number, section_order")
            return [dict(row) for row in cursor.fetchall()]

    def get_corridor_profile(self, from_station: str, to_station: str, train_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve historical profile for a specific track corridor."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if train_number:
                cursor.execute(
                    "SELECT * FROM sectional_profiles WHERE from_station = ? AND to_station = ? AND train_number = ?",
                    (from_station, to_station, train_number),
                )
            else:
                cursor.execute(
                    "SELECT * FROM sectional_profiles WHERE from_station = ? AND to_station = ?",
                    (from_station, to_station),
                )
            return [dict(row) for row in cursor.fetchall()]

    def get_summary_stats(self) -> Dict[str, Any]:
        """Compute top-level summary metrics across the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(DISTINCT train_number) FROM daily_station_delays")
            trains_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM daily_station_delays")
            delays_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM sectional_delay_records")
            sec_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM sectional_profiles")
            prof_count = cursor.fetchone()[0]

            return {
                "total_trains": trains_count,
                "total_delay_observations": delays_count,
                "total_sectional_runs": sec_count,
                "total_sectional_profiles": prof_count,
            }

