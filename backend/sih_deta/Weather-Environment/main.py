#!/usr/bin/env python3
"""
SIH-DETA Weather & Environmental Constraints Engine CLI
Fetches, evaluates, and stores statutory weather speed restrictions along Indian Railways corridors.
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Ensure module path is in sys.path
MODULE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MODULE_DIR))

from collectors.open_meteo_client import OpenMeteoClient
from collectors.station_geo_resolver import StationGeoResolver
from config import DEFAULT_DB_PATH, NOMINAL_TRACK_MPS, TRAINS_DB_PATH
from rules.gsr_rules_engine import GSRRulesEngine
from storage.weather_db import WeatherDatabase
from storage.weather_exporter import WeatherExporter


def print_banner():
    print("""
==============================================================================
  🚆⚡ SIH-DETA: Weather & Environmental Constraints Engine
  Indian Railways General & Subsidiary Rules (G&SR) Physics Evaluator
==============================================================================
    """.strip())
    print()


def format_observation_table(obs_list: list):
    """Prints a formatted ASCII/Unicode table of evaluated weather observations."""
    if not obs_list:
        print("  No weather observations to display.")
        return

    headers = [
        ("STATION", 8),
        ("TIME (IST)", 17),
        ("VIS (m)", 9),
        ("RAIN (mm)", 10),
        ("T_AIR", 7),
        ("T_RAIL", 7),
        ("EFF MPS", 9),
        ("RULE REASON", 28),
    ]

    header_str = " | ".join(f"{title:<{width}}" for title, width in headers)
    divider = "-+-".join("-" * width for _, width in headers)

    print(header_str)
    print(divider)

    for o in obs_list:
        time_short = o["observation_time"]
        if "T" in time_short:
            time_short = time_short.split("T")[1][:5] + " " + time_short.split("T")[0][5:]

        st_code = o["station_code"][:8]
        vis = f"{o['visibility_meters']:.0f}"
        rain = f"{o['precipitation_mm']:.1f}"
        t_air = f"{o['ambient_temp_c']:.1f}°C"
        t_rail = f"{o['estimated_rail_temp_c']:.1f}°C"
        eff_mps = f"{o['effective_mps_cap']} km/h"
        reason = o["throttle_reason"][:28]

        row = (
            f"{st_code:<8} | "
            f"{time_short:<17} | "
            f"{vis:>9} | "
            f"{rain:>10} | "
            f"{t_air:>7} | "
            f"{t_rail:>7} | "
            f"{eff_mps:>9} | "
            f"{reason:<28}"
        )
        print(row)
    print()


def handle_live_station(
    station_code: str,
    resolver: StationGeoResolver,
    client: OpenMeteoClient,
    db: WeatherDatabase,
    has_fog_pass: bool = True,
):
    code = station_code.strip().upper()
    st = resolver.get_station(code)
    if not st:
        print(f"❌ Error: Station '{code}' not found in geographic database.")
        return

    print(f"📡 Querying weather for {code} ({st['name']}) [Lat: {st['lat']:.4f}, Lon: {st['lon']:.4f}]...")

    # Check spatial cluster
    cl = resolver.get_cluster_for_station(code)
    target_lat = cl["centroid_lat"] if cl else st["lat"]
    target_lon = cl["centroid_lon"] if cl else st["lon"]

    raw_obs = client.get_live_weather(target_lat, target_lon)
    evaluated = GSRRulesEngine.evaluate_weather_observation(
        code, raw_obs, station_info=st, nominal_mps=NOMINAL_TRACK_MPS, has_fog_pass=has_fog_pass
    )

    db.save_observation(evaluated)
    print("\n✅ Evaluated Statutory G&SR Environmental Assessment:")
    format_observation_table([evaluated])


def handle_batch_stations(
    station_codes: list,
    resolver: StationGeoResolver,
    client: OpenMeteoClient,
    db: WeatherDatabase,
    has_fog_pass: bool = True,
):
    print(f"📡 Processing batch of {len(station_codes)} stations via spatial cluster centroids...")
    evaluated_records = []

    # Map clusters to reduce API requests
    cluster_weather_cache = {}

    for code in station_codes:
        code_clean = code.strip().upper()
        st = resolver.get_station(code_clean)
        if not st:
            print(f"  ⚠️ Skipping unknown station: {code_clean}")
            continue

        cl = resolver.get_cluster_for_station(code_clean)
        cluster_id = cl["cluster_id"] if cl else f"{st['lat']}_{st['lon']}"
        target_lat = cl["centroid_lat"] if cl else st["lat"]
        target_lon = cl["centroid_lon"] if cl else st["lon"]

        if cluster_id not in cluster_weather_cache:
            cluster_weather_cache[cluster_id] = client.get_live_weather(target_lat, target_lon)

        raw_obs = cluster_weather_cache[cluster_id]
        evaluated = GSRRulesEngine.evaluate_weather_observation(
            code_clean, raw_obs, station_info=st, nominal_mps=NOMINAL_TRACK_MPS, has_fog_pass=has_fog_pass
        )
        evaluated_records.append(evaluated)

    db.save_observations_batch(evaluated_records)
    print(f"✅ Evaluated and saved {len(evaluated_records)} station observations.")
    format_observation_table(evaluated_records)


def handle_route(
    train_number: str,
    resolver: StationGeoResolver,
    client: OpenMeteoClient,
    db: WeatherDatabase,
    has_fog_pass: bool = True,
):
    train_no = train_number.strip()
    print(f"🚆 Fetching scheduled route stops for Train {train_no}...")

    stops = []
    # Try fetching stops from trains.db
    if TRAINS_DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(TRAINS_DB_PATH))
            cur = conn.cursor()
            cur.execute("""
                SELECT station_code, station_name, stop_number 
                FROM train_stops 
                WHERE train_number = ? 
                ORDER BY stop_number ASC;
            """, (train_no,))
            rows = cur.fetchall()
            stops = [r[0] for r in rows]
            conn.close()
        except Exception:
            pass

    # Fallback to predefined high-density corridor if stops table doesn't have it
    if not stops:
        print(f"  ℹ️ Schedule stops not indexed in trains.db for {train_no}; using Delhi-Howrah Trunk Corridor stops.")
        stops = ["NDLS", "CNB", "PRYJ", "DDU", "PNBE", "HWH"]

    print(f"  Route has {len(stops)} stops: {' -> '.join(stops)}")
    handle_batch_stations(stops, resolver, client, db, has_fog_pass=has_fog_pass)


def handle_sync_clusters(resolver: StationGeoResolver, db: WeatherDatabase):
    print("🔄 Synchronizing spatial clusters across nationwide station catalog...")
    clusters = resolver.get_all_clusters()
    total_st = resolver.get_total_stations_count()
    total_cl = resolver.get_total_clusters_count()

    db.save_clusters(clusters)
    reduction = ((total_st - total_cl) / total_st) * 100.0 if total_st else 0.0

    print(f"✅ Successfully clustered {total_st:,} stations into {total_cl:,} spatial grid centroids!")
    print(f"⚡ Network request compression: {reduction:.1f}% reduction in external API overhead.")


def handle_export(db: WeatherDatabase):
    print("📦 Exporting weather feature store matrix...")
    exporter = WeatherExporter()
    csv_file = exporter.export_csv()
    json_file = exporter.export_json()
    count = db.get_total_observations_count()

    print(f"✅ Exported {count:,} observations:")
    print(f"   • CSV:  {csv_file} ({csv_file.stat().st_size / 1024:.1f} KB)")
    print(f"   • JSON: {json_file} ({json_file.stat().st_size / 1024:.1f} KB)")


def main():
    print_banner()

    parser = argparse.ArgumentParser(description="SIH-DETA Weather Constraints & G&SR Rules Engine")
    parser.add_argument(
        "--mode",
        choices=["live", "batch", "route", "sync-clusters", "export"],
        default="live",
        help="Execution mode (default: live)",
    )
    parser.add_argument("--station", type=str, default="NDLS", help="Station code (e.g. NDLS, CNB, MAO)")
    parser.add_argument("--stations", type=str, help="Comma-separated station codes for batch mode")
    parser.add_argument("--train", type=str, default="12301", help="5-digit train number for route scan")
    parser.add_argument(
        "--no-fog-pass",
        action="store_true",
        help="Simulate locomotive WITHOUT GPS FOG-PASS device (enforces 60 km/h cap)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Force offline deterministic mock weather generator",
    )

    args = parser.parse_args()

    # Initialize Components
    resolver = StationGeoResolver()
    client = OpenMeteoClient(use_offline_fallback=True)
    if args.offline:
        # Override to force offline generator
        client.get_live_weather = lambda lat, lon: MockWeatherGenerator.generate(lat, lon, datetime.now())

    db = WeatherDatabase()
    has_fog_pass = not args.no_fog_pass

    if args.mode == "live":
        handle_live_station(args.station, resolver, client, db, has_fog_pass=has_fog_pass)
    elif args.mode == "batch":
        codes = [s.strip() for s in (args.stations or "NDLS,CNB,PRYJ,DDU,PNBE,HWH").split(",") if s.strip()]
        handle_batch_stations(codes, resolver, client, db, has_fog_pass=has_fog_pass)
    elif args.mode == "route":
        handle_route(args.train, resolver, client, db, has_fog_pass=has_fog_pass)
    elif args.mode == "sync-clusters":
        handle_sync_clusters(resolver, db)
    elif args.mode == "export":
        handle_export(db)


if __name__ == "__main__":
    main()
