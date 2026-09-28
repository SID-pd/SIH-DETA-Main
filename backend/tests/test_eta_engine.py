"""
ETA engine tests — the algorithmic core, so this is where correctness is pinned.

Run:  cd services/api && python -m pytest tests/ -q
      (or: python tests/test_eta_engine.py  for a dependency-free run)

Covers the cases real provider data actually produced, including two bugs found by
running against a live train (12301 Howrah Rajdhani) rather than a fixture:
  * a passed ORIGIN has no arrival leg, only a departure
  * a symmetric confidence band around a late ETA implied an early arrival
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.domain.eta_engine import compute_eta, remaining_pairs  # noqa: E402


def stop(code, *, status, sched_arr=None, actual_arr=None, delay=None,
         sched_dep=None, actual_dep=None, dep_delay=None, dist=None, platform=None):
    return {
        "stationCode": code, "stationName": code.title(), "status": status,
        "distanceKm": dist, "platform": platform,
        "arrival": {"scheduled": sched_arr, "actual": actual_arr, "delayMinutes": delay},
        "departure": {"scheduled": sched_dep, "actual": actual_dep, "delayMinutes": dep_delay},
    }


def live_payload(stops, delay=14, last_update="2026-09-01T20:53:00+05:30"):
    return {
        "train": {"number": "12301", "name": "Rajdhani Expres", "journeyDate": "2026-09-01"},
        "position": {"delayMinutes": delay, "lastUpdateAt": last_update,
                     "currentStationCode": "CDB", "lastStationCode": "PNME",
                     "nextStationCode": "GAYA", "speedKmph": None,
                     "distanceCoveredKm": 306, "totalDistanceKm": 1449},
        "stops": stops, "passingPoints": [], "composition": [],
        "unavailableFields": ["position.speedKmph"],
    }


# --- core propagation -------------------------------------------------------

def test_delay_persists_across_remaining_stops():
    """M0 baseline: 14 min late now => ~14 min late at each remaining stop."""
    live = live_payload([
        stop("ASN", status="passed", sched_arr="2026-09-01T18:47:00+05:30",
             actual_arr="2026-09-01T19:06:00+05:30", delay=19),
        stop("GAYA", status="upcoming", sched_arr="2026-09-01T22:32:00+05:30"),
        stop("NDLS", status="upcoming", sched_arr="2026-09-02T10:05:00+05:30"),
    ])
    res = compute_eta(live, {})
    upcoming = [s for s in res.stops if s.status == "upcoming"]
    assert [s.delay_minutes for s in upcoming] == [14, 14]
    # ETA = scheduled + carried delay
    assert upcoming[0].eta_arrival.startswith("2026-09-01T22:46")
    assert upcoming[1].eta_arrival.startswith("2026-09-02T10:19")
    assert res.current_delay_minutes == 14
    assert res.delay_source == "live"


def test_passed_stops_report_observation_not_estimate():
    live = live_payload([
        stop("ASN", status="passed", sched_arr="2026-09-01T18:47:00+05:30",
             actual_arr="2026-09-01T19:06:00+05:30", delay=19),
    ])
    s = compute_eta(live, {}).stops[0]
    assert s.source == "observed"
    assert s.confidence == 1.0
    assert s.delay_minutes == 19          # the observation, not the carried 14
    assert s.band_p10 is None             # no interval on something already measured


def test_passed_origin_uses_departure_not_arrival():
    """
    Regression: an origin has NO arrival leg. It previously fell through to the
    estimate branch and was rendered as "+14m" for a station already departed.
    """
    live = live_payload([
        stop("HWH", status="passed", sched_dep="2026-09-01T16:55:00+05:30",
             actual_dep="2026-09-01T16:55:00+05:30", dep_delay=0, platform="9"),
        stop("GAYA", status="upcoming", sched_arr="2026-09-01T22:32:00+05:30"),
    ])
    origin = compute_eta(live, {}).stops[0]
    assert origin.source == "observed", "origin must be treated as observed, not estimated"
    assert origin.delay_minutes == 0, "origin departed on time; must not inherit +14"
    assert origin.actual_arrival is not None
    assert origin.scheduled_arrival is not None  # falls back to the departure time


def test_band_never_implies_early_arrival_when_late():
    """
    Regression: NDLS (14 min late, ~13h out) produced a p10 of 09:40 against a
    10:05 scheduled arrival — claiming a late train might arrive 25 min early.
    """
    live = live_payload([
        stop("NDLS", status="upcoming", sched_arr="2026-09-02T10:05:00+05:30"),
    ], delay=14)
    s = compute_eta(live, {}).stops[0]
    assert s.band_p10 >= "2026-09-02T10:05:00+05:30", (
        f"p10 {s.band_p10} is earlier than the scheduled arrival for a late train")
    assert s.band_p90 > s.eta_arrival  # pessimistic edge still opens up


def test_band_widens_with_horizon():
    """A stop 13 hours out must carry a wider interval than one 2 hours out."""
    live = live_payload([
        stop("GAYA", status="upcoming", sched_arr="2026-09-01T22:32:00+05:30"),
        stop("NDLS", status="upcoming", sched_arr="2026-09-02T10:05:00+05:30"),
    ])
    near, far = compute_eta(live, {}).stops
    near_w = (near.band_p90 or "") > "" and near.band_p90
    assert near.confidence > far.confidence, "confidence must decay with horizon"
    # width comparison via p90 offset from the point estimate
    from datetime import datetime
    w = lambda s: (datetime.fromisoformat(s.band_p90) - datetime.fromisoformat(s.eta_arrival))
    assert w(far) > w(near), "interval must widen with horizon"


# --- degraded inputs --------------------------------------------------------

def test_missing_live_delay_falls_back_to_timetable_and_says_so():
    """No live reading => schedule-only, flagged, with low confidence. Never invented."""
    live = live_payload([
        stop("GAYA", status="upcoming", sched_arr="2026-09-01T22:32:00+05:30"),
    ], delay=None)
    res = compute_eta(live, {})
    assert res.delay_source == "schedule"
    assert "position.delayMinutes" in res.unavailable_fields
    assert res.stops[0].source == "schedule"
    assert res.stops[0].confidence == 0.35
    assert any("timetable" in n.lower() for n in res.notes)


def test_no_segment_history_is_disclosed():
    live = live_payload([stop("GAYA", status="upcoming", sched_arr="2026-09-01T22:32:00+05:30")])
    res = compute_eta(live, {})
    assert any("pure persistence" in n for n in res.notes), (
        "the engine must state when it has no measured segment history")


def test_segment_history_adds_delay_only_above_min_obs():
    """Measured edges contribute; under-observed ones must contribute nothing."""
    stops = [
        stop("PNME", status="passed", sched_arr="2026-09-01T20:30:00+05:30",
             actual_arr="2026-09-01T20:44:00+05:30", delay=14),
        stop("GAYA", status="upcoming", sched_arr="2026-09-01T22:32:00+05:30"),
    ]
    thin = {("PNME", "GAYA"): {"hist_delay_added_p50": 9.0, "n_obs": 2}}
    thick = {("PNME", "GAYA"): {"hist_delay_added_p50": 9.0, "n_obs": 40}}

    assert compute_eta(live_payload(stops), thin, segment_min_obs=5).stops[1].delay_minutes == 14
    assert compute_eta(live_payload(stops), thick, segment_min_obs=5).stops[1].delay_minutes == 23


def test_null_segment_history_contributes_nothing():
    stops = [
        stop("PNME", status="passed", sched_arr="2026-09-01T20:30:00+05:30",
             actual_arr="2026-09-01T20:44:00+05:30", delay=14),
        stop("GAYA", status="upcoming", sched_arr="2026-09-01T22:32:00+05:30"),
    ]
    segs = {("PNME", "GAYA"): {"hist_delay_added_p50": None, "n_obs": 99}}
    assert compute_eta(live_payload(stops), segs).stops[1].delay_minutes == 14


def test_empty_stop_list_does_not_crash():
    res = compute_eta(live_payload([]), {})
    assert res.stops == []


def test_midnight_crossing_keeps_next_day_date():
    """A 1,449 km overnight run arrives the following day; the date must survive."""
    live = live_payload([
        stop("DDU", status="upcoming", sched_arr="2026-09-02T00:43:00+05:30"),
    ])
    s = compute_eta(live, {}).stops[0]
    assert s.eta_arrival.startswith("2026-09-02T00:57")


# --- provider cross-check ---------------------------------------------------

def test_provider_projection_is_kept_for_cross_check():
    """
    On an UPCOMING stop the provider's `actual` is its own projection. We record it
    and the divergence instead of silently preferring either estimate.
    """
    live = live_payload([
        stop("GAYA", status="upcoming", sched_arr="2026-09-01T22:32:00+05:30",
             actual_arr="2026-09-01T22:40:00+05:30"),
    ])
    s = compute_eta(live, {}).stops[0]
    assert s.provider_eta.startswith("2026-09-01T22:40")
    assert s.eta_arrival.startswith("2026-09-01T22:46")
    assert s.provider_divergence_min == 6   # we are 6 min more pessimistic


# --- graph helper -----------------------------------------------------------

def test_remaining_pairs_builds_consecutive_edges():
    live = live_payload([
        stop("HWH", status="passed"), stop("ASN", status="passed"),
        stop("GAYA", status="upcoming"),
    ])
    assert remaining_pairs(live) == [("HWH", "ASN"), ("ASN", "GAYA")]


def test_station_coordinates_are_joined_for_mapping():
    live = live_payload([stop("GAYA", status="upcoming", sched_arr="2026-09-01T22:32:00+05:30")])
    coords = {"GAYA": {"lat": 24.79, "lon": 85.0}}
    s = compute_eta(live, {}, coords).stops[0]
    assert (s.lat, s.lon) == (24.79, 85.0)


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
                passed += 1
            except AssertionError as exc:
                print(f"  FAIL  {name}: {exc}")
                failed += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
