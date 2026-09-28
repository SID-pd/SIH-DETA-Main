# Project architecture — Dynamic ETA Pipeline (SIH26028)

System design, tech stack, repo layout, team ownership, and timeline for the build. See
[eta-pipeline-diagram.md](./eta-pipeline-diagram.md) for the visual (mermaid) version of the flow
below, and [ui-structure.md](./ui-structure.md) for how this surfaces on screen. Data sources this
architecture depends on are documented in
[eta-data-sources-and-prior-art.md](./eta-data-sources-and-prior-art.md) and
[openrailwaymap-and-osm-data.md](./openrailwaymap-and-osm-data.md).

## System architecture (5 layers)

```
┌─────────────────────────────────────────────────────────────┐
│  1. DATA INGESTION                                           │
│  NTES poller (ntes-client) ──┐                               │
│  ETrain.info scraper (backup)├──> raw live events            │
│  Weather API (IMD/OpenWx)  ──┘    (position, delay, ETA)     │
│  datameet/railways (one-time) ──> static graph (stations,    │
│                                    routes, schedules)         │
└──────────────────────┬────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  2. STORAGE                                                   │
│  Postgres: stations | routes | schedules | live_events |     │
│            weather_snapshots                                  │
│  Redis: latest live position cache (fast reads)                │
└──────────────────────┬────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  3. ML LAYER                                                  │
│  Feature engine (Time/Geography/Route/Weather/Rolling-Stock/  │
│  Operations groups — mirrors the Kaggle 44-feature schema)    │
│  LightGBM/XGBoost regressor → predicted incremental delay     │
└──────────────────────┬────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  4. SERVING API (FastAPI)                                     │
│  eta_engine: walks remaining stops on the route graph,        │
│    propagates cumulative delay + model prediction segment-    │
│    by-segment → dynamic ETA per upcoming station               │
│  rag_assistant: "why is this train late" — retrieval over      │
│    historical delay-cause data + live features, LLM answer,   │
│    multilingual                                                │
└──────────────────────┬────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  5. FRONTEND (React)                                           │
│  Live map (Leaflet, route geometry from datameet) + ETA        │
│  countdowns + zone congestion heatmap + chat panel for the RAG │
│  assistant. Responsive — doubles as the "mobile app."          │
└─────────────────────────────────────────────────────────────┘
```

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Data pipeline | Python, `ntes-client`, `BeautifulSoup` (ETrain backup) | Direct reuse of researched sources — no need to reverse-engineer NTES from scratch |
| Scheduling | **GitHub Actions cron** (free) | Runs the poller every 10–15 min without an always-on server — zero cost, zero infra |
| Database | Postgres via **Supabase or Neon free tier** | Free, includes storage + auth if needed later |
| Cache | **Upstash Redis free tier** | Fast reads for "current position" on the live map |
| ML | pandas, scikit-learn, **LightGBM** | Proven on this exact feature schema (0.92 leaderboard score on the Kaggle synthetic set) |
| RAG/LLM | FAISS/Chroma (local, free) + **Groq or Gemini Flash free-tier API** | Zero budget — no OpenAI bill; swap in a quantized Llama/Mistral via Ollama if a fully offline demo is needed |
| Backend API | **FastAPI** | Same language as the ML stack — less context-switching for a 4-person team |
| Frontend | React (Vite) + Leaflet/Mapbox free tier + Tailwind | Fast to build, map rendering is trivial with the route geometries already sourced |
| Deploy | Frontend → **Vercel free**; API → **Render/Fly.io free**; cron → **GitHub Actions** | Entire stack costs ₹0 |

## Repo structure

```
railpulse/
├── data-pipeline/
│   ├── ntes_poller.py         # hits NTES, writes live_events
│   ├── etrain_scraper.py      # backup source
│   ├── load_static_graph.py   # one-time ETL from datameet/railways
│   └── weather_ingest.py
├── ml/
│   ├── features.py            # Time/Geo/Route/Weather/RollingStock/Ops
│   ├── train_model.py
│   └── models/
├── api/
│   ├── main.py
│   ├── eta_engine.py          # graph-walk delay propagation ← DSA-heavy
│   ├── rag_assistant.py       # RAG "why is my train late" endpoint
│   └── db.py
├── web/
│   └── src/                   # React dashboard + map + chat panel
├── .github/workflows/poller.yml
└── docs/
```

## Team ownership

| Person | Owns | Why it fits |
|---|---|---|
| Both DSA-strong folks | `api/eta_engine.py` — delay-propagation logic (walk remaining stops on the route graph, cascade cumulative + predicted delay) | Literally a graph traversal / DP problem — the algorithmic core of the whole PS |
| Infosys intern | `api/` production concerns — DB schema, deployment, CI/CD, request handling robustness | Enterprise dev background maps directly onto making the API demo-stable |
| printdeed intern | `web/` — dashboard, live map, UX | Full-stack/frontend experience |
| RAG deployer | `ml/` model training + `api/rag_assistant.py` | Model training is generic AI/ML work anyone can pick up; the RAG assistant is the standout differentiator — no other team will have a real retrieval pipeline explaining delays in natural language |

## Timeline (Aug 30 → Sep 20 deadline, ~3 weeks)

- **Now → Sep 5**: Start the NTES poller running immediately via GitHub Actions — this is time-bound,
  not effort-bound, so every day of delay costs real training data. In parallel: static graph ETL, DB
  schema, team onboarding on repo structure.
- **Sep 6–12**: Feature engineering + first model (bootstrap on the Kaggle synthetic schema, swap in
  real accumulated data as it grows). Backend `eta_engine` + API skeleton. Frontend skeleton + map.
- **Sep 13–19**: RAG assistant wired in, full integration of live dashboard + model + poller. Polish,
  deck, demo video.
- **Sep 20**: Submit, with a couple days' buffer built in.
