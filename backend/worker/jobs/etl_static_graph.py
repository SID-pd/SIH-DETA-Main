"""
DARPAN static-graph ETL  (plan §4.2, task W1.7)
================================================
Loads the on-disk Indian Railways dataset into the local relational store, then
derives the route graph (`segments`) that the ETA engine walks.

Why this job is the highest-leverage task in Phase 1
----------------------------------------------------
Every provider call costs quota and ~0.5-2.6s of latency. After this load, these
become free local reads:
    station autocomplete · train search · full route + schedule · route geometry
    · the segment graph used for delay propagation
leaving provider calls for genuinely volatile data only: live position, PNR, boards.
That is what makes the §8 quota budget and the free-tier cost target reachable.

Source files (read-only, never mutated)
---------------------------------------
    stations.json    2.6 MB   GeoJSON FeatureCollection, 8,990 stations (293 w/o geometry)
    trains.json       15 MB   GeoJSON, LineString route geometry + train attributes
    schedules.json    82 MB   flat JSON array of ~1.3M stop rows

Notable data facts discovered while building this (verified, not assumed):
  * schedules.json has NO seq column, but `id` is contiguous per train and starts
    at the origin (the row whose arrival is "None"). seq = rank of id within train.
  * schedules.json lists EVERY timetable point (128 for 12301), whereas the live
    provider returns only booked halts (9 for 12301). The static set is a superset.
  * These static timings drift from live reality (12301 departs 16:55 here, 16:50
    per the provider). Segments are therefore used for TOPOLOGY and as a scheduled
    baseline; live truth always overrides. See `segments.source`.
  * arrival/departure are "HH:MM:SS" or the literal string "None".

Idempotent: safe to re-run. Uses INSERT OR REPLACE inside one transaction per table.

Run:  python services/worker/jobs/etl_static_graph.py [--limit N] [--skip-schedules]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from typing import Iterator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", "..", ".."))
DATA_DIR = os.path.join(REPO_ROOT, "indian-railways-dataset")
DB_DIR = os.path.join(REPO_ROOT, "data")
DB_PATH = os.environ.get("DARPAN_DB", os.path.join(DB_DIR, "darpan.sqlite"))

STATIONS_JSON = os.path.join(DATA_DIR, "stations.json")
TRAINS_JSON = os.path.join(DATA_DIR, "trains.json")
SCHEDULES_JSON = os.path.join(DATA_DIR, "schedules.json")

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Streaming JSON array reader
# ---------------------------------------------------------------------------

def stream_json_array(path: str, array_key: str | None = None,
                      chunk_size: int = 4 << 20) -> Iterator[dict]:
    """
    Yield objects from a large JSON array without loading the file into memory.

    `json.load` on the 82 MB schedules file needs roughly 0.5-1 GB of heap; this
    walks it with `raw_decode` in bounded chunks instead. Dependency-free on
    purpose (no ijson install required to bootstrap the project).

    array_key: for a GeoJSON FeatureCollection pass "features"; None for a file
               that is a bare top-level array.
    """
    decoder = json.JSONDecoder()
    with open(path, "r", encoding="utf-8") as fh:
        buf = fh.read(chunk_size)

        # Position the cursor just past the opening '[' of the target array.
        if array_key:
            marker = f'"{array_key}"'
            while marker not in buf:
                more = fh.read(chunk_size)
                if not more:
                    raise ValueError(f"{array_key} not found in {path}")
                buf += more
            pos = buf.index(marker) + len(marker)
            while buf[pos] not in "[":
                pos += 1
            pos += 1
        else:
            pos = buf.index("[") + 1

        while True:
            # Skip structural whitespace and commas between elements.
            while pos < len(buf) and buf[pos] in " ,\n\r\t":
                pos += 1
            if pos < len(buf) and buf[pos] == "]":
                return
            if pos >= len(buf):
                more = fh.read(chunk_size)
                if not more:
                    return
                buf = buf[pos:] + more
                pos = 0
                continue
            try:
                obj, end = decoder.raw_decode(buf, pos)
            except ValueError:
                # Object straddles the chunk boundary: drop consumed prefix, extend.
                more = fh.read(chunk_size)
                if not more:
                    return
                buf = buf[pos:] + more
                pos = 0
                continue
            yield obj
            pos = end
            # Keep the buffer from growing without bound.
            if pos > chunk_size:
                buf = buf[pos:]
                pos = 0


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS stations (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    state       TEXT,
    zone        TEXT,
    address     TEXT,
    lat         REAL,
    lon         REAL
);
CREATE INDEX IF NOT EXISTS idx_stations_name ON stations(name);
CREATE INDEX IF NOT EXISTS idx_stations_zone ON stations(zone);

CREATE TABLE IF NOT EXISTS trains (
    number          TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    type            TEXT,
    from_code       TEXT,
    from_name       TEXT,
    to_code         TEXT,
    to_name         TEXT,
    departure       TEXT,
    arrival         TEXT,
    duration_min    INTEGER,
    distance_km     REAL,
    zone            TEXT,
    classes         TEXT,
    return_train    TEXT,
    geometry        TEXT      -- GeoJSON LineString coords, JSON-encoded
);
CREATE INDEX IF NOT EXISTS idx_trains_name ON trains(name);
CREATE INDEX IF NOT EXISTS idx_trains_from ON trains(from_code);
CREATE INDEX IF NOT EXISTS idx_trains_to   ON trains(to_code);

CREATE TABLE IF NOT EXISTS schedule_stops (
    train_number    TEXT NOT NULL,
    seq             INTEGER NOT NULL,
    station_code    TEXT NOT NULL,
    station_name    TEXT,
    day             INTEGER,
    arrival         TEXT,      -- "HH:MM:SS" or NULL at origin
    departure       TEXT,      -- "HH:MM:SS" or NULL at destination
    source_id       INTEGER,   -- upstream row id, kept for traceability
    PRIMARY KEY (train_number, seq)
);
CREATE INDEX IF NOT EXISTS idx_sched_station ON schedule_stops(station_code);
CREATE INDEX IF NOT EXISTS idx_sched_train   ON schedule_stops(train_number);

-- The route graph. One row per ordered station pair observed in any timetable.
-- hist_* start NULL and are backfilled from live_observations by the nightly job;
-- NULL means "no measurement yet", which the ETA engine treats as zero added delay
-- rather than inventing a prior.
CREATE TABLE IF NOT EXISTS segments (
    from_code               TEXT NOT NULL,
    to_code                 TEXT NOT NULL,
    sched_minutes_p50       REAL,
    sched_minutes_min       REAL,
    distance_km             REAL,
    n_timetables            INTEGER DEFAULT 0,
    hist_delay_added_p50    REAL,
    hist_delay_added_p90    REAL,
    n_obs                   INTEGER DEFAULT 0,
    source                  TEXT DEFAULT 'schedule',
    PRIMARY KEY (from_code, to_code)
);
CREATE INDEX IF NOT EXISTS idx_seg_from ON segments(from_code);

-- Ground truth harvested from the live provider (plan §4.1). Populated by
-- harvest_live.py, not by this job; created here so the schema lives in one place.
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

-- Predictions we made, so we can score ourselves later (plan §7.2).
CREATE TABLE IF NOT EXISTS eta_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    train_number    TEXT NOT NULL,
    journey_date    TEXT NOT NULL,
    station_code    TEXT NOT NULL,
    predicted_at    TEXT NOT NULL,
    eta             TEXT,
    delay_minutes   INTEGER,
    model_version   TEXT,
    horizon_minutes INTEGER
);
CREATE INDEX IF NOT EXISTS idx_snap_lookup ON eta_snapshots(train_number, journey_date, station_code);

-- Provider call audit for quota accounting (plan §4.1).
CREATE TABLE IF NOT EXISTS provider_calls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    provider    TEXT,
    endpoint    TEXT,
    status      INTEGER,
    latency_ms  INTEGER,
    cache_hit   INTEGER,
    called_at   TEXT
);

CREATE TABLE IF NOT EXISTS etl_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job         TEXT,
    started_at  TEXT,
    finished_at TEXT,
    rows        INTEGER,
    notes       TEXT
);
"""


def connect(path: str = DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _clean(v):
    """Blank-ish upstream values become NULL, never a default."""
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s.lower() in ("none", "null", "na", "n/a", "--"):
        return None
    return s


def load_stations(conn: sqlite3.Connection) -> int:
    print("[1/4] stations.json -> stations")
    t0 = time.time()
    rows, no_geom = [], 0
    for feat in stream_json_array(STATIONS_JSON, "features"):
        p = feat.get("properties") or {}
        code = _clean(p.get("code"))
        if not code:
            continue
        geom = feat.get("geometry")
        lat = lon = None
        if geom and geom.get("type") == "Point":
            coords = geom.get("coordinates") or []
            if len(coords) == 2:
                lon, lat = coords[0], coords[1]   # GeoJSON is [lon, lat]
        if lat is None:
            no_geom += 1
        rows.append((code.upper(), _clean(p.get("name")) or code,
                     _clean(p.get("state")), _clean(p.get("zone")),
                     _clean(p.get("address")), lat, lon))

    with conn:
        conn.executemany(
            "INSERT OR REPLACE INTO stations (code,name,state,zone,address,lat,lon)"
            " VALUES (?,?,?,?,?,?,?)", rows)
    print(f"      {len(rows):,} stations ({no_geom} without coordinates) in {time.time()-t0:.1f}s")
    return len(rows)


def load_trains(conn: sqlite3.Connection) -> int:
    print("[2/4] trains.json -> trains")
    t0 = time.time()
    rows = []
    for feat in stream_json_array(TRAINS_JSON, "features"):
        p = feat.get("properties") or {}
        number = _clean(p.get("number"))
        if not number:
            continue
        geom = feat.get("geometry")
        coords = None
        if geom and geom.get("type") == "LineString":
            coords = json.dumps(geom.get("coordinates"), separators=(",", ":"))
        dur_h = p.get("duration_h") or 0
        dur_m = p.get("duration_m") or 0
        try:
            duration = int(dur_h) * 60 + int(dur_m)
        except (TypeError, ValueError):
            duration = None
        rows.append((
            number, _clean(p.get("name")) or number, _clean(p.get("type")),
            (_clean(p.get("from_station_code")) or "").upper() or None,
            _clean(p.get("from_station_name")),
            (_clean(p.get("to_station_code")) or "").upper() or None,
            _clean(p.get("to_station_name")),
            _clean(p.get("departure")), _clean(p.get("arrival")),
            duration or None, p.get("distance"), _clean(p.get("zone")),
            _clean(p.get("classes")), _clean(p.get("return_train")), coords,
        ))

    with conn:
        conn.executemany(
            "INSERT OR REPLACE INTO trains (number,name,type,from_code,from_name,to_code,"
            "to_name,departure,arrival,duration_min,distance_km,zone,classes,return_train,geometry)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    with_geom = sum(1 for r in rows if r[14])
    print(f"      {len(rows):,} trains ({with_geom:,} with route geometry) in {time.time()-t0:.1f}s")
    return len(rows)


def load_schedules(conn: sqlite3.Connection, limit: int | None = None) -> int:
    """
    Stream ~1.3M stop rows and assign seq per train.

    seq derivation: upstream `id` is contiguous within a train and starts at the
    origin, so ordering by id reproduces route order. We buffer per train rather
    than sorting globally (a global sort of 1.3M rows would need the whole file
    in memory, defeating the streaming reader).
    """
    print("[3/4] schedules.json -> schedule_stops  (streaming, ~1.3M rows)")
    t0 = time.time()
    by_train: dict[str, list] = {}
    scanned = 0

    for row in stream_json_array(SCHEDULES_JSON):
        tn = _clean(row.get("train_number"))
        code = _clean(row.get("station_code"))
        if not tn or not code:
            continue
        by_train.setdefault(tn, []).append((
            int(row.get("id") or 0), code.upper(), _clean(row.get("station_name")),
            row.get("day"), _clean(row.get("arrival")), _clean(row.get("departure")),
        ))
        scanned += 1
        if scanned % 250_000 == 0:
            print(f"      … {scanned:,} rows scanned ({time.time()-t0:.0f}s)")
        if limit and scanned >= limit:
            break

    out = []
    for tn, stops in by_train.items():
        stops.sort(key=lambda r: r[0])          # id order == route order
        for seq, (sid, code, name, day, arr, dep) in enumerate(stops, start=1):
            try:
                day_i = int(day) if day is not None else None
            except (TypeError, ValueError):
                day_i = None
            out.append((tn, seq, code, name, day_i, arr, dep, sid))

    with conn:
        conn.execute("DELETE FROM schedule_stops")   # full refresh keeps seq consistent
        conn.executemany(
            "INSERT OR REPLACE INTO schedule_stops "
            "(train_number,seq,station_code,station_name,day,arrival,departure,source_id)"
            " VALUES (?,?,?,?,?,?,?,?)", out)
    print(f"      {len(out):,} stops across {len(by_train):,} trains in {time.time()-t0:.1f}s")
    return len(out)


def _hhmmss_to_min(s: str | None) -> int | None:
    if not s:
        return None
    parts = s.split(":")
    try:
        h, m = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return h * 60 + m


def derive_segments(conn: sqlite3.Connection) -> int:
    """
    Build the route graph: consecutive timetable stops become directed edges.

    Scheduled traversal minutes = (next.arrival - this.departure), corrected for
    day rollover using the `day` column. A train departing 23:50 on day 1 and
    arriving 00:20 on day 2 takes 30 minutes, not -1410.

    We store p50 and min across all timetables using an edge, because the same
    physical segment is traversed by expresses and passengers at very different
    speeds; the ETA engine wants the distribution, not one number.
    """
    print("[4/4] deriving segments (route graph)")
    t0 = time.time()
    cur = conn.execute(
        "SELECT train_number, seq, station_code, day, arrival, departure"
        " FROM schedule_stops ORDER BY train_number, seq")

    edges: dict[tuple[str, str], list[float]] = {}
    prev = None
    negative = 0
    for tn, seq, code, day, arr, dep in cur:
        if prev and prev[0] == tn and seq == prev[1] + 1:
            _, _, pcode, pday, _, pdep = prev
            dep_min, arr_min = _hhmmss_to_min(pdep), _hhmmss_to_min(arr)
            if dep_min is not None and arr_min is not None:
                delta = arr_min - dep_min
                day_shift = (day or 1) - (pday or 1)
                delta += day_shift * 1440
                if delta < 0:
                    # No day column change but the clock wrapped: assume next day.
                    delta += 1440
                if 0 <= delta <= 1440:
                    edges.setdefault((pcode, code), []).append(float(delta))
                else:
                    negative += 1
        prev = (tn, seq, code, day, arr, dep)

    def pct(vals: list[float], q: float) -> float:
        vals = sorted(vals)
        if not vals:
            return 0.0
        i = min(len(vals) - 1, max(0, int(round(q * (len(vals) - 1)))))
        return vals[i]

    rows = [(f, t, pct(v, 0.5), min(v), None, len(v), None, None, 0, "schedule")
            for (f, t), v in edges.items()]

    with conn:
        conn.execute("DELETE FROM segments")
        conn.executemany(
            "INSERT OR REPLACE INTO segments (from_code,to_code,sched_minutes_p50,"
            "sched_minutes_min,distance_km,n_timetables,hist_delay_added_p50,"
            "hist_delay_added_p90,n_obs,source) VALUES (?,?,?,?,?,?,?,?,?,?)", rows)

    print(f"      {len(rows):,} directed segments in {time.time()-t0:.1f}s"
          f" ({negative:,} implausible durations skipped)")
    return len(rows)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify(conn: sqlite3.Connection) -> bool:
    """Assert the load is usable. A silent partial load is worse than a failure."""
    print("\n[verify]")
    ok = True

    def check(label, sql, predicate, detail=""):
        nonlocal ok
        val = conn.execute(sql).fetchone()[0]
        passed = predicate(val)
        ok = ok and passed
        print(f"  {'PASS' if passed else 'FAIL'}  {label:<44} {val:>10,}  {detail}")
        return val

    check("stations loaded", "SELECT COUNT(*) FROM stations", lambda v: v > 8000)
    check("stations with coordinates", "SELECT COUNT(*) FROM stations WHERE lat IS NOT NULL",
          lambda v: v > 8000)
    check("coords inside India bbox",
          "SELECT COUNT(*) FROM stations WHERE lat IS NOT NULL AND"
          " (lat < 6 OR lat > 38 OR lon < 68 OR lon > 98)",
          lambda v: v == 0, "(expect 0 outliers)")
    check("trains loaded", "SELECT COUNT(*) FROM trains", lambda v: v > 4000)
    check("trains with geometry", "SELECT COUNT(*) FROM trains WHERE geometry IS NOT NULL",
          lambda v: v > 1000)
    check("schedule stops", "SELECT COUNT(*) FROM schedule_stops", lambda v: v > 100_000)
    check("segments derived", "SELECT COUNT(*) FROM segments", lambda v: v > 10_000)
    check("segments with sane duration",
          "SELECT COUNT(*) FROM segments WHERE sched_minutes_p50 < 0 OR sched_minutes_p50 > 1440",
          lambda v: v == 0, "(expect 0)")
    check("schedule stops referencing unknown station",
          "SELECT COUNT(*) FROM schedule_stops s LEFT JOIN stations st"
          " ON s.station_code = st.code WHERE st.code IS NULL",
          lambda v: True, "(informational: dataset drift)")

    # Spot-check a known long-distance route end to end.
    row = conn.execute(
        "SELECT COUNT(*), MIN(seq), MAX(seq) FROM schedule_stops WHERE train_number='12301'"
    ).fetchone()
    print(f"  INFO  12301 stops={row[0]} seq={row[1]}..{row[2]}")
    origin = conn.execute(
        "SELECT station_code, arrival, departure FROM schedule_stops"
        " WHERE train_number='12301' AND seq=1").fetchone()
    if origin:
        print(f"  INFO  12301 origin={origin[0]} arr={origin[1]} dep={origin[2]}"
              f"  (origin must have NULL arrival)")
        if origin[1] is not None:
            print("  WARN  origin has an arrival time — seq ordering may be wrong")
            ok = False
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description="DARPAN static graph ETL")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap schedule rows (smoke test)")
    ap.add_argument("--skip-schedules", action="store_true")
    args = ap.parse_args()

    print("=" * 74)
    print("  DARPAN STATIC GRAPH ETL")
    print("=" * 74)
    for p in (STATIONS_JSON, TRAINS_JSON, SCHEDULES_JSON):
        if not os.path.exists(p):
            print(f"FATAL: missing source file {p}")
            return 1
    print(f"source : {DATA_DIR}\ntarget : {DB_PATH}\n")

    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    t0 = time.time()
    conn = connect()
    conn.executescript(SCHEMA)

    total = 0
    total += load_stations(conn)
    total += load_trains(conn)
    if not args.skip_schedules:
        total += load_schedules(conn, args.limit)
        derive_segments(conn)
    else:
        print("[3/4] skipped\n[4/4] skipped")

    good = verify(conn)
    with conn:
        conn.execute(
            "INSERT INTO etl_runs (job,started_at,finished_at,rows,notes)"
            " VALUES (?,?,?,?,?)",
            ("etl_static_graph", started, time.strftime("%Y-%m-%dT%H:%M:%S"), total,
             f"limit={args.limit} skip_schedules={args.skip_schedules} verified={good}"))

    conn.execute("PRAGMA optimize")
    size_mb = os.path.getsize(DB_PATH) / 1e6
    print(f"\n{'[SUCCESS]' if good else '[COMPLETED WITH WARNINGS]'}"
          f" {time.time()-t0:.1f}s · db {size_mb:.1f} MB")
    conn.close()
    return 0 if good else 2


if __name__ == "__main__":
    raise SystemExit(main())
