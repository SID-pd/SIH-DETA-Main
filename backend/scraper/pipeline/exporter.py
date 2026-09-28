"""
Exporter and aggregator for scraper-erail.
Syncs scraped data to CSV/Parquet and compiles segment metrics into darpan.sqlite.
"""

from __future__ import annotations

import csv
import logging
import sqlite3
from pathlib import Path
from typing import Optional, Union

from config.settings import DEFAULT_DARPAN_DB_PATH, OUTPUT_DIR
from storage.database import Database

logger = logging.getLogger("scraper_erail.exporter")


class DataExporter:
    def __init__(self, db: Optional[Database] = None, output_dir: Optional[Path] = None):
        self.db = db or Database()
        self.output_dir = Path(output_dir) if output_dir else OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_table_to_csv(self, table_name: str, file_path: Optional[Path] = None) -> int:
        target_path = file_path or (self.output_dir / f"{table_name}.csv")
        with self.db.get_connection() as conn:
            cur = conn.execute(f"SELECT * FROM {table_name};")
            rows = cur.fetchall()
            if not rows:
                logger.warning(f"No rows found in table {table_name}")
                return 0

            field_names = [col[0] for col in cur.description]
            with open(target_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(field_names)
                for row in rows:
                    writer.writerow(list(row))

        logger.info(f"Exported {len(rows)} rows from {table_name} to {target_path}")
        return len(rows)

    def export_all_tables(self) -> None:
        tables = [
            "stations",
            "trains",
            "schedule_stops",
            "coach_compositions",
            "historical_station_delays",
            "train_exceptions",
            "live_observations",
            "segments",
        ]
        for tbl in tables:
            try:
                self.export_table_to_csv(tbl)
            except Exception as e:
                logger.warning(f"Could not export table {tbl}: {e}")

    def compile_segments_from_schedule(self) -> int:
        """
        Recompiles the `segments` table from all recorded `schedule_stops`.
        Calculates distance, p50 scheduled runtime, and joins historical delay added.
        """
        sql = """
        WITH consecutive_stops AS (
            SELECT
                s1.station_code AS from_code,
                s2.station_code AS to_code,
                s2.distance_km - s1.distance_km AS seg_distance,
                s1.departure AS dep_time,
                s2.arrival AS arr_time
            FROM schedule_stops s1
            JOIN schedule_stops s2
                ON s1.train_number = s2.train_number
                AND s2.seq = s1.seq + 1
            WHERE s2.distance_km >= s1.distance_km
        )
        INSERT INTO segments (from_code, to_code, distance_km, n_timetables, source)
        SELECT
            from_code,
            to_code,
            AVG(seg_distance) AS distance_km,
            COUNT(*) AS n_timetables,
            'scraped_schedule' AS source
        FROM consecutive_stops
        GROUP BY from_code, to_code
        ON CONFLICT(from_code, to_code) DO UPDATE SET
            distance_km=excluded.distance_km,
            n_timetables=excluded.n_timetables;
        """
        with self.db.get_connection() as conn:
            cur = conn.execute(sql)
            conn.commit()
            count = cur.rowcount
            logger.info(f"Compiled {count} route segments into segments table.")

        # Update historical delay added priors
        self._backfill_segment_historical_delays()
        return count

    def _backfill_segment_historical_delays(self) -> None:
        """
        Backfills `hist_delay_added_p50` on segments from `historical_station_delays`.
        """
        sql = """
        UPDATE segments
        SET hist_delay_added_p50 = (
            SELECT AVG(h2.avg_delay_mins - h1.avg_delay_mins)
            FROM historical_station_delays h1
            JOIN historical_station_delays h2
                ON h1.train_number = h2.train_number
            WHERE h1.station_code = segments.from_code
              AND h2.station_code = segments.to_code
        )
        WHERE EXISTS (
            SELECT 1
            FROM historical_station_delays h1
            JOIN historical_station_delays h2
                ON h1.train_number = h2.train_number
            WHERE h1.station_code = segments.from_code
              AND h2.station_code = segments.to_code
        );
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.execute(sql)
                conn.commit()
                logger.info(f"Backfilled historical delay priors on {cur.rowcount} segments.")
        except Exception as e:
            logger.warning(f"Could not backfill historical delay priors: {e}")
