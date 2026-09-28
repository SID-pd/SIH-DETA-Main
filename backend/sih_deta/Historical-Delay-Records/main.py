#!/usr/bin/env python3
"""
Indian Railways Historical Delay Records & Punctuality Engine CLI
Autonomous multi-horizon batch crawler (90-day & 1-year) with 15-day windowing,
ideal vs real arrival/departure matching, deadlock prevention, and state checkpoints.
"""

import argparse
import csv
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add module to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analytics.delay_matrix_engine import DELAY_STATES, DelayMatrixEngine
from analytics.sectional_profiler import SectionalProfiler
from analytics.timetable_matcher import TimetableMatcher
from config import (
    DEFAULT_DELAY,
    DEFAULT_HISTORY_DAYS,
    HORIZON_1Y,
    HORIZON_90D,
    LOG_FILE,
    MASTER_TRAINS_CSV,
    STATIONS_DB_PATH,
)
from scrapers.crawler_watchdog import CrawlerWatchdog, enforce_non_interactive
from scrapers.historical_delay_scraper import HistoricalDelayScraper
from storage.checkpoint_manager import CheckpointManager
from storage.historical_db import HistoricalDatabase
from storage.historical_exporter import HistoricalExporter
from system_check import print_system_diagnostic

# Configure File & Console Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
    ],
)
logger = logging.getLogger("historical_cli")


def print_table(headers: list, rows: list, max_widths: Optional[list] = None):
    """Print formatted ASCII table to terminal."""
    if not rows:
        print("  (No records found)")
        return

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            str_val = str(val if val is not None else "")
            if max_widths and i < len(max_widths) and max_widths[i]:
                str_val = str_val[:max_widths[i]]
            col_widths[i] = max(col_widths[i], len(str_val))

    header_line = " | ".join(f"{h:<{col_widths[i]}}" for i, h in enumerate(headers))
    sep_line = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    print(header_line)
    print(sep_line)

    for row in rows:
        formatted_cols = []
        for i, val in enumerate(row):
            str_val = str(val if val is not None else "")
            if max_widths and i < len(max_widths) and max_widths[i]:
                str_val = str_val[:max_widths[i]]
            formatted_cols.append(f"{str_val:<{col_widths[i]}}")
        print(" | ".join(formatted_cols))


def load_master_train_list() -> List[str]:
    """
    Extract nationwide catalog of unique 5-digit train numbers.
    Priority 1: station_halts table in stations.db (7,132 trains)
    Priority 2: master_trains.csv (5,208 trains)
    """
    train_set = set()

    # Priority 1: Query stations.db
    if STATIONS_DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(STATIONS_DB_PATH), timeout=15.0)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT train_number FROM station_halts")
            for row in cursor.fetchall():
                t = str(row[0]).strip().split("-")[0]
                if t.isdigit() and len(t) in (4, 5):
                    train_set.add(t.zfill(5))
            conn.close()
        except Exception as e:
            logger.debug(f"Error reading trains from stations.db: {e}")

    # Priority 2: Read master_trains.csv
    if not train_set and MASTER_TRAINS_CSV.exists():
        try:
            with open(MASTER_TRAINS_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    t = str(row.get("number", "")).strip()
                    if t.isdigit() and len(t) in (4, 5):
                        train_set.add(t.zfill(5))
        except Exception as e:
            logger.debug(f"Error reading master_trains.csv: {e}")

    # Fallback to key reference trains if no database populated yet
    if not train_set:
        train_set = {"12004", "12301", "12302", "12423", "22436", "12951", "12002"}

    train_list = sorted(list(train_set))
    logger.info(f"Loaded master train catalog: {len(train_list):,} unique trains identified.")
    return train_list


def cmd_single_train(train_number: str, horizon: str = HORIZON_90D) -> int:
    """Fetch running history, compute timetable matches and sectional profiles for one train."""
    train_clean = str(train_number).strip().zfill(5)
    horizon_label = "90-Day" if horizon == HORIZON_90D else ("1-Year" if horizon == HORIZON_1Y else horizon)
    print("=" * 82)
    print(f"  FETCHING HISTORICAL DELAY PROFILE: TRAIN {train_clean} ({horizon_label.upper()} HORIZON)")
    print("=" * 82)

    scraper = HistoricalDelayScraper()
    history = scraper.fetch_train_history(train_clean, horizon=horizon)

    if not history:
        print(f"❌ Failed to fetch historical records for train {train_clean}")
        return 1

    matrix_engine = DelayMatrixEngine()
    profiler = SectionalProfiler()
    timetable_matcher = TimetableMatcher()
    db = HistoricalDatabase()

    # 1. Compute sectional runs
    horizon_type = "90d" if horizon == HORIZON_90D else "1y"
    sectional_records = matrix_engine.compute_sectional_runs(
        train_number=train_clean,
        station_sequence=history["station_sequence"],
        daily_runs=history["daily_runs"],
        horizon_type=horizon_type,
    )

    # 2. Compute sectional profiles (for overall macro run and sub-windows)
    sectional_profiles = profiler.profile_all_sections(
        sectional_records=sectional_records,
        train_number=train_clean,
        horizon_type=horizon_type,
    )

    # 3. Save to database with ideal vs real arrival/departure enrichment
    db.save_train_history(history, sectional_records, sectional_profiles, timetable_matcher=timetable_matcher)

    d_range = history.get("date_range", {})
    sub_wins = history.get("sub_windows", [])
    print(f"🚆 Train:        {history['train_name']} ({train_clean})")
    print(f"📅 Date Window:  {d_range.get('start')} to {d_range.get('end')} ({history['total_days_retrieved']} days analyzed)")
    print(f"🪟 Sub-Windows:  {len(sub_wins)} bi-weekly 15-day partitions created")
    print(f"🚉 Route Length: {history['total_stations']} stations ({len(sectional_profiles)} track sections)")

    # Print Sample Enriched Halts (First 8 Stops)
    print("\nSample Station Halts with Ideal (STA/STD) vs Real Arrival/Departure Timestamps:")
    halt_headers = ["#", "STATION", "STA (IDEAL)", "ATA (REAL)", "STD (IDEAL)", "ATD (REAL)", "HALT", "DIST (KM)"]
    halt_rows = []
    sample_run = history["daily_runs"][-1] if history["daily_runs"] else None
    if sample_run:
        for idx, stn in enumerate(history["station_sequence"][:8]):
            d_val = sample_run.get("delays", {}).get(stn)
            e = timetable_matcher.enrich_station_delay(train_clean, stn, d_val)
            halt_rows.append([
                idx + 1,
                stn,
                e["scheduled_arrival"] or "--",
                e["actual_arrival"] or "--",
                e["scheduled_departure"] or "--",
                e["actual_departure"] or "--",
                f"{e['scheduled_halt_minutes']}m",
                f"{e['distance_km']} km",
            ])
    print_table(halt_headers, halt_rows)

    # Print Sectional Profiles Table
    print("\nSection-by-Section Delay Absorption & Reliability Profile:")
    headers = ["#", "FROM", "TO", "MEAN Δ", "STD DEV", "MEDIAN", "ABSORB %", "ON-TIME %", "CORRIDOR TYPE"]
    rows = []
    for p in sectional_profiles[:12]:
        rows.append([
            p["section_order"],
            p["from_station"],
            p["to_station"],
            f"{p['mean_delay_delta']:+.1f}m",
            f"{p['std_delay_delta']:.1f}",
            f"{p['median_delay_delta']:+d}m",
            f"{p['absorption_rate_pct']:.0f}%",
            f"{p['punctuality_rate_pct']:.0f}%",
            p["corridor_type"],
        ])
    print_table(headers, rows)
    return 0


def execute_batch_phase(
    phase: str,
    train_queue: List[str],
    checkpoint_mgr: CheckpointManager,
    watchdog: CrawlerWatchdog,
    scraper: HistoricalDelayScraper,
    matrix_engine: DelayMatrixEngine,
    profiler: SectionalProfiler,
    timetable_matcher: TimetableMatcher,
    db: HistoricalDatabase,
    rate_delay: float,
) -> None:
    """Executes crawler loop for a specific phase (90d or 1y) with zero-hang watchdog protection."""
    horizon_code = HORIZON_90D if phase == "90d" else HORIZON_1Y
    horizon_label = "90-Day" if phase == "90d" else "1-Year"
    total_in_phase = len(train_queue)

    print("\n" + "=" * 82)
    print(f"  🚀 STARTING AUTONOMOUS CRAWL: {horizon_label.upper()} HORIZON ({total_in_phase} TRAINS IN QUEUE)")
    print(f"  🛡️  Zero-Hang Protection Active | Auto-Checkpointing Enabled | Delay: {rate_delay:.1f}s")
    print("=" * 82)

    for idx, train_no in enumerate(train_queue, start=1):
        watchdog.processed_count += 1
        watchdog.emit_heartbeat(train_no, total_in_phase, phase, active_status="RUNNING")

        logger.info(f"[{idx}/{total_in_phase}] Scraping Train {train_no} ({phase})...")

        try:
            # Execute fetch with hard watchdog timeout (45 seconds)
            history = watchdog.run_with_timeout(
                scraper.fetch_train_history,
                args=(train_no,),
                kwargs={"horizon": horizon_code},
                timeout=45.0,
            )

            if not history or not history.get("daily_runs"):
                logger.warning(f"Train {train_no}: No running history records returned (skipping).")
                checkpoint_mgr.record_skip(train_no, phase, "EMPTY_HISTORY_OR_NOT_FOUND")
                db.mark_train_skipped(train_no, phase, "EMPTY_HISTORY_OR_NOT_FOUND")
                watchdog.skip_count += 1
                continue

            # Compute sectional transitions & profiles
            sectional_records = matrix_engine.compute_sectional_runs(
                train_number=train_no,
                station_sequence=history["station_sequence"],
                daily_runs=history["daily_runs"],
                horizon_type=phase,
            )

            sectional_profiles = profiler.profile_all_sections(
                sectional_records=sectional_records,
                train_number=train_no,
                horizon_type=phase,
            )

            # Persist with timetable enrichment
            db.save_train_history(history, sectional_records, sectional_profiles, timetable_matcher=timetable_matcher)

            # Record success in checkpoint
            checkpoint_mgr.record_success(
                train_number=train_no,
                phase=phase,
                runs_count=len(history["daily_runs"]),
                stations_count=len(history["station_sequence"]),
            )
            watchdog.success_count += 1
            logger.info(f"  ✓ Saved Train {train_no}: {len(history['daily_runs'])} runs, {len(history['station_sequence'])} stations")

        except TimeoutError:
            logger.error(f"  ⏱️ Train {train_no} timed out (>45s). Skipping to prevent deadlock.")
            checkpoint_mgr.record_failure(train_no, phase, "TIMEOUT_EXCEEDED_45S")
            db.mark_train_failed(train_no, phase, "TIMEOUT_EXCEEDED_45S")
            watchdog.fail_count += 1

        except Exception as e:
            logger.error(f"  ❌ Error processing train {train_no}: {e}")
            checkpoint_mgr.record_failure(train_no, phase, str(e))
            db.mark_train_failed(train_no, phase, str(e))
            watchdog.fail_count += 1

        # Periodic Garbage Collection to preserve flat RAM usage overnight
        watchdog.check_memory(interval_trains=25)


def cmd_batch(
    phase: str = "auto",
    limit: Optional[int] = None,
    delay: float = DEFAULT_DELAY,
) -> int:
    """
    Run autonomous multi-train crawling.
    If phase == 'auto', executes 90-day crawl for all trains, then advances to 1-year crawl.
    """
    enforce_non_interactive()

    all_trains = load_master_train_list()
    if limit:
        all_trains = all_trains[:limit]
        logger.info(f"Testing with limited batch of {limit} trains.")

    checkpoint_mgr = CheckpointManager()
    watchdog = CrawlerWatchdog()
    scraper = HistoricalDelayScraper(rate_limit_delay=delay)
    matrix_engine = DelayMatrixEngine()
    profiler = SectionalProfiler()
    timetable_matcher = TimetableMatcher()
    db = HistoricalDatabase()

    # PHASE 1: 90-Day Horizon
    if phase in ("90d", "auto"):
        pending_90d = checkpoint_mgr.get_pending_trains(all_trains, phase="90d")
        summary_90d = checkpoint_mgr.get_summary(phase="90d")
        logger.info(f"Phase 90-Day: {summary_90d['completed']} completed, {len(pending_90d)} pending.")

        if pending_90d:
            execute_batch_phase(
                phase="90d",
                train_queue=pending_90d,
                checkpoint_mgr=checkpoint_mgr,
                watchdog=watchdog,
                scraper=scraper,
                matrix_engine=matrix_engine,
                profiler=profiler,
                timetable_matcher=timetable_matcher,
                db=db,
                rate_delay=delay,
            )
        else:
            logger.info("Phase 90-Day is already 100% complete.")

    # PHASE 2: 1-Year Horizon (Auto-transitions once 90d completes)
    if phase in ("1y", "auto"):
        pending_1y = checkpoint_mgr.get_pending_trains(all_trains, phase="1y")
        summary_1y = checkpoint_mgr.get_summary(phase="1y")
        logger.info(f"Phase 1-Year: {summary_1y['completed']} completed, {len(pending_1y)} pending.")

        if pending_1y:
            execute_batch_phase(
                phase="1y",
                train_queue=pending_1y,
                checkpoint_mgr=checkpoint_mgr,
                watchdog=watchdog,
                scraper=scraper,
                matrix_engine=matrix_engine,
                profiler=profiler,
                timetable_matcher=timetable_matcher,
                db=db,
                rate_delay=delay,
            )
        else:
            logger.info("Phase 1-Year is already 100% complete.")

    watchdog.emit_heartbeat("FINISHED", len(all_trains), phase, active_status="COMPLETED")
    print("\n" + "=" * 82)
    print("  🎉 ALL REQUESTED HISTORICAL DELAY PHASES COMPLETED SUCCESSFULLY!")
    print(f"  • Total Processed: {watchdog.processed_count} trains")
    print(f"  • Successful:      {watchdog.success_count}")
    print(f"  • Skipped / 404:   {watchdog.skip_count}")
    print(f"  • Failed / Timeout:{watchdog.fail_count}")
    print("=" * 82)
    return 0


def cmd_status() -> None:
    """Display live checkpoint and scraping progress status."""
    mgr = CheckpointManager()
    all_trains = load_master_train_list()
    total = len(all_trains)

    s90 = mgr.get_summary("90d")
    s1y = mgr.get_summary("1y")

    pct90 = (s90["completed"] / total * 100) if total > 0 else 0
    pct1y = (s1y["completed"] / total * 100) if total > 0 else 0

    print("=" * 78)
    print("  📊 HISTORICAL DELAY ENGINE: BATCH PROGRESS & CHECKPOINT STATUS")
    print("=" * 78)
    print(f"  • Master Trains in Catalog: {total:,}")
    print("-" * 78)
    print(f"  • 90-Day Phase (?d=3m):")
    print(f"      Completed: {s90['completed']:,} ({pct90:.1f}%)")
    print(f"      Skipped:   {s90['skipped']:,}")
    print(f"      Failed:    {s90['failed']:,}")
    print(f"      Pending:   {max(0, total - s90['completed'] - s90['skipped']):,}")
    print("-" * 78)
    print(f"  • 1-Year Phase (?d=1y):")
    print(f"      Completed: {s1y['completed']:,} ({pct1y:.1f}%)")
    print(f"      Skipped:   {s1y['skipped']:,}")
    print(f"      Failed:    {s1y['failed']:,}")
    print(f"      Pending:   {max(0, total - s1y['completed'] - s1y['skipped']):,}")
    print("=" * 78)


def main():
    parser = argparse.ArgumentParser(
        description="Indian Railways Autonomous Historical Delay Engine (90-Day & 1-Year Pipeline)"
    )
    parser.add_argument(
        "--mode",
        choices=["system-check", "train", "batch", "status", "reset-checkpoint"],
        default="batch",
        help="Execution mode (default: batch)",
    )
    parser.add_argument(
        "--phase",
        choices=["90d", "1y", "auto"],
        default="auto",
        help="Batch crawling phase: '90d', '1y', or 'auto' (runs 90d then 1y)",
    )
    parser.add_argument(
        "--train",
        type=str,
        default="12004",
        help="Train number for single train mode (e.g. 12004)",
    )
    parser.add_argument(
        "--horizon",
        type=str,
        default=HORIZON_90D,
        help="Horizon code for single train mode ('3m', '1y')",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of trains to scrape (useful for testing)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Polite delay between requests in seconds (default: {DEFAULT_DELAY})",
    )

    args = parser.parse_args()

    if args.mode == "system-check":
        print_system_diagnostic()
        return 0
    elif args.mode == "status":
        cmd_status()
        return 0
    elif args.mode == "reset-checkpoint":
        mgr = CheckpointManager()
        mgr.reset()
        print("✓ Checkpoint state reset successfully.")
        return 0
    elif args.mode == "train":
        return cmd_single_train(args.train, horizon=args.horizon)
    elif args.mode == "batch":
        return cmd_batch(phase=args.phase, limit=args.limit, delay=args.delay)

    return 0


if __name__ == "__main__":
    sys.exit(main())
