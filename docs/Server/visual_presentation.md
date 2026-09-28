# 🚆 SIH-DETA: Visual Architecture & System Presentation
### Comprehensive Visual Diagrams, Process Flows & Operational Blueprints

This document compiles the complete visual presentation of the **SIH-DETA** (Dynamic Estimated Time of Arrival) system for Indian Railways. It visually illustrates the end-to-end multi-tier architecture, the Hybrid ML + Discrete DSA conflict resolution engine, Section Controller incident workflows, station crowd surge models (Prayagraj Maha Kumbh), entity relationships, and real-time dataflows.

---

## 📑 Visual Index

1. [High-Level Paradigm Shift: Naive vs. SIH-DETA](#1-high-level-paradigm-shift-naive-vs-sih-deta)
2. [End-to-End Multi-Tier Pipeline (Tiers 0–7)](#2-end-to-end-multi-tier-pipeline-tiers-07)
3. [The Hybrid Architecture: ML vs. Discrete DSA Closed Loop](#3-the-hybrid-architecture-ml-vs-discrete-dsa-closed-loop)
4. [Platform Slot Allocation & Outer Signal Starvation (Interval Trees)](#4-platform-slot-allocation--outer-signal-starvation-interval-trees)
5. [Section Controller Incident Lifecycle & Rerouting (CRO, Track Block)](#5-section-controller-incident-lifecycle--rerouting-cro-track-block)
6. [Station Passenger Capacity & Pilgrimage Surge Dynamics (Maha Kumbh)](#6-station-passenger-capacity--pilgrimage-surge-dynamics-maha-kumbh)
7. [Complete System Entity-Relationship (ER) Architecture](#7-complete-system-entity-relationship-er-architecture)
8. [Spatial Map-Matching & Approach Cabin Disambiguation (HMM)](#8-spatial-map-matching--approach-cabin-disambiguation-hmm)
9. [Real-Time Distributed Production Infrastructure & API Flow](#9-real-time-distributed-production-infrastructure--api-flow)
10. [System Execution & Verification Gantt Roadmap](#10-system-execution--verification-gantt-roadmap)
11. [Feedback Loop Prevention & Space-Time DAG Marching](#11-feedback-loop-prevention--space-time-dag-marching)
12. [Black Swan Disaster Resilience & 3-Level Degradation](#12-black-swan-disaster-resilience--3-level-degradation)
13. [Adaptive Schedule-Aware Ingestion & Token-Bucket Pacing](#13-adaptive-schedule-aware-ingestion--token-bucket-pacing)

---

## 1. High-Level Paradigm Shift: Naive vs. SIH-DETA

Existing railway apps fail because they assume delays compound linearly. SIH-DETA models non-linear timetable recovery slack, dispatching priority rules, and physical safety caps.

```mermaid
flowchart TD
    subgraph Problem["❌ The Legacy Problem: Naive Static Extrapolation"]
        A1["Live Train Telemetry<br><i>Train 12004 is 35 min late at Etawah</i>"] --> A2["Static Formula:<br><b>ETA = STA + Current Delay</b>"]
        A2 --> A3["False Passenger Alert:<br>'Arriving 35 mins late at Kanpur'"]
        A3 -.-> A4["Reality: Train arrives on time!<br><b>36 mins of timetable slack absorbed.</b><br>Passenger missed train or loses trust."]
    end

    subgraph Solution["✅ The SIH-DETA Solution: Hybrid Physics + ML Engine"]
        B1["Live Multi-Source Stream<br><i>Position, Speed Drift, Weather, Track State</i>"] --> B2{"SIH-DETA Engine"}
        B2 --> B3["🧠 ML Hemisphere<br>Predicts empirical transit Δt & slack absorption<br><b>P10 / P50 / P90 Pinball Loss</b>"]
        B2 --> B4["⚙️ Discrete DSA Hemisphere<br>Validates platform slots & headway intervals<br><b>Guarantees Physical Safety Rules</b>"]
        B3 --> B5["🎯 Dynamic Arrival Windows"]
        B4 --> B5
        B5 --> B6["Transparent Passenger Feed:<br><b>P10 (Early): 11:32 | P50: 11:41 | P90 (Late): 11:58</b><br>Expected Slack Recovery: -14 mins"]
    end

    style Problem fill:#fff1f0,stroke:#ffa39e,stroke-width:2px
    style Solution fill:#f6ffed,stroke:#b7eb8f,stroke-width:2px
```

---

## 2. End-to-End Multi-Tier Pipeline (Tiers 0–7)

The end-to-end dataflow across the 7 operational tiers, moving from raw geographic track topology to real-time client delivery.

```mermaid
flowchart TD
    subgraph Tier0["Tier 0: Physical & Topological Ground Truth"]
        T0_1["Track Adjacency Graph<br><b>8,990 Nodes & 395 Junctions</b>"]
        T0_2["Kinematic Speed Caps<br><b>Section MPS (110–160 km/h)</b>"]
        T0_3["Rolling Stock Dynamics<br><b>LHB Twin-Pipe vs ICF Braking</b>"]
    end

    subgraph Tier1["Tier 1: Multi-Source Ingestion Layer"]
        T1_1["Static Timetables<br><b>420,345 Halts</b>"]
        T1_2["Real-Time Telemetry<br><b>RTIS / NTES Feeds</b>"]
        T1_3["Environmental Feeds<br><b>Fog / Monsoon / Rail Temp</b>"]
        T1_4["Historical Database<br><b>1.51M Recorded Delays</b>"]
        T1_5["Controller Override Stream<br><b>Live Incidents & TSRs</b>"]
    end

    subgraph Tier2["Tier 2: Conflation & Spatial-Temporal Matching"]
        T2_1["HMM Viterbi Map-Matching<br><i>Snaps GPS to Rail Centerline</i>"]
        T2_2["Modulo-24 Midnight Unwrapping<br><i>Resolves multi-day journey rollovers</i>"]
        T2_3["Entity Resolution<br><i>Commercial Stations vs 704 Approach Cabins</i>"]
    end

    subgraph Tier3["Tier 3: Operational Constraints & G&SR Engine"]
        T3_1["G&SR Fog Caps (60/75 km/h)"]
        T3_2["COA Dispatching Hierarchy (Tiers 1-6)"]
        T3_3["Timetable Slack Budget Bounds"]
    end

    subgraph Tier4["Tier 4: Stochastic Profiling & Surge Modeling"]
        T4_1["73,342 Sectional Profiles (μ, σ)"]
        T4_2["Markov State Transition Engine"]
        T4_3["Station NSG Footfall & Surge Multiplier"]
    end

    subgraph Tier5["Tier 5: Core Machine Learning Engine"]
        T5_1["Feature Store Fusion (Arrow)"]
        T5_2["LightGBM Quantile Regressors<br><b>P10 / P50 / P90 Bounds</b>"]
    end

    subgraph Tier6["Tier 6: Discrete DSA Scheduler & Conflict Resolver"]
        T6_1["Interval Tree Platform Allocator"]
        T6_2["FIFO Headway Safety Buffers (3–7 min)"]
        T6_3["Yen's K-Shortest Path Detour Router"]
    end

    subgraph Tier7["Tier 7: Delivery & Operational Support"]
        T7_1["FastAPI REST Endpoints (/api/v1/eta)"]
        T7_2["Controller Incident Portal (WebSockets)"]
        T7_3["Passenger UI Confidence Bars"]
    end

    Tier0 --> Tier2
    Tier1 --> Tier2
    Tier2 --> Tier3
    Tier2 --> Tier4
    Tier3 --> Tier5
    Tier4 --> Tier5
    Tier5 --> Tier6
    Tier6 --> Tier7
```

---

## 3. The Hybrid Architecture: ML vs. Discrete DSA Closed Loop

This diagram details the exact algorithmic boundary: **Machine Learning** predicts unconstrained statistical drift; **Data Structures & Algorithms** strictly enforce physical safety and platform availability.

```mermaid
flowchart LR
    subgraph TelemetryInput["Incoming Event State"]
        TrainState["Train: 12004<br>Section: TDL -> CNB<br>Current Delay: 35m<br>Weather: Visibility 450m"]
    end

    subgraph MLHemisphere["🧠 Machine Learning Hemisphere"]
        direction TB
        FStore["Feature Store Assembly<br>(Slack, Drift, Weather, Gradient)"]
        LGBM["LightGBM Quantile Regressors"]
        FStore --> LGBM
        LGBM --> ML_Out["<b>Unconstrained Transit Predictions</b><br>P10: 11:32<br>P50: 11:41<br>P90: 11:58"]
    end

    subgraph DSAHemisphere["⚙️ Discrete DSA / OR Hemisphere"]
        direction TB
        PlatCheck{"Platform Occupancy Check<br><i>IntervalTree at CNB</i>"}
        OuterHold["<b>Outer Signal Starvation Hold</b><br>Diverted to Juhi Outer Cabin<br>Added Detention: +12 mins"]
        Clear["Platform 1 Free<br>Direct Ingress"]
        Headway["Enforce 5-min Headway Buffer"]

        PlatCheck -->|"Conflict Detected<br>Platforms 1-4 Busy"| OuterHold
        PlatCheck -->|"Slot Clear"| Clear
        OuterHold --> Headway
        Clear --> Headway
    end

    TelemetryInput --> FStore
    ML_Out --> PlatCheck
    Headway --> VerifiedETA["🎯 Verified Dynamic ETA Output<br>P10: 11:44 | P50: 11:53 | P90: 12:10<br>Platform: 1 (Assigned)"]

    style MLHemisphere fill:#e6f7ff,stroke:#91d5ff,stroke-width:2px
    style DSAHemisphere fill:#fff7e6,stroke:#ffd591,stroke-width:2px
```

---

## 4. Platform Slot Allocation & Outer Signal Starvation (Interval Trees)

How approaching trains are scheduled into station platforms using **Interval Trees**, and how conflicts are automatically resolved into outer home signal queuing.

```mermaid
flowchart TD
    TrainArrival["Incoming Train T1<br>Predicted Arrival Window: [14:10, 14:25]"] --> TreeQuery["Query Station Interval Tree<br><code>intervaltree.overlap(14:05, 14:30)</code>"]

    subgraph PlatformStatus["Station Platform Intervals (e.g. Kanpur Central)"]
        P1["Platform 1: [13:50, 14:15] (Occupied by Train 12424)"]
        P2["Platform 2: [14:00, 14:40] (Occupied by Train 12302)"]
        P3["Platform 3: [14:05, 14:35] (Occupied by Train 12562)"]
        P4["Platform 4: Empty"]
    end

    TreeQuery --> PlatformStatus

    PlatformStatus --> Decision{"Is Any Compatible Platform Open?"}

    Decision -->|"Yes: Platform 4 Available"| Assign["✅ Assign Platform 4<br>Reserve Interval [14:10 - h, 14:25 + h]<br>Green Signal Ingress"]
    Decision -->|"No: All Platforms Saturated"| Hold["🛑 Outer Signal Hold Imposed<br>Train routed to approach cabin (e.g. Juhi Outer)<br>Holding Speed: 0 km/h"]

    Hold --> CalcHold["Compute Minimum Clearance Delay:<br><b>Detention = min(Platform Departures) + Headway - Arrival</b>"]
    CalcHold --> UpdateETA["Push Outer Hold Alert & Recalculate ETA"]

    style Assign fill:#f6ffed,stroke:#52c41a,stroke-width:2px
    style Hold fill:#fff1f0,stroke:#f5222d,stroke-width:2px
```

---

## 5. Section Controller Incident Lifecycle & Rerouting (CRO, Track Block)

The end-to-end lifecycle when a **Section Controller** logs a Cattle Run-Over (CRO), Alarm Chain Pulling (ACP), or broken rail incident.

```mermaid
sequenceDiagram
    autonumber
    actor SCR as 👨‍💼 Section Controller (DRM Office)
    participant API as 🌐 Controller Ingestion API
    participant IncidentMgr as ⚡ Incident Manager
    participant NetworkGraph as 🗺️ Track Topology Graph
    participant TrailingQueue as 🚦 FIFO Headway Engine
    participant ClientBus as 📡 Live WebSocket Broadcast

    SCR->>API: POST /api/v1/controller/incident {type: "CRO", section: "ALJN-KRJ", severity: "BLOCK", est_clearance: 35}
    API->>IncidentMgr: Ingest Incident Record
    
    alt Incident: Cattle Run-Over (CRO) / ACP
        IncidentMgr->>IncidentMgr: Inject Air Brake Pipe Repair Detention (+35 mins)
        IncidentMgr->>TrailingQueue: Identify trailing trains within 25 km
        TrailingQueue->>TrailingQueue: Cascade red signal detention to 4 trailing trains
    else Incident: Track Inoperable / Broken Rail
        IncidentMgr->>NetworkGraph: Sever Track Edge (Weight = ∞)
        IncidentMgr->>NetworkGraph: Execute Yen's K-Shortest Paths (Filter Electric Traction)
        NetworkGraph-->>IncidentMgr: Return Electrified Bypass Route
        IncidentMgr->>IncidentMgr: Rewrite active itinerary & recalculate halt times
    end

    IncidentMgr->>ClientBus: Publish INCIDENT_BROADCAST Event
    ClientBus-->>SCR: Confirm Incident Acknowledged & Network Stabilized
    ClientBus-->>SCR: Display Recommended Hold Orders
```

---

## 6. Station Passenger Capacity & Pilgrimage Surge Dynamics (Maha Kumbh)

Visualizing how massive festival crowds (e.g., Prayagraj Maha Kumbh) dilate passenger dwell times and saturate station platforms.

```mermaid
flowchart TD
    subgraph Inputs["Crowd Surge Ingestion Indicators"]
        S1["🏛️ Station Hierarchy: <b>NSG-1</b><br>(Prayagraj Jn: >20M passengers/yr)"]
        S2["🎪 Event Calendar: <b>Maha Kumbh Active</b><br>Surge Multiplier S_event = 3.2"]
        S3["🎫 Booking Pressure: <b>Waitlist 350+</b><br>Unreserved Coach Boarding Crush"]
        S4["🚆 Special Trains Influx: <b>+45 Mela Specials/day</b><br>Eating Corridor Headway Capacity"]
    end

    subgraph DwellModel["⏱️ Dwell Time Dilation Engine"]
        Formula["Formula:<br><b>T_actual = T_sched × (1 + α·Footfall + β·(S_event - 1)) + Δt_ACP</b>"]
        Calc["Scheduled Halt: 5 mins<br>Boarding Overhead: +14 mins<br>ACP Delay Risk: +6 mins<br><b>Dilated Halt: 25 mins</b>"]
        Formula --> Calc
    end

    subgraph Impact["🚉 Physical Network Impact"]
        I1["Platform Turnaround Collapses<br>Trains hold platforms 5x longer"]
        I2["Approaching Expresses Trapped<br>Held at Naini & Subedarganj Outers"]
        I3["P90 Pessimistic Arrival Window Explodes<br>Buffer widened by +40 mins"]
    end

    Inputs ==> DwellModel
    DwellModel ==> Impact

    style DwellModel fill:#fffbe6,stroke:#ffe58f,stroke-width:2px
    style Impact fill:#fff1f0,stroke:#ffa39e,stroke-width:2px
```

---

## 7. Complete System Entity-Relationship (ER) Architecture

The relational architecture connecting all 6 production databases across trains, stations, telemetry, operational incidents, and platform intervals.

```mermaid
erDiagram
    TRAINS ||--o{ SCHEDULES : operates_with
    TRAINS ||--o{ LIVE_STATE : tracks
    TRAINS ||--o{ TRAIN_REROUTES : rerouted_via
    STATIONS ||--o{ SCHEDULES : halts_at
    STATIONS ||--o{ APPROACH_CABINS : has_approach
    STATIONS ||--o{ PLATFORM_INTERVALS : manages_slots
    INCIDENTS ||--o{ TRAIN_REROUTES : triggers
    INCIDENTS ||--o{ SPEED_RESTRICTIONS : imposes
    STATIONS ||--o{ EVENT_CALENDAR : affected_by

    TRAINS {
        string train_number PK
        string train_name
        string train_type
        int priority_tier
        string origin_code
        string dest_code
        float total_distance_km
        string rake_type
    }

    SCHEDULES {
        string train_number PK,FK
        string station_code PK,FK
        int stop_sequence PK
        int scheduled_arr_mins
        int scheduled_dep_mins
        int scheduled_dwell_mins
        float cumulative_km
    }

    STATIONS {
        string station_code PK
        string station_name
        float latitude
        float longitude
        boolean is_junction
        int platform_count
        string nsg_category
        string zone_code
    }

    APPROACH_CABINS {
        string cabin_code PK
        string parent_station_code FK
        string cabin_name
        float latitude
        float longitude
        float distance_to_parent_km
    }

    PLATFORM_INTERVALS {
        string interval_id PK
        string station_code FK
        int platform_number
        string train_number FK
        int reserved_from_mins
        int reserved_until_mins
        string status
    }

    INCIDENTS {
        string incident_id PK
        string incident_type
        string section_from FK
        string section_to FK
        string severity
        int estimated_clearance_mins
        string reported_by
        boolean is_resolved
    }

    LIVE_STATE {
        string journey_uid PK
        string train_number FK
        float current_lat
        float current_lon
        string last_station FK
        int instantaneous_delay_mins
        float delay_drift_rate
        boolean is_outer_held
    }
```

---

## 8. Spatial Map-Matching & Approach Cabin Disambiguation (HMM)

How raw GPS points with multi-path jitter are snapped to physical rail centerlines, and how approach cabins detect outer signal holds before commercial stations.

```mermaid
flowchart TD
    RawGPS["Raw GPS Coordinates<br><i>Lat: 26.4482, Lon: 80.3291 (Jitter ±45m)</i>"] --> KDTree["KD-Tree Spatial Query<br>Find Candidate Tracks within 100m"]

    subgraph CandidateLines["Candidate Track Segments"]
        C1["Track 1: Up Main Line"]
        C2["Track 2: Down Main Line"]
        C3["Track 3: Goods Yard Loop"]
    end

    KDTree --> CandidateLines

    CandidateLines --> HMM["Hidden Markov Model (HMM) with Viterbi Decoding"]

    subgraph Probabilities["Viterbi Probabilities"]
        P1["Emission P(z|x): Haversine distance to centerline"]
        P2["Transition P(x_t|x_t-1): Track continuity vs Euclidean step"]
        P3["Heading Pruning: Reject candidate if bearing delta > 90°"]
    end

    HMM --> Probabilities
    Probabilities --> Snapped["Snapped Track Centerline<br><b>Track 2: Down Main Line confirmed</b>"]

    Snapped --> CabinCheck{"Is Distance to Station < 2 km and Speed = 0?"}
    CabinCheck -->|"Yes"| ApproachDetection["Flag as <b>Held at Outer Cabin</b><br>(e.g., Juhi Outer approach cabin)<br>Trigger Platform Starvation Delay"]
    CabinCheck -->|"No"| NormalRun["Standard Sectional Running State"]

    style Snapped fill:#f6ffed,stroke:#52c41a,stroke-width:2px
    style ApproachDetection fill:#fffbe6,stroke:#faad14,stroke-width:2px
```

---

## 9. Real-Time Distributed Production Infrastructure & API Flow

The deployment architecture designed for sub-50ms query response times under high-concurrency passenger traffic and continuous controller updates.

```mermaid
flowchart TD
    subgraph Clients["Presentation Layer"]
        PWA["Passenger Mobile App<br>(P10/P50/P90 Confidence Bars)"]
        AdminUI["Controller DRM Console<br>(Live Track Graph & Override Portal)"]
    end

    subgraph Edge["Gateway & CDN"]
        LB["Nginx / Cloudflare Load Balancer<br>SSL Termination & Rate Limiting"]
    end

    subgraph AppServers["FastAPI Compute Cluster (Async ASGI)"]
        API1["FastAPI Worker 1"]
        API2["FastAPI Worker 2"]
        API3["FastAPI Worker 3"]
        WS_Server["WebSocket Manager<br>(Push Incident Stream)"]
    end

    subgraph StateAndCache["In-Memory State & Cache"]
        RedisCache[("Redis Cache<br>Sub-second Platform Intervals & Live ETAs")]
    end

    subgraph EngineWorkers["Background Computing Daemons"]
        MLWorker["Quantile ML Inference Engine<br>(LightGBM / PyPolars)"]
        DSAWorker["Discrete Scheduler & Graph Router<br>(IntervalTree / NetworkX)"]
        WeatherPoller["Weather & G&SR Poller<br>(Open-Meteo / Fog Watchdog)"]
    end

    subgraph MasterStorage["Disk Master Storage (660 MB Database Layer)"]
        DB_Master[("SQLite WAL Stores<br>trains.db | stations.db<br>telemetry.db | historical.db")]
    end

    Clients <--> Edge
    Edge <--> AppServers
    AppServers <--> RedisCache
    AppServers <--> EngineWorkers
    EngineWorkers <--> MasterStorage
    WS_Server -.-> AdminUI
```

---

## 10. System Execution & Verification Gantt Roadmap

Timeline and milestones for integrating the DSA Scheduler, Controller Portal, and Quantile Engine into the existing 1.5M historical data foundation.

```mermaid
gantt
    title SIH-DETA Implementation & Verification Timeline
    dateFormat  YYYY-MM-DD
    axisFormat  %b %d

    section Phase 1: Feature Engine
    Assemble Parquet / Arrow Master Feature Store    :done, p1_1, 2026-09-08, 2d
    Compute Historical Slack Absorption Tensors      :done, p1_2, 2026-09-10, 2d

    section Phase 2: DSA & Controller
    Scaffold IntervalTree Platform Scheduler        :active, p2_1, 2026-09-11, 3d
    Implement Controller Ingestion API & Overrides   :p2_2, 2026-09-14, 2d
    Build Yen's K-Shortest Path Rerouting Module     :p2_3, 2026-09-16, 2d

    section Phase 3: ML Quantiles
    Train LightGBM Quantile Models (P10/50/90)      :p3_1, 2026-09-18, 3d
    Benchmark Pinball Loss & Calibration Bounds      :p3_2, 2026-09-21, 2d

    section Phase 4: API & Visual UI
    Scaffold FastAPI REST & WebSocket Endpoints      :p4_1, 2026-09-23, 2d
    Deploy Interactive Map Dashboard                 :p4_2, 2026-09-25, 3d
    Full End-to-End System Stress Testing            :p4_3, 2026-09-28, 2d
```

---

## 11. Feedback Loop Prevention & Space-Time DAG Marching

How the hybrid architecture prevents infinite ping-pong loops between Machine Learning and Discrete DSA using a **strictly forward-marching Space-Time Directed Acyclic Graph (DAG)** and a **2-Pass Decoupled Pipeline**.

```mermaid
flowchart TD
    subgraph Pass1["Pass 1: Macro ML Inference (Computed ONCE)"]
        ML_Init["Predict unconstrained link runtimes:<br><b>Δt(TDL->ETW) = 45m | Δt(ETW->CNB) = 75m | Δt(CNB->PRYJ) = 110m</b>"]
    end

    subgraph Pass2["Pass 2: Micro DSA Forward Marching (Topological DAG)"]
        direction TB
        S1["<b>Station 1: Tundla</b><br>Platform cleared -> Depart 14:00<br><b>Status: LOCKED 🔒</b>"]
        S2["<b>Station 2: Etawah</b><br>Arrival: 14:00 + 45m = 14:45<br>Platform 2 Free -> Depart 14:47<br><b>Status: LOCKED 🔒</b>"]
        S3["<b>Station 3: Kanpur Central</b><br>Arrival: 14:47 + 75m = 16:02<br>⚠️ Conflict: Platforms 1-3 full!<br>Outer Signal Hold: +13 mins<br>Depart 16:17<br><b>Status: LOCKED 🔒</b>"]
        S4["<b>Station 4: Prayagraj</b><br>Downstream Arrival shifted via integer math:<br>16:17 + 110m = 18:07<br><i>Zero expensive ML re-inference needed!</i>"]

        S1 ==> S2
        S2 ==> S3
        S3 ==> S4
    end

    Pass1 ==> Pass2

    style S1 fill:#f6ffed,stroke:#52c41a,stroke-width:2px
    style S2 fill:#f6ffed,stroke:#52c41a,stroke-width:2px
    style S3 fill:#fffbe6,stroke:#faad14,stroke-width:2px
    style S4 fill:#e6f7ff,stroke:#1890ff,stroke-width:2px
```

---

## 12. Black Swan Disaster Resilience & 3-Level Degradation

Visualizing the system's fault-tolerant behavior during catastrophic disruptions (massive derailments, grid power blackouts, civil rail blockades) where historical ML models become invalid.

```mermaid
flowchart TD
    Normal["🟢 LEVEL 1: NORMAL HYBRID MODE<br>• Full Quantile LightGBM Models Active<br>• IntervalTree Platform Allocation<br>• Real-time Telemetry & Micro-Cabins"]

    Normal -->|"Severe Telemetry Drop / Upstream Hang"| Degraded["🟡 LEVEL 2: DEGRADED DEAD-RECKONING<br>• ML switched to conservative physics bounds<br>• Uses historical corridor profile (μ, σ)<br>• Slack absorption limits enforced"]

    Normal -->|"Mid-Section Stall >12 mins OR Track Severed"| BlackSwan["🔴 LEVEL 3: BLACK SWAN DISASTER MODE<br>• <b>Autonomous Stall Watchdog Trips Circuit Breaker</b><br>• ML prediction frozen (Historical data meaningless)<br>• Sever track edge (Weight = ∞)<br>• Trigger Yen's K-Shortest Path Electrified Bypass<br>• UI displays: 'SERVICE SUSPENDED / INDEFINITE DETENTION'"]

    Degraded -->|"Track Clearance Restored"| Normal
    BlackSwan -->|"Divisional Clearance Order"| Normal

    style Normal fill:#f6ffed,stroke:#52c41a,stroke-width:2px
    style Degraded fill:#fffbe6,stroke:#faad14,stroke-width:2px
    style BlackSwan fill:#fff1f0,stroke:#f5222d,stroke-width:2px
```

---

## 13. Adaptive Schedule-Aware Ingestion & Token-Bucket Pacing

Visualizing how the system filters out 4,000+ inactive trains, clusters weather into 180 spatial hexagonal cells, dynamically paces polling based on train speed and approach cabins, and guarantees a flat 3.5 RPS traffic profile.

```mermaid
flowchart TD
    subgraph MasterPool["Master Railway Network Catalog"]
        T_Cat["5,209 Cataloged Trains"]
        S_Cat["8,990 Stations & Cabins"]
    end

    subgraph FilterLayer["Stage 1: Active Journey Window & Spatial Clustering"]
        Filter["Active Journey Window Filter<br><code>Current_Time ∈ [T_orig - 30m, T_dest + 8h]</code>"]
        WeatherCluster["Spatial Hexagonal Clustering<br><i>8,990 stations ➔ 180 Regional Weather Cells</i>"]
    end

    T_Cat --> Filter
    S_Cat --> WeatherCluster

    Filter -->|"Inactive (~4,200 Trains)"| Stabled["💤 Sleep State (Zero Requests)"]
    Filter -->|"Active (~1,000 Trains)"| MinHeap["⚡ Stage 2: Chronological Priority Min-Heap<br>(Sorted by next_poll_timestamp)"]

    subgraph DynamicEngine["Stage 3: Kinematic & Priority Frequency Engine"]
        E1["<b>Tier 1: Vande Bharat / Rajdhani</b><br>Cruise at 130 km/h ➔ Poll every 2-3 mins"]
        E2["<b>Tier 2: Superfast / Express</b><br>Normal Run ➔ Poll every 5-7 mins"]
        E3["<b>Approach Deceleration (Speed 90 -> 30 -> 0)</b><br>Approaching Outer Signal ➔ <b>Poll every 45 secs!</b>"]
        E4["<b>Long Station Halt (Dwell > 20 mins)</b><br>Train parked at platform ➔ Back off to 10 mins"]
    end

    MinHeap --> DynamicEngine

    subgraph PacingLayer["Stage 4: Token Bucket Rate Limiter"]
        TB["🚰 Token Bucket Engine<br><code>Rate: 4.0 req/s | Burst Capacity: 8.0</code><br>Flattens bandwidth into stealthy flat line"]
    end

    DynamicEngine --> TB
    WeatherCluster -.->|"Poll once every 30-45m"| TB

    TB --> NetworkDispatch["🌐 Upstream Railway Portals & Open-Meteo<br>(Zero Rate-Limit Bans | Flat 3.5 RPS Load)"]

    style FilterLayer fill:#e6f7ff,stroke:#1890ff,stroke-width:2px
    style DynamicEngine fill:#fffbe6,stroke:#faad14,stroke-width:2px
    style PacingLayer fill:#f6ffed,stroke:#52c41a,stroke-width:2px
```


