#!/usr/bin/env python3
"""
Indian Railways Train Scraper CLI

Scrapes the list and schedules of all trains operating across India from trusted
railway websites and master datasets. Supports JSON, CSV, and SQLite database exports.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from config import DEFAULT_CONCURRENCY, DEFAULT_DELAY, EXPORTS_DIR
from scrapers.confirmtkt_scraper import ConfirmTktScraper
from scrapers.dataset_loader import DatasetLoader
from scrapers.etrain_scraper import ETrainScraper
from storage.db import Database
from storage.exporter import export_schedules_flattened_csv, export_to_csv, export_to_json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("rail_scraper")


def setup_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scraper for getting list of all trains across India (Indian Railways)."
    )
    parser.add_argument(
        "--mode",
        choices=["discover", "schedule", "sync-master", "search", "stats"],
        default="discover",
        help="Operation mode: 'discover' (all trains via prefix traversal), 'schedule' (deep timetable), 'sync-master' (import master open data), 'search' (find trains), 'stats' (db summary)"
    )
    parser.add_argument(
        "--source",
        choices=["confirmtkt", "etrain", "all"],
        default="confirmtkt",
        help="Source to use for discovery (default: confirmtkt)"
    )
    parser.add_argument(
        "--train", "-t",
        type=str,
        help="Specific train number to scrape schedule for (e.g. 12043)"
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        help="Search keyword (e.g. 'Rajdhani', 'NDLS', 'Shatabdi', '120')"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="Limit number of prefixes or trains to process (useful for quick testing)"
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Number of concurrent worker threads (default: {DEFAULT_CONCURRENCY})"
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Polite delay between requests in seconds (default: {DEFAULT_DELAY})"
    )
    parser.add_argument(
        "--output-format", "-f",
        choices=["all", "json", "csv", "sqlite"],
        default="all",
        help="Output export formats (default: all)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=str(EXPORTS_DIR),
        help=f"Directory to save exported files (default: {EXPORTS_DIR})"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging output"
    )
    return parser


def handle_discover(args, db: Database, output_dir: Path):
    """Run live train number discovery across prefixes."""
    logger.info(f"--- Starting Train Discovery (Source: {args.source}) ---")
    all_trains = []

    if args.source in ("confirmtkt", "all"):
        c_scraper = ConfirmTktScraper(delay=args.delay)
        c_trains = c_scraper.discover_all_trains(concurrency=args.concurrency, limit=args.limit)
        all_trains.extend(c_trains)

    if args.source in ("etrain", "all"):
        e_scraper = ETrainScraper(delay=args.delay)
        e_trains = e_scraper.discover_trains(concurrency=args.concurrency, limit=args.limit)
        all_trains.extend(e_trains)

    # Deduplicate by train number
    unique_trains_map = {}
    for t in all_trains:
        num = t["number"]
        if num not in unique_trains_map or (t.get("name") and not unique_trains_map[num].get("name")):
            unique_trains_map[num] = t

    trains_list = sorted(unique_trains_map.values(), key=lambda x: x["number"])
    logger.info(f"Discovered a total of {len(trains_list)} unique trains.")

    # Save to SQLite database
    if args.output_format in ("all", "sqlite"):
        saved = db.upsert_trains(trains_list)
        logger.info(f"Saved {saved} trains to SQLite database: {db.db_path}")

    # Export to JSON
    if args.output_format in ("all", "json"):
        json_path = output_dir / "all_trains.json"
        export_to_json(trains_list, json_path)

    # Export to CSV
    if args.output_format in ("all", "csv"):
        csv_path = output_dir / "all_trains.csv"
        export_to_csv(trains_list, csv_path)

    print("\n" + "=" * 60)
    print(f"DISCOVERY SUMMARY:")
    print(f"  • Total Unique Trains Found: {len(trains_list)}")
    print(f"  • Database: {db.db_path}")
    if args.output_format in ("all", "json"):
        print(f"  • JSON File: {output_dir / 'all_trains.json'}")
    if args.output_format in ("all", "csv"):
        print(f"  • CSV File:  {output_dir / 'all_trains.csv'}")
    print("=" * 60 + "\n")


def handle_schedule(args, db: Database, output_dir: Path):
    """Scrape detailed route and timetable for one or more trains."""
    scraper = ConfirmTktScraper(delay=args.delay)

    trains_to_scrape: List[str] = []
    if args.train:
        trains_to_scrape = [args.train.strip()]
    else:
        # Pull trains from DB that need schedules
        db_trains = db.get_all_trains()
        if not db_trains:
            logger.warning("No trains found in database. Run '--mode discover' or '--mode sync-master' first, or pass '--train <number>'")
            return
        trains_to_scrape = [t["number"] for t in db_trains]
        if args.limit:
            trains_to_scrape = trains_to_scrape[:args.limit]

    logger.info(f"--- Fetching Schedules for {len(trains_to_scrape)} Train(s) ---")
    schedules = []

    for idx, t_num in enumerate(trains_to_scrape, 1):
        logger.info(f"[{idx}/{len(trains_to_scrape)}] Scraping timetable for train {t_num}...")
        sched = scraper.scrape_schedule(t_num)
        if sched:
            schedules.append(sched)
            if args.output_format in ("all", "sqlite"):
                db.save_schedule(sched)
            print(f"  -> {sched.get('name', 'Train')} ({t_num}): {sched.get('route', '')} | {len(sched.get('stops', []))} stops")
        else:
            logger.warning(f"Could not retrieve schedule for train {t_num}")

    if not schedules:
        return

    # Export schedules
    if args.output_format in ("all", "json"):
        json_path = output_dir / "train_schedules.json"
        export_to_json(schedules, json_path)

    if args.output_format in ("all", "csv"):
        summary_csv = output_dir / "train_schedules_summary.csv"
        export_to_csv(schedules, summary_csv)
        stops_csv = output_dir / "train_stops_detailed.csv"
        export_schedules_flattened_csv(schedules, stops_csv)

    print("\n" + "=" * 60)
    print(f"SCHEDULES SUMMARY:")
    print(f"  • Successfully Scraped: {len(schedules)} train timetables")
    if args.output_format in ("all", "csv"):
        print(f"  • Detailed Stops CSV: {output_dir / 'train_stops_detailed.csv'}")
    print("=" * 60 + "\n")


def handle_sync_master(args, db: Database, output_dir: Path):
    """Download and import the master Indian Railways dataset."""
    logger.info("--- Syncing Master Indian Railways Dataset ---")
    loader = DatasetLoader()
    trains = loader.fetch_master_dataset()

    if not trains:
        logger.error("Failed to load master dataset.")
        return

    if args.limit:
        trains = trains[:args.limit]

    logger.info(f"Importing {len(trains)} trains into database...")
    saved = db.upsert_trains(trains)
    logger.info(f"Successfully saved {saved} trains to SQLite database: {db.db_path}")

    # Export to files
    if args.output_format in ("all", "json"):
        json_path = output_dir / "master_trains.json"
        export_to_json(trains, json_path)

    if args.output_format in ("all", "csv"):
        csv_path = output_dir / "master_trains.csv"
        export_to_csv(trains, csv_path)

    print("\n" + "=" * 60)
    print(f"MASTER SYNC SUMMARY:")
    print(f"  • Total Trains Imported: {len(trains)}")
    print(f"  • Database: {db.db_path}")
    if args.output_format in ("all", "json"):
        print(f"  • JSON File: {output_dir / 'master_trains.json'}")
    if args.output_format in ("all", "csv"):
        print(f"  • CSV File:  {output_dir / 'master_trains.csv'}")
    print("=" * 60 + "\n")


def handle_search(args, db: Database):
    """Search for trains by number or keyword."""
    query = args.query or args.train
    if not query:
        print("Please provide a query via '--query <term>' or '--train <number>'")
        return

    print(f"\nSearching database for '{query}'...")
    results = db.search_trains(query, limit=args.limit or 20)

    if not results:
        print(f"No results in local database. Querying live railway lookup...")
        c_scraper = ConfirmTktScraper()
        results = c_scraper.search_trains(query)

    print(f"Found {len(results)} matching train(s):\n")
    print(f"{'NUMBER':<10} | {'NAME':<35} | {'ROUTE / DETAILS':<35}")
    print("-" * 85)
    for r in results:
        num = r.get("number", "")
        name = r.get("name", "")
        route = r.get("route") or f"{r.get('from_station_code', '')} → {r.get('to_station_code', '')}"
        print(f"{num:<10} | {name[:34]:<35} | {route[:34]:<35}")
    print("\n")


def handle_stats(db: Database):
    """Display summary stats of the local database."""
    total_trains = db.count_trains()
    total_stops = db.count_stops()
    print("\n" + "=" * 45)
    print("INDIAN RAILWAYS LOCAL DATABASE STATS")
    print("=" * 45)
    print(f"  • Total Trains in Database: {total_trains}")
    print(f"  • Total Timetable Stops:   {total_stops}")
    print(f"  • Database Location:        {db.db_path}")
    print("=" * 45 + "\n")


def main():
    parser = setup_args()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    db = Database()

    if args.mode == "discover":
        handle_discover(args, db, output_dir)
    elif args.mode == "schedule":
        handle_schedule(args, db, output_dir)
    elif args.mode == "sync-master":
        handle_sync_master(args, db, output_dir)
    elif args.mode == "search":
        handle_search(args, db)
    elif args.mode == "stats":
        handle_stats(db)


if __name__ == "__main__":
    main()
