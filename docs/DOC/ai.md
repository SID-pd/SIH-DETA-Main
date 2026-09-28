# 🚆 Real-Time Railway ETA Prediction & Operational Intelligence System

## 1. Overview

This project is a **real-time, data-driven ETA prediction and railway traffic intelligence system** designed for Indian Railways coaching trains.

The system combines:

- Historical train-running data
- Live train location data
- Train and station information
- Halt behaviour
- Track and route topology
- Weather and environmental conditions
- Speed restrictions
- Traffic/congestion information
- Operational constraints
- Emergency and maintenance events

to continuously predict train arrival times and evaluate whether the prediction is operationally feasible.

The system is designed around three core computational layers:

```text
Layer 1
Train & Halt Behaviour Analysis
        ↓
Layer 2
Operational Constraint / Verification Engine
        ↓
Layer 3
Real-Time ETA Prediction Engine
        ↓
Final Verified ETA
```

An additional **Admin / Simulation interface** allows railway operators to introduce hypothetical or real operational events and observe their possible impact.

---

# 2. High-Level Architecture

```text
                    ┌──────────────────────────┐
                    │ Historical Data Sources  │
                    │ GPS / Schedules / Logs   │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │      Main Database       │
                    │ PostgreSQL / PostGIS     │
                    └────────────┬─────────────┘
                                 │
                ┌────────────────┴────────────────┐
                │                                 │
                ▼                                 ▼
       ┌─────────────────┐              ┌──────────────────┐
       │   Layer 1       │              │ Network / Track  │
       │ Behaviour Model │              │ Graph Information │
       └────────┬────────┘              └─────────┬────────┘
                │                                 │
                └────────────────┬────────────────┘
                                 ▼
                    ┌──────────────────────────┐
                    │        Layer 2            │
                    │ Constraint & Verification │
                    │        Engine             │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │        Layer 3            │
                    │ Real-Time ETA Prediction  │
                    │          Model            │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │ Verification & Confidence │
                    │        Assessment         │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │     Redis Live Layer     │
                    │ Cache + Current State    │
                    └────────────┬─────────────┘
                                 │
                ┌────────────────┼────────────────┐
                ▼                ▼                ▼
             Mobile App      Dashboard          APIs
```

---

# 3. Railway Network Representation

The railway network is represented as a **time-dependent graph**.

A simplified representation:

```text
Station A
   │
   │ Section
   │
 Halt 1
   │
   │
 Signal / Operational Point
   │
 Halt 2
   │
   │
Station B
```

Each node/segment can contain information such as:

```text
Station / Halt
├── Location
├── Connected stations
├── Track information
├── Expected traversal time
├── Historical traversal time
├── Train movement information
├── Halt behaviour
├── Weather
├── Speed restrictions
├── Congestion
└── Operational conditions
```

This allows the system to work at two levels.

### Normal Mode

If the section is behaving normally:

```text
Station A → Station B
```

the system can use the aggregate section-level prediction.

### Detailed Mode

If abnormal behaviour is detected:

```text
Station A
   ↓
Halt 1
   ↓
Halt 2
   ↓
Signal
   ↓
Station B
```

the system traverses the individual segments and evaluates where the deviation is occurring.

This makes the system more explainable and useful for operational analysis.

---

# 4. Layer 1 — Train & Halt Behaviour Model

Layer 1 learns how different trains behave under normal operating conditions.

The system analyses historical records to determine factors such as:

- Train type
- Train category
- Typical halt duration
- Typical sectional running time
- Historical delays
- Recovery behaviour
- Station-specific delay patterns
- Time-of-day behaviour
- Day-of-week patterns
- Seasonal patterns

For example:

```text
Train Type A
Station Halt → Average 2.5 min

Train Type B
Station Halt → Average 4.0 min

Train Type C
Station Halt → Average 6.2 min
```

Instead of using a fixed value for every train, the model generates a **dynamic behavioural weight**.

Conceptually:

```text
Halt Weight =
f(train type,
  station,
  historical halt duration,
  time,
  day,
  season,
  current conditions)
```

These weights become inputs for subsequent layers.

---

# 5. Layer 2 — Operational Constraint & Verification Engine

Layer 2 is primarily a **mathematical and rule-based computation engine**.

Its purpose is to determine whether a predicted movement is operationally feasible.

It evaluates:

- Train ordering
- Track occupancy
- Section availability
- Scheduled movements
- Expected arrival/departure times
- Minimum operational separation
- Speed restrictions
- Braking constraints
- Platform availability where applicable
- Maintenance blocks
- Track closures
- Rerouting possibilities
- Other operational constraints

The engine does **not replace railway signalling or safety-critical control systems**.

Instead, it acts as a computational verification and decision-support layer.

---

# 6. Conflict Detection

For every predicted train movement, the engine checks for conflicts.

Example:

```text
Train A
Section X
10:00 → 10:12

Train B
Section X
10:08 → 10:20
```

The engine detects a potential conflict based on the applicable operational constraints.

It then evaluates:

```text
Is the movement feasible?
        │
        ├── YES → Accept prediction
        │
        └── NO
             ↓
       Generate alternatives
```

---

# 7. Layer 3 — Real-Time ETA Prediction

Layer 3 is the primary machine-learning prediction engine.

It periodically consumes live data such as:

```text
Current train location
Current speed
Current delay
Previous station arrival
Previous station departure
Upcoming stations
Historical running behaviour
Train type
Weather
Congestion
Speed restrictions
Track conditions
Operational events
```

The model predicts:

```text
ETA at Station 1
ETA at Station 2
ETA at Station 3
...
ETA at Destination
```

The model continuously updates as new information arrives.

Example:

```text
Initial prediction:

Station B → 14:30
Station C → 15:10
Destination → 18:45

New live data arrives
        ↓

Updated prediction:

Station B → 14:34
Station C → 15:18
Destination → 18:57
```

Thus ETA is **dynamic rather than schedule-based**.

---

# 8. Prediction Verification

Layer 3's output is passed through the verification engine.

```text
ML Prediction
      ↓
Operational Verification
      ↓
 ┌───────────────┐
 │ Feasible?     │
 └───────┬───────┘
         │
    ┌────┴────┐
    │         │
   YES        NO
    │         │
    ▼         ▼
Accept       Alternative
ETA          Analysis
```

Only predictions that satisfy the defined operational constraints are marked as verified.

The system can also attach a **confidence score / uncertainty range** to the ETA.

Example:

```text
ETA: 18:42
Expected range: 18:38 – 18:48
Confidence: 91%
```

---

# 9. Alternative Scenario Engine

If the initial prediction fails verification, the system does not simply reject it.

It generates possible alternatives.

For example:

```text
Option 1:
Hold Train A for 3 minutes

Option 2:
Allow Train A to proceed
Hold Train B for 5 minutes

Option 3:
Use alternate route

Option 4:
Adjust downstream movement
```

Each option is evaluated against the network.

The system can calculate the estimated consequences:

```text
Total delay
Number of affected trains
Affected stations
Track utilisation
Expected recovery
Passenger impact
```

---

# 10. Optimization Engine

An optimization function searches for the operationally preferable solution.

Conceptually:

```text
Minimize:

Total Network Delay
+ Number of Conflicts
+ Passenger Impact
+ Operational Cost
```

subject to:

```text
Track constraints
Train constraints
Speed constraints
Separation constraints
Platform constraints
Maintenance constraints
Schedule constraints
```

Example output:

```text
Recommended Action:

Hold Train A at Station X
Duration: 3 minutes

Expected result:

Train A delay: +3 min
Train B delay: 0 min
Network impact: Low
Expected downstream recovery: 2 min
```

The system therefore provides **recommendations**, rather than directly controlling railway infrastructure.

---

# 11. Admin Simulation / Data Injection

An administrator can introduce operational changes into the system.

Examples:

```text
New train introduced
New track introduced
Track closed
Maintenance block
Temporary speed restriction
Platform unavailable
Route changed
Special train movement
Operational disruption
```

The system then runs the scenario through the computational engine.

Example:

```text
Admin:
Close Section X from 14:00–16:00

          ↓

Network Graph Updated

          ↓

Affected trains identified

          ↓

Alternative routes / holds calculated

          ↓

ETA recalculated

          ↓

Impact displayed to administrator
```

This provides a **what-if simulation capability**.

---

# 12. Emergency Event Engine

The system also supports unexpected incidents.

Emergency events can be classified by severity.

### Level 1 — Minor

Examples:

- Small temporary delay
- Minor operational slowdown
- Speed reduction

Usually recoverable through normal running adjustments.

### Level 2 — Moderate

Examples:

- Obstruction requiring removal
- Animal/cattle incident
- Temporary operational blockage

The system estimates the expected clearance time and recalculates ETA.

### Level 3 — Major

Examples:

- Track maintenance
- Track blockage
- Route disruption
- Major operational restriction

The system can calculate:

```text
Estimated clearance
Possible rerouting
Expected delays
Affected trains
```

### Level 4 — Critical / Disaster

Examples:

- Major accident
- Severe infrastructure failure
- Unknown clearance time
- Large-scale disruption

In this case, the system should **not fabricate an ETA**.

Instead:

```text
ETA: Indeterminate

Reason:
Critical incident / clearance time unknown

Next update:
When new operational information becomes available
```

This is an important reliability feature.

---

# 13. Real-Time Data Pipeline

The system continuously receives new information.

```text
Live Data
   ↓
Data Validation
   ↓
Feature Generation
   ↓
Layer 1
   ↓
Layer 3 Prediction
   ↓
Layer 2 Verification
   ↓
Optimization / Alternatives
   ↓
Verified ETA
   ↓
Redis
   ↓
API
```

Whenever new data arrives, the relevant predictions are recalculated.

---

# 14. Redis Live Data Layer

The main database remains the **source of truth**.

Redis acts as the high-speed live serving layer.

For example:

```text
train:{train_id}:status
train:{train_id}:eta
train:{train_id}:position
station:{station_id}:arrivals
section:{section_id}:occupancy
incident:{incident_id}:status
```

The API can therefore serve frequently requested information without repeatedly executing expensive database queries or ML computations.

Architecture:

```text
Main DB
   ↓
Computation Engine
   ↓
Redis
   ↓
API
   ↓
Users / Applications
```

Redis should **not be directly exposed to public users**.

---

# 15. API Layer

The system exposes APIs for external applications.

Possible endpoints:

```text
GET /trains/{train_id}

GET /trains/{train_id}/eta

GET /trains/{train_id}/route

GET /stations/{station_id}/arrivals

GET /sections/{section_id}/status

GET /incidents/active

GET /network/status
```

For authorized administrators:

```text
POST /admin/incident

POST /admin/train

POST /admin/track

POST /admin/maintenance

POST /admin/simulation
```

The APIs can serve:

- Passenger applications
- Railway dashboards
- Station displays
- Control-room interfaces
- Third-party logistics
- Feeder transport systems

---

# 16. Complete End-to-End Example

Suppose a train is currently running from:

```text
Station A → Station B → Station C → Station D
```

The train is currently 7 minutes late.

### Step 1 — Live Data

The system receives:

```text
Current location: between A and B
Current delay: 7 min
Current speed: 72 km/h
Weather: Rain
```

### Step 2 — Layer 1

Historical behaviour indicates:

```text
This train generally recovers
~1.5 minutes on this section.
```

### Step 3 — Layer 3

ML model predicts:

```text
B: +6 min
C: +8 min
D: +5 min
```

### Step 4 — Layer 2

The engine checks downstream traffic.

It discovers another train occupying a relevant section around the predicted arrival window.

The prediction therefore requires adjustment.

### Step 5 — Alternative Simulation

The engine evaluates:

```text
Option A → Hold current train
Option B → Hold downstream train
Option C → Adjust movement timing
```

### Step 6 — Optimization

The system determines that:

```text
Holding current train for 2 minutes
causes the lowest total network delay.
```

### Step 7 — Final ETA

The system produces:

```text
Station B: 14:36
Station C: 15:19
Station D: 16:04

Confidence: 89%
```

### Step 8 — Redis

The latest verified result is written to Redis.

### Step 9 — API

Passenger applications and railway dashboards retrieve the latest ETA through the API.

---

# 17. Core Design Philosophy

The system follows four principles:

### Predict

Use machine learning and historical data to estimate future train movement.

### Verify

Use operational constraints to ensure predictions are physically and operationally plausible.

### Simulate

Evaluate alternative scenarios when the predicted movement creates conflicts or disruptions.

### Recommend

Provide the best available operational recommendation while leaving actual railway control to authorized railway systems/personnel.

---

# 18. Proposed Technology Stack

A possible implementation:

```text
Backend:
Python / FastAPI

ML:
Scikit-learn / XGBoost / LightGBM
or
PyTorch for advanced models

Database:
PostgreSQL + PostGIS

Real-Time Cache:
Redis

Streaming:
Kafka / Redis Streams

Graph / Network:
NetworkX initially
Graph database or optimized graph structures if required

API:
REST APIs
WebSocket/SSE for live updates

Frontend:
React / Next.js

Monitoring:
Prometheus + Grafana

Containerization:
Docker

Deployment:
Kubernetes / Cloud infrastructure
```

The exact stack can be changed according to deployment requirements.

---

# 19. Important Safety Boundary

This system should initially be treated as a:

> **Decision-support and ETA forecasting system**

rather than a system that directly controls:

- Signals
- Points
- Train braking
- Automatic routing
- Railway interlocking
- Safety-critical infrastructure

The prediction engine can recommend actions and identify conflicts, but actual safety-critical railway control should remain within certified railway signalling and operational systems.

---

# 20. Final System Flow

```text
                 ┌─────────────────────┐
                 │ Historical Data     │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │ Main Database       │
                 └──────────┬──────────┘
                            ↓
                ┌──────────────────────┐
                │ Railway Network      │
                │ Graph + Constraints  │
                └──────────┬───────────┘
                           ↓
                ┌──────────────────────┐
                │ Layer 1              │
                │ Behaviour Weights    │
                └──────────┬───────────┘
                           ↓
Live Data ───────→ ┌──────────────────────┐
                   │ Layer 3              │
                   │ ETA Prediction       │
                   └──────────┬───────────┘
                              ↓
                   ┌──────────────────────┐
                   │ Layer 2              │
                   │ Verification         │
                   └──────────┬───────────┘
                              ↓
                    ┌─────────────────────┐
                    │ Feasible?           │
                    └───────┬───────┬─────┘
                            │       │
                           YES      NO
                            │       │
                            ↓       ↓
                         Final    Alternative
                          ETA     Simulation
                            │       │
                            │       ↓
                            │   Optimization
                            │       │
                            └───┬───┘
                                ↓
                         Verified Output
                                ↓
                            Redis
                                ↓
                              APIs
                                ↓
             ┌──────────────────┼─────────────────┐
             ↓                  ↓                 ↓
          Passenger          Railway           Admin
             App             Dashboard        Interface
```

The resulting platform is therefore not merely an **ETA prediction model**, but a broader **real-time railway operational intelligence platform** combining prediction, constraint verification, simulation, optimization, and live information delivery.
