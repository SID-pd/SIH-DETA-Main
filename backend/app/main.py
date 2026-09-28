"""
DARPAN API — BFF + domain service.

Every response uses the envelope from plan §3:
    {"data": ..., "meta": {source, asOf, provider, confidence, degraded,
                           unavailableFields}, "error": null}

`meta.source` and `meta.degraded` are rendered by the client, which is what
structurally removes defect D2 (fallback-to-fiction): the UI can distinguish live
from cached from stale from schedule-only, and there is no code path that invents data.

Run:  uvicorn app.main:app --port 8001
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.domain import eta_engine
from app.domain.risk_overlay import RiskModel
from app.infra.cache import Cache, MemoryCache
from app.infra.provider import ProviderClient, ProviderError
from app.infra.repo import Repo
from app.infra.snapshots import SnapshotWriter
from app.settings import settings

IST = timezone(timedelta(hours=5, minutes=30))

# ---------------------------------------------------------------------------
# Logging with PII redaction (plan §8 Privacy / D7)
# ---------------------------------------------------------------------------

_PNR_RE = re.compile(r"\b\d{10}\b")


class RedactPnrFilter(logging.Filter):
    """
    Structural guarantee that a PNR cannot reach a log line.

    Applied at the FORMATTER level rather than at call sites, because a call-site
    convention is one careless f-string away from leaking. Any 10-digit run in a log
    record is replaced — false positives on other 10-digit numbers are an acceptable
    price for never logging a passenger's PNR.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _PNR_RE.sub("[PNR-REDACTED]", record.msg)
        if record.args:
            record.args = tuple(
                _PNR_RE.sub("[PNR-REDACTED]", a) if isinstance(a, str) else a
                for a in (record.args if isinstance(record.args, tuple) else (record.args,))
            )
        return True


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
log = logging.getLogger("darpan.api")
for _h in logging.getLogger().handlers:
    _h.addFilter(RedactPnrFilter())

# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

def _init_cache() -> Cache:
    if settings.redis_url:
        try:
            from app.infra.cache import RedisCache
            log.info("Connecting to RedisCache at %s", settings.redis_url)
            return Cache(RedisCache(settings.redis_url), stale_grace_s=settings.stale_grace_s)
        except Exception as e:
            log.warning("Failed to initialize RedisCache (%s), falling back to MemoryCache", e)
    return Cache(MemoryCache(), stale_grace_s=settings.stale_grace_s)


cache = _init_cache()
repo = Repo(settings.db_path)
provider = ProviderClient(
    settings.gateway_url, settings.gateway_timeout_s,
    settings.breaker_fail_threshold, settings.breaker_open_seconds,
)
risk_model = RiskModel(settings.model_path, settings.model_enabled)
# Records every ETA we serve so we can score our own accuracy later (plan §7.2).
snapshots = SnapshotWriter(settings.db_path, enabled=settings.record_snapshots)

# Real popularity ranking, replacing the hardcoded "popular trains" list (H9).
_lookup_counts: dict[str, int] = defaultdict(int)
# Naive per-IP rate limiter. Redis-backed in Phase 2 for multi-instance correctness.
_rate_buckets: dict[str, deque] = defaultdict(deque)
_started_at = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    counts = repo.counts()
    log.info("static store: %s", counts)
    if counts.get("stations", 0) <= 0:
        log.warning("stations table is empty — run services/worker/jobs/etl_static_graph.py")

    # Warm the model OFF the request path. Loading joblib + importing sklearn/pandas
    # costs ~20s on first touch; doing it lazily inside a request made the first
    # /live call take 25s while every later one took 55ms. Warming in a background
    # thread keeps startup non-blocking (readiness does not depend on the model,
    # since risk is an optional overlay — the ETA does not need it).
    import asyncio as _asyncio

    async def _warm() -> None:
        t0 = time.time()
        await _asyncio.to_thread(lambda: risk_model.available)
        log.info("risk model warm: available=%s in %.1fs (error=%s)",
                 risk_model.available, time.time() - t0, risk_model.load_error)

    snapshots.start()
    log.info("snapshot recorder: %s", "on" if snapshots.enabled else "off")

    warm_task = _asyncio.create_task(_warm())
    try:
        yield
    finally:
        warm_task.cancel()
        snapshots.stop()
        await provider.aclose()


app = FastAPI(
    title="DARPAN API",
    version="1.0.0",
    description="Indian Railways live status, PNR and dynamic ETA. Every value carries "
                "a source and confidence; no value is ever synthesised.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Envelope helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ok(data: Any, *, source: str = "live", confidence: float | None = None,
       unavailable: list[str] | None = None, extra_meta: dict | None = None) -> JSONResponse:
    unavailable = unavailable or []
    meta = {
        "source": source,
        "asOf": _now_iso(),
        "provider": "railkit",
        "confidence": confidence,
        "degraded": bool(unavailable) or source == "stale",
        "unavailableFields": unavailable,
    }
    if extra_meta:
        meta.update(extra_meta)
    return JSONResponse({"data": data, "meta": meta, "error": None})


def fail(code: str, message: str, status: int = 502, retryable: bool = False,
         source: str = "error") -> JSONResponse:
    """
    Error responses carry data:null. There is deliberately NO fallback payload here:
    an error must be indistinguishable from nothing, never from real data (ADR-004).
    """
    return JSONResponse(
        status_code=status,
        content={
            "data": None,
            "meta": {"source": source, "asOf": _now_iso(), "provider": "railkit",
                     "confidence": None, "degraded": True, "unavailableFields": []},
            "error": {"code": code, "message": message, "retryable": retryable},
        },
    )


@app.middleware("http")
async def rate_limit_and_log(request: Request, call_next):
    client = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = _rate_buckets[client]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= settings.rate_limit_per_min and request.url.path.startswith("/v1/"):
        return fail("RATE_LIMITED",
                    f"more than {settings.rate_limit_per_min} requests/min from this client",
                    429, True)
    bucket.append(now)

    t0 = time.time()
    response = await call_next(request)
    # Log the PATH only — a query string can contain a PNR.
    log.info("%s %s -> %s %dms", request.method, request.url.path,
             response.status_code, int((time.time() - t0) * 1000))
    return response


def _handle_provider_error(exc: ProviderError) -> JSONResponse:
    mapping = {
        "NOT_FOUND": ("NOT_FOUND", 404),
        "PNR_NOT_FOUND": ("PNR_NOT_FOUND", 404),
        "BAD_REQUEST": ("BAD_REQUEST", 400),
        "PROVIDER_REJECTED": ("BAD_REQUEST", 400),
        "BREAKER_OPEN": ("PROVIDER_UNAVAILABLE", 503),
        "GATEWAY_UNREACHABLE": ("PROVIDER_UNAVAILABLE", 503),
        "QUOTA_EXHAUSTED": ("QUOTA_EXHAUSTED", 429),
        "PROVIDER_QUOTA": ("QUOTA_EXHAUSTED", 429),
        "PROVIDER_TIMEOUT": ("PROVIDER_TIMEOUT", 504),
    }
    code, status = mapping.get(exc.code, ("PROVIDER_ERROR", 502))
    return fail(code, exc.message, status, exc.retryable)


def _ist_date_ddmmyyyy(dt: datetime | None = None) -> str:
    dt = dt or datetime.now(IST)
    return dt.astimezone(IST).strftime("%d-%m-%Y")


# ---------------------------------------------------------------------------
# Health & meta
# ---------------------------------------------------------------------------


@app.get("/v1/health", tags=["health"])
async def health():
    counts = repo.counts()
    return ok({
        "status": "ok" if counts.get("stations", 0) > 0 else "degraded",
        "uptimeSeconds": int(time.time() - _started_at),
        "staticStore": counts,
        "cache": {**cache.stats, "hitRatio": cache.hit_ratio()},
        "snapshotRecorder": {"enabled": snapshots.enabled, **snapshots.stats},
    }, source="live")


@app.get("/v1/health/providers", tags=["health"])
async def provider_health():
    gw = await provider.health()
    return ok({"gateway": gw, "client": provider.snapshot()}, source="live")


@app.get("/v1/meta/model", tags=["meta"])
async def model_meta():
    """
    The honesty surface (plan Phase-1 exit criterion 7): states publicly which
    features are unavailable and how that constrains what we may claim.
    """
    return ok({
        "etaEngine": {
            "version": "m0-propagation-1.0",
            "method": "deterministic delay propagation over the derived route graph",
            "ownsClockTimes": True,
            "recoveryModelling": settings.eta_recovery_enabled,
            "confidenceIsCalibrated": False,
            "note": "confidence and p10/p90 are documented heuristics, not calibrated "
                    "intervals; Phase 2 replaces them with quantile regression on "
                    "harvested observations",
        },
        "riskModel": risk_model.metadata(),
        "staticGraph": repo.counts(),
    }, source="live")


# ---------------------------------------------------------------------------
# Stations  (local reads: zero provider cost)
# ---------------------------------------------------------------------------


@app.get("/v1/stations", tags=["stations"])
async def search_stations(q: str = Query("", min_length=0, max_length=60),
                          limit: int = Query(10, ge=1, le=50)):
    return ok(repo.search_stations(q, limit), source="schedule")


@app.get("/v1/stations/{code}", tags=["stations"])
async def get_station(code: str = Path(..., max_length=8)):
    st = repo.get_station(code)
    if not st:
        return fail("NOT_FOUND", f"no station with code {code!r}", 404)
    return ok(st, source="schedule")


@app.get("/v1/stations/{code}/board", tags=["stations"])
async def station_board(code: str = Path(..., max_length=8),
                        window: int = Query(2), mode: str = Query("dep")):
    """Live station board — replaces the 13 hardcoded departures (H8)."""
    code = code.upper()
    if window not in (2, 4, 8):
        window = 2
    station = repo.get_station(code)
    key = f"board:{code}:{window}"
    try:
        data, state = await cache.get_or_load(
            key, settings.ttl_board, lambda: provider.station_board(code, window))
    except ProviderError as exc:
        # Graceful fallback to static timetable when external gateway is unreachable/out of quota
        scheduled_trains = repo.get_station_board(code, hours=window, mode=mode)
        if scheduled_trains or station:
            data = {"totalTrains": len(scheduled_trains), "trains": scheduled_trains}
            state = "schedule"
        else:
            return _handle_provider_error(exc)

    trains = list(data.get("trains") or [])
    if mode == "arr":
        trains.sort(key=lambda t: (t.get("arrival") or {}).get("scheduled") or "")
    else:
        trains.sort(key=lambda t: (t.get("departure") or {}).get("scheduled") or "")

    return ok({
        "station": station or {"code": code},
        "window": window,
        "mode": mode,
        "totalTrains": data.get("totalTrains"),
        "trains": trains,
    }, source=state)


# ---------------------------------------------------------------------------
# Trains
# ---------------------------------------------------------------------------


@app.get("/v1/trains", tags=["trains"])
async def search_trains(q: str = Query("", max_length=60), limit: int = Query(10, ge=1, le=50)):
    return ok(repo.search_trains(q, limit), source="schedule")


@app.get("/v1/trains/popular", tags=["trains"])
async def popular_trains(limit: int = Query(6, ge=1, le=20)):
    """
    Real popularity from actual lookups (H9). Cold start returns an empty list rather
    than a curated "popular" fiction — an empty state is honest, a fake one is not.
    """
    top = sorted(_lookup_counts.items(), key=lambda kv: -kv[1])[:limit]
    out = []
    for number, hits in top:
        t = repo.get_train(number)
        if t:
            out.append({**t, "lookups": hits})
    return ok(out, source="live", extra_meta={"basis": "observed lookups this process"})


@app.get("/v1/trains/{number}", tags=["trains"])
async def get_train(number: str = Path(..., pattern=r"^\d{5}$")):
    static = repo.get_train(number)
    schedule = repo.get_schedule(number)
    key = f"train:{number}"
    provider_info, state, unavailable = None, "schedule", []
    try:
        provider_info, state = await cache.get_or_load(
            key, settings.ttl_train, lambda: provider.train_info(number))
    except ProviderError as exc:
        if exc.code in ("NOT_FOUND",) and not static:
            return _handle_provider_error(exc)
        # Provider unavailable but we still hold the full local timetable: serve it,
        # clearly marked as schedule-only rather than live.
        unavailable.append("providerRoute")
        state = "schedule"

    if not static and not provider_info:
        return fail("NOT_FOUND", f"no train {number}", 404)

    _lookup_counts[number] += 1
    return ok({
        "train": (provider_info or {}).get("train") or {
            "number": number, "name": (static or {}).get("name"),
            "type": (static or {}).get("type"),
            "from": {"code": (static or {}).get("from_code"), "name": (static or {}).get("from_name")},
            "to": {"code": (static or {}).get("to_code"), "name": (static or {}).get("to_name")},
        },
        "static": static,
        "providerRoute": (provider_info or {}).get("route"),
        "scheduleStops": schedule,
        "scheduleStopCount": len(schedule),
    }, source=state, unavailable=unavailable)


@app.get("/v1/trains/{number}/route.geojson", tags=["trains"])
async def train_route_geojson(number: str = Path(..., pattern=r"^\d{5}$")):
    """
    Route geometry from our own store — replaces the third-party RailRadar iframe (H11).
    Zero provider calls, so panning the map costs nothing.
    """
    coords = list(repo.get_train_geometry(number) or [])
    train = repo.get_train(number)
    schedule = list(repo.get_schedule(number) or [])
    codes = [s["station_code"] for s in schedule]

    # Check if provider has full extended route (e.g. 12555 extended to Bathinda BTI)
    try:
        provider_info, _ = await cache.get_or_load(
            f"train:{number}", settings.ttl_train, lambda: provider.train_info(number)
        )
    except Exception:
        provider_info = None

    provider_route = (provider_info or {}).get("route") or []
    dest_name = (provider_info or {}).get("train", {}).get("name") or (train or {}).get("name")

    # Correct route extension: ONLY append stations from provider_route that appear strictly AFTER
    # the last matching station of schedule (e.g. HSR -> ADR -> BHT -> SSA -> BTI).
    # Intermediate stations (like ASH, BNZ) must NEVER be appended at the end of the line.
    extra_schedule = []
    codes_set = set(codes)
    if provider_route and codes:
        last_matched_idx = -1
        for i, ps in enumerate(provider_route):
            if ps.get("stationCode") in codes_set:
                last_matched_idx = i

        if last_matched_idx >= 0 and last_matched_idx < len(provider_route) - 1:
            extra_seq = len(schedule)
            for ps in provider_route[last_matched_idx + 1:]:
                sc = ps.get("stationCode")
                if sc and sc not in codes_set:
                    codes.append(sc)
                    codes_set.add(sc)
                    extra_seq += 1
                    extra_schedule.append({"station_code": sc, "seq": extra_seq})

    all_schedule = list(schedule) + extra_schedule
    coord_map = repo.stations_by_codes(codes)

    points = [
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": [c["lon"], c["lat"]]},
         "properties": {"code": c["code"], "name": c["name"], "seq": s["seq"]}}
        for s in all_schedule
        if (c := coord_map.get(s["station_code"])) and c.get("lat") is not None and c.get("lon") is not None
    ]

    # If coords is missing or ends before the final stops, extend coords
    if not coords and points:
        coords = [p["geometry"]["coordinates"] for p in points]
    elif coords and extra_schedule:
        for s in extra_schedule:
            c = coord_map.get(s["station_code"])
            if c and c.get("lat") is not None and c.get("lon") is not None:
                pt = [c["lon"], c["lat"]]
                if coords[-1] != pt:
                    coords.append(pt)

    if not coords or len(coords) < 2:
        return fail("NOT_FOUND", f"no route geometry or coordinates stored for train {number}", 404)

    return ok({
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature",
             "geometry": {"type": "LineString", "coordinates": coords},
             "properties": {"number": number, "name": dest_name, "kind": "route"}},
            *points,
        ],
    }, source="schedule")


def compute_available_run_dates(
    running_days: str | None = None,
    days_of_run: dict[str, bool] | None = None,
    ref_dt: datetime | None = None,
) -> tuple[list[dict], bool]:
    """
    Computes available journey run dates based on the train's actual operating schedule.
    Index 0..6 = Mon..Sun (aligned with datetime.weekday()).
    Returns (available_runs, runs_on_today).
    """
    now = ref_dt or datetime.now(IST)
    today_date = now.date()
    days_map = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    full_day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    mask = [True] * 7  # default: daily train
    if days_of_run and isinstance(days_of_run, dict):
        mask = [bool(days_of_run.get(d, False)) for d in days_map]
    elif running_days and len(str(running_days).strip()) == 7:
        mask = [ch == "1" for ch in str(running_days).strip()]

    today_weekday = today_date.weekday()
    runs_on_today = mask[today_weekday]

    # If the train is daily (runs every day)
    if all(mask):
        offsets = [-1, 0, 1]  # Yesterday, Today, Tomorrow
    else:
        # Check window: past runs (up to -7 days) and next runs (up to +7 days)
        past_offsets = [off for off in range(-7, 0) if mask[(today_date + timedelta(days=off)).weekday()]]
        future_offsets = [off for off in range(1, 8) if mask[(today_date + timedelta(days=off)).weekday()]]

        offsets = []
        if past_offsets:
            offsets.extend(past_offsets[-2:] if not runs_on_today else past_offsets[-1:])
        if runs_on_today:
            offsets.append(0)
        if future_offsets:
            offsets.extend(future_offsets[:2] if not runs_on_today else future_offsets[:1])

        if not offsets:
            offsets = [-1, 0, 1]

    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    runs = []
    for off in offsets:
        target_date = today_date + timedelta(days=off)
        dd = f"{target_date.day:02d}"
        mm = f"{target_date.month:02d}"
        yyyy = f"{target_date.year}"
        date_str = f"{dd}-{mm}-{yyyy}"
        date_label = f"{dd} {months[target_date.month - 1]}"
        weekday_idx = target_date.weekday()
        day_short = days_map[weekday_idx]
        day_full = full_day_names[weekday_idx]

        if off == 0:
            label = "Today"
        elif off == -1:
            label = "Yesterday"
        elif off == 1:
            label = "Tomorrow"
        elif off < 0:
            label = f"Last Run ({day_short})"
        else:
            label = f"Next Run ({day_short})"

        runs.append({
            "key": date_str,
            "label": label,
            "dateLabel": date_label,
            "dayName": day_short,
            "fullDayName": day_full,
            "offset": off,
            "isToday": off == 0,
        })
    return runs, runs_on_today


@app.get("/v1/trains/{number}/live", tags=["trains"])
async def train_live(number: str = Path(..., pattern=r"^\d{5}$"),
                     date: str | None = Query(None, pattern=r"^\d{2}-\d{2}-\d{4}$")):
    """
    THE endpoint that replaces H4/H5 — the 3 hardcoded trains in LivePage.

    Returns header + position + full stop timeline + per-stop ETA + risk in one round
    trip, so the client renders and never orchestrates (plan §2.1.2).
    """
    today_date = _ist_date_ddmmyyyy()
    now_ist = datetime.now(IST)
    yesterday_date = (now_ist - timedelta(days=1)).strftime("%d-%m-%Y")

    active_date = today_date
    run_previews: dict[str, dict] = {}

    if not date:
        # When date is not explicitly specified, fetch both today and yesterday
        # to determine which run is actively on the tracks.
        today_live, today_state = None, None
        last_provider_error = None
        try:
            today_live, today_state = await cache.get_or_load(
                f"live:{number}:{today_date}", settings.ttl_live, lambda: provider.live_status(number, today_date)
            )
        except ProviderError as e:
            last_provider_error = e
        except Exception as e:
            log.warning("Could not fetch today live status for %s: %s", number, e)

        yest_live, yest_state = None, None
        try:
            yest_live, yest_state = await cache.get_or_load(
                f"live:{number}:{yesterday_date}", settings.ttl_live, lambda: provider.live_status(number, yesterday_date)
            )
        except ProviderError as e:
            last_provider_error = e
        except Exception as e:
            log.warning("Could not fetch yesterday live status for %s: %s", number, e)

        if not today_live and not yest_live:
            if last_provider_error:
                return _handle_provider_error(last_provider_error)
            return fail("NOT_FOUND", f"no live status available for train {number}", 404)

        today_dist = ((today_live or {}).get("position") or {}).get("distanceCoveredKm") or 0
        yest_dist = ((yest_live or {}).get("position") or {}).get("distanceCoveredKm") or 0

        # If today has not departed (0 km covered) and yesterday is currently running (> 0 km covered):
        if yest_dist > 0 and today_dist == 0:
            date = yesterday_date
            live = yest_live or {}
            state = yest_state or "fresh"
            active_date = yesterday_date
        else:
            date = today_date
            live = today_live if today_live is not None else (yest_live or {})
            state = today_state if today_state is not None else (yest_state or "fresh")
            active_date = today_date if today_dist > 0 else (yesterday_date if yest_dist > 0 else today_date)

        if today_live:
            t_pos = today_live.get("position") or {}
            run_previews[today_date] = {
                "distanceCoveredKm": t_pos.get("distanceCoveredKm"),
                "delayMinutes": t_pos.get("delayMinutes"),
                "status": "in_transit" if (t_pos.get("distanceCoveredKm") or 0) > 0 else "scheduled",
            }
        if yest_live:
            y_pos = yest_live.get("position") or {}
            run_previews[yesterday_date] = {
                "distanceCoveredKm": y_pos.get("distanceCoveredKm"),
                "delayMinutes": y_pos.get("delayMinutes"),
                "status": "in_transit" if (y_pos.get("distanceCoveredKm") or 0) > 0 else "completed",
            }
    else:
        key = f"live:{number}:{date}"
        try:
            live, state = await cache.get_or_load(
                key, settings.ttl_live, lambda: provider.live_status(number, date))
        except ProviderError as exc:
            return _handle_provider_error(exc)

    _lookup_counts[number] += 1
    static = repo.get_train(number)

    # Join provider station CODES to our coordinates so the map needs no extra call.
    codes = [s.get("stationCode") for s in (live.get("stops") or [])]
    pos_raw = live.get("position") or {}
    for extra in (pos_raw.get("currentStationCode"), pos_raw.get("lastStationCode"), pos_raw.get("nextStationCode")):
        if extra:
            codes.append(extra)
    coord_map = repo.stations_by_codes([c for c in codes if c])

    # Walk the route graph and propagate delay (M0).
    pairs = eta_engine.remaining_pairs(live)
    segments = repo.get_segments(pairs)
    eta = eta_engine.compute_eta(
        live, segments, coord_map,
        recovery_enabled=settings.eta_recovery_enabled,
        segment_min_obs=settings.eta_segment_min_obs,
    )

    zone = None
    last_code = (live.get("position") or {}).get("lastStationCode")
    if last_code:
        st = repo.get_station(last_code)
        zone = (st or {}).get("zone")

    risk = risk_model.predict(
        train=(live.get("train") or {}),
        static_train={**(static or {}), "num_scheduled_stops": len(live.get("stops") or [])},
        station_zone=zone,
    )

    # Record the forecast for later scoring. Fire-and-forget: never blocks the request.
    snapshots.record(
        train_number=number,
        journey_date=(live.get("train") or {}).get("journeyDate"),
        stops=eta.stops,
        model_version=eta.model_version,
    )

    unavailable = list(live.get("unavailableFields") or []) + list(eta.unavailable_fields)

    from_code = (eta.stops[0].station_code if eta.stops else None) or (static or {}).get("from_code")
    from_name = (eta.stops[0].station_name if eta.stops else None) or (static or {}).get("from_name")
    to_code = (eta.stops[-1].station_code if eta.stops else None) or (static or {}).get("to_code")
    to_name = (eta.stops[-1].station_name if eta.stops else None) or (static or {}).get("to_name")
    train_type = (static or {}).get("type") or (live.get("train") or {}).get("type") or "Express"

    pos = dict(live.get("position") or {})
    curr_code = pos.get("currentStationCode") or pos.get("lastStationCode") or (eta.stops[0].station_code if eta.stops else None)
    matched_curr = next((s for s in eta.stops if s.station_code == curr_code), None) if curr_code else None
    db_station = repo.get_station(curr_code) if curr_code else None
    curr_name = (
        pos.get("currentStationName")
        or (db_station["name"] if db_station else None)
        or pos.get("lastStationName")
        or (matched_curr.station_name if matched_curr else None)
        or (eta.stops[0].station_name if eta.stops else None)
    )
    pos["currentStationCode"] = curr_code
    pos["currentStationName"] = curr_name
    curr_coord = coord_map.get(curr_code or "") or (db_station if db_station else None)
    pos["coordinates"] = (
        lambda c: {"lat": c["lat"], "lon": c["lon"]} if c and c.get("lat") else None
    )(curr_coord)

    next_code = pos.get("nextStationCode")
    next_stop = (
        next((s for s in eta.stops if s.station_code == next_code), None)
        if next_code else None
    ) or next((s for s in eta.stops if s.status == "upcoming"), None) or next((s for s in eta.stops if s.status == "current"), None)

    # Compute operating run dates based on train's schedule
    running_days = (static or {}).get("running_days")
    days_of_run = (live.get("train") or {}).get("daysOfRun") or (live.get("train") or {}).get("DaysOfRun")
    available_runs, runs_today = compute_available_run_dates(running_days=running_days, days_of_run=days_of_run)

    for r in available_runs:
        r["isActive"] = (r["key"] == active_date)
        if r["key"] in run_previews:
            r["preview"] = run_previews[r["key"]]

    return ok({
        "train": {**(live.get("train") or {}),
                  "type": train_type,
                  "from": {"code": from_code, "name": from_name},
                  "to": {"code": to_code, "name": to_name},
                  "availableRuns": available_runs,
                  "runsOnToday": runs_today,
                  "runningDays": running_days,
                  "activeDate": active_date,
                  "selectedDate": date},
        "position": pos,
        "nextStop": next_stop.to_dict() if next_stop else None,
        "stops": [s.to_dict() for s in eta.stops],
        "passingPointCount": len(live.get("passingPoints") or []),
        "composition": live.get("composition") or [],
        "eta": {"currentDelayMinutes": eta.current_delay_minutes,
                "delaySource": eta.delay_source,
                "engine": eta.model_version,
                "notes": eta.notes},
        "risk": risk,
    }, source=state,
       confidence=(next_stop.confidence if next_stop else None),
       unavailable=sorted(set(unavailable)))


@app.get("/v1/trains/{number}/composition", tags=["trains"])
async def train_composition(number: str = Path(..., pattern=r"^\d{5}$"),
                            date: str | None = Query(None, pattern=r"^\d{2}-\d{2}-\d{4}$")):
    """
    Real coach position (replaces the fabricated rake, H10).

    Discovered during the build: the provider genuinely supplies this, so the panel
    survives as a real feature instead of being deleted.
    """
    date = date or _ist_date_ddmmyyyy()
    try:
        live, state = await cache.get_or_load(
            f"live:{number}:{date}", settings.ttl_live,
            lambda: provider.live_status(number, date))
    except ProviderError as exc:
        return _handle_provider_error(exc)

    coaches = live.get("composition") or []
    if not coaches:
        return fail("UNAVAILABLE", "provider did not supply coach composition for this train", 404)
    return ok({"trainNumber": number, "coaches": coaches, "coachCount": len(coaches)},
              source=state)


# ---------------------------------------------------------------------------
# ETA
# ---------------------------------------------------------------------------


@app.get("/v1/eta/{number}", tags=["eta"])
async def train_eta(number: str = Path(..., pattern=r"^\d{5}$"),
                    from_code: str | None = Query(None, alias="from", max_length=8),
                    date: str | None = Query(None, pattern=r"^\d{2}-\d{2}-\d{4}$")):
    """ETA detail with the provider cross-check and per-stop drivers."""
    date = date or _ist_date_ddmmyyyy()
    try:
        live, state = await cache.get_or_load(
            f"live:{number}:{date}", settings.ttl_live,
            lambda: provider.live_status(number, date))
    except ProviderError as exc:
        return _handle_provider_error(exc)

    coord_map = repo.stations_by_codes(
        [s.get("stationCode") for s in (live.get("stops") or []) if s.get("stationCode")])
    segments = repo.get_segments(eta_engine.remaining_pairs(live))
    eta = eta_engine.compute_eta(live, segments, coord_map,
                                 recovery_enabled=settings.eta_recovery_enabled,
                                 segment_min_obs=settings.eta_segment_min_obs)

    stops = [s for s in eta.stops if s.status in ("upcoming", "current")]
    if from_code:
        fc = from_code.upper()
        idx = next((i for i, s in enumerate(stops) if (s.station_code or "").upper() == fc), None)
        if idx is not None:
            stops = stops[idx:]

    divergences = [abs(s.provider_divergence_min) for s in stops
                   if s.provider_divergence_min is not None]
    return ok({
        "trainNumber": number,
        "journeyDate": (live.get("train") or {}).get("journeyDate"),
        "currentDelayMinutes": eta.current_delay_minutes,
        "delaySource": eta.delay_source,
        "engine": eta.model_version,
        "notes": eta.notes,
        "stops": [s.to_dict() for s in stops],
        "providerCrossCheck": {
            "comparedStops": len(divergences),
            "meanAbsDivergenceMinutes": (
                round(sum(divergences) / len(divergences), 1) if divergences else None),
            "interpretation": "mean absolute difference between our M0 ETA and the "
                              "provider's own projection; large values warrant "
                              "investigation, not silent preference for either source",
        },
    }, source=state, confidence=(stops[0].confidence if stops else None))


# ---------------------------------------------------------------------------
# PNR  (PII-sensitive: see the salted cache key and the log filter)
# ---------------------------------------------------------------------------


@app.get("/v1/pnr/{pnr}", tags=["pnr"])
async def pnr_status(pnr: str = Path(..., pattern=r"^\d{10}$")):
    """
    PNR status — replaces the two hardcoded PNR responses (H1/H2).

    Privacy (plan D7 / §8): the cache key is a salted hash so the PNR never appears
    in a key; passenger names are dropped at the gateway boundary; the log filter
    redacts any 10-digit run; nothing is written to the database.
    """
    digest = hashlib.sha256(f"{settings.pnr_cache_salt}:{pnr}".encode()).hexdigest()[:32]
    try:
        data, state = await cache.get_or_load(
            f"pnr:{digest}", settings.ttl_pnr, lambda: provider.pnr(pnr))
    except ProviderError as exc:
        return _handle_provider_error(exc)

    train_no = (data.get("train") or {}).get("number")
    enriched = repo.get_train(train_no) if train_no else None
    return ok({**data, "trainStatic": enriched},
              source=state,
              extra_meta={"retention": "not persisted; cached "
                                       f"{settings.ttl_pnr}s under a salted hash"})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    """
    Keep the envelope uniform for input errors too.

    FastAPI's default 422 handler returns {"detail": [...]}, which is a second
    response shape the client would have to special-case — and the generated client
    would not know about it. Rewriting it into the standard envelope means the
    frontend has exactly one parse path for every response.
    """
    first = (exc.errors() or [{}])[0]
    loc = ".".join(str(p) for p in first.get("loc", []) if p != "path")
    return fail("BAD_REQUEST",
                f"{loc}: {first.get('msg', 'invalid value')}" if loc
                else first.get("msg", "invalid request"),
                400, False)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)
    return fail("INTERNAL", "internal error", 500, True)
