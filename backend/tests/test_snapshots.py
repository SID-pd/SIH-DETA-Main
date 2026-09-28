"""SnapshotWriter tests — the accuracy-telemetry path (plan §7.2)."""
import os, sqlite3, sys, tempfile, time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.domain.eta_engine import StopEta          # noqa: E402
from app.infra.snapshots import SnapshotWriter     # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))


def stop(code, status, eta=None, delay=None, conf=0.8):
    return StopEta(station_code=code, station_name=code, distance_km=10, platform="1",
                   status=status, scheduled_arrival="2026-09-01T22:32:00+05:30",
                   actual_arrival=None, eta_arrival=eta, delay_minutes=delay,
                   band_p10="2026-09-01T22:33:00+05:30", band_p90="2026-09-01T22:59:00+05:30",
                   source="model", confidence=conf)


def with_writer(fn):
    path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
    w = SnapshotWriter(path); w.start()
    try:
        return fn(w, path)
    finally:
        w.stop()


def rows(path):
    c = sqlite3.connect(path); c.row_factory = sqlite3.Row
    r = [dict(x) for x in c.execute("SELECT * FROM eta_snapshots")]
    c.close(); return r


def test_records_forecasts():
    def go(w, path):
        w.record(train_number="12301", journey_date="2026-09-01", model_version="m0-1.0",
                 stops=[stop("GAYA", "upcoming", "2026-09-01T22:46:00+05:30", 14)])
        time.sleep(1.5)
        r = rows(path)
        assert len(r) == 1, r
        assert r[0]["train_number"] == "12301"
        assert r[0]["delay_minutes"] == 14
        assert r[0]["confidence"] == 0.8
        assert r[0]["band_p90"] is not None
    with_writer(go)


def test_passed_stops_are_not_recorded():
    """A passed stop is an OBSERVATION. Recording it as a prediction would let the
    scorer compare a measurement against itself and report a flattering zero error."""
    def go(w, path):
        w.record(train_number="12301", journey_date="2026-09-01", model_version="m0-1.0",
                 stops=[stop("ASN", "passed", "2026-09-01T19:06:00+05:30", 19),
                        stop("GAYA", "upcoming", "2026-09-01T22:46:00+05:30", 14)])
        time.sleep(1.5)
        r = rows(path)
        assert len(r) == 1
        assert r[0]["station_code"] == "GAYA"
    with_writer(go)


def test_repeated_polling_dedupes_within_a_minute():
    """60s polling must not write a near-identical row every time."""
    def go(w, path):
        s = [stop("GAYA", "upcoming", "2026-09-01T22:46:00+05:30", 14)]
        for _ in range(5):
            w.record(train_number="12301", journey_date="2026-09-01",
                     model_version="m0-1.0", stops=s)
        time.sleep(1.5)
        assert len(rows(path)) == 1
        assert w.stats["deduped"] >= 4
    with_writer(go)


def test_horizon_is_computed():
    def go(w, path):
        future = datetime.now(timezone.utc) + timedelta(minutes=90)
        w.record(train_number="12301", journey_date="2026-09-01", model_version="m0-1.0",
                 stops=[stop("GAYA", "upcoming", future.isoformat(), 14)])
        time.sleep(1.5)
        h = rows(path)[0]["horizon_minutes"]
        assert 85 <= h <= 95, h
    with_writer(go)


def test_stops_without_an_eta_are_skipped():
    def go(w, path):
        w.record(train_number="12301", journey_date="2026-09-01", model_version="m0-1.0",
                 stops=[stop("GAYA", "upcoming", None, None)])
        time.sleep(1.5)
        assert rows(path) == []
    with_writer(go)


def test_disabled_writer_is_a_noop():
    path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
    w = SnapshotWriter(path, enabled=False); w.start()
    w.record(train_number="12301", journey_date="2026-09-01", model_version="m",
             stops=[stop("GAYA", "upcoming", "2026-09-01T22:46:00+05:30", 14)])
    assert not os.path.exists(path)   # telemetry off must not even create the file
    w.stop()


if __name__ == "__main__":
    p = f = 0
    for n, fn in sorted(globals().items()):
        if n.startswith("test_") and callable(fn):
            try:
                fn(); print(f"  PASS  {n}"); p += 1
            except Exception as e:
                print(f"  FAIL  {n}: {type(e).__name__}: {e}"); f += 1
    print(f"\n{p} passed, {f} failed")
    raise SystemExit(1 if f else 0)
