# DARPAN — Frontend/Backend Separation & Real-Data Backend
## Implementation Plan and Long-Term Roadmap

**Status:** proposed · **Owner:** platform/architecture · **Written:** 2026-09-01
**Scope:** `ETA/WEB-1` (React app), `ETA/*.py` (ML), `ETA/Indian-railway-Railkit-main-api` (RailKit SDK), `ETA/indian-railways-dataset` (static graph)
**Companion docs:** [project-architecture.md](./project-architecture.md) · [implementation-plan.md](./implementation-plan.md) · [ui-structure.md](./ui-structure.md) · [eta-data-sources-and-prior-art.md](./eta-data-sources-and-prior-art.md)

---

## 0. Executive summary

Today DARPAN is a **single-tier React app** that renders convincing railway telemetry from arrays
literally typed into component bodies. There is no backend. The one live integration attempt
([railApi.ts](../WEB-1/src/services/railApi.ts)) proxies API Mitra straight from the browser, holds
the API key in `localStorage`, and silently falls back to a hardcoded "verified simulation" whenever
the call fails — which is always, because no key is configured. Meanwhile a trained model
(`eta_model.joblib`, HistGradientBoosting, journey-level `is_delayed` classifier) and a working
real-data SDK (RailKit, 14 endpoints incl. PNR + live tracking) both exist **outside** the web app,
unreachable from it.

This plan does four things, in order of architectural importance:

1. **Introduces a backend tier** — a Python/FastAPI **BFF + ETA service** plus a thin Node
   **rail-gateway** (RailKit is Node-only, obfuscated, and currently invoked by spawning a `node`
   process per call from Python — unusable in production). All third-party keys move server-side.
2. **Makes the contract the source of truth** — OpenAPI schema → generated TypeScript client. The
   frontend stops owning data shapes; it consumes them. Every hardcoded array is deleted against a
   real endpoint, not "commented out for demo."
3. **Fixes a model/product mismatch that nobody has flagged yet** — the shipped model answers
   *"will this journey arrive >15 min late?"* (binary, journey-level, on a **synthetic Kaggle
   schema**). The product needs *"what minute will this train reach each of its remaining stops?"*
   (continuous, per-stop, from live inputs). ~9 of the model's 44 features **cannot be obtained
   live at all**. §5 resolves this honestly rather than papering over it.
4. **Splits delivery into two phases with hard exit criteria** — Phase 1 ships a real, honest,
   zero-hardcoded product on deterministic propagation plus a model-driven risk overlay. Phase 2
   earns the right to per-stop ML by first harvesting our own ground truth.

**Non-negotiable principle carried through both phases:** *never fabricate a number and present it
as live.* Every value the UI shows carries a `source` (`live` | `schedule` | `model` | `stale`) and
a `confidence`. Where data is genuinely unavailable, the UI says so. The current
`provider: 'Verified Simulation'` pattern — real-looking data labelled as if it came from an API —
is the single worst thing in the codebase and is deleted in Phase 1, Week 1.

---

## 1. Current-state audit (evidence)

### 1.1 What exists

| Asset | Location | State | Verdict |
|---|---|---|---|
| React SPA (Vite + TS + Tailwind) | `WEB-1/src` | 2,735 LoC, 5 pages, 6 components | **Keep.** UI quality is good; only its data source is wrong |
| PNR "service" | `WEB-1/src/services/railApi.ts` (229 LoC) | Browser→API Mitra via Vite proxy; key in `localStorage`; hardcoded fallback | **Delete & replace** |
| Live status page | `WEB-1/src/pages/LivePage.tsx` (581 LoC) | 3 trains hardcoded incl. per-stop platforms & delays | **Rewire** |
| Station board | `WEB-1/src/pages/StationPage.tsx` (277 LoC) | 6 stations listed, 3 with hardcoded boards | **Rewire** |
| Map page | `WEB-1/src/pages/MapPage.tsx` (15 LoC) | `<iframe src="https://railradar.in/railradar">` | **Replace** (3rd-party iframe = zero control, zero data) |
| RailKit SDK | `Indian-railway-Railkit-main-api/RailKit-main/` | Obfuscated Node ESM, 14 typed endpoints, key in `.env` | **Wrap in a service** |
| Python RailKit bridge | `railkit_client.py` | Spawns `node -e` **per call** | **Delete** (see ADR-002) |
| ETA model | `eta_model.joblib` (1.8 MB) + `train_eta_model.py` | HistGradientBoostingClassifier, 44 raw → ~60 engineered features; artifact bundles feature names, categorical mappings, freq map, metrics | **Keep, re-scope** (§5) |
| Static rail graph | `indian-railways-dataset/` | `stations.json` 2.6 MB GeoJSON, `trains.json` 14.8 MB LineString routes, `schedules.json` 82 MB stop rows | **Load into Postgres** — this is the backbone and it is already on disk |
| Kaggle delay dataset | `indian-railways-predict-train-delay/` | 1.5 M train / 375 k test rows, **synthetic** | Keep for pretraining only |
| Second web app | `Web-App/` | Separate Vite app (`ArchitectureFlow`, `PredictionSandbox`, `inferenceSimulator.ts`) | **Decide: fold in or archive** (§10, D-1) |

### 1.2 Hardcoded-data inventory (Phase 1 kill list)

| # | Location | What is faked | Replacement endpoint |
|---|---|---|---|
| H1 | `railApi.ts:getSimulatedPnr()` | Two full PNR responses (Vande Bharat / Rajdhani) incl. coach, berth, chart status | `GET /v1/pnr/{pnr}` |
| H2 | `railApi.ts:parseApiResponse()` | Defaults that invent `12301 / Howrah Rajdhani / HWH→NDLS` whenever a field is missing | Strict schema validation; missing field ⇒ `null` + `source` flag |
| H3 | `railApi.ts:getApiConfig/saveApiConfig` | Provider keys stored in `localStorage`, provider switch exposed in UI | Server-side key vault; provider selection is **ops config, not user config** |
| H4 | `LivePage.tsx:trainsData` | 3 trains × up to 8 stops: speeds, platforms, per-stop delays, "Live GPS Telemetry" label | `GET /v1/trains/{no}/live` |
| H5 | `LivePage.tsx:handleSearch` | Unknown train silently falls back to `22436` | 404 → real "train not found" UI state |
| H6 | `LivePage.tsx` API-settings modal | Three fictional endpoints presented as configurable backends | Remove; replace with a real provider-health indicator |
| H7 | `StationPage.tsx:stationsList` | 6 stations w/ platform counts | `GET /v1/stations?q=` (autocomplete over 8 k+ real stations) |
| H8 | `StationPage.tsx:stationBoards` | 13 hardcoded departures across 3 stations | `GET /v1/stations/{code}/board` |
| H9 | `HomePage.tsx:popularTrains` | Static "popular" list | `GET /v1/trains/popular` (Redis sorted set of real lookups) |
| H10 | `PnrPage.tsx:coachRake` | Fabricated rake composition | `GET /v1/trains/{no}/composition` (real if the provider exposes it; else omit the panel) |
| H11 | `MapPage.tsx` | External RailRadar iframe | Own MapLibre map over `trains.json` geometry + live positions |
| H12 | `App.tsx:trackedTrain='22436'` | Hardcoded default train | Empty state → search-first UX |

### 1.3 Architectural defects (beyond hardcoding)

- **D1 — No trust boundary.** The browser talks to third parties directly; secrets are client-side.
  Any user can read the key out of `localStorage` and burn the quota.
- **D2 — Fallback-to-fiction.** `catch` → simulated data tagged `provider: 'API Mitra'`. Failure is
  indistinguishable from success. Unacceptable for a system whose product claim is accuracy.
- **D3 — Types live in the UI layer.** `PnrResponse`/`StationStop` are declared inside pages, so the
  contract drifts per component — `railApi.ts` and `LivePage.tsx` already model a stop differently.
- **D4 — Per-call `node` subprocess** in `railkit_client.py`: ~80–250 ms spawn overhead, no
  connection reuse, no caching, no rate limiting, unbounded concurrency, key passed on argv.
- **D5 — Live path only exists in dev.** `vite.config.ts` proxies `api.apimitra.in` from the dev
  server. In a production build there is no proxy, so the "live" code path cannot work at all —
  which is why the simulated fallback is always what users see.
- **D6 — Model unreachable.** No Python process serves `eta_model.joblib`; the web app has no path
  to it, and `engineer_features()` exists only inside the training script.
- **D7 — PII handling undefined.** PNR payloads carry passenger names and berths. Nothing specifies
  cache TTL, log redaction, or retention.
- **D8 — Two divergent frontends** (`WEB-1`, `Web-App`) with overlapping intent and no shared code.

---

## 2. Target architecture

```
┌───────────────────────────────────────────────────────────────────────────┐
│  CLIENT — apps/web (React 18 + Vite + TS)                                 │
│  · Zero data literals. Zero third-party keys. Zero fallback fiction.      │
│  · TanStack Query cache · generated API client · MapLibre GL              │
│  · Every datum rendered with {value, source, confidence, asOf}            │
└──────────────────────────────┬────────────────────────────────────────────┘
                       HTTPS · /v1/* · JSON envelope
                               ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  BFF + DOMAIN API — services/api (FastAPI, Python 3.11)                   │
│  routers/   pnr · trains · stations · eta · search · health               │
│  domain/    eta_engine (route-graph walk + delay propagation)  ← DSA core │
│             risk_overlay (model inference) · schedule_resolver            │
│  infra/     provider_client · cache (Redis) · repo (Postgres) · limiter   │
│  Cross-cutting: schema validation · circuit breaker · single-flight ·     │
│                 structured logs w/ PII redaction · OpenAPI emission       │
└───────┬──────────────────────────────┬────────────────────────┬───────────┘
        ▼                              ▼                        ▼
┌───────────────────┐    ┌──────────────────────────┐   ┌──────────────────┐
│ services/rail-    │    │ Postgres 16 + PostGIS    │   │ Redis 7          │
│ gateway (Node 20, │    │ stations · segments ·    │   │ provider resp    │
│ Fastify)          │    │ trains · schedule_stops ·│   │ cache · single-  │
│ · owns RailKit    │    │ live_observations ·      │   │ flight locks ·   │
│   SDK + API key   │    │ eta_snapshots ·          │   │ rate limits ·    │
│ · normalises to   │    │ provider_calls ·         │   │ hot positions ·  │
│   canonical DTOs  │    │ zone_stats · calendar    │   │ popular trains   │
│ · per-provider    │    │ train_asset_profile      │   └──────────────────┘
│   quota + retry   │    └──────────────────────────┘
└───────────────────┘
        ▲
┌───────┴───────────────────────────────────────────────────────────────────┐
│  WORKERS — services/worker (APScheduler → Celery/Arq in Phase 2)          │
│  · harvester: poll live status for tracked trains → live_observations     │
│  · station-board refresher for top-N stations                            │
│  · nightly: segment stats, zone indices, model feature marts             │
│  · one-time/idempotent: static graph ETL from indian-railways-dataset     │
└───────────────────────────────────────────────────────────────────────────┘
        ▲
┌───────┴───────────────────────────────────────────────────────────────────┐
│  ML — packages/ml (training, offline) + served in-process by services/api │
│  Phase 1: risk classifier (existing artifact, retrained on the live-      │
│           feasible feature subset) → delay-probability + band only        │
│  Phase 2: per-segment delay regressor trained on OUR harvested data →     │
│           feeds eta_engine directly                                       │
└───────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Why this shape — the four decisions that matter

1. **Python API, Node gateway.** The ML artifact is scikit-learn; the SDK is obfuscated Node ESM.
   Neither crosses languages cheaply. Two small services, one HTTP hop, each in its native runtime,
   beats a subprocess bridge (ADR-002) or a rewrite of either side.
2. **BFF, not a generic REST facade.** Endpoints are shaped to screens — `/trains/{no}/live` returns
   header + metrics + the full stop timeline in one round trip — so the client never orchestrates.
   This is what lets the pages be gutted of *logic*, not merely of literals.
3. **Provider-agnostic core.** `provider_client` speaks a canonical DTO; RailKit is one adapter.
   API Mitra / IRCTC-partner / NTES become adapters later without touching domain code, and the
   provider choice becomes **server config** — which is what kills H3 and H6.
4. **Cache-first with single-flight.** Third-party rail APIs are quota-metered and slow. Every read
   goes Redis → provider, with exactly one in-flight request per key. 500 users tracking `12301`
   cost one upstream call per TTL window, not 500.

### 2.2 Repository layout (monorepo: pnpm workspaces + uv)

```
ETA/
├── apps/
│   └── web/                       # ← moved from WEB-1/, same UI, new data layer
│       └── src/{pages,components,features,lib/api-client(generated),hooks}
├── services/
│   ├── api/                       # FastAPI BFF + domain
│   │   ├── app/{main.py,routers/,domain/,infra/,schemas/,settings.py}
│   │   └── tests/
│   ├── rail-gateway/              # Fastify + RailKit
│   │   └── src/{server.ts,adapters/railkit.ts,dto.ts,quota.ts}
│   └── worker/                    # schedulers + ETL
│       └── jobs/{harvest_live.py,refresh_boards.py,etl_static_graph.py,nightly_marts.py}
├── packages/
│   ├── ml/                        # training, feature engine, model registry
│   │   ├── features/{time.py,geo.py,route.py,weather.py,ops.py}
│   │   ├── train_risk_classifier.py      # ← evolved train_eta_model.py
│   │   ├── train_segment_regressor.py    # Phase 2
│   │   └── registry/                     # versioned artifacts + metric cards
│   └── contracts/                 # openapi.yaml (source of truth) + generated TS types
├── data/
│   ├── raw/                       # indian-railways-dataset (read-only, git-lfs/DVC)
│   └── migrations/                # Alembic
├── infra/
│   ├── docker-compose.dev.yml     # api, gateway, worker, postgres+postgis, redis
│   └── {Dockerfiles, deploy/}
├── legacy/                        # Web-App/, railkit_client.py, old scripts (frozen)
└── docs/                          # this plan, ADRs, runbooks
```

---

## 3. API contract (contract-first, v1)

**Envelope — every response, no exceptions:**

```jsonc
{
  "data": { /* payload, or null on error */ },
  "meta": {
    "source": "live" | "schedule" | "model" | "cache" | "stale",
    "asOf": "2026-09-01T14:32:10Z",
    "provider": "railkit",
    "confidence": 0.86,                 // null where not applicable
    "degraded": false,                  // true ⇒ some fields unavailable
    "unavailableFields": []             // explicit, never silently defaulted
  },
  "error": null | { "code": "TRAIN_NOT_FOUND", "message": "...", "retryable": false }
}
```

`meta.source` and `meta.degraded` are **rendered**, not just logged. That is the structural cure for D2.

| Method & path | Purpose | Cache TTL | Provider calls |
|---|---|---|---|
| `GET /v1/health` · `/v1/health/providers` | Liveness + per-provider breaker state & quota | – | 0 |
| `GET /v1/stations?q=&limit=` | Station autocomplete (H7) | ∞ (local DB) | 0 |
| `GET /v1/stations/{code}` | Station detail + coords + zone | 30 d | 0–1 |
| `GET /v1/stations/{code}/board?window=2\|4\|8&mode=dep\|arr` | Live station board (H8) | 60 s | 1 |
| `GET /v1/trains?q=` | Train search by number/name | ∞ (local DB) | 0 |
| `GET /v1/trains/{no}` | Train info + full route + schedule | 7 d | 1 |
| `GET /v1/trains/{no}/live?date=` | **Live status + per-stop ETA + risk** (H4/H5) | 45 s | 1 |
| `GET /v1/trains/{no}/route.geojson` | Route geometry for the map (H11) | ∞ (local DB) | 0 |
| `GET /v1/trains/popular` | Real popularity ranking (H9) | 5 m | 0 |
| `GET /v1/pnr/{pnr}` | PNR status, PII-safe (H1/H2) | 60 s, salted-hash key | 1 |
| `GET /v1/eta/{no}?from=&date=` | ETA detail: per-stop propagation + bands + drivers | 45 s | 0 (reuses live) |
| `POST /v1/eta/simulate` | What-if: perturb features → ETA delta (powers a real Prediction Sandbox) | – | 0 |
| `GET /v1/trains/{no}/history?date=` | Completed-journey timeline (ground truth) | ∞ | 1 |
| `GET /v1/meta/model` | Active model version, metrics, feature availability | – | 0 |

**`/v1/trains/{no}/live` — the endpoint that replaces H4.** Shape mirrors what `LivePage` already
renders, so the page becomes a pure view:

```jsonc
{ "data": {
  "train": { "number":"12301","name":"Howrah Rajdhani Express","type":"Rajdhani",
             "from":{"code":"HWH","name":"Howrah Jn"},"to":{"code":"NDLS","name":"New Delhi"} },
  "position": { "lastStation":{"code":"DHN"}, "nextStation":{"code":"GAYA"},
                "distanceCoveredKm":259, "totalDistanceKm":1451,
                "speedKmph":{"value":116,"source":"live"} | null,
                "delayMinutes":12, "lastUpdateAt":"2026-09-01T14:31:02Z" },
  "stops": [ { "code":"GAYA","name":"Gaya Jn","distanceKm":459,
               "scheduled":{"arr":"22:31","dep":"22:34"},
               "actual":{"arr":null,"dep":null},
               "eta":{"arr":"22:43","delayMinutes":12,
                      "band":{"p10":"22:38","p50":"22:43","p90":"22:57"},
                      "source":"model","confidence":0.78},
               "platform":{"value":"1","source":"schedule"} | null } ],
  "risk": { "delayProbability":0.34, "modelVersion":"risk-clf-2026.09.1",
            "topDrivers":[{"feature":"zone_congestion_index","contribution":0.11}] }
}, "meta": { "source":"live","degraded":false,"unavailableFields":[] } }
```

Note that `speedKmph` and `platform` are **nullable with a source tag**. If the provider does not
report live speed, the UI shows "—", not `128`.

**Contract workflow:** hand-authored `packages/contracts/openapi.yaml` → FastAPI validated against
it in CI (schemathesis) → `openapi-typescript` generates `apps/web/src/lib/api-client`. A shape
change that breaks the client fails CI. That is what makes D3 structurally unable to recur.

---

## 4. Data layer

### 4.1 Schema (Postgres 16 + PostGIS)

| Table | Key columns | Source | Notes |
|---|---|---|---|
| `stations` | `code` PK, name, state, zone, `geom(Point,4326)`, category | `stations.json` | ~8 k rows; PostGIS index for map / nearby queries |
| `trains` | `number` PK, name, type, from/to codes, `geom(LineString)` | `trains.json` | Route rendering with zero provider calls |
| `schedule_stops` | (`train_number`,`seq`) PK, station_code, day, arr, dep, distance_km | `schedules.json` | ~1.3 M+ rows; the schedule spine |
| `segments` | (`from_code`,`to_code`) PK, distance_km, sched_minutes, `hist_delay_added_p50/p90`, n_obs | **derived** from consecutive `schedule_stops` | The route graph. Stats start `NULL`, backfilled nightly |
| `live_observations` | id, train_number, journey_date, station_code, obs_at, delay_min, source | harvester | **Our ground truth.** Append-only, monthly partitions |
| `eta_snapshots` | id, train_number, journey_date, station_code, predicted_at, eta, model_version | api/worker | Lets us measure our own accuracy (§7.2) |
| `provider_calls` | id, provider, endpoint, status, latency_ms, called_at, cache_hit | middleware | Quota accounting + cost dashboard |
| `zone_stats` | zone_abbr, month, congestion_index, fog_index, severity | nightly job | Replaces the Kaggle synthetic indices with **our** measurements |
| `calendar_flags` | date, is_festival, season, is_monsoon | curated + rules | Feature source, no provider needed |
| `train_asset_profile` | train_number, has_lhb, coach_age_est, traction, confidence | curated / inferred | Explicit home for the unavailable features (§5.2) |

**No PNR table.** PNR data is request-scoped: cached in Redis under `sha256(pnr + salt)` for 60 s,
never written to Postgres, passenger names never logged. (Cures D7.)

### 4.2 Static ETL — the highest-leverage task in the plan (Phase 1, W1)

`etl_static_graph.py`: stream-parse the three JSON files (the 82 MB `schedules.json` must be
`ijson`-streamed, not `json.load`), bulk `COPY` into staging, upsert idempotently, then derive
`segments` by walking each train's ordered stops.

Outcome: **station search, train search, route geometry, schedules, and the entire ETA graph become
local reads at zero provider cost.** Every provider call afterwards is spent only on things that
genuinely change minute to minute — live position, PNR, station boards. This single job is what
makes the quota budget (§8) and the free-tier cost target achievable.

Target: full load < 10 min, re-runnable, with row-count and geometry-validity assertions.

---

## 5. The model question (read before writing any ML code)

### 5.1 The mismatch, stated plainly

| | Shipped model | Product need |
|---|---|---|
| Target | `is_delayed` — binary, >15 min late **at destination** | arrival time at **each remaining stop**, in minutes |
| Granularity | one row per journey | one row per (train, journey, stop) |
| Inputs | 44 columns incl. rake age, seat utilisation, maintenance score | whatever RailKit + our DB can supply at request time |
| Training data | **synthetic Kaggle set** (`ir_train.csv`) | real IR behaviour |
| Output usefulness | "this journey will probably be late" | "+12 min at GAYA, 22:43, ±9 min" |

The metrics printed by `train_eta_model.py` are honest *for that dataset* — but the dataset is
generated, so its AUC says nothing about real-world ETA error. **A model trained on synthetic data
must not produce the minute numbers a passenger plans around.** Doing so would reproduce D2 in a
more sophisticated disguise.

### 5.2 Feature-availability matrix — the constraint that drives the design

| Group | Features | Live availability |
|---|---|---|
| **Temporal** (9) | year, month, day_of_week, departure_hour, is_weekend, is_night_departure, is_peak_hour, is_festival_season, season | ✅ derivable — clock + `calendar_flags` |
| **Route / topology** (8) | distance_km, num_scheduled_stops, scheduled_travel_hours, track_doubled, is_hdn_route, psr_count, is_circular_route, is_electrified | 🟡 partly — first three from `schedule_stops`; the rest need one-time curation/OSM, then they are static |
| **Geography** (4) | zone, zone_abbr, source/destination station category | 🟡 zone ✅ from `stations`; IR station *category* (A1/A/B/…) needs a curated lookup |
| **Weather / hazard** (6) | is_monsoon_season, is_fog_risk, fog_risk_score, zone_fog_index, zone_congestion_index, season_severity_score | 🟡 rules + a weather API + `zone_stats` (ours, once accumulated) |
| **Operations** (2) | late_incoming_rake, route_historical_ontime_pct | 🟡 computable from `live_observations` **once we have history** — free after ~2 weeks of harvesting |
| **Rolling stock / occupancy** (9) | loco_age_years, coach_age_years, has_lhb_coaches, is_rake_shared, maintenance_score, seat_utilisation_pct, is_overloaded, is_special_train, traction_type | ❌ **not obtainable** from any public API — asset and occupancy data is internal to IR |

**~9 of 44 features are structurally unavailable.** Imputing them with training-set means and
serving the result as a live prediction is exactly the failure mode this plan exists to remove.

### 5.3 Resolution — a three-model ladder, shipped in order

- **M0 — Deterministic propagation (Phase 1, W2).** `eta_engine` walks the remaining `segments`,
  carries the current live delay forward, applies scheduled halt times and per-segment historical
  recovery/erosion (`segments.hist_delay_added_p50`; `NULL` → 0 until backfilled). Fully
  explainable, needs no training data, and is correct on day one for the dominant real case —
  "the train is 12 min late and will stay roughly 12 min late." **In Phase 1, every minute the UI
  shows comes from M0**, tagged `live` where a real fix exists and `schedule` where it does not.
- **M1 — Risk overlay (Phase 1, W3).** Retrain the existing classifier on the **live-feasible
  feature subset only** (drop the 9 unavailable columns; expect a lower AUC — that is the honest
  number). Serve it as `risk.delayProbability` plus a p10/p50/p90 **band width** around M0's point
  estimate — never as the point estimate itself. Publish both the full-feature and subset metrics on
  `/v1/meta/model` so the gap is visible rather than hidden.
- **M2 — Per-segment delay regressor (Phase 2).** Train on `live_observations` harvested by our own
  worker: target = `delay_added` across segment A→B for a real train on a real day. Features = M1's
  live-feasible set + segment identity + upstream delay + time of day + weather + our `zone_stats`.
  This is the model that can legitimately replace M0's per-segment estimate. Promotion is gated on
  §7.2 backtests beating M0 by a pre-declared margin on **held-out real journeys**.

Pretraining on the synthetic set stays useful — as initialisation and as a pipeline exercise — but
the promotion gate is always real data.

### 5.4 Serving

Load the artifact bundle (`model`, `feature_names`, `categorical_mappings`, `train_freq_map`) once
at API startup and keep it in process. `predict_proba` on a single ~60-feature row is sub-millisecond
at this scale — no separate inference service, and none until p99 says otherwise.

`packages/ml/features/` becomes the **single** feature implementation, imported by both the training
script and the API, so train/serve skew is impossible by construction. Today `engineer_features()`
lives only inside `train_eta_model.py`; copying it into the API would guarantee skew instead.

---

## 6. Phase 1 — "Real data, zero fiction" (Weeks 1–4)

**Goal:** the app runs on real fetched data end to end; not one number in the UI is invented; the
model contributes risk and confidence, not fabricated minutes.
**Definition of done:** grepping for the H1–H12 literals returns nothing, and every screen degrades
visibly and correctly when the provider is down.

### W1 — Foundation & the trust boundary

| # | Task | Deliverable | Owner |
|---|---|---|---|
| 1.1 | Monorepo skeleton; `WEB-1` → `apps/web` (git-mv, no rewrite); `Web-App` + `railkit_client.py` → `legacy/` | Repo builds; `pnpm dev` + `uv run` work | platform |
| 1.2 | `docker-compose.dev.yml`: postgres+postgis, redis, api, gateway | `docker compose up` → all healthy | platform |
| 1.3 | Secrets: `RAILKIT_API_KEY` **server-only**; `.env.example`; `.gitignore` audit; **rotate the key currently sitting in `ETA/.env`** | Zero keys reachable from the browser | platform |
| 1.4 | `rail-gateway`: Fastify + RailKit, all 14 endpoints, canonical DTO normalisation, per-endpoint quota counter | `GET /internal/pnr/:pnr` returns real data | backend-node |
| 1.5 | **Delete the client-side provider path**: remove `getApiConfig`/`saveApiConfig`, the Vite proxy, and the H6 modal | D1 & D5 closed | frontend |
| 1.6 | Alembic migrations for §4.1 | `alembic upgrade head` | backend-py |
| 1.7 | **Static ETL** — the 82 MB stream-parse job (§4.2) | ~8 k stations, ~1.3 M stops, derived `segments` in DB | data |

**Exit:** real PNR + real live status retrievable via `curl` through the gateway; static graph queryable.

### W2 — Domain API & the ETA engine

| # | Task | Deliverable |
|---|---|---|
| 2.1 | `openapi.yaml` v1 for §3; CI schema check | Contract merged |
| 2.2 | FastAPI skeleton: envelope, error taxonomy, request-id, structured logs with **PNR/name redaction** | `/v1/health` green |
| 2.3 | `infra/cache`: Redis get-or-load, per-key TTL, **single-flight**, stale-while-revalidate | Load test: 200 rps on one train ⇒ ≤1 provider call per TTL |
| 2.4 | `infra/provider_client`: gateway adapter + 3 s timeout + one jittered retry + **circuit breaker** + `provider_calls` audit | Breaker trips and recovers under test |
| 2.5 | Routers: stations, trains, search, pnr, board | Endpoints live on real data |
| 2.6 | **`domain/eta_engine.py` — M0** graph walk: remaining stops, cumulative delay, halt handling, day rollover, midnight crossing | Unit tests incl. multi-day trains (`12301`: 1,451 km, next-day arrival) |
| 2.7 | Generated TS client + typed hooks | `apps/web` compiles against the contract |

**Exit:** every §3 endpoint returns real data with a correct `meta` block; the ETA engine is tested
on multi-day, circular, and midnight-crossing routes.

### W3 — Frontend rewiring & the risk overlay

| # | Task | Deliverable |
|---|---|---|
| 3.1 | TanStack Query provider; `useTrainLive`, `usePnr`, `useStationBoard`, `useStationSearch` | Data layer in place |
| 3.2 | **Kill H4/H5/H12** — `LivePage` becomes a pure view over `/trains/{no}/live`; real 404 / empty / error / stale states | `trainsData` deleted |
| 3.3 | **Kill H1/H2/H10** — `PnrPage` on `/pnr/{pnr}`; drop the fabricated rake panel or gate it on real data | `getSimulatedPnr` deleted |
| 3.4 | **Kill H7/H8/H9** — autocomplete over 8 k real stations; real board; real popular list | `stationBoards` deleted |
| 3.5 | **Kill H11** — MapLibre + `route.geojson` + live position marker; RailRadar iframe removed | Our own map |
| 3.6 | Universal `<SourceBadge source confidence asOf/>`; skeletons; retry affordances; "provider degraded" banner | D2 structurally closed |
| 3.7 | **M1**: retrain the classifier on the live-feasible subset; publish both metric sets; wire `risk` + p10/p50/p90 band | `/v1/meta/model` live |
| 3.8 | Accessibility & responsive pass on every changed surface | axe clean on all 5 pages |

**Exit:** the app is fully live-data; disabling the gateway produces honest degradation, never fiction.

### W4 — Harvesting, hardening, ship

| # | Task | Deliverable |
|---|---|---|
| 4.1 | **`harvest_live.py`** — poll the top-N tracked trains every 5–10 min → `live_observations`. *Pull this earlier than W4 if at all possible: it is time-bound, not effort-bound, and every day of delay is a lost day of Phase-2 training data.* | Rows accumulating |
| 4.2 | `refresh_boards.py` for top stations (warm cache, cheap reads) | Board p95 < 150 ms |
| 4.3 | Nightly marts: `segments` stats backfill, `zone_stats` | M0 gains real per-segment recovery behaviour |
| 4.4 | Rate limiting (per-IP + global provider budget), abuse guards, CORS allowlist | Quota cannot be burned |
| 4.5 | Observability: OTel traces, Prometheus (`provider_latency`, `cache_hit_ratio`, `breaker_state`, `eta_error`), Sentry | Dashboard + 3 alerts |
| 4.6 | Tests: unit (engine, features, cache), contract (schemathesis), integration (recorded provider fixtures), 2 Playwright E2E | CI green, ≥70 % coverage on `domain/` |
| 4.7 | CI/CD: lint/typecheck/test/build, images, migrations-on-deploy, staging → prod | One-click deploy |
| 4.8 | Docs: runbook, ADRs, `/docs` OpenAPI UI, a public "what's real vs. estimated" page | Reviewable |

**Phase 1 exit criteria — all must hold:**

1. Zero data literals in `apps/web` (enforced by a CI grep rule over the known fixture patterns).
2. No third-party key or provider hostname in any client bundle (enforced by a bundle-scan CI step).
3. Provider down ⇒ every screen shows stale-with-timestamp or an error state; **never** invented data.
4. p95 latency: cached < 200 ms, cold < 1.5 s.
5. Cache hit ratio > 80 % on live endpoints under realistic traffic.
6. `live_observations` growing daily; ≥14 days banked before Phase 2 modelling starts.
7. `/v1/meta/model` states publicly which features are unavailable and how that limits our claims.

---

## 7. Phase 2 — "Earned intelligence & scale" (Weeks 5–10+)

Phase 2 is unblocked *only* by Phase 1's harvested data. Everything here compounds.

### 7.1 Real ETA modelling (M2) — weeks 5–7

- Build the training mart from `live_observations` ⋈ `schedule_stops` ⋈ `segments` ⋈ weather ⋈
  `calendar_flags`: one row per (train, journey_date, segment), target `delay_added_minutes`.
- **Time-based splits only** — train on weeks 1…k, validate on k+1. Random splits leak on a temporal
  process and would recreate the synthetic-data optimism in a new costume.
- LightGBM/HistGB **quantile** regression (α = 0.1 / 0.5 / 0.9) → genuinely calibrated prediction
  intervals, replacing M1's heuristic band.
- Promotion gate: MAE *and* interval coverage beat M0 on held-out **real** journeys by a
  pre-declared margin; otherwise M0 stays. Model registry + metric cards + one-command rollback.

### 7.2 Backtesting & accuracy telemetry — week 7

Join `eta_snapshots` (what we predicted) against `live_observations` (what happened) → continuous
MAE by horizon (30/60/120/240 min out), zone, train type, and hour of day. **Publish it in the UI.**
A system whose pitch is "better ETA than the schedule" must show its own error bars — and this is
also the single strongest demo artifact available to us.

### 7.3 Explainability & the RAG assistant — weeks 7–8

- Per-prediction SHAP top drivers (already stubbed as `risk.topDrivers`).
- "Why is my train late?" — retrieval over `live_observations` + `segments` history + a delay-cause
  taxonomy, composed by an LLM but **grounded strictly in the features the model actually used**,
  multilingual (Hindi + regional). It refuses to answer where data is absent rather than
  confabulating a cause.
- Turn `Web-App/PredictionSandbox` into a real UI over `POST /v1/eta/simulate`.

### 7.4 Platform maturity — weeks 8–10

- **Realtime:** SSE/WebSocket push for tracked trains (replaces client polling); Redis pub/sub fan-out.
- **Multi-provider:** a second adapter (API Mitra / NTES) behind the same DTO; per-field
  cross-validation, automatic failover, and a provider-quality scorecard.
- **Async:** Celery/Arq + beat; harvest fan-out by zone; backpressure.
- **Data:** partition `live_observations` monthly, retention policy, cold storage to Parquet;
  DVC/lakeFS for dataset and model lineage.
- **API surface:** ETag/`If-None-Match`, cursor pagination, API keys + tiered rate limits if opened
  to third parties, a `/v2` policy with deprecation windows.
- **Reliability:** blue/green deploys with migration gates, weekly chaos drills (kill the gateway in
  staging), documented SLOs (99.5 % availability; freshness < 90 s for tracked trains) with error budgets.
- **Product:** journey subscriptions + push alerts ("your train just slipped 20 min"),
  platform-change alerts, PWA offline-last-known, i18n, a zone congestion heatmap over real `zone_stats`.
- **Governance:** DPDP-aligned PNR handling (no retention, redaction, documented lawful basis),
  provider-ToS compliance review, security review (authn on write paths, dependency scanning,
  secret rotation).

---

## 8. Non-functional requirements

| Concern | Target / policy |
|---|---|
| Latency | p95: cached 200 ms · cold 1.5 s · ETA compute (100-stop walk) < 20 ms |
| Freshness | tracked trains ≤ 90 s · station boards ≤ 60 s · PNR on demand ≤ 60 s |
| Provider budget | ≤ N calls/day (set from the actual plan), enforced by a **global token bucket**; hard-fail to stale rather than exceed quota |
| Availability | Phase 1 best-effort · Phase 2 99.5 % monthly with an error budget |
| Degradation | ordered ladder: fresh → cached → **stale-with-timestamp** → schedule-only → explicit error. **Never** synthetic |
| Security | keys server-side only · CORS allowlist · rate limits · no PII in logs/metrics/traces · Dependabot + `pip-audit` |
| Privacy | PNR: 60 s Redis TTL under a salted hash, no persistence, names never logged, no analytics on PNR payloads |
| Observability | traces on every provider call · RED metrics per route · `cache_hit_ratio`, `breaker_state`, `provider_quota_remaining`, `eta_mae` |
| Testability | domain logic pure and provider-free; all provider I/O behind one interface with recorded fixtures |
| Cost | Phase 1 stays inside free tiers (Neon/Supabase, Upstash, Fly/Render, Vercel); the static ETL is what keeps provider spend near zero |

---

## 9. Risk register

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | Provider quota/rate limits bite under demo load | High | Static ETL removes most calls; single-flight + an 80 % cache floor; global token bucket; pre-warm the demo trains |
| R2 | RailKit is obfuscated and single-vendor; ToS or availability changes | High | Adapter isolation from day one; second provider in Phase 2; the DTO layer makes a swap ≈ one file |
| R3 | The synthetic-trained model quietly becomes the source of user-facing minutes | **Critical** (credibility) | Structural: M0 owns minutes in Phase 1; M1 is band + probability only; M2 promotion gated on real-data backtests; `/v1/meta/model` public |
| R4 | 9 features permanently unavailable ⇒ a weaker model than the Kaggle score implies | Medium | Publish subset metrics honestly; `train_asset_profile` for slow curation; lean on `live_observations`-derived operational features, which are the strongest signal actually available |
| R5 | The 82 MB / 1.3 M-row ETL blows memory or wall-clock | Medium | `ijson` streaming + `COPY` bulk load + idempotent upsert; assert row counts |
| R6 | The two frontends diverge further | Medium | Decide D-1 in W1: fold `Web-App`'s three good components into `apps/web`, freeze the rest in `legacy/` |
| R7 | PNR PII mishandled | High (legal) | No persistence, hashed cache key, redaction at the log formatter, covered by a redaction unit test |
| R8 | Scope creep (RAG / realtime pulled into Phase 1) | Medium | Phase gates: nothing in §7 starts until all seven Phase-1 exit criteria pass |
| R9 | The API key already committed in `ETA/.env` is leaked | High | Rotate in W1 task 1.3; add a pre-commit secret scan; treat the old key as burned |
| R10 | Live data arrives with unstable/undocumented schemas | Medium | Strict Pydantic validation at the gateway boundary; unknown-field logging; `unavailableFields` instead of defaults |

---

## 10. Decisions needed from the team

| # | Decision | Recommendation |
|---|---|---|
| D-1 | Fate of `Web-App/` | Fold `ArchitectureFlow`, `TemporalConfidence`, `PredictionSandbox` into `apps/web` (they become real once `/eta/simulate` exists); freeze the rest in `legacy/` |
| D-2 | Provider strategy | RailKit as primary (already keyed and typed); design the adapter seam now, add a second provider in Phase 2 |
| D-3 | Hosting | Fly.io for api + gateway + worker (co-located, cheap), Neon Postgres, Upstash Redis, Vercel for web |
| D-4 | Auth | None in Phase 1 (read-only public data) + rate limits; add auth in Phase 2 when subscriptions land |
| D-5 | Map tiles | MapLibre + free raster/vector tiles; route geometry from our own DB — no vendor lock |
| D-6 | Model-minutes policy | **M0 owns user-facing minutes until M2 passes its gate.** Recommend adopting this as a written rule |

---

## 11. Architecture Decision Records

- **ADR-001 — Two backend services (Python API + Node gateway).** *Alternatives:* all-Node (loses
  scikit-learn), all-Python (loses the obfuscated SDK), subprocess bridge (ADR-002). *Chosen* for
  native runtimes plus a clean provider seam. *Cost:* one extra hop (~2–5 ms in-cluster) and one
  more deployable.
- **ADR-002 — Delete `railkit_client.py`'s per-call `node -e` subprocess.** Spawn cost, no pooling,
  no caching, key on argv, unbounded concurrency. Superseded by a long-lived HTTP service.
- **ADR-003 — Contract-first OpenAPI with a generated client.** Prevents the type drift already
  present between `railApi.ts` and `LivePage.tsx`, and turns breaking changes into CI failures.
- **ADR-004 — No synthetic fallback, ever.** The fallback ladder ends in an explicit error state.
  Rationale: an accuracy product cannot ship a code path that fabricates data under a live label.
- **ADR-005 — Deterministic propagation (M0) owns user-facing minutes** until a real-data model wins
  a backtest. ML enters as bands and probabilities first.
- **ADR-006 — One feature implementation in `packages/ml/features`,** imported by both trainer and
  API. Eliminates train/serve skew by construction.
- **ADR-007 — Local static graph before provider calls.** Load `indian-railways-dataset` into
  Postgres so search, routes, and schedules are free and instant, cutting the provider dependency
  down to genuinely volatile data.

---

## 12. Immediate next actions (first 48 hours)

1. **T-0** — Rotate `RAILKIT_API_KEY` (it is currently sitting in `ETA/.env`) and add a pre-commit
   secret scan.
2. **T-1** — `git init` the monorepo, `git mv WEB-1 apps/web`, move `Web-App` → `legacy/`.
3. **T-2** — `docker compose up` with postgres+postgis+redis; run the first Alembic migration.
4. **T-3** — Stand up `rail-gateway` and prove one real `checkPNRStatus` and one real `trackTrain`
   round trip. **This is the go/no-go on the entire plan** — everything downstream assumes the
   provider works with the current key and quota.
5. **T-4** — Start the static ETL (`stations.json` first: smallest file, and it unblocks autocomplete).
6. **T-5** — Open a tracking issue per H1–H12 so hardcode removal is visible and closable.

> **Sequencing rationale:** T-3 de-risks the external dependency before a line of code is written on
> top of it, and T-4 produces the artifact every other component consumes. The live harvester (4.1)
> should be pulled forward from W4 wherever possible — it is the only task where calendar time,
> rather than effort, sets Phase 2's ceiling.

---
---

# PHASE 1 — IMPLEMENTATION STATUS

**Implemented:** 2026-09-01 · verified against live provider data and, unplanned, against a real provider outage.

## 13. What shipped

| Plan task | Status | Where |
|---|---|---|
| 1.1 Monorepo skeleton | **Partial** — `services/`, `packages/`, `data/` created; `WEB-1` left in place (D-7) | repo root |
| 1.2 Local infra | **Deviated** — SQLite + in-process cache instead of Docker Postgres/Redis (D-8) | `data/darpan.sqlite` |
| 1.3 Secrets server-side | **Done** — key only in the gateway; `.env.example` added; **rotation still outstanding** | `.env.example` |
| 1.4 rail-gateway | **Done** — 7 routes, DTO normalisation, quota budget, concurrency cap, typed errors | `services/rail-gateway/` |
| 1.5 Delete client provider path | **Done** — `railApi.ts` deleted, Vite proxy retargeted, settings modal removed | `WEB-1/src` |
| 1.6 Schema | **Done** — 11 tables incl. `segments`, `live_observations`, `eta_snapshots` | `etl_static_graph.py` |
| 1.7 Static ETL | **Done** — 8,990 stations · 5,208 trains · 417,080 stops · 16,509 segments in 20.5s | `services/worker/jobs/` |
| 2.1 Contract | **Deviated** — generated from the running API rather than hand-authored (D-9) | `packages/contracts/openapi.json` |
| 2.2 Envelope + PII redaction | **Done** — uniform envelope incl. validation errors; formatter-level PNR filter | `app/main.py` |
| 2.3 Cache + single-flight | **Done** — measured 25,180 ms cold to 33 ms cached | `app/infra/cache.py` |
| 2.4 Provider client + breaker | **Done** — breaker correctly does *not* trip on 4xx | `app/infra/provider.py` |
| 2.5 Routers | **Done** — 14 endpoints | `app/main.py` |
| 2.6 **ETA engine (M0)** | **Done** — 14 unit tests incl. midnight crossing and multi-day runs | `app/domain/eta_engine.py` |
| 2.7 Typed client + hooks | **Done** — dependency-free (D-10) | `WEB-1/src/lib`, `src/hooks` |
| 3.1–3.6 Frontend rewiring | **Done** — H1–H12 all closed | `WEB-1/src/pages` |
| 3.7 Risk overlay (M1) | **Partial** — artifact served as probability-only with full disclosure; **subset retraining not done** (F-6) | `app/domain/risk_overlay.py` |
| 4.1 Harvester | **Done** — running; first observations banked | `harvest_live.py` |
| 4.3 Nightly marts | **Done** — segment deltas + zone stats | `nightly_marts.py` |
| 4.4 Rate limiting | **Done** — per-IP, plus the gateway's global budget | `app/main.py` |
| 4.6 Tests | **Partial** — 17 gateway + 14 engine tests; **no Playwright E2E** | `*/test*/` |
| 3.8 / 4.2 / 4.5 / 4.7 | **Not done** — a11y audit, board pre-warm, OTel/Prometheus/Sentry, CI/CD | — |

**Hardcode kill list: H1–H12 all closed.** Verified by grep over `src/` (only documentation
comments remain) and by scanning the built bundle: zero occurrences of `apimitra`,
`railkit_`, `indianrailapi`, or `railradar`.

## 14. Findings that change the plan

**F-1 — R1 materialised on day one: the provider quota is already exhausted.**
After 26 calls the account began returning *"Usage limit exceeded for current billing
cycle"*. PNR and uncached live lookups now fail. This is the biggest risk to a demo and
needs a decision before anything else: upgrade the RailKit plan, or pull the second
provider adapter forward from Phase 2. **The mitigation worked exactly as designed** —
station search, train search, route geometry, schedules and cached live status all kept
serving from the local store, so the product degrades to "mostly working" rather than
"down". This is the clearest possible vindication of ADR-007 (load the static graph
first).

**F-2 — the 1.5 s cold-latency target is not achievable and should be rewritten.**
Provider `trackTrain` latency ranged 0.5–10 s across the session. Section 8 should read:
*cached p95 < 200 ms (achieved ~35 ms); cold latency is provider-bound and effectively
unbounded; the mitigation is worker pre-warming, not optimisation.*

**F-3 — live speed does not exist.** The provider reports no speed field at all, so H4's
`speed: 128` was not merely stale, it was unobtainable. It is now permanently rendered
"—" with the reason on hover. UI copy promising "precision GPS speed" should be dropped.

**F-4 — coach composition is real, so H10 became a feature rather than a deletion.**
`trackTrain` returns a 24-unit rake (ENG, LPR, B1–B11 3A, PC, H1–H2 1A, A1–A6 2A, VP).
Both the Live and PNR pages now render it, with the passenger's own coach highlighted.

**F-5 — the provider supplies its own ETA projection for upcoming stops.** That is a free
accuracy baseline to beat before our own ground truth accumulates. `/v1/eta/{no}` reports
`providerCrossCheck.meanAbsDivergenceMinutes` instead of silently preferring either
estimate. **Recommend adopting this as a Phase 2 promotion benchmark** for M2, alongside
the M0 comparison.

**F-6 — the risk model needs 23 imputed features, not 9.** Section 5.2 counted the nine
structurally-unavailable rolling-stock and occupancy columns, but not the amber route and
geography rows we have not curated (`psr_count`, `track_doubled`, `is_hdn_route`, station
categories, zone indices, `route_historical_ontime_pct`, the festival calendar). Over half
the feature vector is currently assumption. This raises the priority of the W3.7 subset
retraining, which remains **outstanding**: the artifact is served as-is with disclosure,
which is honest but is not yet the plan's M1.

**F-7 — dataset facts corrected.** `schedules.json` holds **417,080** rows, not the ~1.3 M
estimated in section 4.1. Static timings also drift from live reality (12301 departs HWH
at 16:55 in the dataset, 16:50 per the provider), so `segments` are used for topology and
as a scheduled baseline only — live data always overrides.

**F-8 — two engine bugs surfaced only by running against a live train**, both now covered
by regression tests: a passed *origin* has no arrival leg and was being rendered as an
estimate carrying the current delay (`Howrah Jn … +14m` for a station already departed);
and a symmetric confidence band around a late ETA implied a possible *early* arrival
(NDLS p10 of 09:40 against a 10:05 scheduled arrival). The optimistic edge is now floored
at the scheduled time whenever the train is running late.

## 15. Exit criteria

| # | Criterion | Status |
|---|---|---|
| 1 | Zero data literals in the web app | **PASS** — grep + bundle scan clean |
| 2 | No third-party key or host in the client bundle | **PASS** |
| 3 | Provider down ⇒ stale or error, never invented data | **PASS — verified against a real outage**, not a simulation |
| 4 | p95 cached < 200 ms / cold < 1.5 s | **PARTIAL** — cached ~35 ms passes; cold is provider-bound (F-2) |
| 5 | Cache hit ratio > 80 % | **Not measured** under realistic traffic |
| 6 | `live_observations` growing; ≥14 days before Phase 2 | **STARTED** — day 1 of 14 |
| 7 | `/v1/meta/model` publishes feature unavailability | **PASS** |

## 16. New deviations

| # | Deviation | Rationale | Reversal cost |
|---|---|---|---|
| D-7 | `WEB-1` not moved to `apps/web` | It is the session's working directory; moving it mid-session risked breaking tooling | Low — `git mv` plus one path update |
| D-8 | SQLite + in-process cache, not Postgres + Redis | Docker daemon not running. Ports-and-adapters means both real adapters already exist behind the same interfaces (`RedisCache` in `infra/cache.py`, `Repo` in `infra/repo.py`) | Low — config swap plus a Postgres `Repo` |
| D-9 | OpenAPI generated, not hand-authored | FastAPI emits an accurate 3.1.0 spec; a hand-authored copy would have drifted immediately | None — CI validation can still be layered on |
| D-10 | No TanStack Query | Five screens need abort, dedupe and polling only; every page consumes one `{data, meta, error, loading}` shape | Low — mechanical |
| D-11 | `node:http`, not Fastify | Zero install, and no supply-chain surface on the one process that holds a secret | Low |

## 17. Immediate next actions

1. **Resolve the provider quota (F-1).** Blocking for any demo. Upgrade the plan, or pull
   the second provider adapter forward from Phase 2.
2. **Rotate `RAILKIT_API_KEY`** — still outstanding from T-0, and the current key sits in
   the repo's `.env`.
3. **Leave `harvest_live.py --interval 600` running.** Day 1 of the 14 needed before M2
   training. Calendar-bound: nothing recovers lost days later.
4. **Do the W3.7 subset retraining** and publish both metric sets, now that F-6 shows the
   imputation is materially worse than estimated.
5. Then the untouched W4 items: observability, CI/CD, Playwright E2E, accessibility audit.

---
---

# PHASE 2 — PROGRESS (session 2)

Phase 2's headline item (M2, the per-segment regressor) is **calendar-blocked**: it needs
~14 days of harvested observations and we are on day 1. The provider quota is also
exhausted (F-1), which blocks anything requiring live calls. So this session took the
work that is blocked by neither, prioritising the two items that are themselves
calendar-bound or integrity-critical.

## 18. Radar View separated from Map

Two distinct surfaces, per the product decision:

| Surface | Data | Dependency |
|---|---|---|
| **Map** tab | Ours — `trains.geometry` (5,208 LineStrings) + our live position + per-stop ETA | none |
| **Radar** tab | RailRadar's network-wide live radar, embedded | external |

`RadarPage.tsx` renders the embed full-screen (with an expand control) under a source bar
that names RailRadar and links out; their in-frame branding is untouched. Treated as
untrusted third-party content: least-privilege `sandbox`, `referrerPolicy="no-referrer"`,
no credential passthrough, and a timeout-based failure state — `onError` does not fire
when a site refuses embedding via CSP `frame-ancestors`, so a timer is the only way to
detect that. Nav went from five tabs to six (`rd-6`, label widths trimmed to fit); the
header "Radar View" pill now opens Radar rather than Map.

Note for the record: styling or hiding anything *inside* that frame is not possible
regardless of intent — same-origin policy blocks all CSS/JS access to `railradar.in`.

## 19. M1 subset retraining — task W3.7 closed, F-6 answered

`packages/ml/train_risk_classifier.py` retrains the risk classifier on **only the
features the running API can genuinely source**, and reports both models side by side on
identical data (full 1.5M synthetic rows):

| metric | full, 44 cols (not servable) | **subset, live-feasible (served)** | cost of honesty |
|---|---|---|---|
| ROC AUC | 0.9229 | **0.8494** | −0.0735 |
| PR AUC | 0.9677 | **0.9349** | −0.0328 |
| Brier | 0.0978 | **0.1375** | +0.0397 |
| Accuracy | 0.8618 | **0.7963** | −0.0655 |

Subset generalisation gap (train − val ROC AUC): **0.0000**.

16 raw features kept (25 after engineering), 28 dropped — each with a recorded reason,
which makes `droppedFeatures` an itemised data-access request rather than a shrug. **8 of
the 28 are IR-internal** (rake age, LHB, rake sharing, maintenance score, seat
utilisation, overload, special-train flag, traction) and unobtainable without an
agreement; the rest are either uncurated route attributes or pending our own harvested
history.

**The −0.0735 AUC gap is now a quotable figure for exactly what the missing IR data is
worth.** That is more useful than the original 0.92 headline, which was only reachable by
imputing over half the feature vector at inference time.

Serving changed accordingly:
- `eta_model_subset.joblib` is loaded in preference to `eta_model.joblib`; the legacy
  artifact is a fallback that self-reports as low-confidence.
- **`imputedFeatureCount` went 23 → 0.** Each prediction now reports
  `featureProvenance` in three buckets — 9 `measured`, 7 `derived`, 0 `imputed`.
- `derived` is a deliberately separate bucket from `imputed`: `is_fog_risk` and
  `fog_risk_score` are computed by *our* documented rule (winter month + pre-noon +
  fog-prone zone), which approximates rather than reproduces the training set's
  generator. Calling that "measured" would overstate it.
- `/v1/meta/model` publishes both metric columns, the kept/dropped lists, and the
  synthetic-training caveat.

## 20. Accuracy telemetry — §7.2 foundation laid

`app/infra/snapshots.py` records every ETA served into `eta_snapshots`; 6 unit tests.
Fire-and-forget on a background thread with its own write connection, so the request path
keeps its read-only `Repo` guarantee and telemetry can never slow or break a user request.
Deduplicated per minute, so 60-second polling does not swamp the signal.

Two design points worth keeping:
- **Only forecasts are recorded.** A passed stop is an observation and belongs to
  `live_observations`; recording it as a prediction would let the scorer compare a
  measurement against itself and report a flattering zero error.
- Telemetry is expendable under pressure — a full queue drops rows rather than blocking.

`services/worker/jobs/score_accuracy.py` joins predictions against outcomes and scores
**three baselines on identical rows**: `schedule` (the incumbent), `provider` (their own
projection), and `m0` (ours). It prints MAE, signed bias, p90 error and p10–p90 interval
coverage, grouped by horizon, zone or train type, and states the verdict plainly —
including *"THE CORE CLAIM DOES NOT HOLD YET"* if M0 fails to beat the timetable. Better
to learn that from a job than from a judge.

This is the M2 promotion gate from §7.1, and it doubles as the strongest demo artifact
available: a system claiming better-than-timetable ETA should show its own error bars.

## 21. Still blocked / not started

| Item | Blocker |
|---|---|
| M2 per-segment quantile regressor (§7.1) | needs ~14 days of observations; day 1 |
| Populating `eta_snapshots` / running the scorer | needs the quota restored (F-1) |
| Segment history reaching `n_obs >= 5` | needs sustained harvesting |
| SHAP per-prediction drivers (§7.3) | unblocked; not started |
| RAG "why is my train late" (§7.3) | needs an LLM key + budget decision |
| Realtime SSE, multi-provider adapter, ETag (§7.4) | unblocked; not started |
| Observability, CI/CD, Playwright E2E, a11y | carried over from Phase 1 W4 |
