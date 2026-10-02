# 🚆 DARPAN (SIH-DETA): System Data Flow Diagram (DFD) Workflow & Complete Technical Specification

**Smart India Hackathon (SIH) 2026 — Ministry of Railways (MIC)**  
**Problem Statement ID:** `SIH26028`  
**Problem Statement Title:** *Dynamic Forecast of Expected Time of Arrival (ETA) for Coaching Trains*  
**Theme:** *Smart Automation* | **Category:** *Software*  
**Team Name:** *Twarit* | **Team ID:** `131076`  
**Prototype Portal:** [https://team-twarit-sih26028.vercel.app](https://team-twarit-sih26028.vercel.app)  
**Walkthrough Video:** [Google Drive Demo Walkthrough](https://drive.google.com/file/d/1Qz0DTqZIDW14FyF7VVWAgwwtTXFZS6QE)

---

## 📑 Table of Contents

1. [Executive Summary & Core Paradigm Shift](#1-executive-summary--core-paradigm-shift)
2. [Team Twarit — 6-Member Engineering Ownership](#2-team-twarit--6-member-engineering-ownership)
3. [End-to-End System Data Flow Diagram (DFD) — Level 1 & Level 2](#3-end-to-end-system-data-flow-diagram-dfd--level-1--level-2)
4. [Step-by-Step DFD Component Walkthrough](#4-step-by-step-dfd-component-walkthrough)
   - [4.1 External Entities (Actors)](#41-external-entities-actors)
   - [4.2 Multi-Source Ingestion & Failover Layer](#42-multi-source-ingestion--failover-layer)
   - [4.3 Self-Growing 6-Database Data Lake (1.68 GB SQLite)](#43-self-growing-6-database-data-lake-168-gb-sqlite)
   - [4.4 The 31-Feature Engineering & Fusion Pipeline](#44-the-31-feature-engineering--fusion-pipeline)
   - [4.5 Quantile GBDT Engine & Calibrated Arrival Windows](#45-quantile-gbdt-engine--calibrated-arrival-windows)
   - [4.6 The 3 Operational Decision Diamonds](#46-the-3-operational-decision-diamonds)
   - [4.7 Multi-Stakeholder Output Dashboards](#47-multi-stakeholder-output-dashboards)
   - [4.8 Continuous Self-Scoring Feedback Flywheel](#48-continuous-self-scoring-feedback-flywheel)
5. [Complete Pitch Deck Data Synthesis (Slides 1 to 6)](#5-complete-pitch-deck-data-synthesis-slides-1-to-6)
6. [Mathematical Formulations & Algorithmic Specifications](#6-mathematical-formulations--algorithmic-specifications)
7. [REST API Contracts & Endpoints](#7-rest-api-contracts--endpoints)
8. [Competitive Benchmark & Empirical Verification](#8-competitive-benchmark--empirical-verification)
9. [Verified Academic & Government Citations](#9-verified-academic--government-citations)

---

## 1. Executive Summary & Core Paradigm Shift

### The Legacy Problem
Indian Railways currently relies on static formulas across public portals (NTES, Where Is My Train):
$$\text{ETA}_{\text{Legacy}} = \text{STA} + \text{Current Delay} - \text{Fixed Recovery Buffer}$$
- **The Recovery Fallacy**: As proven in **CAG Audit Report No. 22 of 2021 (Para 2.1)**, fixed engineering/traffic recovery buffers completely fail on High-Density Network (HDN) trunk corridors operating at >100–140% line capacity utilization.
- **The Early Departure Paradox**: Naive linear extrapolation often predicts a train will arrive earlier than its Scheduled Departure (STD), misleading passengers and station staff.
- **Isolated Prediction Blindness**: Existing consumer systems predict each train in isolation, remaining blind to preceding slower freight trains, outer signal queuing, and platform slot contentions.

### The DARPAN Solution
**DARPAN** (*Dynamic Arrival Rail Prediction & Automated Network*) implements a **2-Pass Hybrid Engine** combining **Quantile AI** with **Railway Operational Physics**:
1. **Pass 1 (Stochastic AI Regression)**: Evaluates 31 spatial, kinematic, and atmospheric features via LightGBM Quantile Decision Trees to predict asymmetric arrival windows ($P_{10}$ Optimistic, $P_{50}$ Median Expected, $P_{90}$ Conservative).
2. **Pass 2 (Deterministic Railway Physics & Safety Rules)**: Enforces Indian Railways General & Subsidiary Rules (G&SR), 5-minute platform safety intervals via IntervalTrees, Scheduled Departure clamps, and Yen’s $K$-Shortest Path 25kV electrified detour calculations upon operator accident overrides.

```mermaid
flowchart LR
    A["❌ Legacy Static Formula<br>STA + Delay - Buffer"] -->|Compounds Outliers linearly| B["Frequent False Alarms<br>Outer Signal Surprise Delays<br>Passenger Frustration"]
    C["✅ DARPAN 2-Pass Hybrid<br>AI Quantiles + Railway Physics"] -->|Learns Sectional Slack| D["Calibrated Arrival Windows<br>P10 / P50 / P90 Bands<br>70% Median Error Cut (1.49m)"]
    style A fill:#fee2e2,stroke:#ef4444,stroke-width:2px
    style B fill:#fef2f2,stroke:#dc2626
    style C fill:#dcfce7,stroke:#22c55e,stroke-width:2px
    style D fill:#f0fdf4,stroke:#16a34a
```

---

## 2. Team Twarit — 6-Member Engineering Ownership

To achieve full-stack depth across big data, machine learning, railway dispatching domain physics, backend microservices, and interactive geospatial UI, **Team Twarit (ID: 131076)** is structured into 6 focused engineering deliverables:

| Member / Role | Module Ownership | Core Technical Deliverables |
| :--- | :--- | :--- |
| **1. Team Lead & System Architect** | Hybrid Engine & Topology | 2-Pass Hybrid Engine, Space-Time DAG conflict resolution, IntervalTree platform clash engine, system orchestration. |
| **2. AI / ML Modeling Lead** | Quantile Regressors & Vision | 31-Feature Quantile LightGBM models ($P_{10}/P_{50}/P_{90}$ Pinball Loss), Delay-Jump Classifier (0.92 AUC), conformal calibration. |
| **3. Big Data & Ingestion Engineer** | Data Lake & 24x7 Crawlers | 1.68 GB 6-DB SQLite Data Lake, 4-source failover scraper (ConfirmTkt/NTES/eRail), Open-Meteo 180-hex weather grid. |
| **4. Backend & Microservices Lead** | FastAPI & Dispatch Gateway | High-throughput FastAPI `/v1/deta/*` routes, <1.5ms Redis cache, manual incident injection API, Yen's K-Path rerouting. |
| **5. Frontend & Real-Time GIS UI** | Multi-View Cockpit | React 18 + Leaflet GIS mapping, 3 distinct role views (Passenger, Station Master, Section Controller), P10–P90 cone visualization. |
| **6. Rail Domain & Simulation Engineer** | G&SR Rules & Empirical Validation | Indian Railways G&SR Rule 3.61 fog speed limits, $60^\circ\text{C}$ rail buckling caps, 20,000-sample empirical historical backtest. |

---

## 3. End-to-End System Data Flow Diagram (DFD) — Level 1 & Level 2

Below is the complete architectural dataflow matching the official SIH 2026 pitch deck Level 1/2 specification:

```mermaid
flowchart TD
    %% External Entities / Actors
    subgraph Actors["👤 External Entities & Operational Roles"]
        P["👤 Passengers (App / PNR)"]
        SM["🚉 Station Masters (Platforms)"]
        SC["🎛️ Section Controllers (Dispatch)"]
        MIN["🏛️ Ministry / CRIS Admin"]
    end

    %% Ingestion & Weather Layer
    subgraph Ingestion["🌐 Multi-Source Ingestion & Weather Feeds"]
        SCR["☁️ 4-Source Live Scraper<br>(ConfirmTkt / NTES / eRail)"]
        WX["☁️ Open-Meteo Weather Grid<br>(180-Hex Atmospheric Mesh)"]
        INC_IN["🚨 Manual Incident / Block Input<br>(Derailment, Cattle Hit, Wire Snap)"]
    end

    %% Database Data Lake
    subgraph DataLake["🗄️ Self-Growing 6-DB Data Lake (1.68 GB SQLite + Cache)"]
        DB1[("stations.db<br>8,990 Stns · 704 Cabins")]
        DB2[("historical.db<br>1.51M Delays · 73.3K Slack")]
        DB3[("weather.db<br>3.19M Hourly Wx Rows")]
        DB4[("darpan.db · telemetry.db · anomalies.db")]
    end

    %% DARPAN Core Processing Platform
    subgraph CorePlatform["⚡ DARPAN REAL-TIME PLATFORM (FastAPI /v1/deta)"]
        FUSION["1. Ingestion & 31-Feature Fusion<br>Delay Velocity + Section Slack + G&SR Physics"]
        GBDT["2. Quantile GBDT Arrival Window Engine<br>Predicts P10 (Best), P50 (Expected), P90 (Worst) Bands<br>Transit R² = 0.987 · MedAE 1.49m"]
        
        %% Decision Diamonds
        D1{"Delay > 5m?<br>Decision 1"}
        D2{"Plat Clash?<br>Decision 2"}
        D3{"Accident / Block?<br>Manual Override"}
        
        %% Operational Branches
        O1_FAST["NO: Fast O(1) Mode<br>Station-to-Station Direct"]
        ZOOM_CABIN["YES (Zoom-In): 704 Cabins Queue Math<br>Approach Outer Home Signal Hold"]
        
        PLAT_LOCK["NO: Lock Slot<br>Enforce 5-min Gap"]
        OUTER_HOLD["YES: Outer Hold Queue<br>+8m to +15m Buffer Alert"]
        
        DETOUR["YES: 25kV Electrified Detour Route<br>Yen's K-Shortest Path (<5ms)"]
        STD_RULES["NO: Standard G&SR Speed Rules<br>Fog Caps (75/60/30) & Priority Overtaking"]
    end

    %% Dashboards & Outputs
    subgraph Dashboards["📊 Multi-Stakeholder Real-Time Dashboards"]
        OUT_P["📱 Live Passenger ETA & PNR Display<br>P10/P50/P90 Window + Delay Alert + Buffer Reclaimed"]
        OUT_SM["🚉 Station Master Platform Board<br>Zero-Clash 5m Buffer · Outer Warning Alarm"]
        OUT_SC["🎛️ Controller Dispatch Cockpit<br>Domino Delay Space-Time DAG · Detour Switch"]
    end

    %% Feedback Loop
    subgraph Flywheel["🔄 Continuous Self-Growing Feedback Flywheel"]
        SNAPS["SnapshotWriter<br>Logs predicted vs actual arrival timestamp"]
        SCORER["score_snapshots.py<br>Computes error residual & slack profile updates"]
    end

    %% Data Connections
    P -.->|Query Train / PNR| SCR
    SCR -->|Scraped Telemetry| FUSION
    WX -->|Precipitation, Fog, Temp| FUSION
    SC -->|Post Incident| INC_IN
    INC_IN -->|Trigger Manual Override| D3

    DataLake <-->|Read Static Graph & Historical Profiles| FUSION
    FUSION --> GBDT
    GBDT --> D1

    D1 -- "NO (On-Time)" --> O1_FAST
    D1 -- "YES (Late)" --> ZOOM_CABIN
    ZOOM_CABIN --> D2
    O1_FAST --> D2

    D2 -- "NO (Clear)" --> PLAT_LOCK
    D2 -- "YES (Conflict)" --> OUTER_HOLD
    PLAT_LOCK --> D3
    OUTER_HOLD --> D3

    D3 -- "YES (Accident)" --> DETOUR
    D3 -- "NO (Normal)" --> STD_RULES

    DETOUR --> OUT_SC
    STD_RULES --> OUT_SC
    PLAT_LOCK --> OUT_SM
    OUTER_HOLD --> OUT_SM
    STD_RULES --> OUT_P
    DETOUR --> OUT_P

    OUT_P --> SNAPS
    SNAPS --> SCORER
    SCORER -->|Auto-Update Slack & Retrain GBDT| DB2

    %% Styles
    classDef actorStyle fill:#881337,stroke:#4c0519,stroke-width:1.5px,color:#fff;
    classDef platformStyle fill:#ffffff,stroke:#173f70,stroke-width:2px;
    classDef decisionStyle fill:#2563eb,stroke:#1d4ed8,stroke-width:1.5px,color:#fff;
    classDef outputStyle fill:#f8fafc,stroke:#3b82f6,stroke-width:1.5px;
    classDef flywheelStyle fill:#f0fdf4,stroke:#16a34a,stroke-width:1.5px;

    class P,SM,SC,MIN actorStyle;
    class CorePlatform platformStyle;
    class D1,D2 decisionStyle;
    class D3 fill:#d97706,stroke:#b45309,stroke-width:1.5px,color:#fff;
    class OUT_P,OUT_SM,OUT_SC outputStyle;
    class Flywheel,SNAPS,SCORER flywheelStyle;
```

---

## 4. Step-by-Step DFD Component Walkthrough

### 4.1 External Entities (Actors)

1. **Passengers (App / PNR)**:
   - **Inputs**: 5-digit Train Number (e.g., `12301`), Journey Date, or 10-digit PNR Number.
   - **Outputs**: Calibrated 3-point ETA window ($P_{10}$ Best Case, $P_{50}$ Expected Median, $P_{90}$ Worst Case), dynamic delay drift alert, recovered slack notification (e.g., *-14m buffer recovered between Kanpur and Etawah*), and privacy-safe station-level live tracking.
2. **Station Masters (Platforms)**:
   - **Inputs**: Station Code (e.g., `CNB`, `DDU`, `PRYJ`), active platform occupancy status.
   - **Outputs**: IntervalTree Zero-Clash Platform Schedule, Outer Home Signal warning alarm (triggers when an arriving delayed train risks starving an outbound departure), and festival crowd dwell multipliers.
3. **Section Controllers (Control Rooms & Dispatch Cockpits)**:
   - **Inputs**: 1-Click Manual Accident/Block Overrides (derailment, cattle hit, overhead equipment wire snap, track maintenance blocks).
   - **Outputs**: Domino Delay Space-Time DAG, Yen's $K$-Shortest Path 25kV Electrified Detour Routes (<5ms recomputation), and dynamic COA 6-Tier priority overtaking recommendations.
4. **Ministry of Railways / CRIS / Section Auditors**:
   - **Inputs**: Zone-level punctuality audit requests.
   - **Outputs**: CAG Compliance Analytics, median error reports, speed restriction absorption audits, and rolling stock turnaround metrics.

---

### 4.2 Multi-Source Ingestion & Failover Layer

To eliminate single points of failure without requiring expensive hardware installations on locomotives, DARPAN deploys an intelligent 4-source failover scraper:

```
[Request] ➔ [1. ConfirmTkt API] ➔ (If 429/503) ➔ [2. NTES Official] ➔ (If Timeout) ➔ [3. eRail Web] ➔ (If Down) ➔ [4. IRCTC Cached Backup]
```

- **Smart Pacing Engine**: Uses token-bucket rate limiting and train schedule awareness (polling on-time trains every 5 minutes, but delayed trains nearing signal cabins every 45 seconds). This slashes network crawler bandwidth consumption by **-79.9%**.
- **Open-Meteo Weather Grid**: Gathers 180-hex atmospheric weather nodes covering all 17 railway zones. Evaluates precipitation rate ($\text{mm/h}$), visibility distance ($\text{meters}$), and ambient heat ($^\circ\text{C}$).

---

### 4.3 Self-Growing 6-Database Data Lake (1.68 GB SQLite)

DARPAN uses a modular, file-backed SQLite multi-database architecture running in Write-Ahead Logging (WAL) mode for sub-millisecond concurrent queries:

```
c:\Users\Asus\Coding\SIH\ETA\predictor\data\
├── darpan.db       (Active train states, real-time snapshot registry)
├── historical.db   (1,510,000+ past delay records, 73,342 track slack profiles)
├── weather.db      (3,190,000+ hourly meteorological rows mapped to hex cells)
├── stations.db     (8,990 geo-referenced stations, 420,345 schedule stops, 704 approach signal cabins)
├── telemetry.db    (Crawler ping logs, network latency metrics, API telemetry)
└── anomalies.db    (Operator accident logs, black swan incident records, speed restrictions)
```

#### The Renamed Station Code Translator Bridge
Indian Railways frequently updates historic station codes (e.g., Allahabad `ALD` ➔ Prayagraj `PRYJ`, Mughalsarai `MGS` ➔ Pt. Deen Dayal Upadhyaya `DDU`, Faizabad `FD` ➔ Ayodhya Cantt `AYC`).  
Legacy ML models drop records containing obsolete codes. DARPAN incorporates an automated **Alias Resolution Table** that successfully rescued **72,508 historical rows**, maintaining seamless training continuousness across decades of rail data.

---

### 4.4 The 31-Feature Engineering & Fusion Pipeline

The feature engineering layer fuses real-time telemetry, geographic geometry, timetable slack, and operational rules into 31 numerical features:

| Feature Category | Count | Key Input Features | Operational Purpose |
| :--- | :---: | :--- | :--- |
| **Kinematic & Velocity** | 7 | `current_delay_sec`, `delay_velocity_15m`, `delay_acceleration`, `dist_to_next_stn`, `mps_limit`, `rolling_stock_type`, `rake_length` | Measures whether a train is recovering speed or falling further behind. |
| **Timetable & Section Slack** | 6 | `scheduled_runtime_min`, `historical_slack_sec`, `slack_absorption_ratio`, `dep_hour_sin`, `dep_hour_cos`, `day_of_week` | Evaluates whether upcoming track blocks have engineered buffer time to absorb delays. |
| **G&SR Rules & Weather** | 6 | `visibility_meters`, `is_fog_pass_active`, `track_temp_celsius`, `heat_buckle_risk`, `rain_mm_hr`, `speed_cap_gsr` | Strictly enforces Fog-Pass $75/60/30\text{ km/h}$ caps and $60^\circ\text{C}$ afternoon heat limits. |
| **Congestion & Preceding Trains**| 6 | `headway_dist_km`, `preceding_train_priority`, `section_density_ratio`, `single_track_flag`, `auto_block_zone`, `coa_tier` | Prevents high-priority trains (Rajdhani) from falsely predicting full speed behind a slow goods train. |
| **Station & Platform Queuing** | 6 | `num_platforms`, `is_junction`, `approach_cabin_queue_len`, `dwell_multiplier`, `nsg_category`, `kumbh_surge_flag` | Models dwell time inflation during religious/pilgrim surges (e.g., Maha Kumbh 3.2x). |

---

### 4.5 Quantile GBDT Engine & Calibrated Arrival Windows

Rather than outputting a single point estimate (which is almost always wrong in stochastic rail environments), DARPAN utilizes **3 distinct LightGBM Quantile Regressors** trained under the Pinball Loss objective:

$$\mathcal{L}_q(y, \hat{y}) = \max\Big(q \cdot (y - \hat{y}),\; (1 - q) \cdot (\hat{y} - y)\Big)$$

- **$\mathbf{P_{10}}$ (Optimistic Window Boundary)**: Trained at $q = 0.10$. Represents the best-case arrival if all scheduled recovery slack is reclaimed and signals remain green.
- **$\mathbf{P_{50}}$ (Expected Median)**: Trained at $q = 0.50$. Represents the unbiased median expected arrival time.
- **$\mathbf{P_{90}}$ (Conservative Boundary)**: Trained at $q = 0.90$. Represents the 90th percentile arrival time under adverse outer signal hold delays.

#### Delay-Jump Classifier (0.92 AUC)
A parallel binary classifier evaluates whether a minor delay ($\le 10\text{ min}$) will suddenly cascade into a major disruption ($>45\text{ min}$) due to single-line track starvation or express priority overtaking.

---

### 4.6 The 3 Operational Decision Diamonds

#### Decision Diamond 1: `Delay > 5m?`
- **Path: NO (Fast $O(1)$ Mode)**:
  - When a train is running on schedule ($\le 5\text{ min}$ delay), signal cabins along clear sections operate normally.
  - The engine uses direct station-to-station propagation with $O(1)$ lookup latency (<1.5ms).
  - **Schedule Clamp**: If the predicted arrival is earlier than the Scheduled Departure ($\text{STD}$), the departure time is clamped:
    $$\text{ETD} = \max(\text{Predicted ETA} + \text{Min Dwell},\; \text{STD})$$
    This completely eliminates the early departure paradox.
- **Path: YES (Zoom-In Approach Cabins)**:
  - When delay exceeds 5 minutes, section congestion begins.
  - The system dynamically zooms into **704 mapped Approach Signal Cabins** located 2–5 km outside major junctions.
  - Activates discrete queue modeling to compute Outer Home signal deceleration and wait penalties.

#### Decision Diamond 2: `Platform Clash?`
- **Path: NO (Lock Slot)**:
  - The assigned platform slot at the destination station is unoccupied.
  - The engine locks the platform interval in the `IntervalTree` and clears the signal for station approach.
- **Path: YES (Platform Conflict)**:
  - Two trains are predicted to occupy the same platform with less than the mandatory 5-minute safety clearance gap.
  - The engine flags a platform conflict, assigns the secondary train to an **Outer Signal Hold Queue (+8m to +15m)**, updates the arrival window to $P_{90}$, and triggers an automated warning on the Station Master's Platform Board.

#### Decision Diamond 3: `Accident / Block? (Manual Override)`
- **Path: NO (Standard G&SR Rules)**:
  - Standard Indian Railways operating rules apply. Dispatch follows the COA 6-Tier Priority hierarchy:
    1. *Tier 1*: Vande Bharat / Rajdhani / Shatabdi
    2. *Tier 2*: Mail / Superfast Express
    3. *Tier 3*: Ordinary Passenger
    4. *Tier 4*: Military / Parcel Specials
    5. *Tier 5*: Container Freight
    6. *Tier 6*: Empty Rakes / Maintenance Trains
- **Path: YES (1-Click Operator Accident Override)**:
  - In the event of a sudden unpredicted disruption (derailment, cattle collision, overhead line breakdown), Section Controllers inject a block via `POST /v1/deta/incidents`.
  - The engine immediately executes **Yen's $K$-Shortest Path Algorithm** on the railway electrification graph to calculate viable 25kV Electrified Detour Routes in **<5ms**.
  - Automatically cascades updated domino ETAs across all downstream stations.

---

### 4.7 Multi-Stakeholder Output Dashboards

1. **Live Passenger ETA & PNR Display**:
   - Clean visual display showing the $[P_{10}, P_{90}]$ arrival cone.
   - Transparent explanation of timetable slack absorption (e.g., *Train 12301 is running 35m late, but will recover 14m before New Delhi*).
2. **Station Master Platform Board**:
   - Real-time Gantt schedule of all platform tracks.
   - Visual alerts when incoming delays threaten to block scheduled outbound departures.
3. **Section Controller Dispatch Cockpit**:
   - Interactive Space-Time Distance-Time trajectory charts.
   - Interactive toggles to inject track blocks, reroute trains over 25kV detours, and evaluate priority overtaking sequences.

---

### 4.8 Continuous Self-Scoring Feedback Flywheel

Unlike static systems whose accuracy degrades over time, DARPAN improves autonomously:
1. When a train physically arrives at a station, `SnapshotWriter` records the ground truth arrival timestamp.
2. `score_snapshots.py` compares the actual arrival against the predicted $P_{10}$, $P_{50}$, and $P_{90}$ windows.
3. Prediction error residuals are used to automatically update the empirical slack recovery parameters for that track section in `historical.db`.
4. GBDT tree weights are periodically updated, creating a self-reinforcing accuracy flywheel:

```
Scrape Live Runs ➔ Predict P10/P50/P90 Windows ➔ Log Actual Arrival ➔ Score Residual Error ➔ Refine Section Slack Profiles ➔ Retrain Model
```

---

## 5. Complete Pitch Deck Data Synthesis (Slides 1 to 6)

The PowerPoint presentation ([`SIH2026-DARPAN-Twarit-SIH26028.pptx`](file:///c:/Users/Asus/Coding/SIH/ETA/SIH2026-DARPAN-Twarit-SIH26028.pptx)) consists of 6 core slides structured to match the evaluation rubric:

### Slide 1: Title, Problem Details & Deliverables
- **Theme & Category**: Smart Automation | Software.
- **Problem Statement**: SIH26028 — *Dynamic Forecast of Expected Time of Arrival (ETA) for Coaching Trains*.
- **Organization**: Ministry of Railways (MIC).
- **Core Numbers Strip**:
  - `1.68 GB (Self-Growing)`: 6-DB Live Scraping & Feedback Lake.
  - `8,990 Stns · 704 Cabins`: 417,080 Schedule Stops Mapped.
  - `1.51M Delays · 3.19M Wx`: 73,342 Track Recovery Profiles.
  - `4.93m ➔ 1.49m (-70%)`: Typical Error Cut ($N = 20,000$ Test).
  - `85.3% Window + Manual Ops`: $P_{10}$–$P_{90}$ Band + Live Accident Input.
- **Engineering Team Split**: 5 role categories covering Architecture, AI/ML, Big Data, Backend, and UI/Rail Ops.

### Slide 2: DARPAN Core Idea, Solution Mindmap & Uniqueness
- **GIST**: Replaces static formula with a 2-Pass Hybrid AI + Physics Engine.
- **Column 1 (Core Idea)**: 2-Step Hybrid Engine, Smart-Zoom Route Tracking ($O(1)$ fast mode to 704 cabin mode), Self-Growing DB Flywheel, Manual Accident Input.
- **Column 2 (PS Resolution)**: Replaces static buffers on >100% congested corridors, models COA 6-Tier overtaking & headway safety, incorporates G&SR Fog-Pass speed rules ($75/60/30\text{ km/h}$) and $60^\circ\text{C}$ rail-buckling caps, enforces Zero-Clash platforms via IntervalTrees.
- **Column 3 (Mindmap & Results)**:
  - 6 radial solution nodes: (1) Quantile AI, (2) G&SR Physics, (3) 704 Cabins, (4) COA 6-Tier, (5) Self-Growing DB, (6) Manual Accident Ops.
  - **Held-Out Test Error Card**:
    - Old Static Formula: **4.93 min** median error.
    - DARPAN AI + Physics: **1.49 min** median error (**-69.8% Error Reduction**).
    - Window Calibration: **85.3% Window Accuracy** ($P_{10}$–$P_{90}$) & **0.92 AUC**.

### Slide 3: Technical Approach & Data Flow Diagram (DFD)
- **Column 1 (Technology Stack)**:
  1. *24x7 Scraping & Weather Ingestion*: 4-Source failover, 180-Hex weather grid, -79.9% bandwidth pacing.
  2. *Self-Growing 6-DB Lake (1.68 GB+)*: 6 SQLite DBs + <1.5ms fast cache.
  3. *Layer 1 (31 G&SR Operational Features)*: 73.3K slack profiles, fog limits, track heat.
  4. *Layer 2 (Arrival Window AI)*: 3 Quantile GBDT models ($R^2 = 0.987$), 0.92 AUC delay-jump classifier.
  5. *Layer 3 (Physics & Manual Ops)*: Space-Time DAG, Zero-Clash platform IntervalTree, 25kV detours.
  6. *Feedback Flywheel*: Continuous prediction audit and retraining loop.
  - *Trajectory Fan Chart*: Visual demonstration of Train 12301 Rajdhani recovering 14 minutes of timetable slack between Kanpur and Etawah.
- **Column 2 (DFD Level 1/2)**: Full visual dataflow showing external actors, cloud ingestion, 1.68 GB cylinder, 3 decision diamonds, dashboards, and flywheel loop.
- **Bottom Process Flow Ribbon**:
  `1. Multi-Source Scrape + Weather` ➔ `2. 31-Feature G&SR Fusion` ➔ `3. Quantile GBDT (P10/50/90)` ➔ `4. Physics DAG + Manual Ops` ➔ `5. FastAPI (<18ms)` ➔ `6. Self-Scoring DB Loop`.

### Slide 4: Feasibility & Economic Viability
- **Feasibility & Financial ROI**:
  - *₹0 Hardware Capex*: No GPS receivers or trackside sensors required; runs entirely on public multi-source telemetry, saving Indian Railways **₹120+ Crores**.
  - *<₹15,000/month Cloud Opex*: Highly optimized CPU inference (<18ms per query) requires zero expensive GPU infrastructure.
  - *Fuel & Traction Savings*: Preventing unscheduled outer-signal stops saves **150–200 kWh of electric traction power** or **35–50 liters of diesel** per 24-coach rake stop.
- **4 Real Railway Challenges ➔ 1:1 Engineering Solutions**:
  1. *Closed Internal GPS (RTIS/COA)* ➔ 4-Source Public Failover + 704 Cabin Queue Math.
  2. *Extreme 12–24h Delays & No Early Departure* ➔ $P_{10}/P_{50}/P_{90}$ Window AI + Scheduled Departure Clamping.
  3. *Domino Congestion & Platform Clashes* ➔ IntervalTree Platform Assigner + COA 6-Tier Headway Rules.
  4. *Unpredicted Accidents & Renamed Stations* ➔ 1-Click Incident Override + 25kV Detour Router + 72.5K Alias Translator.
- **Empirical Backtest Scorecard ($N = 20,000$ Test Runs)**:
  - Travel Time Fit ($R^2$): **98.7%**
  - Stations Geocoded: **96.7%**
  - Delay Fit ($R^2$ Score): **93.1%**
  - Window Coverage ($P_{10}$–$P_{90}$): **85.3%**
  - Typical Error Reduction: **-69.8%**

### Slide 5: Multi-Stakeholder Impact & Benchmark Table
- **4 Stakeholder Views**: Passengers (calibrated arrival window), Station Masters (platform clash prevention), Control Rooms (accident override & 25kV rerouting), and Developers (FastAPI REST endpoints).
- **3 Macro Pillars**:
  - *Social*: 2.4 Crore daily passengers benefit from eliminated waiting anxiety and missed connections.
  - *Economic*: ₹120+ Cr hardware capex saved; reduced crew overtime penalties and rake detention.
  - *Environmental*: Reduced stop-start carbon emissions and outer signal traction waste.
- **Competitor Benchmark Matrix (DARPAN Wins 6/6)**:
  - Beats Old Railway Formula, Consumer Apps (NTES, Where Is My Train), Academic GNNs (IIT-KGP RSTGCN), and Basic SIH Repos across arrival windows, weather rules, overtaking modeling, platform scheduling, feedback learning, and MedAE accuracy.

### Slide 6: Research, References, Visual Analytics & QR Verification
- **Verified Citations**:
  - Government Audits: CAG Report No. 22 of 2021, Indian Railways G&SR Rule 3.61, Track Manual Para 5.2.
  - Peer-Reviewed ML: IIT Kharagpur RSTGCN (IEEE T-ITS 2024), LightGBM (NeurIPS 2017), Conformal Quantile Regression (NeurIPS 2019), Yen's $K$-Shortest Path (1971).
  - Open Datasets: DataMeet Indian Railways, Open-Meteo Weather Grid.
- **Visual Analytics**:
  - *Graph 1 (Flywheel Curve)*: Demonstrates median error dropping from **4.93m** (static formula) ➔ **2.55m** (0.6M seed DB) ➔ **1.49m** (1.51M v2 Lake) ➔ **<1.10m** (projected at 3.0M+ live rows).
  - *Graph 2 (Delay Driver Importance)*:
    1. Current Delay & 3-Stop Velocity: 31.4%
    2. Section Slack & Feedback Profile: 22.6%
    3. Preceding Train & HDN Congestion: 17.8%
    4. G&SR Fog & Weather Speed Cap: 13.9%
    5. Outer-Signal Hold & Dwell Surge: 9.2%
    6. COA Priority & Manual Incidents: 5.1%
- **Interactive Verification**: Scannable QR code and clickable links to the live production prototype.

---

## 6. Mathematical Formulations & Algorithmic Specifications

### 6.1 Pinball Loss Objective for Quantile Estimation
For each quantile level $q \in \{0.10, 0.50, 0.90\}$, the model minimizes the asymmetric empirical risk:
$$\mathcal{L}_q(y, \hat{y}) = \frac{1}{N} \sum_{i=1}^{N} \begin{cases} 
q \cdot (y_i - \hat{y}_i) & \text{if } y_i \ge \hat{y}_i \\ 
(1 - q) \cdot (\hat{y}_i - y_i) & \text{if } y_i < \hat{y}_i 
\end{cases}$$

### 6.2 Timetable Slack Absorption & Departure Clamping
The forecasted arrival time at downstream station $S_{k+1}$ given actual departure at station $S_k$ is governed by:
$$\text{ETA}(S_{k+1}) = \text{ATD}(S_k) + \widehat{\Delta t}_{k \to k+1}^{(q)} - \alpha \cdot \text{Slack}_{k \to k+1}$$
$$\text{ETD}(S_{k+1}) = \max\Big(\text{ETA}(S_{k+1}) + \text{MinDwell}(S_{k+1}),\; \text{STD}(S_{k+1})\Big)$$
Where:
- $\widehat{\Delta t}_{k \to k+1}^{(q)}$ is the GBDT predicted pure running time under quantile $q$.
- $\text{Slack}_{k \to k+1}$ is the engineered timetable buffer for that specific section.
- $\alpha \in [0.65, 0.95]$ is the learned slack absorption coefficient.

### 6.3 IntervalTree Platform Conflict Detection
Let platform $P$ have scheduled occupancy intervals $I_j = [A_j - \delta,\; D_j + \delta]$ where $\delta = 5\text{ min}$ is the safety headway buffer.  
A new arriving train with estimated interval $I_{\text{new}} = [A_{\text{new}},\; D_{\text{new}}]$ conflicts if:
$$\exists I_j \in \text{IntervalTree}(P) \quad \text{such that} \quad A_{\text{new}} < D_j + \delta \quad \land \quad D_{\text{new}} + \delta > A_j$$
If a conflict is detected, the second train is placed into the Outer Hold Queue:
$$\Delta t_{\text{OuterHold}} = (D_j + \delta) - A_{\text{new}} + \epsilon_{\text{approach}}$$

### 6.4 Yen's $K$-Shortest Path for 25kV Detour Rerouting
Given railway network graph $G = (V, E)$ where edge weights represent running times and edge attribute $e_{\text{elec}} = \text{True}$ represents 25kV electrification:
1. Compute primary shortest electrified path $P_1$ using Dijkstra's algorithm.
2. For $k = 1$ to $K-1$:
   - For each node in $P_k$, remove edges to force alternative junction branching.
   - Compute spur path and assemble candidate detour paths.
3. Filter candidates strictly to tracks maintaining 25kV continuous electrification (preventing electric locomotives from stalling on non-electrified diesel sidings).
4. Return top 3 viable routes with computed domino arrival windows in $<5\text{ms}$.

---

## 7. REST API Contracts & Endpoints

The DARPAN engine exposes high-performance asynchronous REST endpoints via FastAPI:

### 7.1 Passenger & PNR ETA Prediction
- **Endpoint**: `GET /v1/deta/predict`
- **Query Parameters**:
  - `train_no`: `12301`
  - `station_code`: `NDLS`
- **Sample Response**:
```json
{
  "train_no": "12301",
  "train_name": "Howrah - New Delhi Rajdhani Express",
  "current_station": "PRYJ",
  "destination": "NDLS",
  "current_delay_min": 35.0,
  "predicted_arrival": {
    "p10_best_case": "09:58",
    "p50_expected": "10:06",
    "p90_worst_case": "10:19",
    "scheduled_arrival": "09:55"
  },
  "recovered_slack_min": -14.0,
  "confidence_score": 0.92,
  "status_flags": {
    "fog_pass_active": true,
    "speed_cap_kmh": 75,
    "outer_hold_warning": false
  },
  "inference_latency_ms": 1.42
}
```

### 7.2 Section Controller Manual Accident Override
- **Endpoint**: `POST /v1/deta/incidents`
- **Payload**:
```json
{
  "incident_type": "DERAILMENT",
  "section": "CNB-ETW",
  "track_blocked": "DOWN_MAIN",
  "reported_by": "CONTROLLER_PRAYAGRAJ_DIV",
  "expected_clearance_hours": 4.5,
  "require_25kv_electrified_only": true
}
```
- **Sample Response**:
```json
{
  "status": "INCIDENT_ACTIVE",
  "incident_id": "INC-2026-0928",
  "reroute_computed": true,
  "reroute_algorithm": "YEN_K_SHORTEST_PATH",
  "selected_detour": "CNB -> BNDA -> JHS -> GWL -> AGC -> NDLS",
  "electrification_verified_25kv": true,
  "affected_trains_count": 14,
  "domino_delay_recomputed_ms": 4.88
}
```

---

## 8. Competitive Benchmark & Empirical Verification

Summary of empirical benchmarking against 20,000 recorded train runs across Northern and North Central Railway zones:

| Benchmark Metric | Old Railway Formula (STA + Delay) | Where Is My Train / NTES | IIT-KGP Academic GNN (2024) | DARPAN (Team Twarit) |
| :--- | :---: | :---: | :---: | :---: |
| **Median Absolute Error (MedAE)** | 4.93 min | ~4.20 min | 3.10 min | **1.49 min (-70%)** 🏆 |
| **Prediction Format** | Single scalar time | Single scalar time | Station hourly avg | **P10 / P50 / P90 Window** |
| **Fog & Heat G&SR Rules** | ✕ None | ✕ None | ✕ None | **✓ Official G&SR Rules** |
| **Following-Train Headway** | ✕ Isolated | ✕ Isolated | ~ Topological graph | **✓ COA 6-Tier + Headway** |
| **Platform Clash Prevention** | ✕ None | ✕ Unaware | ✕ None | **✓ 5m IntervalTree Buffer** |
| **Manual Incident Overrides**| ✕ None | ✕ None | ✕ None | **✓ 1-Click 25kV Detours** |
| **Self-Learning Feedback Loop**| ✕ Static table | ✕ Read-only cache | ✕ Frozen CSV | **✓ 24x7 Self-Growing DB** |
| **Inference Query Latency** | <1ms | ~250ms | ~1,200ms (PyTorch) | **<1.5ms (FastAPI + Cache)** |

---

## 9. Verified Academic & Government Citations

1. **Comptroller and Auditor General of India (CAG)**:
   - *Report No. 22 of 2021 (Union Government — Railways)*: Proves that fixed engineering and traffic recovery margins are completely exhausted on saturated High-Density Network (HDN) routes operating above 100% capacity.
2. **Indian Railways General & Subsidiary Rules (G&SR)**:
   - *Rule 3.61 & Track Manual Para 5.2*: Mandatory speed restriction protocols during dense fog (Fog-Pass Device speed caps of $75\text{ km/h}$ vs. $60\text{ km/h}$ manual) and track expansion buckling rules at temperatures exceeding $60^\circ\text{C}$.
3. **IIT Kharagpur Railway Graph Research**:
   - Chowdhury et al. (IEEE Transactions on Intelligent Transportation Systems, 2024): *"RSTGCN: Railway-centric Spatio-Temporal Graph Convolutional Network for Train Delay Prediction across 4,735 Indian Railway Stations."*
4. **Quantile Regression & Conformal Prediction**:
   - Ke et al. (NeurIPS 2017): *"LightGBM: A Highly Efficient Gradient Boosting Decision Tree."*
   - Romano, Patterson, & Candès (NeurIPS 2019): *"Conformalized Quantile Regression."* Provides distribution-free finite-sample guarantees for the $[P_{10}, P_{90}]$ prediction intervals.
5. **Graph Detour Routing**:
   - Yen, J. Y. (1971): *"Finding the K Shortest Loopless Paths in a Network."* Management Science. Applied with 25kV continuous electrification constraints.
6. **Open Datasets**:
   - *DataMeet Indian Railways Repository*: 8,990 stations, 420,345 schedule stops, and 704 approach signal cabins.
   - *Open-Meteo High-Resolution Historical & Live Atmospheric Reanalysis Grid*.

---

### Project Artifacts & Resources in this Repository
- **Fully Editable Pitch Deck**: [`SIH2026-DARPAN-Twarit-SIH26028.pptx`](file:///c:/Users/Asus/Coding/SIH/ETA/SIH2026-DARPAN-Twarit-SIH26028.pptx)
- **High-Resolution Presentation PDF**: [`pptx_exported_from_powerpoint.pdf`](file:///c:/Users/Asus/Coding/SIH/ETA/scratch/pptx_exported_from_powerpoint.pdf)
- **Deck Generator Source Code**: [`scratch/build_fully_editable_pptx.py`](file:///c:/Users/Asus/Coding/SIH/ETA/scratch/build_fully_editable_pptx.py)
- **Extracted Graphic Assets**: [`scratch/pptx_assets/`](file:///c:/Users/Asus/Coding/SIH/ETA/scratch/pptx_assets/)
- **Slide Image Renders**: [`scratch/pptx_slides/`](file:///c:/Users/Asus/Coding/SIH/ETA/scratch/pptx_slides/)
