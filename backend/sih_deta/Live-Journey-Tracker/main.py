#!/usr/bin/env python3
"""
Indian Railways Live Journey & Telemetry Tracker CLI
Captures real-time GPS telemetry, instantaneous delay, platform predictions,
sectional speeds, and intermediate signaling cabins for dynamic ETA calculation.
"""

import argparse
import logging
import sys
import time
from typing import List, Optional

from storage.telemetry_db import TelemetryDatabase
from storage.telemetry_exporter import TelemetryExporter
from trackers.live_journey_scraper import LiveJourneyScraper
from trackers.telemetry_analyzer import TelemetryAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("live_cli")


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


def cmd_track(train_number: str, date: Optional[str] = None):
    """Live track a single train with station progress, platform predictions, and intermediate cabins."""
    train_clean = train_number.strip()
    print("=" * 75)
    print(f"  LIVE TELEMETRY TRACKER: TRAIN {train_clean}")
    print("=" * 75)

    scraper = LiveJourneyScraper()
    raw_data = scraper.fetch_live_status(train_clean, journey_date=date)

    if not raw_data:
        print(f"❌ Could not retrieve live telemetry for train {train_clean}.")
        return 1

    analyzer = TelemetryAnalyzer()
    analysis = analyzer.analyze_snapshot(raw_data)

    db = TelemetryDatabase()
    db.save_telemetry(raw_data, analysis)

    cur_stn = analysis["current_station"]
    next_stn = analysis.get("next_station")
    dest = analysis.get("destination", {})

    print(f"🚆 Train: {raw_data['train_name']} ({train_clean}) | Type: {raw_data.get('train_type')}")
    print(f"📍 Current Position: {cur_stn.get('name')} ({cur_stn.get('code')})")
    print(f"⏱️  Current Delay:     {analysis['instantaneous_delay_mins']} min ({analysis['delay_trend']})")
    print(f"📊 Journey Progress:  {analysis['journey_progress_pct']}% ({cur_stn.get('distance_from_origin_km', 0.0):.1f} / {analysis['total_journey_distance_km']:.1f} km)")

    if next_stn and next_stn.get("code"):
        pf_str = f" [Platform {next_stn['platform']}]" if next_stn.get("platform") else ""
        print(f"➡️  Next Station:      {next_stn.get('name')} ({next_stn.get('code')}){pf_str} in {next_stn.get('distance_km', 0.0):.1f} km @ {next_stn.get('scheduled_arrival')}")

    print(f"🏁 Destination:       {dest.get('name')} ({dest.get('code')})")
    print(f"📶 Intermediate Signaling Cabins Mapped: {raw_data['total_intermediate_cabins']}")

    # Display station stops table
    stops = raw_data.get("schedule", [])
    print("\nStation Progress & Platform Predictions:")
    headers = ["CODE", "STATION NAME", "SCHED ARR", "SCHED DEP", "ARR DELAY", "DEP DELAY", "PF", "DIST", "STATUS"]
    rows = []
    for s in stops:
        if s.get("is_current"):
            status = "▶ CURRENT"
        elif s.get("has_passed"):
            status = "✓ PASSED"
        else:
            status = "○ UPCOMING"

        rows.append([
            s["station_code"],
            s["station_name"],
            s["scheduled_arrival"] or "--",
            s["scheduled_departure"] or "--",
            f"{s['arrival_delay_mins']}m" if s['arrival_delay_mins'] else "--",
            f"{s['departure_delay_mins']}m" if s['departure_delay_mins'] else "--",
            s["expected_platform"] or "--",
            f"{s['distance_km']:.0f}km",
            status,
        ])

    print_table(headers, rows, max_widths=[7, 22, 9, 9, 9, 9, 4, 7, 11])

    # Show sample intermediate cabins
    cabins = raw_data.get("intermediate_cabins", [])
    if cabins:
        print(f"\nSample Intermediate Signaling Cabins & Passing Loops ({len(cabins)} total):")
        c_headers = ["CABIN CODE", "CABIN / BLOCK POST", "APPROACH TO", "DIST (KM)", "COORDINATES (LAT, LON)"]
        c_rows = [
            [
                c["station_code"],
                c["station_name"],
                c["parent_station"],
                f"{c['distance_km']:.1f}",
                f"({c['latitude']:.4f}, {c['longitude']:.4f})" if c.get("latitude") and c.get("longitude") else "--",
            ]
            for c in cabins[:8]
        ]
        print_table(c_headers, c_rows, max_widths=[10, 26, 12, 10, 24])

    print("\n💾 Telemetry snapshot saved to database.")
    return 0


def cmd_monitor(trains_str: str, interval: int = 15, count: int = 1):
    """Monitor a fleet of trains simultaneously."""
    train_list = [t.strip() for t in trains_str.split(",") if t.strip()]
    if not train_list:
        print("❌ Error: Specify at least one train number.")
        return 1

    print("=" * 75)
    print(f"  MONITORING FLEET OF {len(train_list)} TRAINS ({', '.join(train_list)})")
    print("=" * 75)

    scraper = LiveJourneyScraper()
    analyzer = TelemetryAnalyzer()
    db = TelemetryDatabase()

    for iteration in range(1, count + 1):
        if count > 1:
            print(f"\n--- Polling Iteration {iteration}/{count} ---")

        headers = ["TRAIN NO", "TRAIN NAME", "CURRENT POSITION", "DELAY", "NEXT STOP", "PROGRESS", "TREND"]
        rows = []

        for train_num in train_list:
            raw = scraper.fetch_live_status(train_num)
            if not raw:
                rows.append([train_num, "Fetch Error", "--", "--", "--", "--", "Offline"])
                continue

            analysis = analyzer.analyze_snapshot(raw)
            db.save_telemetry(raw, analysis)

            cur_stn = analysis["current_station"]
            next_stn = analysis.get("next_station") or {}

            rows.append([
                train_num,
                raw["train_name"],
                f"{cur_stn.get('name')} ({cur_stn.get('code')})",
                f"{analysis['instantaneous_delay_mins']}m",
                f"{next_stn.get('code') or '--'} in {next_stn.get('distance_km', 0.0):.0f}km",
                f"{analysis['journey_progress_pct']}%",
                analysis["delay_trend"].split()[0],
            ])

        print_table(headers, rows, max_widths=[9, 22, 22, 7, 16, 8, 14])

        if iteration < count:
            time.sleep(interval)

    return 0


def cmd_outer_delays(min_surge: int = 15):
    """Identify trains experiencing severe delay surges near stations (outer signals)."""
    db = TelemetryDatabase()
    delays = db.get_outer_signal_delays(min_delay_surge=min_surge)

    print("=" * 75)
    print(f"  OUTER SIGNAL HOLD-UPS & PLATFORM BOTTLENECK REPORT (Surge >= {min_surge}m)")
    print("=" * 75)

    headers = ["TRAIN NO", "STATION CODE", "STATION NAME", "ARR DELAY", "DEP DELAY", "DELAY SURGE", "PLATFORM"]
    rows = [
        [
            d["train_number"],
            d["station_code"],
            d["station_name"],
            f"{d['arrival_delay_mins']}m",
            f"{d['departure_delay_mins']}m",
            f"+{d['delay_surge']}m",
            d["platform"] or "--",
        ]
        for d in delays
    ]

    print_table(headers, rows, max_widths=[10, 12, 24, 10, 10, 12, 8])
    return 0


def cmd_stats():
    """Display telemetry database overview and fleet punctuality."""
    db = TelemetryDatabase()
    stats = db.get_summary_stats()

    print("=" * 75)
    print("  LIVE JOURNEY & TELEMETRY TRACKER OVERVIEW")
    print("=" * 75)
    print(f"  Active Trains Monitored:       {stats['total_monitored_trains']:,}")
    print(f"  Total Telemetry Snapshots:     {stats['total_snapshots']:,}")
    print(f"  Station Stop Delay Records:    {stats['total_stop_records']:,}")
    print(f"  Intermediate Cabins Mapped:    {stats['total_cabin_points']:,}")
    print(f"  Average Fleet Delay:           {stats['average_delay_mins']} minutes")
    print(f"  ├─ On-Time (<= 15 mins):       {stats['on_time_trains']}")
    print(f"  ├─ Moderate Delay (15-60m):    {stats['moderately_delayed_trains']}")
    print(f"  └─ Severe Delay (> 60 mins):   {stats['severely_delayed_trains']}")
    print("=" * 75)
    return 0


def cmd_export():
    """Export telemetry snapshots to CSV and JSON."""
    db = TelemetryDatabase()
    exporter = TelemetryExporter(db=db)
    print("📄 Exporting live telemetry datasets...")
    files = exporter.export_all()
    for name, path in files.items():
        print(f"  ✓ {name:<18} -> {path}")
    print("✅ Telemetry export completed successfully!")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Indian Railways Live Journey & Telemetry Tracker CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--track", type=str, help="Train number to track live (e.g. 12004, 12301)")
    parser.add_argument("--date", type=str, help="Journey start date (e.g. today, yesterday)")
    parser.add_argument("--monitor", type=str, help="Comma-separated train numbers (e.g. 12004,12301,12043)")
    parser.add_argument("--interval", type=int, default=15, help="Poll interval in seconds for monitor mode")
    parser.add_argument("--count", type=int, default=1, help="Polling iterations for monitor mode")
    parser.add_argument("--outer-delays", action="store_true", help="Report outer signal bottleneck hold-ups")
    parser.add_argument("--surge", type=int, default=15, help="Delay surge threshold in minutes")
    parser.add_argument("--stats", action="store_true", help="Show fleet telemetry statistics")
    parser.add_argument("--export", action="store_true", help="Export telemetry snapshots to CSV/JSON")

    args = parser.parse_args()

    if args.track:
        sys.exit(cmd_track(args.track, date=args.date))
    elif args.monitor:
        sys.exit(cmd_monitor(args.monitor, interval=args.interval, count=args.count))
    elif args.outer_delays:
        sys.exit(cmd_outer_delays(min_surge=args.surge))
    elif args.stats:
        sys.exit(cmd_stats())
    elif args.export:
        sys.exit(cmd_export())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
