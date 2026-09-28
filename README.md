# 🚆 SIH-DETA (`Main`) — Indian Railways Dynamic ETA & Hybrid ML+DSA Operational Intelligence System

> **Smart India Hackathon (SIH 2026) — Problem Statement 26028**  
> **Ministry of Railways | Dynamic Forecast of Expected Time of Arrival (ETA) for Coaching Trains**

---

## 🏛️ Unified Repository Layout

```text
Main/
├── frontend/                              # React 18 + Vite + TypeScript + Tailwind + Framer Motion + Leaflet
│   ├── src/
│   │   ├── pages/
│   │   │   ├── HomePage.tsx               # Universal Search + SIH-DETA 7-Module Data Foundation
│   │   │   ├── LivePage.tsx               # Hybrid ML (P10/P50/P90) + DSA Live ETA & Dual-Mode Halt Traversal
│   │   │   ├── ControlRoomPage.tsx        # Section Controller DRM Cockpit (CRO/ACP/Block/Yen's Rerouting)
│   │   │   ├── StationPage.tsx            # Station Master PIDS, Platform IntervalTree & Maha Kumbh Surge
│   │   │   ├── MapPage.tsx                # 8,990-Station National Rail Atlas + Approach Cabins
│   │   │   ├── PnrPage.tsx                # 10-Digit PNR Lookup (Zero PII) + Live ETA Link
│   │   │   └── AboutPage.tsx              # 3-Layer Hybrid Observatory, 6-DB Audit & Token-Bucket Pacing
│   │   ├── components/
│   │   └── lib/
│   └── package.json
│
├── backend/                               # Complete FastAPI + Hybrid ML/DSA + 7 SIH-DETA Modules
│   ├── app/
│   │   ├── main.py                        # FastAPI Gateway (:8001) serving /v1/* and /v1/deta/*
│   │   ├── domain/                        # M0 Schedule-Graph Propagation & M1 Risk Classifier
│   │   ├── providers/getinfo/             # Zero-Quota Cascading Engine (ConfirmTkt -> NTES -> eRail -> RailYatri)
│   │   └── sih_deta/                      # Core Hybrid ML + Discrete DSA Engine
│   │       ├── data_bridge.py             # Cross-DB Alias Resolver (72,508 records recovered) & Unified Halts
│   │       ├── quantile_engine.py         # Layer 1 & 3: Quantile LightGBM (P10/P50/P90) + G&SR Weather Caps
│   │       ├── dsa_scheduler.py           # Layer 2: Platform IntervalTree, FIFO Headway, Space-Time DAG & Yen's Rerouting
│   │       ├── surge_profiler.py          # Station NSG (1-6) & Event Surge Engine (Maha Kumbh, Chhath, Diwali)
│   │       └── controller_ops.py          # Section Controller Incidents, 3-Level Black Swan & Dual-Mode Traversal
│   ├── sih_deta/                          # 7 Production Data & Physics Modules (from Server-ETA)
│   │   ├── Train-Scraper/                 # Module 01: 5,209 Master Trains (trains.db)
│   │   ├── Station-Halt Scraper/          # Module 02: 8,990 Stations & 420,345 Halts (stations.db)
│   │   ├── Live-Journey-Tracker/          # Module 03: Live Telemetry & 704 Approach Cabins (telemetry.db)
│   │   ├── Historical-Delay-Records/      # Module 04: 1.51M Daily Delays & 73,342 Profiles (historical.db)
│   │   ├── Weather-Environment/           # Module 05: 3.19M Weather Rows & G&SR Rules (weather.db)
│   │   ├── Network-Anomalies/             # Module 06: 39,754 Incidents & M/M/c Outer Queue (anomalies.db)
│   │   └── ETA-Prediction-Engine/         # Module 07: Unified Feature Pipeline & Inference Engine
│   ├── predictor/                         # 31-Feature Station Quantile Regressor (station_eta_model.joblib)
│   ├── ml/                                # Risk Classifier Registry (eta_model_subset.joblib)
│   └── tests/                             # Automated Backend & Hybrid Engine Test Suite
│
├── unpushed_assets/                       # Large Databases (>50MB) Excluded from Git + Manifest
│   └── UNPUSHED_FILES_MANIFEST.md         # Detailed documentation of all unpushed SQLite/CSV/JSON files
├── docs/                                  # Complete Architecture Blueprints (Server.md, visual_presentation.md, DOC/)
├── UNPUSHED_FILES_MANIFEST.md             # Root pointer to unpushed large files manifest
├── start-backend.bat                      # One-click FastAPI backend launcher (:8001)
└── start-frontend.bat                     # One-click Vite React frontend launcher (:5173)
```

---

## 📦 Unpushed Large Assets (>50 MB)

See [`unpushed_assets/UNPUSHED_FILES_MANIFEST.md`](unpushed_assets/UNPUSHED_FILES_MANIFEST.md) for the complete inventory, database schemas, and restoration instructions for the **1.5+ GB** of local SQLite databases (`historical.db`, `weather.db`, `darpan.sqlite`, `stations.db`, `anomalies.db`) stored inside `unpushed_assets/`.

---

## 🚀 Quick Start

### 1. Start the Backend API (`:8001`)
```powershell
.\start-backend.bat
# Or manually:
cd backend
python -m uvicorn app.main:app --port 8001 --reload
```

### 2. Start the Frontend Web App (`:5173`)
```powershell
.\start-frontend.bat
# Or manually:
cd frontend
npm run dev
```
Open `http://localhost:5173` in your browser.
