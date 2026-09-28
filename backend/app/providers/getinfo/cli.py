"""
Command-Line Interface for Get-info.
Provides interactive and scriptable commands for Live Status, PNR, Coaches, Timelines, and Exceptions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure package root on sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fetcher import InfoFetcher


def format_live(res) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append(f"  🚂 LIVE RUNNING STATUS: {res.train_number} - {res.train_name}")
    lines.append("=" * 60)
    if not res.success:
        lines.append(f"  ❌ Status: {res.status_text}")
        lines.append(f"  Provider: {res.provider}")
        return "\n".join(lines)

    delay_color = "🟢 On Time" if res.delay_minutes <= 0 else f"🔴 Delayed by {res.delay_minutes} min"
    lines.append(f"  📍 Current Station: {res.current_station_name or res.current_station_code or 'Unknown'}")
    if res.next_station_name or res.next_station_code:
        lines.append(f"  ⏩ Next Stop:       {res.next_station_name or res.next_station_code}")
    lines.append(f"  ⏱️ Status:          {res.status_text} ({delay_color})")

    if res.distance_covered_km is not None and res.total_distance_km:
        pct = res.journey_percentage or 0.0
        bar_len = 25
        filled = int((pct / 100) * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        lines.append(f"  📊 Progress:        [{bar}] {pct}% ({res.distance_covered_km:.0f}/{res.total_distance_km:.0f} km)")

    lines.append(f"  📡 Source:          Provider '{res.provider}' {'(Cached)' if res.cached else '(Live)'}")
    lines.append("=" * 60)
    return "\n".join(lines)


def format_pnr(res) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append(f"  🎫 PNR STATUS INQUIRY: {res.pnr}")
    lines.append("=" * 60)
    if not res.success:
        lines.append(f"  ❌ Error: {res.error_message or 'Unable to fetch PNR status.'}")
        lines.append(f"  Provider: {res.provider}")
        return "\n".join(lines)

    lines.append(f"  🚆 Train:       {res.train_number} - {res.train_name or 'N/A'}")
    lines.append(f"  📅 Journey Date: {res.doj or 'N/A'} (Class: {res.travel_class or 'N/A'}, Quota: {res.quota or 'N/A'})")
    lines.append(f"  🚩 Journey:      {res.from_station or 'N/A'} ➡️ {res.to_station or 'N/A'}")
    if res.boarding_station:
        lines.append(f"  🚉 Boarding:     {res.boarding_station} (Platform: {res.expected_platform or 'TBA'})")

    chart_badge = "✅ CHART PREPARED" if res.chart_prepared else "⏳ CHART NOT PREPARED"
    lines.append(f"  📋 Chart Status: {chart_badge}")

    lines.append("-" * 60)
    lines.append(f"  PASSENGERS ({res.passenger_count}):")
    for p in res.passengers:
        coach_berth = f"Coach {p.coach or '-'} / Berth {p.berth or '-'} ({p.berth_type or '-'})"
        lines.append(f"    Passenger #{p.passenger_no}: Booking [{p.booking_status}] ➡️ Current [{p.current_status}] | {coach_berth}")

    if res.coach_position:
        lines.append(f"  🚃 Rake Layout:  {res.coach_position[:60]}...")
    lines.append(f"  📡 Source:       Provider '{res.provider}' {'(Cached)' if res.cached else '(Live)'}")
    lines.append("=" * 60)
    return "\n".join(lines)


def format_coach(res) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append(f"  🚃 RAKE & COACH POSITION: Train {res.train_number}")
    lines.append("=" * 60)
    lines.append(f"  Type: {res.rake_type} | Total Coaches: {res.total_coaches}")
    lines.append("-" * 60)
    lines.append("  Sequence (Engine ➡️ Guard):")

    codes = [c.coach_code for c in res.coach_sequence]
    chunk_size = 8
    for i in range(0, len(codes), chunk_size):
        chunk = codes[i:i + chunk_size]
        boxes = " ─ ".join([f"[{c:^4}]" for c in chunk])
        lines.append(f"    {boxes}")

    lines.append("-" * 60)
    lines.append("  Coach Breakdown:")
    for c in res.coach_sequence:
        lines.append(f"    Pos #{c.position_index:2d}: {c.coach_code:5s} ➡️ {c.coach_category}")

    lines.append(f"  📡 Source: Provider '{res.provider}' {'(Cached)' if res.cached else '(Live)'}")
    lines.append("=" * 60)
    return "\n".join(lines)


def format_timeline(res) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append(f"  ⏱️ TIMELINE & SCHEDULE: {res.train_number} - {res.train_name}")
    lines.append(f"  Route: {res.source} ➡️ {res.destination} | Total Stops: {res.total_stops}")
    lines.append("=" * 70)
    lines.append(f"  {'#':<3} {'Station':<24} {'Sch Arr':<8} {'Sch Dep':<8} {'Delay':<8} {'Halt':<6} {'Dist':<6} {'Plat'}")
    lines.append("-" * 70)

    for s in res.stops:
        stn_label = f"{s.station_name[:17]} ({s.station_code})"
        arr = s.scheduled_arrival or "--:--"
        dep = s.scheduled_departure or "--:--"
        delay_val = s.departure_delay_min if s.departure_delay_min is not None else s.arrival_delay_min
        delay_str = f"+{delay_val}m" if delay_val and delay_val > 0 else ("RT" if delay_val == 0 else "-")
        halt_str = f"{s.halt_minutes}m" if s.halt_minutes else "-"
        dist_str = f"{s.distance_km:.0f}km"
        plat_str = s.platform or "-"
        lines.append(f"  {s.stop_number:<3} {stn_label:<24} {arr:<8} {dep:<8} {delay_str:<8} {halt_str:<6} {dist_str:<6} {plat_str}")

    lines.append("=" * 70)
    return "\n".join(lines)


def format_exceptions(res) -> str:
    lines = []
    lines.append("=" * 65)
    lines.append(f"  ⚠️ OPERATIONAL EXCEPTIONS ({res.exception_type.upper()}) - {res.journey_date}")
    lines.append("=" * 65)

    if res.rescheduled:
        lines.append(f"  RESCHEDULED TRAINS ({len(res.rescheduled)}):")
        for r in res.rescheduled[:20]:
            lines.append(f"    🚆 {r.train_number} {r.train_name[:20]}: {r.source} ➡️ {r.destination} | Sch: {r.original_departure} ➡️ Rev: {r.rescheduled_departure} (Late: {r.delay_hours_mins})")
    elif res.diverted:
        lines.append(f"  DIVERTED TRAINS ({len(res.diverted)}):")
        for d in res.diverted[:20]:
            skipped = ", ".join(d.stations_skipped[:4])
            lines.append(f"    🔀 {d.train_number} {d.train_name[:20]}: Div {d.diverted_from} ➡️ {d.diverted_to} | Skipped: [{skipped}]")
    elif res.cancelled:
        lines.append(f"  CANCELLED TRAINS ({len(res.cancelled)}):")
        for c in res.cancelled[:20]:
            lines.append(f"    🚫 {c.train_number} {c.train_name[:20]}: {c.cancellation_type} Cancelled ({c.from_station} ➡️ {c.to_station})")
    else:
        lines.append("  No exceptions recorded for this date.")

    lines.append("=" * 65)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Get-info: High-Reliability Indian Railways Information Fetcher")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # live
    p_live = subparsers.add_parser("live", help="Fetch real-time train running status")
    p_live.add_argument("train", help="5-digit train number (e.g. 12951)")
    p_live.add_argument("--date", default=None, help="Journey date: today, yesterday, tomorrow, or DD-MM-YYYY")
    p_live.add_argument("--json", action="store_true", help="Output raw JSON")

    # pnr
    p_pnr = subparsers.add_parser("pnr", help="Fetch 10-digit PNR booking and current status")
    p_pnr.add_argument("pnr", help="10-digit PNR number")
    p_pnr.add_argument("--json", action="store_true", help="Output raw JSON")

    # coach
    p_coach = subparsers.add_parser("coach", help="Fetch rake composition and coach positions")
    p_coach.add_argument("train", help="5-digit train number")
    p_coach.add_argument("--json", action="store_true", help="Output raw JSON")

    # seat
    p_seat = subparsers.add_parser("seat", help="Calculate exact berth type & bay for coach and seat number")
    p_seat.add_argument("coach_type", help="Coach type (e.g. 3A, 2A, SL, 3E, CC, EC, B3)")
    p_seat.add_argument("seat_number", type=int, help="Seat / berth number")
    p_seat.add_argument("--json", action="store_true", help="Output raw JSON")

    # timeline
    p_timeline = subparsers.add_parser("timeline", help="Fetch complete station-by-station schedule timeline")
    p_timeline.add_argument("train", help="5-digit train number")
    p_timeline.add_argument("--date", default=None, help="Journey date")
    p_timeline.add_argument("--json", action="store_true", help="Output raw JSON")

    # exceptions
    p_ex = subparsers.add_parser("exceptions", help="Fetch rescheduled, diverted, or cancelled trains")
    p_ex.add_argument("--type", default="rescheduled", choices=["rescheduled", "diverted", "cancelled"], help="Exception type")
    p_ex.add_argument("--date", default=None, help="Date in DD-MM-YYYY")
    p_ex.add_argument("--json", action="store_true", help="Output raw JSON")

    # all
    p_all = subparsers.add_parser("all", help="Fetch consolidated live, coach, and timeline in one dashboard")
    p_all.add_argument("train", help="5-digit train number")
    p_all.add_argument("--date", default=None, help="Journey date")
    p_all.add_argument("--json", action="store_true", help="Output raw JSON")

    # interactive
    subparsers.add_parser("interactive", help="Start interactive numeric menu console")

    # cache
    p_cache = subparsers.add_parser("clean-cache", help="Prune expired entries from cache")

    args = parser.parse_args()
    if not args.command:
        from interactive import run_interactive
        run_interactive()
        return

    if args.command == "interactive":
        from interactive import run_interactive
        run_interactive()
        return

    fetcher = InfoFetcher()

    if args.command == "live":
        res = fetcher.get_live_status(args.train, date=args.date)
        if args.json:
            print(json.dumps(res.to_dict(), indent=2))
        else:
            print(format_live(res))

    elif args.command == "pnr":
        res = fetcher.get_pnr_status(args.pnr)
        if args.json:
            print(json.dumps(res.to_dict(), indent=2))
        else:
            print(format_pnr(res))

    elif args.command == "coach":
        res = fetcher.get_coach_position(args.train)
        if args.json:
            print(json.dumps(res.to_dict(), indent=2))
        else:
            print(format_coach(res))

    elif args.command == "seat":
        res = fetcher.get_seat_layout(args.coach_type, args.seat_number)
        if args.json:
            print(json.dumps(res.to_dict(), indent=2))
        else:
            print(f"Coach: {res.coach_type} | Seat: {res.seat_number}")
            print(f"Berth: {res.berth_type} ({res.berth_code}) | Bay #{res.bay_number}")
            if res.layout_diagram:
                print(res.layout_diagram)

    elif args.command == "timeline":
        res = fetcher.get_timeline(args.train, date=args.date)
        if args.json:
            print(json.dumps(res.to_dict(), indent=2))
        else:
            print(format_timeline(res))

    elif args.command == "exceptions":
        res = fetcher.get_exceptions(date=args.date, exception_type=args.type)
        if args.json:
            print(json.dumps(res.to_dict(), indent=2))
        else:
            print(format_exceptions(res))

    elif args.command == "all":
        data = fetcher.get_all_info(args.train, date=args.date)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            live = fetcher.live_engine.get_live_status(args.train, date=args.date)
            coach = fetcher.coach_engine.get_coach_position(args.train)
            timeline = fetcher.timeline_engine.get_timeline(args.train, date=args.date)
            print(format_live(live))
            print()
            print(format_coach(coach))
            print()
            print(format_timeline(timeline))

    elif args.command == "clean-cache":
        count = fetcher.clear_cache()
        print(f"Purged {count} expired entries from cache.")


if __name__ == "__main__":
    main()
