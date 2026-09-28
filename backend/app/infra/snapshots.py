"""
Prediction recorder (plan §7.2).

Every ETA we serve is written to `eta_snapshots`. Later, `score_accuracy.py` joins those
rows against `live_observations` — what actually happened — to produce our real error
distribution by horizon, zone and train type.

Why this must start now, before it is useful
--------------------------------------------
Like the harvester, this is calendar-bound: a prediction not recorded today can never be
scored tomorrow. Without it we can only ever claim our ETA is better than the timetable;
with it we can *show* the MAE curve. For a project whose entire pitch is "more accurate
ETA than the schedule", being unable to quantify our own error is the weakest possible
position — and publishing that curve is the strongest demo artifact available.

Design notes
------------
* Writes are fire-and-forget on a background thread. An accuracy-telemetry failure must
  never slow down or break a user request.
* Its own write connection: the request-path `Repo` is deliberately opened read-only so
  the API cannot mutate reference data. Snapshots are append-only telemetry, not
  reference data, so they get a separate writer rather than loosening that guarantee.
* Deduplicated per (train, date, station, model, minute): polling every 60s would
  otherwise write near-identical rows forever and swamp the real signal.
"""

from __future__ import annotations

import logging
import queue
import sqlite3
import threading
from datetime import datetime, timezone

log = logging.getLogger("darpan.snapshots")

SCHEMA = """
CREATE TABLE IF NOT EXISTS eta_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    train_number    TEXT NOT NULL,
    journey_date    TEXT NOT NULL,
    station_code    TEXT NOT NULL,
    predicted_at    TEXT NOT NULL,
    eta             TEXT,
    delay_minutes   INTEGER,
    model_version   TEXT,
    horizon_minutes INTEGER,
    confidence      REAL,
    band_p10        TEXT,
    band_p90        TEXT,
    provider_eta    TEXT,
    UNIQUE (train_number, journey_date, station_code, model_version, predicted_at)
);
CREATE INDEX IF NOT EXISTS idx_snap_lookup
    ON eta_snapshots(train_number, journey_date, station_code);
CREATE INDEX IF NOT EXISTS idx_snap_time ON eta_snapshots(predicted_at);
"""


class SnapshotWriter:
    """Background, best-effort writer for ETA predictions."""

    def __init__(self, db_path: str, enabled: bool = True, max_queue: int = 2000) -> None:
        self.db_path = db_path
        self.enabled = enabled
        self._q: queue.Queue = queue.Queue(maxsize=max_queue)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.stats = {"queued": 0, "written": 0, "deduped": 0, "dropped": 0, "errors": 0}

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        try:
            conn = sqlite3.connect(self.db_path)
            conn.executescript(SCHEMA)
            # Schema migration: alter table if created with old schema lacking columns
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(eta_snapshots)")
            existing = {row[1] for row in cur.fetchall()}
            for col, ctype in [("confidence", "REAL"), ("band_p10", "TEXT"), ("band_p90", "TEXT"), ("provider_eta", "TEXT")]:
                if col not in existing:
                    try:
                        cur.execute(f"ALTER TABLE eta_snapshots ADD COLUMN {col} {ctype}")
                    except sqlite3.OperationalError:
                        pass
            conn.commit()
            conn.close()
        except sqlite3.Error as exc:
            log.warning("snapshot schema init failed, recorder disabled: %s", exc)
            self.enabled = False
            return
        self._thread = threading.Thread(target=self._run, name="snapshot-writer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _run(self) -> None:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            while not self._stop.is_set():
                try:
                    batch = [self._q.get(timeout=1.0)]
                except queue.Empty:
                    continue
                # Drain whatever else is waiting so a burst costs one transaction.
                while len(batch) < 200:
                    try:
                        batch.append(self._q.get_nowait())
                    except queue.Empty:
                        break
                try:
                    before = conn.total_changes
                    with conn:
                        conn.executemany(
                            "INSERT OR IGNORE INTO eta_snapshots (train_number,journey_date,"
                            "station_code,predicted_at,eta,delay_minutes,model_version,"
                            "horizon_minutes,confidence,band_p10,band_p90,provider_eta)"
                            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", batch)
                    written = conn.total_changes - before
                    self.stats["written"] += written
                    self.stats["deduped"] += len(batch) - written
                except sqlite3.Error as exc:
                    self.stats["errors"] += 1
                    log.warning("snapshot write failed: %s", exc)
        finally:
            conn.close()

    def record(self, *, train_number: str, journey_date: str | None,
               stops: list, model_version: str, now: datetime | None = None) -> None:
        """
        Queue predictions for the upcoming stops of one train.

        Only stops with an actual estimate are recorded, and the timestamp is truncated
        to the minute so repeated polling inside the same minute collapses to one row
        via the UNIQUE constraint.
        """
        if not self.enabled:
            return
        now = now or datetime.now(timezone.utc)
        predicted_at = now.replace(second=0, microsecond=0).isoformat()
        journey_date = journey_date or now.date().isoformat()

        for s in stops:
            # Record forecasts only. A passed stop is an observation, and belongs to
            # live_observations — recording it here would let the scorer compare a
            # measurement against itself and report a flattering zero error.
            if s.status not in ("upcoming", "current") or not s.eta_arrival:
                continue
            try:
                eta_dt = datetime.fromisoformat(s.eta_arrival)
                horizon = int((eta_dt - now).total_seconds() / 60)
            except (ValueError, TypeError):
                horizon = None

            row = (train_number, journey_date, s.station_code, predicted_at,
                   s.eta_arrival, s.delay_minutes, model_version, horizon,
                   s.confidence, s.band_p10, s.band_p90, s.provider_eta)
            try:
                self._q.put_nowait(row)
                self.stats["queued"] += 1
            except queue.Full:
                # Telemetry is expendable; the request is not.
                self.stats["dropped"] += 1
