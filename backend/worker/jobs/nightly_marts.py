"""
Nightly marts  (plan §6 W4.3)
=============================
Turns raw harvested observations into the aggregates the ETA engine and the risk
model actually read. This job is what closes the loop:

    harvest_live.py  ->  live_observations  ->  [THIS JOB]  ->  segments.hist_delay_added
                                                            ->  zone_stats
                                                                  |
                                                                  v
                                             eta_engine stops doing pure persistence
                                             and starts using measured per-segment behaviour

Until this has real data, `segments.hist_delay_added_p50` stays NULL and the ETA
engine correctly treats that as "no information" rather than assuming zero risk.
The engine only trusts an edge once it has ETA_SEGMENT_MIN_OBS observations, so these
numbers earn their way in gradually.

What it computes
----------------
1. segments.hist_delay_added_p50 / _p90 / n_obs
     For each consecutive station pair observed on the same journey, the DELTA in
     delay across that segment (delay_at_B - delay_at_A). That delta — not the
     absolute delay — is the quantity M0 needs, because absolute delay is already
     carried forward by the walk.

2. zone_stats.congestion_index / severity
     Per (zone, month) mean delay, normalised. Replaces the synthetic Kaggle
     zone indices with OUR measurements for the risk model's features.

Run:  python services/worker/jobs/nightly_marts.py [--min-obs 3] [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", "..", ".."))
DB_PATH = os.environ.get("DARPAN_DB", os.path.join(REPO_ROOT, "data", "darpan.sqlite"))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def pct(vals: list[float], q: float) -> float:
    vals = sorted(vals)
    if not vals:
        return 0.0
    i = min(len(vals) - 1, max(0, int(round(q * (len(vals) - 1)))))
    return vals[i]


def ensure_zone_stats(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS zone_stats (
            zone_abbr           TEXT NOT NULL,
            month               INTEGER NOT NULL,
            congestion_index    REAL,
            fog_index           REAL,
            severity            REAL,
            mean_delay_minutes  REAL,
            n_obs               INTEGER,
            updated_at          TEXT,
            PRIMARY KEY (zone_abbr, month)
        );
        """
    )


def rebuild_segment_stats(conn: sqlite3.Connection, min_obs: int, dry_run: bool) -> int:
    """
    Derive per-segment delay DELTAS from consecutive observations on the same journey.

    Ordering within a journey comes from `schedule_stops.seq` where the station is
    known to the static graph; observations for stations missing from the timetable
    are skipped rather than guessed into an order.
    """
    print("[1/2] segment delay deltas from live_observations")
    t0 = time.time()

    seq_map: dict[tuple[str, str], int] = {
        (r[0], r[1]): r[2]
        for r in conn.execute("SELECT train_number, station_code, seq FROM schedule_stops")
    }

    rows = conn.execute(
        """
        SELECT train_number, journey_date, station_code, delay_minutes
        FROM live_observations
        WHERE delay_minutes IS NOT NULL
        GROUP BY train_number, journey_date, station_code
        HAVING observed_at = MAX(observed_at)      -- latest snapshot per stop
        """
    ).fetchall()

    journeys: dict[tuple[str, str], list[tuple[int, str, int]]] = defaultdict(list)
    unknown = 0
    for train, date, code, delay in rows:
        seq = seq_map.get((train, code))
        if seq is None:
            unknown += 1
            continue
        journeys[(train, date)].append((seq, code, int(delay)))

    deltas: dict[tuple[str, str], list[float]] = defaultdict(list)
    for stops in journeys.values():
        stops.sort()
        for (_, a_code, a_delay), (_, b_code, b_delay) in zip(stops, stops[1:]):
            deltas[(a_code, b_code)].append(float(b_delay - a_delay))

    qualifying = {k: v for k, v in deltas.items() if len(v) >= min_obs}
    print(f"      {len(journeys)} journeys · {len(deltas)} distinct segments observed · "
          f"{len(qualifying)} with >={min_obs} observations"
          f"{f' · {unknown} obs for stations absent from the timetable' if unknown else ''}")

    if dry_run:
        for (a, b), v in list(qualifying.items())[:10]:
            print(f"      {a}->{b}: n={len(v)} p50={pct(v,0.5):+.1f} p90={pct(v,0.9):+.1f} min")
        return 0

    updated = 0
    with conn:
        for (a, b), v in qualifying.items():
            cur = conn.execute(
                "UPDATE segments SET hist_delay_added_p50=?, hist_delay_added_p90=?,"
                " n_obs=?, source='observed' WHERE from_code=? AND to_code=?",
                (round(pct(v, 0.5), 2), round(pct(v, 0.9), 2), len(v), a, b),
            )
            updated += cur.rowcount
    print(f"      updated {updated} segment rows in {time.time()-t0:.1f}s")
    if updated == 0 and qualifying:
        print("      NOTE: observed segments are not in the derived graph — these are "
              "station pairs the timetable does not list as consecutive.")
    return updated


def rebuild_zone_stats(conn: sqlite3.Connection, dry_run: bool) -> int:
    """
    Per (zone, month) delay statistics from our own observations.

    Replaces the synthetic zone_congestion_index / season_severity_score the risk
    model currently imputes. Normalisation: mean delay mapped onto 0..1 with 60 min
    as the practical ceiling — documented so the number is interpretable rather than
    a magic scale.
    """
    print("[2/2] zone statistics")
    rows = conn.execute(
        """
        SELECT st.zone, CAST(strftime('%m', o.journey_date) AS INTEGER) AS month,
               AVG(o.delay_minutes) AS mean_delay, COUNT(*) AS n
        FROM live_observations o
        JOIN stations st ON st.code = o.station_code
        WHERE o.delay_minutes IS NOT NULL AND st.zone IS NOT NULL
        GROUP BY st.zone, month
        """
    ).fetchall()

    if not rows:
        print("      no zone-attributable observations yet (needs stations with a zone)")
        return 0

    out = []
    for zone, month, mean_delay, n in rows:
        congestion = max(0.0, min(1.0, (mean_delay or 0) / 60.0))
        out.append((zone, month, round(congestion, 3), None, round(congestion, 3),
                    round(mean_delay or 0, 2), n, datetime.now().isoformat(timespec="seconds")))

    if dry_run:
        for r in out[:10]:
            print(f"      {r[0]} month={r[1]}: mean={r[5]}min n={r[6]} congestion={r[2]}")
        return 0

    with conn:
        conn.executemany(
            "INSERT OR REPLACE INTO zone_stats (zone_abbr,month,congestion_index,"
            "fog_index,severity,mean_delay_minutes,n_obs,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?)", out)
    print(f"      wrote {len(out)} zone-month rows")
    return len(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="DARPAN nightly marts")
    ap.add_argument("--min-obs", type=int, default=3,
                    help="minimum observations before a segment stat is written")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print("=" * 74)
    print("  DARPAN NIGHTLY MARTS")
    print("=" * 74)
    print(f"db: {DB_PATH}{'  (DRY RUN)' if args.dry_run else ''}\n")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_zone_stats(conn)

    total_obs = conn.execute("SELECT COUNT(*) FROM live_observations").fetchone()[0]
    print(f"observations available: {total_obs:,}\n")

    seg = rebuild_segment_stats(conn, args.min_obs, args.dry_run)
    zones = rebuild_zone_stats(conn, args.dry_run)

    ready = conn.execute("SELECT COUNT(*) FROM segments WHERE n_obs >= 5").fetchone()[0]
    print(f"\nsegments the ETA engine will now trust (n_obs >= 5): {ready:,}")
    if ready == 0:
        print("ETA engine stays on pure persistence until this is non-zero — which is "
              "the correct behaviour, not a failure. Keep harvest_live.py running.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
