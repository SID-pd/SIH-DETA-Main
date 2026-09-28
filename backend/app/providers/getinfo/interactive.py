"""
Interactive Terminal Interface for Get-info.
Runs in a continuous while-True loop with numeric navigation and exits on ESC / '0' / 'q'.
"""

from __future__ import annotations

import os
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

# Optional msvcrt for immediate ESC key detection on Windows
try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

from cli import (
    format_coach,
    format_exceptions,
    format_live,
    format_pnr,
    format_timeline,
)
from fetcher import InfoFetcher


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    print("=" * 64)
    print("  🚄 INDIAN RAILWAYS TRANSIT FETCHER - INTERACTIVE CONSOLE")
    print("=" * 64)
    print("  [1] 📍 Live Running Status (Real-time station, delay, GPS)")
    print("  [2] 🎫 PNR Status Inquiry (10-digit PNR, chart, berths)")
    print("  [3] 🚃 Coach Position & Rake (Engine ➡️ Guard sequence)")
    print("  [4] 💺 Seat / Berth Layout Calculator & ASCII Diagram")
    print("  [5] ⏱️ Journey Timeline (Schedule vs actual stops & delays)")
    print("  [6] ⚠️ Operational Exceptions (Rescheduled / Diverted / Cancelled)")
    print("  [7] 📊 Consolidated All-In-One Dashboard")
    print("  [8] 🧹 Purge Expired Cache Entries")
    print("  [0] 🚪 Exit (or type 'q' / press ESC)")
    print("=" * 64)


def get_user_choice(prompt: str = "👉 Enter your choice [0-8]: ") -> str:
    print(prompt, end="", flush=True)
    
    # Check if immediate ESC key is pressed on Windows console
    if HAS_MSVCRT and sys.stdin.isatty():
        try:
            # Check for non-blocking keypress if available or fall back to input
            pass
        except Exception:
            pass

    try:
        line = sys.stdin.readline()
        if not line:
            return "0"
        return line.strip()
    except (KeyboardInterrupt, EOFError):
        return "0"


def pause():
    print("\nPress ENTER to return to menu...", end="", flush=True)
    try:
        sys.stdin.readline()
    except Exception:
        pass


def run_interactive():
    fetcher = InfoFetcher()

    while True:
        clear_screen()
        print_banner()
        choice = get_user_choice()

        # Exit conditions (0, q, quit, exit, esc, or empty ESC char '\x1b')
        if choice in ("0", "q", "Q", "quit", "QUIT", "exit", "EXIT", "esc", "ESC", "\x1b"):
            print("\n👋 Exiting Indian Railways Transit Fetcher. Goodbye!\n")
            break

        # [1] Live Status
        elif choice == "1":
            print("\n" + "-" * 50)
            print("📍 LIVE TRAIN RUNNING STATUS")
            print("-" * 50)
            train_no = input("Enter 5-digit Train Number (e.g. 12951, 12301, 22436): ").strip()
            if not train_no or train_no.lower() in ("0", "q", "esc", "\x1b"):
                continue
            date_opt = input("Journey Date (today / yesterday / tomorrow or leave blank for today): ").strip() or None
            print("\nFetching live telemetry from multi-provider cascade...")
            res = fetcher.get_live_status(train_no, date=date_opt)
            print(format_live(res))
            pause()

        # [2] PNR Status
        elif choice == "2":
            print("\n" + "-" * 50)
            print("🎫 PNR STATUS INQUIRY")
            print("-" * 50)
            pnr_no = input("Enter 10-digit PNR Number: ").strip()
            if not pnr_no or pnr_no.lower() in ("0", "q", "esc", "\x1b"):
                continue
            print("\nQuerying direct PNR gateways...")
            res = fetcher.get_pnr_status(pnr_no)
            print(format_pnr(res))
            pause()

        # [3] Coach Position
        elif choice == "3":
            print("\n" + "-" * 50)
            print("🚃 COACH POSITION & RAKE COMPOSITION")
            print("-" * 50)
            train_no = input("Enter 5-digit Train Number (e.g. 12951, 12002, 22436): ").strip()
            if not train_no or train_no.lower() in ("0", "q", "esc", "\x1b"):
                continue
            print("\nExtracting rake sequence...")
            res = fetcher.get_coach_position(train_no)
            print(format_coach(res))
            pause()

        # [4] Seat Layout
        elif choice == "4":
            print("\n" + "-" * 50)
            print("💺 SEAT / BERTH LAYOUT CALCULATOR")
            print("-" * 50)
            coach_class = input("Enter Coach Class (e.g. 3A, 2A, SL, 3E, CC, EC, B3, S2): ").strip()
            if not coach_class or coach_class.lower() in ("0", "q", "esc", "\x1b"):
                continue
            seat_str = input("Enter Seat/Berth Number (1-80): ").strip()
            if not seat_str.isdigit():
                print("❌ Invalid seat number.")
                pause()
                continue
            seat_no = int(seat_str)
            res = fetcher.get_seat_layout(coach_class, seat_no)
            print("\n" + "=" * 50)
            print(f"  Coach: {res.coach_type} | Seat #{res.seat_number}")
            print(f"  Berth: {res.berth_type} ({res.berth_code}) | Compartment Bay #{res.bay_number}")
            if res.layout_diagram:
                print(res.layout_diagram)
            print("=" * 50)
            pause()

        # [5] Journey Timeline
        elif choice == "5":
            print("\n" + "-" * 50)
            print("⏱️ COMPLETE JOURNEY TIMELINE")
            print("-" * 50)
            train_no = input("Enter 5-digit Train Number (e.g. 12951, 12301): ").strip()
            if not train_no or train_no.lower() in ("0", "q", "esc", "\x1b"):
                continue
            date_opt = input("Journey Date (or leave blank for today): ").strip() or None
            print("\nCompiling timetable and intermediate delays...")
            res = fetcher.get_timeline(train_no, date=date_opt)
            print(format_timeline(res))
            pause()

        # [6] Exceptions
        elif choice == "6":
            print("\n" + "-" * 50)
            print("⚠️ OPERATIONAL DISRUPTIONS & EXCEPTIONS")
            print("-" * 50)
            print("  1. Rescheduled Trains")
            print("  2. Diverted Trains")
            print("  3. Cancelled Trains")
            ex_choice = input("Select category [1-3] (default: 1): ").strip() or "1"
            type_map = {"1": "rescheduled", "2": "diverted", "3": "cancelled"}
            ex_type = type_map.get(ex_choice, "rescheduled")
            date_opt = input("Date in DD-MM-YYYY (or leave blank for today): ").strip() or None
            print(f"\nFetching official {ex_type} feeds from CRIS NTES...")
            res = fetcher.get_exceptions(date=date_opt, exception_type=ex_type)
            print(format_exceptions(res))
            pause()

        # [7] Consolidated All-In-One Dashboard
        elif choice == "7":
            print("\n" + "-" * 50)
            print("📊 ALL-IN-ONE TRAIN DASHBOARD")
            print("-" * 50)
            train_no = input("Enter 5-digit Train Number (e.g. 12951): ").strip()
            if not train_no or train_no.lower() in ("0", "q", "esc", "\x1b"):
                continue
            date_opt = input("Journey Date (or leave blank for today): ").strip() or None
            print("\nGenerating comprehensive train dossier...")
            live = fetcher.get_live_status(train_no, date=date_opt)
            coach = fetcher.get_coach_position(train_no)
            timeline = fetcher.get_timeline(train_no, date=date_opt)
            print()
            print(format_live(live))
            print()
            print(format_coach(coach))
            print()
            print(format_timeline(timeline))
            pause()

        # [8] Cache Purge
        elif choice == "8":
            print("\n" + "-" * 50)
            print("🧹 CACHE MANAGEMENT")
            print("-" * 50)
            print("  [1] Prune expired cache records only")
            print("  [2] Flush & reset ENTIRE cache database")
            sub = input("Select action [1-2] (default: 1): ").strip() or "1"
            if sub == "2":
                count = fetcher.clear_all_cache()
                print(f"\n✨ Flushed and wiped {count} records from cache database.")
            else:
                count = fetcher.clear_cache()
                print(f"\n🧹 Successfully pruned {count} expired cache records.")
            pause()

        else:
            print("\n❌ Invalid selection. Please enter a number between 0 and 8, or 'q' to exit.")
            pause()


if __name__ == "__main__":
    run_interactive()
