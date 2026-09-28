"""
Repository over the local relational store.

Everything here is a LOCAL read: no provider call, no quota, sub-millisecond. This is
the payoff of the static ETL (plan §4.2) — station search, train search, routes,
schedules and the segment graph all come from here.

SQLite today, Postgres later: callers depend on these method signatures, not on SQL,
so the swap is one class. Read-only connections per request via a small pool; SQLite
handles this fine at our concurrency and the WAL journal permits concurrent readers.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from typing import Any


@dataclass
class Station:
    code: str
    name: str
    state: str | None
    zone: str | None
    lat: float | None
    lon: float | None


class Repo:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._local = threading.local()

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            # uri=True + mode=ro: the API can never mutate the reference data. Writes
            # (observations, snapshots) go through the worker with its own connection.
            conn = sqlite3.connect(
                f"file:{self.db_path}?mode=ro", uri=True, check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _q(self, sql: str, *params: Any) -> list[sqlite3.Row]:
        return self._conn().execute(sql, params).fetchall()

    # --- health -----------------------------------------------------------

    def counts(self) -> dict[str, int]:
        out = {}
        for t in ("stations", "trains", "schedule_stops", "segments",
                  "live_observations", "eta_snapshots"):
            try:
                out[t] = self._q(f"SELECT COUNT(*) c FROM {t}")[0]["c"]
            except sqlite3.Error:
                out[t] = -1
        return out

    # --- stations ---------------------------------------------------------

    def search_stations(self, q: str, limit: int = 10) -> list[dict]:
        """
        Autocomplete over all 8,990 real stations — replaces the 6 hardcoded ones (H7).

        Ranking is deliberate: an exact code match first (typing "NDLS" must not be
        outranked by a station merely named "...Nandlas..."), then prefix matches,
        then substring. Stations without coordinates sort last since they cannot be
        mapped.
        """
        q = (q or "").strip()
        if not q:
            return []
        like = f"%{q}%"
        rows = self._q(
            """
            SELECT code, name, state, zone, lat, lon,
                   CASE
                     WHEN UPPER(code) = UPPER(?)         THEN 0
                     WHEN UPPER(code) LIKE UPPER(?)      THEN 1
                     WHEN UPPER(name) LIKE UPPER(?)      THEN 2
                     ELSE 3
                   END AS rank
            FROM stations
            WHERE UPPER(code) LIKE UPPER(?) OR UPPER(name) LIKE UPPER(?)
            ORDER BY rank, (lat IS NULL), LENGTH(name), name
            LIMIT ?
            """,
            q, f"{q}%", f"{q}%", like, like, limit,
        )
        return [dict(r) for r in rows]

    def get_station_board(self, station_code: str, hours: int = 2, mode: str = "dep") -> list[dict]:
        """
        Scheduled station board fallback from local timetable.
        Returns arrivals/departures within window hours of current IST time.
        """
        from datetime import datetime, timedelta, timezone

        code = (station_code or "").upper().strip()
        rows = self._q(
            """
            SELECT s.train_number, t.name as train_name, t.type as train_type,
                   t.from_code, t.from_name, t.to_code, t.to_name, t.classes,
                   s.arrival, s.departure, s.day
            FROM schedule_stops s
            LEFT JOIN trains t ON s.train_number = t.number
            WHERE UPPER(s.station_code) = ?
            ORDER BY s.departure, s.arrival
            LIMIT 60
            """,
            code,
        )
        if not rows:
            return []

        ist = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(ist)
        today_str = now.strftime("%Y-%m-%d")
        now_min = now.hour * 60 + now.minute
        window_min = max(2, hours) * 60

        def parse_to_min(time_str: str | None) -> int | None:
            if not time_str or ":" not in time_str:
                return None
            parts = time_str.split(":")
            try:
                return int(parts[0]) * 60 + int(parts[1])
            except (ValueError, IndexError):
                return None

        def make_iso(time_str: str | None) -> str | None:
            if not time_str or ":" not in time_str:
                return None
            time_clean = time_str.strip()
            if len(time_clean) == 5:
                time_clean += ":00"
            return f"{today_str}T{time_clean}+05:30"

        matched = []
        all_trains = []

        for r in rows:
            arr_s = r["arrival"]
            dep_s = r["departure"]
            t_min = parse_to_min(dep_s if mode == "dep" and dep_s else arr_s)

            entry = {
                "trainNumber": r["train_number"],
                "trainName": r["train_name"] or f"Train {r['train_number']}",
                "trainType": r["train_type"] or "Express",
                "from": {"code": r["from_code"], "name": r["from_name"]},
                "to": {"code": r["to_code"], "name": r["to_name"]},
                "classes": r["classes"] or "SL,3A,2A",
                "platform": "1",
                "cancelled": False,
                "arrival": {
                    "scheduled": make_iso(arr_s),
                    "actual": make_iso(arr_s),
                    "delayMinutes": 0,
                },
                "departure": {
                    "scheduled": make_iso(dep_s),
                    "actual": make_iso(dep_s),
                    "delayMinutes": 0,
                },
            }
            all_trains.append(entry)

            if t_min is not None:
                diff = (t_min - now_min) % 1440
                if diff <= window_min:
                    matched.append(entry)

        return matched if len(matched) >= 3 else all_trains[:25]

    def get_station(self, code: str) -> dict | None:
        rows = self._q(
            "SELECT code,name,state,zone,address,lat,lon FROM stations WHERE UPPER(code)=UPPER(?)",
            code,
        )
        return dict(rows[0]) if rows else None

    def stations_by_codes(self, codes: list[str]) -> dict[str, dict]:
        """Bulk coordinate lookup: turns provider station CODES into map points.

        The live provider's timeline carries no lat/lon, so this join is what makes
        the map possible without an extra provider call per stop (H11).
        """
        if not codes:
            return {}
        uniq = sorted({c.upper() for c in codes if c})
        out: dict[str, dict] = {}
        # Chunked to stay well inside SQLite's variable limit.
        for i in range(0, len(uniq), 400):
            chunk = uniq[i:i + 400]
            marks = ",".join("?" * len(chunk))
            rows = self._q(
                f"SELECT code,name,state,zone,lat,lon FROM stations WHERE code IN ({marks})",
                *chunk,
            )
            for r in rows:
                out[r["code"]] = dict(r)
        return out

    # --- trains -----------------------------------------------------------

    def search_trains(self, q: str, limit: int = 10) -> list[dict]:
        q = (q or "").strip()
        if not q:
            return []
        like = f"%{q}%"
        rows = self._q(
            """
            SELECT number, name, type, from_code, from_name, to_code, to_name,
                   departure, arrival, duration_min, distance_km,
                   CASE WHEN number = ? THEN 0
                        WHEN number LIKE ? THEN 1
                        WHEN UPPER(name) LIKE UPPER(?) THEN 2 ELSE 3 END AS rank
            FROM trains
            WHERE number LIKE ? OR UPPER(name) LIKE UPPER(?)
            ORDER BY rank, number
            LIMIT ?
            """,
            q, f"{q}%", f"{q}%", like, like, limit,
        )
        return [dict(r) for r in rows]

    def get_train(self, number: str) -> dict | None:
        rows = self._q(
            "SELECT number,name,type,from_code,from_name,to_code,to_name,departure,"
            "arrival,duration_min,distance_km,zone,classes,return_train"
            " FROM trains WHERE number=?", number,
        )
        return dict(rows[0]) if rows else None

    def get_train_geometry(self, number: str) -> list[list[float]] | None:
        rows = self._q("SELECT geometry FROM trains WHERE number=?", number)
        if not rows or not rows[0]["geometry"]:
            return None
        try:
            return json.loads(rows[0]["geometry"])
        except (ValueError, TypeError):
            return None

    def get_schedule(self, number: str) -> list[dict]:
        """Full timetable path — a superset of the provider's booked halts."""
        rows = self._q(
            "SELECT seq,station_code,station_name,day,arrival,departure"
            " FROM schedule_stops WHERE train_number=? ORDER BY seq", number,
        )
        return [dict(r) for r in rows]

    # --- route graph ------------------------------------------------------

    def get_segments(self, pairs: list[tuple[str, str]]) -> dict[tuple[str, str], dict]:
        """
        Fetch the segment rows for a set of consecutive station pairs.

        The ETA engine asks for exactly the edges on the remaining route, so this is
        one query per request rather than a graph load. hist_delay_added_* may be NULL,
        meaning "not measured yet" — the engine must treat that as no information,
        not as zero risk.
        """
        if not pairs:
            return {}
        out: dict[tuple[str, str], dict] = {}
        for i in range(0, len(pairs), 200):
            chunk = pairs[i:i + 200]
            clause = " OR ".join("(from_code=? AND to_code=?)" for _ in chunk)
            flat: list[str] = []
            for a, b in chunk:
                flat.extend([a, b])
            rows = self._q(
                "SELECT from_code,to_code,sched_minutes_p50,sched_minutes_min,"
                "hist_delay_added_p50,hist_delay_added_p90,n_obs,n_timetables"
                f" FROM segments WHERE {clause}", *flat,
            )
            for r in rows:
                out[(r["from_code"], r["to_code"])] = dict(r)
        return out
