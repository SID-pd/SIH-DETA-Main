# Implementation Plan — Dynamic ETA for Coaching Trains (SIH26028)

Master planning document. Companion files: [project-architecture.md](./project-architecture.md) (stack
detail), [ui-structure.md](./ui-structure.md) (screens), [eta-pipeline-diagram.md](./eta-pipeline-diagram.md)
(visual architecture), [eta-data-sources-and-prior-art.md](./eta-data-sources-and-prior-art.md) and
[openrailwaymap-and-osm-data.md](./openrailwaymap-and-osm-data.md) (data sources),
[problem-statement-selection.md](./problem-statement-selection.md) (why this PS).

## 1. Problem, restated

Indian Railways currently forecasts coaching-train ETA from static schedules, current delay, and
built-in recovery time — it doesn't account for real-time ground conditions (congestion, weather,
late incoming rakes, unscheduled halts). Passengers, station staff, and downstream logistics all plan
against a number that's frequently wrong. The PS asks for a system that dynamically forecasts ETA
from live data and keeps refining it as the journey progresses.

## 2. Solution, in one paragraph

A pipeline that polls Indian Railways' own live-tracking system (NTES) continuously, combines that
with the static rail network graph and weather data, and feeds a gradient-boosted model that predicts
incremental delay for every remaining stop on a train's route. A lightweight API walks the route graph
and turns that into a per-station ETA, served to a live dashboard. When a train is delayed, a
retrieval-based assistant explains *why*, grounded in the same features the model used — not a
generic chatbot bolted on top.

## 3. Architecture

```
Live sources (NTES, ETrain, weather)  ──┐
Static graph (datameet/railways)      ──┤──▶  Postgres + Redis  ──▶  Feature engine  ──▶  LightGBM
                                                     │                                        │
                                                     ▼                                        ▼
                                              eta_engine (graph walk,               predicted incremental
                                              cumulative delay propagation)  ◀──────────────  delay
                                                     │
                                                     ▼
                                          FastAPI  ──▶  React dashboard (map, ETA, chat)
                                                     │
                                                     ▼
                                          rag_assistant (retrieval over historical
                                          delay causes + live features + LLM)
```

Full tech stack, repo layout, and team ownership: [project-architecture.md](./project-architecture.md).

## 4. Data model — the "placeholder" entity schema

Every station, track segment, and train stop is a typed record that starts mostly empty and gets
filled in over time, rather than requiring complete data upfront:

- **Station** (node): id, code, coordinates, zone, category, `connected_stations` (derived free from
  schedule data — two consecutive stops in any train's timetable = an edge), `track_doubled`
  (capacity proxy), `electrified` (optional, OSM-sourced later).
- **Segment** (edge, station A→B): distance, scheduled travel time, `historical_avg_delay_added`
  (starts null, gets backfilled — see §5).
- **Run-point** (one train's one stop on one day): scheduled vs. actual arrival, delay minutes,
  and a `source` tag — `schedule` → `baseline_estimate` → `live_observed` → `live_model` — plus a
  `confidence` value, so the UI can honestly show "estimated" vs. "live" instead of treating every
  number as equally solid.

Defined once as typed **SQLModel** classes so the same definition serves as the Postgres schema, the
Pydantic validation layer, and the FastAPI request/response contract.

## 5. Model strategy — two stages, not one heavy model

**Stage 1 — baseline / cold-start.** Trained on the Kaggle synthetic 44-feature schema (proven to
0.92 accuracy on this exact feature shape — see data-sources doc) plus the static graph. Its job:
give a reasonable ETA for any station/segment that has no real history yet, and backfill
`historical_avg_delay_added` for those segments via `sklearn.IterativeImputer` (impute from similar
segments — same zone, same `track_doubled` flag, same train type). Every prediction from this stage
is tagged `baseline_estimate`.

**Stage 2 — live.** Same model family (LightGBM), retrained on a schedule (nightly cron) against
`live_events` as the NTES poller accumulates real data. Once a segment has enough real observations,
its predictions switch to this stage, tagged `live_model`, and `historical_avg_delay_added` gets
recomputed from real data instead of the imputed value.

The handoff is **per-segment, not global** — high-traffic segments graduate to Stage 2 within days;
sparse routes may still be on Stage 1 by demo day. That's expected, and the `confidence` field makes
it visible rather than hidden.

**Why LightGBM and not deep learning**: trains in seconds on a laptop, no GPU, sample-efficient on
the small real dataset that's still accumulating, and `shap.TreeExplainer` gives free,
one-line-of-code feature attribution — which *is* the "why is it late" explanation, not a separate
system. GNN/deep spatio-temporal approaches (cited in the data-sources doc) are named explicitly as
future work, not attempted now — see §7.

## 6. Network effects — bounded, not simulated

A delay at one station can affect other trains through shared track, congestion, and rake/crew reuse.
Full network simulation (every train, every switch, recomputed on every event) is a hard
operations-research problem on its own — not attempted here. Instead:

- **Statistical proxy features** (`zone_congestion_index`, `late_incoming_rake`,
  `station_current_load`) let the model learn network effects from historical correlation — the same
  approach production ETA systems (ride-hailing, maps) use. Cost: a SQL aggregation, not a
  simulation.
- **Bounded event-propagation** (stretch goal, good demo visual): when a disruption is flagged at
  station X, walk forward through the schedule graph only for trains passing through X within an
  N-hour window, and nudge their ETA. A bounded BFS/priority-queue problem — blast radius is
  *time-window × trains actually affected*, not the whole network, which is what prevents the "one
  operation crashes everything" failure mode.

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| NTES rate-limits or blocks the poller | ETrain.info scrape as a documented backup source (see data-sources doc) |
| Not enough real data accumulated by demo day | Stage 1 baseline model + Kaggle synthetic schema keeps every segment answerable from day one |
| Network-wide modeling attempted, doesn't finish in time | Explicitly scoped out (§6) — statistical proxies + bounded propagation only |
| Heavy DL model fails to train / underperforms on small data | LightGBM only for the core predictor; DL cited as future work, never on the critical path |
| "Why is it late" answers disagree with the displayed delay tags | Both are generated from the same SHAP output on the same model call — single source of truth |
| Team unfamiliar with a piece of the stack | Ownership mapped to existing skills — see [project-architecture.md](./project-architecture.md) §Team ownership |

## 8. Future features

Beyond the hackathon MVP, roughly in order of cost vs. value:

**Near-term (cheap, high passenger value)**
- Delay/arrival alerts via push notification (PWA) or SMS for passengers without a smartphone
- Save a journey / PNR for one-tap re-check
- Historical reliability score per train ("on time 61% of the time this monsoon"), computed from
  `live_events` already being collected

**Public-utility features**
- Feeder transport suggestions at the destination station (explicitly called out in the PS)
- Alternate-route nudges when a connection is at risk of being missed
- Crowdsourced ground reports (arrival confirmation, platform correction, coach condition) — patches
  NTES coverage gaps in remote/low-signal sections
- Voice + regional-language input
- Low-data mode / SMS-keyword query path for 2G or feature-phone users

**Ecosystem / infrastructure**
- Public API (`/trains/:id`, `/stations/:code/board`, etc.) — matches the PS's own ask for APIs
  feeding mobile apps, station displays, and control-room dashboards
- Physical station display board integration
- A full Control Room analytics view for Railways staff: recurring bottleneck routes, seasonal delay
  patterns, per-zone trends

**Long-term vision (name-drop, don't build)**
- Real track/switch-level topology from OpenRailwayMap/OSM, replacing the schedule-derived adjacency
  graph where precision matters (junction-level conflict detection)
- Full network-wide dispatch optimization — hybrid RL (scheduling heuristics) + operations research
  (safety-constrained MILP) + explainable AI, in the spirit of the RailFlow reference project — the
  natural end-state of the "bounded propagation" idea in §6, scaled up once there's a real deployment
  and a much larger data/compute budget than a 3-week hackathon allows
- Deep spatio-temporal models (graph neural nets, per the HetETA/LibCity references) once enough real
  training data exists to justify moving past LightGBM
