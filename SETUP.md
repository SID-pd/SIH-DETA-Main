# SIH 26028 — DARPAN / SIH-DETA Complete Setup & Deployment Guide (`SETUP.md`)

**Repository**: [`https://github.com/SID-pd/SIH-DETA-Main`](https://github.com/SID-pd/SIH-DETA-Main)  
**System**: Indian Railways Dynamic Arrival & Railway Predictive Analytics Network (**DARPAN** / **SIH-DETA** / **RailPulse**)  
**Architecture**: 3-Layer Hybrid Quantile Machine Learning ($P_{10}/P_{50}/P_{90}$) + Discrete Data Structures & Algorithms (IntervalTree Platform Allocator, Unidirectional Space-Time DAG, Yen's K-Shortest Path Electrified Bypass Rerouting, and Section Controller Dispatch Cockpit).

---

## 1. Prerequisites

Ensure the following tools are installed on your machine or remote instance:
- **Python**: `3.11+` (or Anaconda / Miniconda environment)
- **Node.js**: `18.x+` and `npm` (`9.x+`)
- **Git**: `2.40+`
- **Ngrok** *(Optional, for remote public tunnel sharing)*: `ngrok v3.20+`

---

## 2. Repository Directory Layout

```text
Main/
├── backend/                        # Unified FastAPI + Hybrid ML/DSA Backend (:8001)
│   ├── app/
│   │   ├── main.py                 # FastAPI Gateway + /v1/* and /v1/deta/* endpoints
│   │   ├── settings.py             # CORS origins, ports, cache TTLs, DB paths
│   │   ├── domain/                 # M0 deterministic propagation & M1 risk overlay
│   │   ├── infra/                  # SQLite repo, provider circuit breaker, snapshot writer
│   │   └── sih_deta/               # 3-Layer Hybrid ML + Discrete DSA Engine
│   │       ├── data_bridge.py      # 6-DB bridge & 72,508-record Station Alias Engine
│   │       ├── quantile_engine.py  # P10/P50/P90 Quantile ML + G&SR Weather + 2-Pass DAG
│   │       ├── dsa_scheduler.py    # Platform IntervalTree & Yen's K-Shortest Rerouter
│   │       ├── surge_profiler.py   # NSG 1-6 Categorization & Festival Crowd Surge
│   │       └── controller_ops.py   # Section Controller Incident Overrides & Pacing
│   ├── predictor/                  # 31-Feature LightGBM/XGBoost Station ETA Pipeline
│   ├── sih_deta/                   # 6 Standalone Data/ML Modules + Module 07 CLI
│   └── tests/                      # 28 Automated Pytest Unit & Integration Tests
├── frontend/                       # React 18 + Vite + TypeScript + Tailwind Web App (:5173)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── HomePage.tsx        # National Command Overview & Quick Search
│   │   │   ├── LivePage.tsx        # Live Telemetry + Hybrid P10/P50/P90 & Dual-Mode DAG
│   │   │   ├── StationPage.tsx     # Station PIDS + Platform IntervalTree & Surge Inspector
│   │   │   ├── RadarPage.tsx       # Section Controller DRM Dispatch Cockpit + Spatial Radar
│   │   │   ├── MapPage.tsx         # Pan-India GIS Route & Station Map
│   │   │   ├── PnrPage.tsx         # Privacy-Hardened PNR Status Lookup
│   │   │   └── AboutPage.tsx       # 6-Database Data Lake & 5 Audit Remediations Observatory
│   │   └── lib/api.ts              # Typed API Client for /v1/* and /v1/deta/*
│   └── vite.config.ts              # Vite Dev Server (:5173), Proxy (/v1 -> :8001), & AllowedHosts
├── unpushed_assets/                # Local holding folder for >50MB SQLite DBs & CSVs (Git-ignored)
│   └── UNPUSHED_FILES_MANIFEST.md  # Complete manifest & restoration commands for 14 large files
├── docs/                           # Master Architectural & Mathematical Specifications
├── start-backend.bat               # 1-Click Windows Launcher for Backend (:8001)
├── start-frontend.bat              # 1-Click Windows Launcher for Frontend (:5173)
└── SETUP.md                        # This Setup Guide
```

---

## 3. Cloning & Restoring Large Database Assets (`>50 MB`)

```bash
git clone https://github.com/SID-pd/SIH-DETA-Main.git
cd SIH-DETA-Main
```

### Restoring Unpushed Large SQLite Databases
Because GitHub enforces a strict `100 MB` file limit, the 14 heavy data files (`historical.db` `691 MB`, `weather.db` `580 MB`, `darpan.sqlite` `96.4 MB`, `stations.db` `82.5 MB`, `anomalies.db` `11.6 MB`, etc.) are documented in [`unpushed_assets/UNPUSHED_FILES_MANIFEST.md`](unpushed_assets/UNPUSHED_FILES_MANIFEST.md).

- **Note**: Even without copying the `1.63 GB` databases onto a fresh machine, the backend (`app/sih_deta/`) includes built-in canonical corridor profiles and deterministic fallbacks so all API endpoints and UI views run out-of-the-box.
- If you have the `unpushed_assets/` files locally, restore them into their runtime locations with PowerShell:

```powershell
New-Item -ItemType HardLink -Path "backend\data\darpan.sqlite" -Target "unpushed_assets\darpan.sqlite" -Force
New-Item -ItemType HardLink -Path "backend\sih_deta\Historical-Delay-Records\data\historical.db" -Target "unpushed_assets\historical.db" -Force
New-Item -ItemType HardLink -Path "backend\sih_deta\Weather-Environment\data\weather.db" -Target "unpushed_assets\weather.db" -Force
New-Item -ItemType HardLink -Path "backend\sih_deta\Station-Halt Scraper\data\stations.db" -Target "unpushed_assets\stations.db" -Force
New-Item -ItemType HardLink -Path "backend\sih_deta\Network-Anomalies\data\anomalies.db" -Target "unpushed_assets\anomalies.db" -Force
```

---

## 4. Backend Setup & Execution (`Port 8001`)

### Install Python Dependencies
```bash
cd backend
pip install fastapi uvicorn httpx pydantic scikit-learn joblib lightgbm xgboost numpy pandas pytest
```

### Run the FastAPI Backend Server
```bash
# From Main/backend:
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```
Or on Windows, double-click **`start-backend.bat`** from the root `Main/` directory.

### Verify Backend Health & SIH-DETA Engine
- **Health Check**: `http://127.0.0.1:8001/v1/health`
- **6-DB Data Lake & Audit Overview**: `http://127.0.0.1:8001/v1/deta/overview`
- **Hybrid Quantile + DSA ETA**: `http://127.0.0.1:8001/v1/deta/eta?train_number=12301&event_id=MAHA_KUMBH`

### Run Backend Unit & Integration Tests
```bash
cd backend
python -m pytest tests/ -v
```

---

## 5. Frontend Setup & Execution (`Port 5173`)

### Install Node Dependencies
```bash
cd frontend
npm install
```

### Start the Vite Development Server
```bash
# From Main/frontend:
npm run dev -- --host 0.0.0.0 --port 5173
```
Or on Windows, double-click **`start-frontend.bat`** from the root `Main/` directory.

- **Local Web URL**: `http://localhost:5173`
- **Production Build Check**:
  ```bash
  npm run build
  ```

---

## 6. Sharing the Frontend via Ngrok & Configuring CORS

Because Vite (`:5173`) proxies all `/v1/*` requests directly to the FastAPI backend (`http://127.0.0.1:8001`), you only need **one** ngrok tunnel pointing to port `5173`!

### Step 1: Start Ngrok Tunnel on Port `5173`
```bash
ngrok http 5173
```
Copy the generated `https://*.ngrok-free.dev` or `https://*.ngrok-free.app` forwarding URL (for example: `https://doorpost-smashing-regime.ngrok-free.dev`).

### Step 2: CORS Policy & Vite `allowedHosts` Configuration
1. **Backend CORS Policy (`backend/app/settings.py` & `backend/app/main.py`)**:
   - `backend/app/settings.py` includes `CORS_ORIGINS` (defaulting to `http://localhost:5173,http://127.0.0.1:5173,https://doorpost-smashing-regime.ngrok-free.dev` plus any custom ngrok URL).
   - `backend/app/main.py` also configures `allow_origin_regex=r"https://.*\.ngrok(-free)?\.(app|dev|io)"` on `CORSMiddleware` so any active ngrok tunnel domain is automatically permitted by the backend CORS policy.
   - To add a custom domain via environment variable:
     ```powershell
     $env:CORS_ORIGINS="http://localhost:5173,https://your-custom-subdomain.ngrok-free.app"
     ```
2. **Frontend Host Whitelist (`frontend/vite.config.ts`)**:
   - `server.allowedHosts` in `frontend/vite.config.ts` is configured to allow `.ngrok-free.dev`, `.ngrok-free.app`, `.ngrok.io`, and your active ngrok URL so Vite serves assets over the public tunnel without host-header rejection.
