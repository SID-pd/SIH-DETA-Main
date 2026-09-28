"""
ETA engine — M0 deterministic delay propagation.
================================================
The algorithmic core of DARPAN (plan §5.3, ADR-005).

**M0 owns every user-facing minute in Phase 1.** The trained artifact in the repo is a
binary journey-level classifier fitted to a SYNTHETIC dataset; using it to produce
arrival clock times would be fabrication wearing a lab coat. So the numbers come from
an explainable walk over the route graph, and the model contributes only a risk
probability and an interval width (see risk_overlay).

Algorithm
---------
Given the live delay observed at the train's current position, walk the remaining
stops in order and carry the delay forward:

    delay[i] = delay[i-1] + segment_added_delay(i-1 -> i) - recovery(i)
    eta[i]   = scheduled_arrival[i] + delay[i]

where
  * `segment_added_delay` comes from measured history on that edge
    (segments.hist_delay_added_p50) and is 0 when n_obs < ETA_SEGMENT_MIN_OBS.
    NULL history means "unmeasured", which must contribute nothing rather than a
    guessed prior.
  * `recovery` is OFF by default. Trains do recover delay in halt padding, but the
    amount is route-specific and we have no measurements until the nightly backfill
    runs. A recovery constant would manufacture optimism, which is the exact failure
    mode ADR-004 forbids.

Pure persistence ("12 minutes late now => ~12 minutes late at each remaining stop")
is therefore the Phase-1 baseline. It is unglamorous and correct far more often than
a schedule-only estimate, which is the incumbent this project exists to beat.

Confidence
----------
`confidence` is an explicitly-labelled HEURISTIC that decays with prediction horizon
and with the number of intervening stops. It is NOT a calibrated probability, and
/v1/meta/model says so. Phase 2's quantile regressor replaces it with a measured
interval (plan §7.1).

Provider cross-check
--------------------
The provider supplies its own projection for upcoming stops. We keep it alongside our
own as `providerEta` and report the divergence rather than silently preferring one.
Two independent estimates that agree is information; disagreement is a signal worth
showing, and it gives us a free accuracy baseline to beat before our own ground truth
has accumulated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


@dataclass
class StopEta:
    station_code: str
    station_name: str | None
    distance_km: float | None
    platform: str | None
    status: str | None
    scheduled_arrival: str | None
    actual_arrival: str | None
    eta_arrival: str | None
    delay_minutes: int | None
    band_p10: str | None
    band_p90: str | None
    source: str                      # observed | model | schedule | unknown
    confidence: float | None
    scheduled_departure: str | None = None
    actual_departure: str | None = None
    provider_eta: str | None = None
    provider_divergence_min: int | None = None
    segment_obs: int = 0
    lat: float | None = None
    lon: float | None = None

    def to_dict(self) -> dict:
        return {
            "stationCode": self.station_code,
            "stationName": self.station_name,
            "distanceKm": self.distance_km,
            "platform": self.platform,
            "status": self.status,
            "scheduled": {
                "arrival": self.scheduled_arrival,
                "departure": self.scheduled_departure,
            },
            "actual": {
                "arrival": self.actual_arrival,
                "departure": self.actual_departure,
            },
            "eta": {
                "arrival": self.eta_arrival,
                "delayMinutes": self.delay_minutes,
                "band": {"p10": self.band_p10, "p90": self.band_p90},
                "source": self.source,
                "confidence": self.confidence,
                "providerArrival": self.provider_eta,
                "providerDivergenceMinutes": self.provider_divergence_min,
                "segmentObservations": self.segment_obs,
            },
            "coordinates": (
                {"lat": self.lat, "lon": self.lon}
                if self.lat is not None and self.lon is not None else None
            ),
        }


@dataclass
class EtaResult:
    stops: list[StopEta] = field(default_factory=list)
    current_delay_minutes: int | None = None
    delay_source: str = "unknown"
    model_version: str = "m0-propagation-1.0"
    notes: list[str] = field(default_factory=list)
    unavailable_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "stops": [s.to_dict() for s in self.stops],
            "currentDelayMinutes": self.current_delay_minutes,
            "delaySource": self.delay_source,
            "engine": self.model_version,
            "notes": self.notes,
        }


def _confidence(horizon_min: float, stops_ahead: int, has_live_delay: bool) -> float:
    """
    Heuristic confidence, documented as such.

    Rationale for the shape: uncertainty grows with time-to-arrival (more chances for
    something to change) and with intervening stops (each halt is a chance to gain or
    lose time). Anchored at 0.92 for an imminent arrival with a live fix, floored at
    0.25 so the UI never implies near-zero knowledge when it does have a live position.
    Without a live delay reading we are effectively quoting the timetable, so the
    ceiling drops hard.
    """
    if not has_live_delay:
        return 0.35
    horizon_penalty = min(0.5, (max(0.0, horizon_min) / 60.0) * 0.055)
    stop_penalty = min(0.25, stops_ahead * 0.018)
    return round(max(0.25, 0.92 - horizon_penalty - stop_penalty), 3)


def _band_minutes(horizon_min: float, stops_ahead: int, segment_obs: int) -> float:
    """
    Half-width of the p10/p90 interval, in minutes.

    Grows ~sqrt-ish with horizon (error accumulates but not linearly — a train hours
    away has time to both lose and recover), plus a per-stop term. Narrows where we
    actually have segment observations, because those edges are measured rather than
    assumed. Replaced by real quantile regression in Phase 2.
    """
    base = 4.0 + 5.5 * (max(0.0, horizon_min) / 60.0) ** 0.65
    base += stops_ahead * 0.8
    if segment_obs >= 20:
        base *= 0.75
    return round(min(base, 90.0), 1)


def _clamp_optimistic(p10: datetime, scheduled: datetime | None,
                      carried_delay: float) -> datetime:
    """
    Keep the optimistic edge of the interval physically plausible.

    A symmetric band around a delayed ETA can dip below the scheduled arrival,
    which would claim a train currently running 14 minutes late might still arrive
    early. Trains recover delay slowly and rarely beat the timetable, so when the
    train is late the p10 edge is floored at the scheduled time.
    """
    if scheduled is None or carried_delay <= 0:
        return p10
    return max(p10, scheduled)


def compute_eta(
    live: dict,
    segments: dict[tuple[str, str], dict],
    station_coords: dict[str, dict] | None = None,
    *,
    recovery_enabled: bool = False,
    segment_min_obs: int = 5,
) -> EtaResult:
    """
    Walk the remaining route and produce a per-stop ETA.

    live      canonical live-status DTO from the gateway
    segments  edge rows for consecutive pairs on the remaining route
    """
    result = EtaResult()
    station_coords = station_coords or {}
    stops_in = live.get("stops") or []
    position = live.get("position") or {}

    carried = position.get("delayMinutes")
    has_live_delay = carried is not None
    if has_live_delay:
        result.current_delay_minutes = int(carried)
        result.delay_source = "live"
    else:
        # No live delay reading: we can still emit the timetable, clearly marked.
        carried = 0
        result.delay_source = "schedule"
        result.notes.append(
            "No live delay reading available; ETAs fall back to the published timetable."
        )
        result.unavailable_fields.append("position.delayMinutes")

    # Anchor for horizon maths: the provider's last update, else now.
    now = _parse(position.get("lastUpdateAt")) or datetime.now(IST)

    # Index of the current position in the stop list.
    curr_code = position.get("currentStationCode") or position.get("lastStationCode")
    dist_covered = position.get("distanceCoveredKm")

    current_idx = -1
    for i, s in enumerate(stops_in):
        if s.get("status") in ("passed", "current"):
            current_idx = i

    # If provider stops didn't explicitly tag status, infer from current station code or distance covered
    if current_idx == -1 and (curr_code or dist_covered is not None):
        if curr_code:
            for i, s in enumerate(stops_in):
                if s.get("stationCode") == curr_code:
                    current_idx = i
                    break
        if current_idx == -1 and dist_covered is not None and dist_covered > 0:
            for i, s in enumerate(stops_in):
                s_dist = s.get("distanceKm")
                if s_dist is not None and s_dist <= dist_covered:
                    current_idx = i

    upcoming_seen = 0
    prev_code: str | None = None

    for i, s in enumerate(stops_in):
        code = s.get("stationCode")
        arr = s.get("arrival") or {}
        dep = s.get("departure") or {}
        sched = _parse(arr.get("scheduled"))
        actual = _parse(arr.get("actual"))
        status = s.get("status")

        # Infer status if missing or default
        s_dist = float(s.get("distanceKm") or 0.0)
        is_curr = bool(curr_code and code and code.upper() == curr_code.upper())
        if not status or status == "upcoming":
            if is_curr:
                status = "current"
            elif dist_covered is not None and dist_covered > 0:
                if s_dist < dist_covered:
                    status = "passed"
                else:
                    status = "upcoming"
            elif current_idx >= 0:
                if i < current_idx:
                    status = "passed"
                elif i == current_idx:
                    status = "current"
                else:
                    status = "upcoming"
            elif i == 0 and (dist_covered == 0 or dist_covered is None):
                status = "current"
            else:
                status = "upcoming"

        coords = station_coords.get((code or "").upper(), {})

        seg = segments.get((prev_code, code)) if prev_code and code else None
        seg_obs = int(seg.get("n_obs") or 0) if seg else 0

        # An origin station has no arrival at all — only a departure. Treat a passed
        # stop as observed if EITHER leg has an actual time, otherwise the origin
        # falls through to the estimate branch and gets tagged with the carried
        # delay (the UI showed "Howrah Jn … +14m" for a station already departed).
        dep_sched = _parse(dep.get("scheduled"))
        dep_actual = _parse(dep.get("actual"))
        is_origin = sched is None and dep_sched is not None
        effective_sched = sched or dep_sched

        if status == "passed":
            # Already happened: report the observation, do not model it.
            observed_delay = arr.get("delayMinutes")
            if observed_delay is None:
                observed_delay = dep.get("delayMinutes")
            if observed_delay is None and effective_sched is not None and (actual is not None or dep_actual is not None):
                observed_delay = round(((actual or dep_actual) - effective_sched).total_seconds() / 60)
            shown = actual or dep_actual or effective_sched
            result.stops.append(StopEta(
                station_code=code, station_name=s.get("stationName"),
                distance_km=s.get("distanceKm"), platform=s.get("platform"),
                status=status,
                scheduled_arrival=_iso(sched or (dep_sched if is_origin else None)),
                actual_arrival=_iso(actual or (shown if is_origin else None)),
                eta_arrival=_iso(shown),
                scheduled_departure=_iso(dep_sched),
                actual_departure=_iso(dep_actual or (shown if is_origin else None)),
                delay_minutes=int(observed_delay) if observed_delay is not None else None,
                band_p10=None, band_p90=None, source="observed", confidence=1.0,
                segment_obs=seg_obs,
                lat=coords.get("lat"), lon=coords.get("lon"),
            ))
            prev_code = code
            continue

        # --- upcoming (or current-but-not-yet-arrived) ---
        upcoming_seen += 1

        # Carry the delay forward, adding measured per-segment delay where we have it.
        if seg and seg_obs >= segment_min_obs and seg.get("hist_delay_added_p50") is not None:
            carried = carried + float(seg["hist_delay_added_p50"])
        if recovery_enabled and seg and seg.get("sched_minutes_p50") and seg.get("sched_minutes_min"):
            slack = float(seg["sched_minutes_p50"]) - float(seg["sched_minutes_min"])
            carried = max(0.0, carried - max(0.0, min(slack, 2.0)))

        delay = int(round(carried))
        eta = effective_sched + timedelta(minutes=delay) if effective_sched else None
        horizon = ((eta - now).total_seconds() / 60.0) if eta else 0.0

        conf = _confidence(horizon, upcoming_seen, has_live_delay)
        half = _band_minutes(horizon, upcoming_seen, seg_obs)

        # The provider's own projection for this stop, kept for cross-check.
        provider_eta = actual or (dep_actual if is_origin else None)
        divergence = None
        if provider_eta is not None and eta is not None:
            divergence = round((eta - provider_eta).total_seconds() / 60)

        result.stops.append(StopEta(
            station_code=code, station_name=s.get("stationName"),
            distance_km=s.get("distanceKm"), platform=s.get("platform"),
            status=status,
            scheduled_arrival=_iso(sched or (dep_sched if is_origin else None)),
            actual_arrival=None,
            eta_arrival=_iso(eta),
            scheduled_departure=_iso(dep_sched),
            actual_departure=_iso(dep_actual),
            delay_minutes=delay if has_live_delay or delay else (0 if effective_sched else None),
            band_p10=_iso(_clamp_optimistic(eta - timedelta(minutes=half), effective_sched, carried)) if eta else None,
            band_p90=_iso(eta + timedelta(minutes=half)) if eta else None,
            source="model" if has_live_delay else "schedule",
            confidence=conf,
            provider_eta=_iso(provider_eta),
            provider_divergence_min=divergence,
            segment_obs=seg_obs,
            lat=coords.get("lat"), lon=coords.get("lon"),
        ))
        prev_code = code

    measured = sum(1 for s in result.stops if s.segment_obs > 0)
    if measured == 0 and result.stops:
        result.notes.append(
            "No per-segment history yet: delay is propagated unchanged (pure persistence). "
            "Accuracy improves once harvest_live.py has accumulated observations."
        )
    return result


def remaining_pairs(live: dict) -> list[tuple[str, str]]:
    """Consecutive (from, to) station pairs on the route — the edges the walk needs."""
    codes = [s.get("stationCode") for s in (live.get("stops") or []) if s.get("stationCode")]
    return [(codes[i], codes[i + 1]) for i in range(len(codes) - 1)]
