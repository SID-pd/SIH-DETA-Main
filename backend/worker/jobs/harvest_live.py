"""
Live harvester  (plan §6 W4.1)
==============================
Polls live status for tracked trains and appends every observed stop to
`live_observations`.

**Start this running as early as possible.** It is the only task in Phase 1 whose
output is bounded by CALENDAR TIME rather than effort: Phase 2's per-segment regressor
(M2) can only be as good as the history banked before it is trained. A week of delay
here is a week of training data that cannot be recovered later.

It does double duty:
  1. accumulates ground truth for M2 and for the nightly segment/zone marts
  2. pre-warms the API cache for popular trains, so real users hit a 30ms cached read
     instead of a 1-10s provider call (the cold-latency mitigation in §8)

Quota discipline: the gateway enforces a hard daily budget, and this job is the
biggest consumer. `--max-calls` caps a single run, and the interval x train-count is
what to tune. Defaults are deliberately conservative.

Run once:        python services/worker/jobs/harvest_live.py --once
Run forever:     python services/worker/jobs/harvest_live.py --interval 600
Pick trains:     python services/worker/jobs/harvest_live.py --trains 12301,12002,22436
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", "..", ".."))
DB_PATH = os.environ.get("DARPAN_DB", os.path.join(REPO_ROOT, "data", "darpan.sqlite"))
GATEWAY = os.environ.get("GATEWAY_URL", "http://127.0.0.1:8081")

# Long-distance trains with many halts give the richest per-segment signal per call.
DEFAULT_TRAINS = [
    "12301",  # Howrah Rajdhani      HWH-NDLS, 1449 km
    "12302",  # Howrah Rajdhani (up)
    "12002",  # Bhopal Shatabdi      NDLS-RKMP
    "22436",  # Vande Bharat         NDLS-BSB
    "12951",  # Mumbai Rajdhani      MMCT-NDLS
    "12259",  # Sealdah Duronto
    "12621",  # Tamil Nadu Express   MAS-NDLS
    "12841",  # Coromandel Express
]

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def log(msg: str) -> None:
    print(f"{datetime.now(IST).strftime('%H:%M:%S')} {msg}", flush=True)


def fetch_live(train: str, date: str, timeout: float = 25.0) -> dict | None:
    """Call the gateway (never the vendor directly) — one canonical DTO back."""
    url = f"{GATEWAY}/internal/live?train={train}&date={date}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            err = json.loads(exc.read().decode("utf-8")).get("error", {})
            log(f"  {train}: {err.get('code')} — {err.get('message')}")
        except Exception:
            log(f"  {train}: HTTP {exc.code}")
        return None
    except Exception as exc:  # noqa: BLE001
        log(f"  {train}: gateway unreachable — {type(exc).__name__}: {exc}")
        return None
    if not body.get("ok"):
        return None
    return body.get("data")


def ensure_schema(conn: sqlite3.Connection) -> None:
    """The harvester may run before the API has ever started; create if absent."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS live_observations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            train_number    TEXT NOT NULL,
            journey_date    TEXT NOT NULL,
            station_code    TEXT NOT NULL,
            observed_at     TEXT NOT NULL,
            sched_arrival   TEXT,
            actual_arrival  TEXT,
            delay_minutes   INTEGER,
            status          TEXT,
            source          TEXT DEFAULT 'railkit',
            UNIQUE (train_number, journey_date, station_code, observed_at)
        );
        CREATE INDEX IF NOT EXISTS idx_obs_train ON live_observations(train_number, journey_date);
        CREATE INDEX IF NOT EXISTS idx_obs_station ON live_observations(station_code);
        """
    )


def persist(conn: sqlite3.Connection, train: str, live: dict) -> tuple[int, int]:
    """
    Append observations for stops the train has actually PASSED.

    Only passed stops with a real `actual` arrival are recorded: an upcoming stop's
    `actual` field holds the provider's *projection*, and storing a projection as
    ground truth would poison the training set with the very predictions M2 is meant
    to improve on. This one filter is the difference between a training mart and a
    feedback loop.
    """
    stops = live.get("stops") or []
    journey_date = (live.get("train") or {}).get("journeyDate") or datetime.now(IST).date().isoformat()
    observed_at = (live.get("position") or {}).get("lastUpdateAt") or datetime.now(IST).isoformat()

    rows = []
    for s in stops:
        if s.get("status") != "passed":
            continue
        arr = s.get("arrival") or {}
        if not arr.get("actual"):
            continue
        rows.append((
            train, journey_date, s.get("stationCode"), observed_at,
            arr.get("scheduled"), arr.get("actual"), arr.get("delayMinutes"),
            s.get("status"), "railkit",
        ))

    if not rows:
        return 0, 0
    before = conn.execute("SELECT COUNT(*) FROM live_observations").fetchone()[0]
    with conn:
        # UNIQUE(...observed_at) makes re-polling idempotent: the same snapshot
        # inserted twice is ignored, so a tight interval costs quota but not integrity.
        conn.executemany(
            "INSERT OR IGNORE INTO live_observations (train_number,journey_date,"
            "station_code,observed_at,sched_arrival,actual_arrival,delay_minutes,"
            "status,source) VALUES (?,?,?,?,?,?,?,?,?)", rows)
    after = conn.execute("SELECT COUNT(*) FROM live_observations").fetchone()[0]
    return len(rows), after - before


def harvest_round(conn: sqlite3.Connection, trains: list[str], max_calls: int) -> dict:
    date = datetime.now(IST).strftime("%d-%m-%Y")
    stats = {"calls": 0, "trains_ok": 0, "rows_seen": 0, "rows_new": 0, "failures": 0}

    for train in trains:
        if stats["calls"] >= max_calls:
            log(f"  max-calls={max_calls} reached; stopping this round")
            break
        live = fetch_live(train, date)
        stats["calls"] += 1
        if not live:
            stats["failures"] += 1
            continue
        seen, new = persist(conn, train, live)
        stats["trains_ok"] += 1
        stats["rows_seen"] += seen
        stats["rows_new"] += new
        pos = live.get("position") or {}
        log(f"  {train}: delay={pos.get('delayMinutes')}min at "
            f"{pos.get('currentStationCode')} — {seen} passed stops, {new} new rows")
        time.sleep(0.6)  # gentle pacing; the gateway also caps concurrency

    return stats


def report(conn: sqlite3.Connection) -> None:
    total = conn.execute("SELECT COUNT(*) FROM live_observations").fetchone()[0]
    trains = conn.execute(
        "SELECT COUNT(DISTINCT train_number || journey_date) FROM live_observations").fetchone()[0]
    segments_ready = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT train_number, journey_date FROM live_observations
            GROUP BY train_number, journey_date HAVING COUNT(*) >= 2)
        """
    ).fetchone()[0]
    log(f"  store: {total:,} observations · {trains} train-days · "
        f"{segments_ready} journeys with >=2 stops (usable for segment deltas)")
    if total < 500:
        log("  NOTE: M2 (per-segment regressor) needs weeks of history. "
            "Keep this running daily — see plan section 7.1.")


def main() -> int:
    ap = argparse.ArgumentParser(description="DARPAN live harvester")
    ap.add_argument("--trains", type=str, default=None, help="comma-separated train numbers")
    ap.add_argument("--interval", type=int, default=600, help="seconds between rounds")
    ap.add_argument("--once", action="store_true", help="single round then exit")
    ap.add_argument("--max-calls", type=int, default=40, help="cap provider calls per round")
    args = ap.parse_args()

    trains = ([t.strip() for t in args.trains.split(",") if t.strip()]
              if args.trains else DEFAULT_TRAINS)

    print("=" * 74)
    print("  DARPAN LIVE HARVESTER")
    print("=" * 74)
    print(f"db       : {DB_PATH}\ngateway  : {GATEWAY}")
    print(f"trains   : {', '.join(trains)}")
    print(f"mode     : {'single round' if args.once else f'every {args.interval}s'}\n")

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_schema(conn)

    rounds = 0
    try:
        while True:
            rounds += 1
            t0 = time.time()
            log(f"round {rounds}")
            stats = harvest_round(conn, trains, args.max_calls)
            log(f"  round done in {time.time()-t0:.1f}s: {stats}")
            report(conn)
            if args.once:
                break
            time.sleep(max(60, args.interval))
    except KeyboardInterrupt:
        log("interrupted; shutting down cleanly")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
