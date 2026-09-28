#!/usr/bin/env python3
"""
SIH-DETA Network Anomalies & Stochastic Disruptions CLI
Simulates operational incidents, models junction outer throat queues,
and mines historical delay spikes from nationwide sectional profiles.
"""

import argparse
import sys
from pathlib import Path

# Add module path
MODULE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MODULE_DIR))

from analytics.historical_anomaly_miner import HistoricalAnomalyMiner
from config import BOTTLENECK_JUNCTIONS, DEFAULT_DB_PATH, INCIDENT_CATEGORIES
from models.anomaly_simulator import IncidentSimulator
from models.outer_queue_model import OuterSignalQueueModel
from storage.anomaly_db import AnomalyDatabase
from storage.anomaly_exporter import AnomalyExporter


def print_banner():
    print("""
==============================================================================
  🚨⚡ SIH-DETA: Network Anomalies & Stochastic Incidents Engine
  Indian Railways Non-Nominal Operations & Junction Throats Queue Model
==============================================================================
    """.strip())
    print()


def print_incidents_table(incidents: list):
    if not incidents:
        print("  No operational incidents to display.")
        return

    headers = [
        ("INCIDENT ID", 15),
        ("TRAIN", 8),
        ("SECTION / NODE", 16),
        ("CATEGORY", 26),
        ("DETENTION", 11),
        ("SEVERITY", 10),
        ("SPEED CAP", 10),
    ]

    header_str = " | ".join(f"{title:<{width}}" for title, width in headers)
    divider = "-+-".join("-" * width for _, width in headers)

    print(header_str)
    print(divider)

    for inc in incidents:
        # Handles both dataclass object and sqlite row dict
        if hasattr(inc, "incident_id"):
            iid = inc.incident_id
            trn = inc.train_number
            sec = inc.section_id
            cat = inc.category
            det = f"{inc.detention_minutes:.1f} min"
            sev = inc.severity
            spd = f"{inc.speed_restriction_kmh} km/h" if inc.speed_restriction_kmh else "N/A"
        else:
            iid = inc["incident_id"]
            trn = str(inc["train_number"])
            sec = inc["section_id"]
            cat = inc["category"]
            det = f"{inc['detention_minutes']:.1f} min"
            sev = inc["severity"]
            spd = f"{inc['speed_restriction_kmh']} km/h" if inc.get("speed_restriction_kmh") else "N/A"

        row = (
            f"{iid:<15} | "
            f"{trn:<8} | "
            f"{sec:<16} | "
            f"{cat[:26]:<26} | "
            f"{det:>11} | "
            f"{sev:<10} | "
            f"{spd:>10}"
        )
        print(row)
    print()


def handle_simulate(category: str, section: str, train: str, db: AnomalyDatabase):
    print(f"🚨 Simulating calibrated incident [{category}] in section [{section}]...")
    inc = IncidentSimulator.generate_incident(category, section, train_number=train)
    db.save_incident(inc)
    print(f"\n✅ Generated and recorded Incident:")
    print_incidents_table([inc])
    print(f"  Details: {inc.description}")


def handle_route(train: str, stops_str: str, priority: int, hour: int, db: AnomalyDatabase):
    stops = [s.strip().upper() for s in stops_str.split(",") if s.strip()]
    print(f"🚆 Analyzing route corridor for Train {train} ({len(stops)} stops)...")
    print(f"   Priority Tier: {priority} | Arrival Peak Hour: {hour:02d}:00 IST")

    incidents = IncidentSimulator.simulate_route_anomalies(
        train_number=train,
        stop_stations=stops,
        arrival_hour=hour,
        priority_tier=priority,
    )

    if incidents:
        db.save_incidents_batch(incidents)
        print(f"\n⚠️ Identified {len(incidents)} stochastic bottlenecks & queue delays:")
        print_incidents_table(incidents)
    else:
        print("✅ Route operates under clear line conditions with zero queue bottlenecks.")


def handle_mine(limit: int, db: AnomalyDatabase):
    print(f"⛏️ Scanning historical sectional delay database for 3-sigma catastrophe spikes...")
    miner = HistoricalAnomalyMiner()
    if not miner.is_available():
        print("❌ Historical database not found at expected path. Ensure historical.db exists.")
        return

    anomalies = miner.mine_sectional_anomalies(min_extra_delay_mins=35.0, limit=limit)
    print(f"✅ Extracted {len(anomalies)} historical 3-sigma delay spikes from nationwide operations:")
    print_incidents_table(anomalies)

    print("\n📊 Top 5 Highest-Variance / Most Volatile Railway Sections:")
    hotspots = miner.get_highest_variance_sections(limit=5)
    for i, h in enumerate(hotspots, 1):
        print(f"   {i}. Section {h['section']:<12} | Std Dev: {h['std_dev_min']:>5.1f}m | Mean Jump: {h['mean_delay_jump_min']:>5.1f}m (Samples: {h['sample_count']:,})")
    print()


def handle_export(db: AnomalyDatabase):
    print("📦 Exporting anomaly feature store matrix...")
    exporter = AnomalyExporter()
    csv_file = exporter.export_csv()
    json_file = exporter.export_json()
    count = db.get_total_incidents_count()

    print(f"✅ Exported {count:,} network incidents:")
    print(f"   • CSV:  {csv_file} ({csv_file.stat().st_size / 1024:.1f} KB)")
    print(f"   • JSON: {json_file} ({json_file.stat().st_size / 1024:.1f} KB)")


def main():
    print_banner()

    parser = argparse.ArgumentParser(description="SIH-DETA Network Anomalies & Stochastic Disruptions")
    parser.add_argument(
        "--mode",
        choices=["simulate", "route", "mine", "list", "export"],
        default="mine",
        help="Execution mode (default: mine)",
    )
    parser.add_argument("--category", choices=list(INCIDENT_CATEGORIES.keys()), default="SIGNAL_FAILURE_AUTO")
    parser.add_argument("--section", type=str, default="CNB-PRYJ", help="Section ID (e.g. CNB-PRYJ) or Station (CNB)")
    parser.add_argument("--train", type=str, default="12301", help="Train number")
    parser.add_argument("--stops", type=str, default="NDLS,CNB,PRYJ,DDU,PNBE,HWH", help="Comma-separated stops")
    parser.add_argument("--priority", type=int, default=1, help="Dispatching Priority (1=Rajdhani, 3=Mail/Exp)")
    parser.add_argument("--hour", type=int, default=8, help="Arrival hour in IST (0 to 23)")
    parser.add_argument("--limit", type=int, default=10, help="Record limit for mining")

    args = parser.parse_args()
    db = AnomalyDatabase()

    if args.mode == "simulate":
        handle_simulate(args.category, args.section, args.train, db)
    elif args.mode == "route":
        handle_route(args.train, args.stops, args.priority, args.hour, db)
    elif args.mode == "mine":
        handle_mine(args.limit, db)
    elif args.mode == "list":
        incidents = db.get_active_incidents()
        print(f"📋 Listing active recorded disruptions ({len(incidents)} total):")
        print_incidents_table(incidents)
    elif args.mode == "export":
        handle_export(db)


if __name__ == "__main__":
    main()
