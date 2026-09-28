#!/usr/bin/env python3
"""
Indian Railways Station & Halt Scraper CLI
Production-grade cataloging of 8,990+ stations, geospatial coordinates,
NSG/SG/HG categories, junction topologies, and train halt schedules across India.
"""

import argparse
import logging
import sys
from typing import Optional

from scrapers.station_dataset_loader import StationDatasetLoader
from scrapers.station_live_scraper import StationLiveScraper
from storage.db import StationDatabase
from storage.exporter import StationExporter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("station_cli")


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

    # Print header
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


def cmd_sync_master(force: bool = False):
    """Download and sync ~8,990 master Indian Railway stations with production-grade schema."""
    print("=" * 75)
    print("  SYNCING PRODUCTION-GRADE MASTER ALL-INDIA STATIONS & TOPOLOGY")
    print("=" * 75)

    loader = StationDatasetLoader()
    db = StationDatabase()
    exporter = StationExporter(db=db)

    stations = loader.fetch_stations_master(force_download=force)
    if not stations:
        print("❌ Failed to fetch stations dataset.")
        return 1

    print(f"📥 Parsed {len(stations)} stations from master GeoJSON.")
    print("💾 Upserting stations into SQLite database...")
    db.upsert_stations(stations)

    print("📄 Exporting master datasets to CSV and JSON...")
    csv_path = exporter.export_stations_to_csv()
    json_path = exporter.export_stations_to_json()

    print("✅ Master Stations Sync Completed Successfully!")
    print(f"   - Total Stations: {len(stations):,}")
    print(f"   - Database: {db.db_path}")
    print(f"   - CSV Export: {csv_path}")
    print(f"   - JSON Export: {json_path}")
    return 0


def cmd_sync_halts(limit: Optional[int] = None, force: bool = False):
    """Download and sync bulk train halt schedules (~417,000 all-India halts)."""
    print("=" * 75)
    print("  SYNCING BULK TRAIN HALTS & STATION TIMETABLES")
    print("=" * 75)

    loader = StationDatasetLoader()
    db = StationDatabase()
    exporter = StationExporter(db=db)

    print("📥 Loading bulk train halt schedules from cache/download...")
    halts = loader.fetch_schedules_master(force_download=force, limit=limit)
    if not halts:
        print("❌ Failed to fetch train halt schedules.")
        return 1

    print(f"📥 Parsed {len(halts):,} train halt records.")
    print("💾 Upserting halts in batch transactions...")

    # Batch insert to optimize performance
    batch_size = 25000
    total_upserted = 0
    for i in range(0, len(halts), batch_size):
        chunk = halts[i : i + batch_size]
        db.upsert_halts(chunk, update_counts=False)
        total_upserted += len(chunk)
        print(f"   ✓ Ingested {total_upserted:,} / {len(halts):,} halt records...")

    print("🔄 Recalculating station halt counts across all stations...")
    db.update_all_station_halt_counts()

    print("📄 Exporting halt datasets...")
    exporter.export_halts_to_csv()
    exporter.export_halts_to_json()
    exporter.export_stations_to_csv()  # re-export with updated total_halts_count

    print("✅ Bulk Halt Sync Completed Successfully!")
    print(f"   - Total Halts Upserted: {total_upserted:,}")
    return 0


def cmd_scrape_station(station_code: str):
    """Live scrape all train halts for a specific railway station."""
    code = station_code.strip().upper()
    print("=" * 75)
    print(f"  LIVE SCRAPING TRAIN HALTS FOR STATION: {code}")
    print("=" * 75)

    db = StationDatabase()
    station_meta = db.get_station(code)
    if station_meta:
        print(f"🚉 Station: {station_meta['official_name']} ({code}) | State: {station_meta.get('state')} | Zone: {station_meta.get('zone')}")
        print(f"   Division: {station_meta.get('division')} | Category: {station_meta.get('ir_category')} | Platforms: {station_meta.get('platform_count')}")
        print(f"   Coordinates: ({station_meta.get('latitude')}, {station_meta.get('longitude')})")
    else:
        print(f"🚉 Station Code: {code}")

    scraper = StationLiveScraper()
    result = scraper.scrape_station_timetable(code)
    trains = result.get("trains", [])

    if not trains:
        print(f"⚠️ No train halt records found for station {code}.")
        return 1

    print(f"✓ Found {len(trains)} trains halting/passing through {code}.")
    db.upsert_halts(trains, update_counts=True)

    headers = ["TRAIN NO", "TRAIN NAME", "ARR", "DEP", "HALT", "DAYS OF RUN", "CLASSES"]
    rows = [
        [
            t["train_number"],
            t["train_name"],
            t["arrival_time"] or "--",
            t["departure_time"] or "--",
            f"{t['halt_minutes']}m" if t["halt_minutes"] else "--",
            t["days_of_run"],
            t["classes"],
        ]
        for t in trains[:30]
    ]

    print("\nSample Scheduled Trains (First 30):")
    print_table(headers, rows, max_widths=[10, 26, 8, 8, 8, 16, 14])
    if len(trains) > 30:
        print(f"  ... and {len(trains) - 30} more trains stored in database.")

    print(f"\n✅ Successfully saved {len(trains)} train halt records into database.")
    return 0


def cmd_search(query: str, limit: int = 25):
    """Search stations by code, official name, division, city, district, or state."""
    db = StationDatabase()
    results = db.search_stations(query, limit=limit)

    print("=" * 75)
    print(f"  STATION SEARCH RESULTS FOR: '{query}' (Found {len(results)})")
    print("=" * 75)

    headers = ["CODE", "STATION NAME", "STATE", "ZONE", "DIVISION", "CATEGORY", "PF", "HALTS", "STATUS"]
    rows = [
        [
            s["code"],
            s["official_name"],
            s["state"] or "--",
            s["zone"] or "--",
            s["division"] or "--",
            s["ir_category"],
            s["platform_count"],
            s["total_halts_count"],
            "Active" if s["passenger_service"] else "Yard/Chord",
        ]
        for s in results
    ]

    print_table(headers, rows, max_widths=[7, 24, 15, 6, 14, 15, 4, 6, 12])
    return 0


def cmd_halts(station_code: str, limit: int = 50):
    """Display all train halts recorded for a station."""
    code = station_code.strip().upper()
    db = StationDatabase()

    stn = db.get_station(code)
    stn_name = stn["official_name"] if stn else code

    halts = db.get_station_halts(code, limit=limit)
    print("=" * 75)
    print(f"  TRAIN HALTS AT {stn_name} ({code}) - Showing {len(halts)} records")
    print("=" * 75)

    headers = ["TRAIN NO", "TRAIN NAME", "ARR", "DEP", "HALT", "DAY", "DAYS", "SOURCE"]
    rows = [
        [
            h["train_number"],
            h["train_name"],
            h["arrival_time"] or "--",
            h["departure_time"] or "--",
            f"{h['halt_minutes']}m" if h["halt_minutes"] else "--",
            h["day"],
            h["days_of_run"] or "--",
            h["source"],
        ]
        for h in halts
    ]

    print_table(headers, rows, max_widths=[10, 26, 8, 8, 8, 5, 14, 14])
    return 0


def cmd_train(train_number: str):
    """Display all station halts along a train journey."""
    db = StationDatabase()
    halts = db.get_train_halts(train_number)

    print("=" * 75)
    print(f"  STATION HALTS FOR TRAIN: {train_number} ({len(halts)} stops)")
    print("=" * 75)

    if not halts:
        print(f"⚠️ No halt records found for train {train_number}.")
        return 1

    train_name = halts[0].get("train_name", "")
    if train_name:
        print(f"🚆 Train Name: {train_name}")

    headers = ["STN CODE", "STATION NAME", "ARR", "DEP", "HALT", "DAY", "DIVISION", "ZONE"]
    rows = [
        [
            h["station_code"],
            h.get("station_full_name") or h["station_code"],
            h["arrival_time"] or "--",
            h["departure_time"] or "--",
            f"{h['halt_minutes']}m" if h["halt_minutes"] else "--",
            h["day"],
            h.get("division") or "--",
            h.get("zone") or "--",
        ]
        for h in halts
    ]

    print_table(headers, rows, max_widths=[10, 26, 8, 8, 8, 5, 14, 8])
    return 0


def cmd_junctions(limit: int = 40):
    """Display key Indian Railway junctions with divisions and platforms."""
    db = StationDatabase()
    junctions = db.get_junctions(limit=limit)

    print("=" * 75)
    print(f"  MAJOR INDIAN RAILWAY JUNCTIONS & HUBS ({len(junctions)} shown)")
    print("=" * 75)

    headers = ["CODE", "JUNCTION NAME", "STATE", "ZONE", "DIVISION", "CATEGORY", "PF", "HALTS"]
    rows = [
        [
            j["code"],
            j["official_name"],
            j["state"] or "--",
            j["zone"] or "--",
            j["division"] or "--",
            j["ir_category"],
            j["platform_count"],
            j["total_halts_count"],
        ]
        for j in junctions
    ]

    print_table(headers, rows, max_widths=[7, 24, 15, 6, 14, 16, 4, 7])
    return 0


def cmd_stats():
    """Display aggregate statistics of Indian Railways stations and halts."""
    db = StationDatabase()
    stats = db.get_summary_stats()

    print("=" * 75)
    print("  INDIAN RAILWAYS PRODUCTION-GRADE STATION & HALT REPOSITORY")
    print("=" * 75)
    print(f"  Total Network Nodes Cataloged:  {stats['total_stations']:,}")
    print(f"  ├─ Commercial Passenger Stns:   {stats['passenger_stations']:,}")
    print(f"  └─ Freight / Chords / Cabins:   {stats['freight_chord_stations']:,}")
    print(f"  Geocoded (with Lat/Lon):        {stats['geocoded_stations']:,}")
    print(f"  Railway Junctions (3+ lines):   {stats['total_junctions']:,}")
    print(f"  Major Terminals & Central Hubs: {stats['total_terminals']:,}")
    print(f"  Official Halt & Flag Stations:  {stats['total_halt_stations']:,}")
    print(f"  Amrit Bharat Redevelopment:     {stats['amrit_bharat_count']:,} stations")
    print(f"  Total Train Halt Records:       {stats['total_train_halts']:,}")
    print(f"  Trains with Mapped Halts:       {stats['trains_with_halts']:,}")

    if stats["category_distribution"]:
        print("\nStation Classification (NSG / SG / HG Framework):")
        for item in stats["category_distribution"][:7]:
            print(f"  • {item['ir_category']:<26} : {item['count']:,} stations")

    print("\nTop Railway Zones by Station Density:")
    for item in stats["zone_distribution"][:8]:
        print(f"  • {item['zone']:<8} : {item['count']:,} stations")

    print("\nTop Railway Divisions:")
    for item in stats["division_distribution"][:8]:
        print(f"  • {item['division']:<20} : {item['count']:,} stations")

    print("\nTop States by Railway Station Count:")
    for item in stats["state_distribution"][:8]:
        print(f"  • {item['state']:<20} : {item['count']:,} stations")

    if stats["busiest_stations"]:
        print("\nBusiest Stations by Recorded Train Halts:")
        for item in stats["busiest_stations"][:8]:
            print(f"  • {item['code']:<6} ({item['official_name']}) [{item['ir_category']}, {item['platform_count']} PFs]: {item['halt_count']:,} train halts")

    print("=" * 75)
    return 0


def cmd_export():
    """Export database to CSV and JSON."""
    db = StationDatabase()
    exporter = StationExporter(db=db)
    print("📄 Exporting all station and halt tables...")
    files = exporter.export_all()
    for name, path in files.items():
        print(f"  ✓ {name:<18} -> {path}")
    print("✅ Export completed successfully!")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Indian Railways Station & Halt Scraper CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=[
            "sync-master",
            "sync-halts",
            "scrape-station",
            "search",
            "halts",
            "train",
            "junctions",
            "stats",
            "export",
        ],
        help="Execution mode",
    )
    parser.add_argument("--code", type=str, help="Station code (e.g. NDLS, CNB, HWH)")
    parser.add_argument("--train", type=str, help="Train number (e.g. 12043, 12301)")
    parser.add_argument("--query", type=str, help="Search query for stations")
    parser.add_argument("--limit", type=int, help="Record limit for queries / halts")
    parser.add_argument("--force", action="store_true", help="Force redownload ignoring cache")

    args = parser.parse_args()

    if args.mode == "sync-master":
        sys.exit(cmd_sync_master(force=args.force))
    elif args.mode == "sync-halts":
        sys.exit(cmd_sync_halts(limit=args.limit, force=args.force))
    elif args.mode == "scrape-station":
        if not args.code:
            print("❌ Error: --code is required for scrape-station mode (e.g. --code NDLS)")
            sys.exit(1)
        sys.exit(cmd_scrape_station(args.code))
    elif args.mode == "search":
        if not args.query:
            print("❌ Error: --query is required for search mode (e.g. --query Kanpur)")
            sys.exit(1)
        sys.exit(cmd_search(args.query, limit=args.limit or 25))
    elif args.mode == "halts":
        if not args.code:
            print("❌ Error: --code is required for halts mode (e.g. --code CNB)")
            sys.exit(1)
        sys.exit(cmd_halts(args.code, limit=args.limit or 50))
    elif args.mode == "train":
        if not args.train:
            print("❌ Error: --train is required for train mode (e.g. --train 12043)")
            sys.exit(1)
        sys.exit(cmd_train(args.train))
    elif args.mode == "junctions":
        sys.exit(cmd_junctions(limit=args.limit or 40))
    elif args.mode == "stats":
        sys.exit(cmd_stats())
    elif args.mode == "export":
        sys.exit(cmd_export())


if __name__ == "__main__":
    main()
