# Dynamic ETA Prediction Engine 🧠

## Purpose
The machine learning and algorithmic inference core of **SIH-DETA**. Merges static timetables, live telemetry, sectional topology, weather constraints, and historical delay distributions to output accurate, dynamic arrival times.

## Mathematical Formulation

$$\text{Dynamic ETA}(T, S_{\text{target}}) = t_{\text{now}} + \sum_{k=i}^{\text{target}-1} \Delta T(S_k, S_{k+1}) + \sum_{k=i+1}^{\text{target}-1} H(S_k)$$

Where:
- $t_{\text{now}}$: Current timestamp.
- $\Delta T(S_k, S_{k+1})$: Predicted travel time through block section $(k \to k+1)$, conditioned on:
  - Nominal running time $T_{\text{sched}}$
  - Section speed limit (MPS vs Fog/TSR restrictions)
  - Preceding train headway and sectional capacity utilization
  - Historical delay absorption factor $\alpha_{k}$
- $H(S_k)$: Predicted halt duration at intermediate station $k$ ($H_{\text{sched}} + \text{Delay}_{\text{dispatch}}$).

---

## Machine Learning Pipeline

```text
┌───────────────────────────┐    ┌───────────────────────────┐
│     Static Timetable      │    │    Live Telemetry Feed    │
│ (Distance, STA, Priority) │    │ (Current Delay, Speed)    │
└─────────────┬─────────────┘    └─────────────┬─────────────┘
              │                                │
              ▼                                ▼
       ┌──────────────────────────────────────────────┐
       │           Unified Feature Pipeline           │
       │  • Residual Slack Remaining                  │
       │  • Fog Speed Cap Flag (FOG-PASS)             │
       │  • Right-of-Way Priority Tier (1 to 6)       │
       │  • Terminal Congestion / Yard Factor         │
       └──────────────────────┬───────────────────────┘
                              │
                              ▼
       ┌──────────────────────────────────────────────┐
       │         Prediction Model Architecture        │
       │  Primary: LightGBM / XGBoost Regressor       │
       │  Advanced: Spatial-Temporal GNN (ST-GNN)     │
       └──────────────────────┬───────────────────────┘
                              │
                              ▼
       ┌──────────────────────────────────────────────┐
       │             Dynamic ETA Output               │
       │  • Point Estimate: Predicted Arrival (HH:MM) │
       │  • Confidence Intervals: P10, P50, P90       │
       │  • Delay Trend: Absorbing / Compounding      │
       └──────────────────────────────────────────────┘
```

## Recommended Tech Stack
- **Feature Store & Preprocessing:** Python, Pandas, Polars, NumPy.
- **Model Training:** LightGBM, XGBoost, CatBoost, PyTorch Geometric (for GNNs).
- **Inference API:** FastAPI / Flask exposing endpoints like:
  - `GET /api/v1/eta?train=12301&station=NDLS`
