"""
Unified CLI for scraper-erail.
Provides intuitive commands to scrape, validate, export, and poll
data from erail.in and CRIS NTES.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import List, Optional

from core.state_manager import StateManager
from pipeline.dataset_builder import DatasetBuilder
from pipeline.exporter import DataExporter
from scrapers.erail_scraper import ErailScraper
from scrapers.live_poller import LivePoller
from scrapers.ntes_scraper import NtesScraper
from storage.database import Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("scraper_erail.cli")


def get_train_list_from_db(db: Database, limit: Optional[int] = None) -> List[str]:
    with db.get_connection() as conn:
        q = "SELECT number FROM trains"
        if limit:
            q += f" LIMIT {limit}"
        cur = conn.execute(q)
        return [r["number"] for r in cur.fetchall()]


def cmd_catalog(args: argparse.Namespace) -> None:
    scraper = ErailScraper()
    asyncio.run(scraper.fetch_train_catalog())
    asyncio.run(scraper.fetch_station_catalog())
    print("\n[OK] Master train and station catalogs successfully updated in database.")


def cmd_route(args: argparse.Namespace) -> None:
    db = Database()
    scraper = ErailScraper(db=db)

    if args.trains:
        train_list = [t.strip() for t in args.trains.split(",") if t.strip()]
    else:
        train_list = get_train_list_from_db(db, limit=args.limit)

    print(f"Targeting {len(train_list)} trains for route extraction...")
    success = asyncio.run(scraper.scrape_batch_routes(train_list, resume=not args.no_resume))
    print(f"\n[OK] Completed route scrape: {success}/{len(train_list)} successful.")


def cmd_coach(args: argparse.Namespace) -> None:
    db = Database()
    scraper = ErailScraper(db=db)

    if args.trains:
        train_list = [t.strip() for t in args.trains.split(",") if t.strip()]
    else:
        train_list = get_train_list_from_db(db, limit=args.limit)

    print(f"Targeting {len(train_list)} trains for coach composition & rake type...")
    success = asyncio.run(scraper.scrape_batch_coaches(train_list, resume=not args.no_resume))
    print(f"\n[OK] Completed coach scrape: {success}/{len(train_list)} successful.")


def cmd_delays(args: argparse.Namespace) -> None:
    db = Database()
    scraper = ErailScraper(db=db)

    if args.trains:
        train_list = [t.strip() for t in args.trains.split(",") if t.strip()]
    else:
        train_list = get_train_list_from_db(db, limit=args.limit)

    print(f"Targeting {len(train_list)} trains for historical delay profiles...")
    success = asyncio.run(scraper.scrape_batch_delays(train_list, resume=not args.no_resume))
    print(f"\n[OK] Completed delay profiles scrape: {success}/{len(train_list)} successful.")


def cmd_live(args: argparse.Namespace) -> None:
    scraper = NtesScraper()
    if args.trains:
        train_list = [t.strip() for t in args.trains.split(",") if t.strip()]
    else:
        train_list = ["12301", "12302", "12002", "22436", "12951"]

    obs_count = asyncio.run(scraper.scrape_batch_live(train_list, journey_date=args.date))
    print(f"\n[OK] Captured {obs_count} live observation stops from NTES.")


def cmd_exceptions(args: argparse.Namespace) -> None:
    scraper = NtesScraper()
    for ex_type in ["RescheduledTrains", "CancelledTrains", "DivertedTrains"]:
        res = asyncio.run(scraper.fetch_train_exceptions(journey_date=args.date, exception_type=ex_type))
        print(f"Recorded {len(res)} {ex_type} from NTES.")
    print("\n[OK] Operational exception feeds synced.")


def cmd_compile(args: argparse.Namespace) -> None:
    exporter = DataExporter()
    count = exporter.compile_segments_from_schedule()
    print(f"\n[OK] Compiled {count} route segments into segments table with historical priors.")


def cmd_export(args: argparse.Namespace) -> None:
    exporter = DataExporter()
    exporter.export_all_tables()
    print(f"\n[OK] All tables exported to CSV in {exporter.output_dir}.")


def cmd_build_dataset(args: argparse.Namespace) -> None:
    builder = DatasetBuilder()
    if args.type in ("journey", "all"):
        count = builder.build_journey_dataset(days_history=args.days)
        print(f"\n[OK] Built journey-level ML training dataset (ir_train_real.csv) with {count} rows.")
    if args.type in ("point", "all"):
        count = builder.build_point_delays_dataset()
        print(f"\n[OK] Built intermediate point delay dataset (ir_point_delays_master.csv) with {count} rows.")
    print("[NOTE] Database (darpan.sqlite) remains fully intact as the relational source of truth.")


def cmd_poll(args: argparse.Namespace) -> None:
    poller = LivePoller(interval_seconds=args.interval)
    train_list = [t.strip() for t in args.trains.split(",")] if args.trains else None
    print(f"Starting live poller (interval={args.interval}s)... Press Ctrl+C to stop.")
    try:
        asyncio.run(poller.run_forever(train_numbers=train_list))
    except KeyboardInterrupt:
        print("\nPoller stopped.")


def cmd_status(args: argparse.Namespace) -> None:
    state_mgr = StateManager()
    summary = state_mgr.get_summary()
    print("=" * 45)
    print("       SCRAPER CHECKPOINT STATE SUMMARY      ")
    print("=" * 45)
    if not summary:
        print("No tasks recorded yet.")
    for t_type, stats in summary.items():
        print(f"Task: {t_type}")
        for st, count in stats.items():
            print(f"  - {st}: {count}")
    print("=" * 45)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="scraper-erail",
        description="Unified Indian Railways scraper for erail.in & CRIS NTES",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # catalog
    p_catalog = subparsers.add_parser("catalog", help="Scrape master train & station catalogs")
    p_catalog.set_defaults(func=cmd_catalog)

    # route
    p_route = subparsers.add_parser("route", help="Scrape full timetable routes, halts, and platforms")
    p_route.add_argument("--trains", type=str, help="Comma-separated train numbers (e.g. 12301,12002)")
    p_route.add_argument("--limit", type=int, help="Limit number of trains to scrape from catalog")
    p_route.add_argument("--no-resume", action="store_true", help="Do not skip already completed targets")
    p_route.set_defaults(func=cmd_route)

    # coach
    p_coach = subparsers.add_parser("coach", help="Scrape coach compositions and rake types (LHB/ICF)")
    p_coach.add_argument("--trains", type=str, help="Comma-separated train numbers")
    p_coach.add_argument("--limit", type=int, help="Limit number of trains to scrape")
    p_coach.add_argument("--no-resume", action="store_true", help="Do not skip completed targets")
    p_coach.set_defaults(func=cmd_coach)

    # delays
    p_delays = subparsers.add_parser("delays", help="Scrape 1-year historical delay distributions")
    p_delays.add_argument("--trains", type=str, help="Comma-separated train numbers")
    p_delays.add_argument("--limit", type=int, help="Limit number of trains to scrape")
    p_delays.add_argument("--no-resume", action="store_true", help="Do not skip completed targets")
    p_delays.set_defaults(func=cmd_delays)

    # live
    p_live = subparsers.add_parser("live", help="Scrape NTES live running status and delays")
    p_live.add_argument("--trains", type=str, help="Comma-separated train numbers")
    p_live.add_argument("--date", type=str, help="Journey date DD-MM-YYYY (defaults to today)")
    p_live.set_defaults(func=cmd_live)

    # exceptions
    p_ex = subparsers.add_parser("exceptions", help="Scrape NTES rescheduled, cancelled, and diverted lists")
    p_ex.add_argument("--date", type=str, help="Journey date DD-MM-YYYY (defaults to today)")
    p_ex.set_defaults(func=cmd_exceptions)

    # compile
    p_compile = subparsers.add_parser("compile", help="Compile segments route graph and historical delay priors")
    p_compile.set_defaults(func=cmd_compile)

    # export
    p_export = subparsers.add_parser("export", help="Export all tables to CSV in output directory")
    p_export.set_defaults(func=cmd_export)

    # build-dataset
    p_build = subparsers.add_parser("build-dataset", help="Compile ML training dataset matching model schema (ir_train_real.csv)")
    p_build.add_argument("--type", choices=["journey", "point", "all"], default="all", help="Dataset type to build")
    p_build.add_argument("--days", type=int, default=30, help="Days of historical expansion (default: 30)")
    p_build.set_defaults(func=cmd_build_dataset)

    # poll
    p_poll = subparsers.add_parser("poll", help="Run continuous background live harvester")
    p_poll.add_argument("--interval", type=int, default=600, help="Polling interval in seconds (default: 600)")
    p_poll.add_argument("--trains", type=str, help="Comma-separated train numbers to poll")
    p_poll.set_defaults(func=cmd_poll)

    # status
    p_status = subparsers.add_parser("status", help="Show checkpoint state and scraped counts")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
