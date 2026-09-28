# Phase 3A: Weather & Environmental Constraints Module ⛅
## Master Implementation Plan & Architectural Blueprint
**System:** SIH-DETA (Indian Railways Dynamic ETA Prediction System)  
**Module:** `05. Weather-Environment`  
**Target Path:** `/scratch/home/sid01/SIH-DETA/Weather-Environment/`

---

## 1. Executive Summary & Objective

In Indian Railways operations, weather is the single largest cause of non-systemic, unpredicted seasonal delays:
- **Winter Fog (Dec–Feb):** Severe visibility drops across Northern & Eastern Plains (NR, NCR, NER, ECR) legally mandate dropping Maximum Permissible Speed (MPS) from 130 km/h to 60 km/h (or 75 km/h with GPS FOG-PASS), creating cascading 4 to 12-hour delays.
- **Monsoon & Flash Flooding (Jun–Oct):** Enforces statutory speed reductions on coastal corridors (e.g. Konkan Railway 741 km line capped to 75–90 km/h) and strict 10 km/h cautionary limits when water rises above rail flanges.
- **Summer Thermal Stress (Apr–Jun):** Continuous Welded Rail (CWR) expands under extreme solar heat, risking explosive track buckling if rail temperatures exceed neutral limits ($T_d + 20^\circ\text{C}$).

**Objective:**  
Build a high-performance, resilient, and deterministic weather ingestion and G&SR rules engine that transforms raw atmospheric observations into physical speed constraint features for downstream ETA models (`ETA-Prediction-Engine`).

---

## 2. Indian Railways G&SR Domain Specifications

The implementation will strictly encode statutory operational rules from the **General and Subsidiary Rules (G&SR)** of Indian Railways:

### A. Dense Fog & Visibility Rules (G&SR 3.61 & Railway Board Directives)
| Parameter | Threshold | Operational Rule & Impact |
|---|---|---|
| **Nominal Track MPS** | Visibility $\ge 600\text{ m}$ | Normal line speed permitted (110–130 km/h). |
| **Standard Fog Cap** | Visibility $< 600\text{ m}$ | Loco Pilot must not exceed **60 km/h**; detonator audible warning placed 270m before Home Signal. |
| **GPS FOG-PASS Cap** | Visibility $< 600\text{ m}$ + GPS Unit | Speed relaxed up to **75 km/h** if locomotive has operational FOG-PASS equipment. |
| **Severely Impaired** | Visibility $< 100\text{ m}$ | Caution order; stop-and-proceed at signals capped at **30 km/h**. |

### B. Monsoon & Waterlogging Rules (G&SR 2.11)
| Parameter | Condition | Operational Rule & Impact |
|---|---|---|
| **Konkan Monsoon Timetable** | Date between **June 10 and October 31** | Entire Roha–Thokur section speed slashed from 110 km/h to **75–90 km/h**; crossing slack inflated. |
| **Water Above Rail Flange** | Precipitation rate $> 50\text{ mm/hr}$ or local inundation | Speed capped at **10 km/h** with pilot walking ahead, or full traffic halt if ballast washed out. |

### C. Summer Rail Temperature & Buckling Rules (Track Manual Para 5.2)
| Parameter | Formula / Condition | Operational Rule & Impact |
|---|---|---|
| **Rail Temperature Estimation** | $T_{\text{rail}} \approx T_{\text{air}} + (0.022 \times \text{Direct Solar Radiation W/m}^2)$ | Rail steel heats significantly faster than ambient air. |
| **Buckling Caution Order** | $T_{\text{rail}} \ge 60^\circ\text{C}$ (i.e. $T_d + 20^\circ\text{C}$) | Deploy Hot Weather Patrolling; impose speed restriction of **30–50 km/h** during 12:00 PM – 5:00 PM. |

---

## 3. Modular Architecture & Directory Layout

To maintain maximum code cleanliness, loose coupling, and testability, the module is structured into 4 isolated layers:

```text
Weather-Environment/
├── README.md                      # Architecture documentation & domain rules
├── IMPLEMENTATION_PLAN.md         # (This document) Step-by-step engineering plan
├── config.py                      # Master endpoints, spatial grid tolerances, G&SR constants
├── requirements.txt               # Lightweight dependencies (requests, urllib3)
│
├── collectors/                    # Data Acquisition & Spatial Clustering Layer
│   ├── __init__.py
│   ├── station_geo_resolver.py    # Extracts coords from stations.db; clusters into 25km spatial grids
│   ├── open_meteo_client.py       # High-res REST client (visibility, rain, solar radiation, temp)
│   └── mock_weather_data.py       # Offline deterministic fallback (zero-failure guarantee)
│
├── rules/                         # Physical & Operational Rules Engine
│   ├── __init__.py
│   └── gsr_rules_engine.py        # Evaluates raw weather into statutory speed limits & risk flags
│
├── storage/                       # Persistence & Feature Store Layer
│   ├── __init__.py
│   ├── weather_db.py              # SQLite storage engine (WAL mode)
│   └── weather_exporter.py        # Exports weather_features.csv for ML pipeline
│
├── main.py                        # Unified CLI runner (live queries, train route scans, exports)
│
└── tests/                         # Unit & Integration Verification Suite
    ├── __init__.py
    └── test_weather_rules.py      # Automated tests for fog caps, monsoon flags, and heat buckling
```

---

## 4. Spatial Clustering Optimization (Crucial for API Efficiency)

There are **8,990 railway stations** in `stations.db`. Querying weather for every station individually would require ~9,000 API calls per refresh, triggering rate limits.

**Spatial Centroid Clustering Strategy:**
1. Round station coordinates to **$0.25^\circ \times 0.25^\circ$ grid cells** ($\approx 25\text{ km} \times 28\text{ km}$ area, matching mesoscale weather patterns).
2. Group all 8,990 stations into approximately **220–280 unique cluster centroids**.
3. Query the weather API **only once per cluster centroid**.
4. Map the resulting meteorological parameters back to all member stations in that cluster via an in-memory hash index.

*Result:* **97% reduction in API calls** (from 8,990 calls down to ~250 calls per nationwide snapshot).

---

## 5. Data Contracts & Database Schema

### A. SQLite Table: `station_weather_observations`
Stored in `Weather-Environment/data/weather.db`:
```sql
CREATE TABLE IF NOT EXISTS station_weather_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_code TEXT NOT NULL,
    observation_time TIMESTAMP NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    visibility_meters REAL NOT NULL,
    is_foggy BOOLEAN NOT NULL,              -- 1 if visibility < 600m
    fog_speed_cap INTEGER NOT NULL,          -- 60 or 75 km/h
    precipitation_mm REAL NOT NULL,
    monsoon_active BOOLEAN NOT NULL,         -- 1 if Konkan monsoon / heavy rain
    monsoon_speed_cap INTEGER,               -- 75 or 10 km/h (null if clear)
    ambient_temp_c REAL NOT NULL,
    estimated_rail_temp_c REAL NOT NULL,
    heat_buckling_warning BOOLEAN NOT NULL,  -- 1 if rail_temp >= 60°C
    effective_mps_cap INTEGER NOT NULL,      -- MIN(nominal_mps, fog_cap, monsoon_cap)
    data_source TEXT NOT NULL,               -- 'OPEN_METEO_LIVE' or 'MOCK_OFFLINE'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(station_code, observation_time)
);

CREATE INDEX IF NOT EXISTS idx_weather_station_time 
ON station_weather_observations(station_code, observation_time);
```

### B. Output Feature Store: `weather_features.csv`
Used directly by `ETA-Prediction-Engine`:
```csv
station_code,timestamp_hour,visibility_meters,is_foggy,fog_speed_cap,rainfall_mm,rail_temp_c,monsoon_active,effective_mps_cap
NDLS,2026-09-24T06:00:00,350.0,1,60,0.0,18.5,0,60
CNB,2026-09-24T06:00:00,420.0,1,75,0.0,19.2,0,75
MAO,2026-09-24T14:00:00,8000.0,0,130,12.5,28.4,1,75
```

---

## 6. Phased Execution Steps

### 🟢 Step 1: Configuration & Requirements Setup
- Create `requirements.txt` (`requests>=2.28.0`).
- Create `config.py` declaring API endpoints, timeout thresholds (10.0s), cluster grid size (`0.25`), and G&SR constants (600m visibility, 60/75 km/h caps, 60°C rail threshold).

### 🟢 Step 2: Station Coordinate Resolver & Spatial Clustering
- Implement `collectors/station_geo_resolver.py`.
- Query coordinates directly from `Station-Halt Scraper/data/stations.db`.
- Formulate the spatial cluster mapping dictionary (`cluster_id -> [station_codes]`).

### 🟢 Step 3: Open-Meteo REST Client & Offline Mock Generator
- Implement `collectors/open_meteo_client.py`:
  - Query Open-Meteo API for `visibility`, `precipitation`, `temperature_2m`, `direct_normal_irradiance`.
  - Implement retry with exponential backoff and connection caching.
- Implement `collectors/mock_weather_data.py`:
  - Generate deterministic, realistic weather scenarios (e.g. Fog in Delhi/Kanpur, Monsoon in Goa, Heat in Nagpur) for offline testing without internet dependency.

### 🟢 Step 4: Indian Railways G&SR Rules Engine
- Implement `rules/gsr_rules_engine.py`:
  - Function `evaluate_fog_constraint(visibility_m, has_fog_pass=True) -> (is_foggy, speed_cap)`
  - Function `evaluate_monsoon_constraint(station_code, date, precipitation_mm) -> (monsoon_active, speed_cap)`
  - Function `evaluate_thermal_buckling(ambient_temp, solar_irradiance) -> (rail_temp, buckling_warning)`
  - Function `compute_effective_mps(nominal_mps, fog_cap, monsoon_cap, heat_warning) -> effective_mps`

### 🟢 Step 5: SQLite Storage & Feature Store Exporter
- Implement `storage/weather_db.py`:
  - Database initialization, table migration, and bulk upsert operations.
- Implement `storage/weather_exporter.py`:
  - Exports station observations to clean `weather_features.csv` and JSON format.

### 🟢 Step 6: Unified CLI Runner
- Implement `main.py` with commands:
  - `python3 main.py --mode live --station NDLS` (fetches real-time weather & speed limit for a station)
  - `python3 main.py --mode route --train 12301` (fetches corridor weather along all stops of a train)
  - `python3 main.py --mode sync-clusters` (generates spatial clusters for all nationwide stations)
  - `python3 main.py --mode export` (dumps `weather_features.csv`)

### 🟢 Step 7: Test Suite & Verification
- Implement `tests/test_weather_rules.py`.
- Verify 100% of G&SR rules against corner cases:
  - Visibility = 599m vs 600m
  - Konkan station inside vs outside monsoon dates
  - Extreme ambient temperatures (48°C) triggering rail buckling caution orders.

---

## 7. Verification & Acceptance Criteria

| Check | Expected Result |
|---|---|
| **Spatial Clustering** | 8,990 stations cluster into $< 300$ grid points; 100% of geocoded stations assigned. |
| **Fog Logic** | If visibility $= 450\text{m}$, speed cap must be 60 km/h (standard) or 75 km/h (FOG-PASS). |
| **Monsoon Logic** | Station `MAO` on July 15 must output `monsoon_active = True` and `monsoon_speed_cap = 75 km/h`. |
| **Heat Logic** | Ambient 45°C with $800\text{ W/m}^2$ irradiance must calculate $T_{\text{rail}} \approx 62.6^\circ\text{C}$ and trigger `heat_buckling_warning = True`. |
| **Zero-Crash Resilience** | In offline mode or on HTTP timeout, system seamlessly falls back to mock generator without crashing. |
| **Git Safety** | `weather.db` is strictly caught by `.gitignore` and excluded from git tracking. |
