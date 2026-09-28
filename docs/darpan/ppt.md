# Pitch Deck Content Plan — SIH26028

Follows the standard SIH pitch template (Title → Idea → Technical Approach → Feasibility → Impact →
References). 6 slides — that's the format SIH judges expect and skim fast, so every slide below is
written to be readable in ~15 seconds, not read aloud. Content pulls from
[implementation-plan.md](./implementation-plan.md), [project-architecture.md](./project-architecture.md),
and [ui-structure.md](./ui-structure.md) — this file defines what goes *on the slide*, not the full
detail behind it.

## Theme

Carries the same identity as the architecture diagram artifact already built, so every submitted
material (deck, diagram, demo) reads as one product rather than three unrelated files.

- **Palette**: deep navy ground (`#0d1420`–`#101827`) with off-white text (`#e7ecf5`), one warm
  signal-amber accent (`#eab04a`) for headlines/highlights, signal-green (`#4fbf8b`) for
  positive/on-time stats, signal-red (`#e2584a` — used sparingly, only for risk/challenge callouts).
  This is a railway signal-board palette, not a generic dark-mode default — it's grounded in the
  subject (signal lamps are amber/green/red) and matches the diagram you already have.
- **Type**: headings in **Barlow Condensed** (bold, uppercase for eyebrows/labels — echoes station
  departure-board signage), body in **IBM Plex Sans**, data/metrics/code snippets in **IBM Plex
  Mono**. Same pairing as the diagram artifact.
- **Layout**: every content slide keeps a thin top eyebrow bar (slide number + section name, mono,
  amber) and a consistent left-aligned title — no centered walls of text, no clip-art. Diagrams and
  screenshots get a "monitor panel" treatment (dark panel, thin border) matching the diagram artifact
  so a screenshot of the dashboard or the architecture diagram drops in without looking like a
  mismatched insert.
- **One practical note**: PowerPoint/Google Slides can't render mermaid natively — export the
  architecture diagram from the published artifact as a PNG/SVG screenshot before placing it on
  Slide 3, don't paste the raw mermaid code.

---

## Slide 1 — Title

- **Problem Statement ID**: SIH26028
- **Problem Statement Title**: Dynamic Forecast of Expected Time of Arrival (ETA) for Coaching Trains
- **Theme**: Smart Automation
- **Category**: Software
- **Organization**: Ministry of Railways
- Team name, team leader, member names — *(fill in)*
- Visual: minimal — the deck's amber accent line, project name, nothing else competing for attention.

## Slide 2 — Idea / Proposed Solution

**Headline**: Turn ETA from a static schedule lookup into a live, self-explaining forecast.

- **What it is**: A pipeline that continuously polls Indian Railways' own live-tracking system (NTES),
  combines it with the rail network graph and weather data, and predicts arrival time at every
  upcoming station — updated as the journey progresses, not computed once at departure.
- **How it addresses the problem statement**: Replaces "schedule + current delay + fixed recovery
  time" with a model trained on real running conditions (congestion, weather, late incoming rakes),
  refreshed continuously and served through APIs to apps, station displays, and control rooms — as
  the PS itself asks for.
- **What's actually new here** (3 bullets, this is what differentiates from every other team's
  "ML delay predictor"):
  1. **Self-explaining, not just a number** — when a train is late, the system says *why* (fog,
     congestion, a late incoming rake), grounded in the same features the model used, via a
     retrieval-based assistant — not a bolted-on generic chatbot.
  2. **Cold-start to live, honestly** — every prediction is tagged by its own confidence: a
     bootstrap estimate on day one, a real-data-trained forecast once enough live history exists.
     The UI shows this, it doesn't fake certainty.
  3. **Network-aware without simulating the network** — a delay's downstream effect is captured
     through statistical features and a bounded, time-windowed propagation, not a full
     network simulation — the same practical approach production ETA systems (ride-hailing, maps)
     actually use.

## Slide 3 — Technical Approach

- **Architecture diagram** (screenshot of the mermaid diagram, monitor-panel treatment) — this slide
  is 70% diagram, 30% text.
- **Flow, one line per stage**: Live sources (NTES + weather) → Postgres/Redis → feature engine →
  LightGBM (predicted delay) → `eta_engine` (graph walk, cumulative propagation) → API → dashboard,
  with the RAG assistant pulling from the same store.
- **Tech stack** (compact table or icon row): Python/FastAPI · LightGBM + SHAP · PostgreSQL + Redis
  · React + Leaflet · GitHub Actions (cron) · Vercel/Render (free-tier deploy)
- **Methodology callout**: two-stage model — a cold-start baseline (Kaggle-validated feature schema,
  0.92 accuracy on this exact shape) that hands off per-segment to a live model as real data
  accumulates from the poller.

## Slide 4 — Feasibility and Viability

Two columns: **Challenges** ↔ **Strategy** (paired, not two separate lists — a judge should be able
to read across a row and see the answer right next to the problem).

| Challenge | Strategy |
|---|---|
| NTES may rate-limit or go down during the demo | ETrain.info scrape as a documented backup live source |
| Real historical data is thin on day one | Cold-start baseline model trained on a validated public feature schema; every station answerable from day one |
| Network-wide cascading effects are a hard OR problem on their own | Deliberately scoped to statistical proxy features + bounded, time-windowed propagation — not a full simulation |
| Heavy DL models are expensive and fragile on small real-world data | Core predictor is LightGBM — trains in seconds, no GPU, proven at 0.92 accuracy on this feature shape |
| Zero budget | Entire stack runs on free tiers — Vercel, Render, Supabase, GitHub Actions, Groq/Gemini free tier — ₹0 to build and demo |

## Slide 5 — Impact and Benefits

- **Passengers**: accurate, continuously-updating ETA instead of a static number; transparency on
  *why* a delay happened instead of just seeing "late."
- **Railways operations**: better platform allocation, crew scheduling, and cleaning-turnaround
  planning from a forecast that reflects ground reality, not a fixed schedule.
- **Downstream logistics**: feeder transport, connecting trains, and delivery services can plan
  against a number that's actually reliable.
- **Reach**: built entirely on public APIs and open data — deployable as an overlay without
  depending on internal Railways infrastructure changes, and exposed as a public API itself so
  third-party apps and physical station displays can consume the same forecast.
- **Scales toward**: a real network-optimization system (see Future Features in the implementation
  plan) — this is a foundation, not a dead end.

## Slide 6 — Research and References

- **Live data**: NTES (`enquiry.indianrail.gov.in`) via [ntes-client](https://github.com/x64vbhv/ntes-client);
  ETrain.info (backup)
- **Static network data**: [datameet/railways](https://github.com/datameet/railways);
  [data.gov.in](https://www.data.gov.in) Train Time Table + Punctuality Index
- **Training data**: [Kaggle — Indian Railways Predict Train Delay](https://www.kaggle.com/competitions/indian-railways-predict-train-delay)
  (1.5M records, 44-feature schema, 0.92 top accuracy); [naijilaji real delay dataset](https://www.kaggle.com/datasets/naijilaji/indian-railways-passenger-train-delays-dataset)
- **Prior art studied**: [RailFlow](https://github.com/zer-art/Railflow) (RL+OR+XAI vision reference);
  [Railway-GraphRAG](https://github.com/LahaArnab/Railway-Lora-Customer-Support-GraphRAG) (graph-based
  delay reasoning); [HetETA](https://github.com/didi/heteta) / [LibCity](https://github.com/LibCity/Bigscity-LibCity)
  (spatio-temporal ETA techniques, cited as future direction)
- **Academic**: Prediction of Train Delay in Indian Railways through Machine Learning Techniques
  ([ResearchGate](https://www.researchgate.net/publication/332113402_Prediction_of_Train_Delay_in_Indian_Railways_through_Machine_Learning_Techniques))

Full source list with notes: [eta-data-sources-and-prior-art.md](./eta-data-sources-and-prior-art.md).
