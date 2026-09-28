To achieve the **highest predictive accuracy** for Indian Railways ETA and delay models while avoiding misleading historical artifacts, here is the analytical breakdown of **how many years of data you should collect**, the **trade-offs involved**, and the **critical features required**.

---

### 1. The Sweet Spot: How Many Years of Data?

> **Recommendation: 1 to 2 Years (Rolling 12 to 24 Months)**  
> **Ideal Target: 1.5 to 2 full annual cycles (spanning at least two winter fog seasons and two monsoon seasons).**

#### Why NOT 5–10 years? (The Concept Drift Trap)

In machine learning, more data is only better if the underlying distribution remains stationary. Indian Railways has undergone massive infrastructural and structural shifts over the last 3–5 years:

1. **The Post-COVID "Zero-Based Timetable" (2021–2022):** Indian Railways scrapped the pre-2020 timetable and re-engineered almost every train schedule, adding systematic operational slack and renumbering trains. Training on pre-2022 schedules teaches the model bottlenecks and scheduled runtimes that no longer exist.
2. **Dedicated Freight Corridors (DFC) (2022–2024):** The commissioning of the Western DFC (Rewari–Palanpur) and Eastern DFC (Ludhiana–Sonnagar) diverted tens of thousands of freight trains off passenger trunk lines. Sections like Delhi–Kanpur–Mughalsarai that previously suffered 4-hour systemic congestion now clear traffic significantly faster. Pre-2022 data reflects phantom freight bottlenecks.
3. **Electrification & LHB Conversion:** 95%+ of broad-gauge routes are now electrified, and ICF (blue) rakes have been aggressively replaced with LHB (red/silver) coaches. LHB trains have higher Maximum Permissible Speeds (MPS 130 km/h vs 110 km/h) and disc brakes, altering deceleration/acceleration physics.
4. **Conclusion on Pre-2022 Data:** Pre-2022 data acts as **noise/poison** for ETA prediction.

#### Why at least 1 full year (minimum)?

A model trained on only 3–6 months will fail drastically when seasons change due to Indian Railways' extreme calendar-driven shocks:

- **Winter Fog (Dec 15 – Feb 15):** Dense fog across Northern/North-Central Railway (NR, NCR, NER, ECR) enforces automatic block signal speed restrictions (dropping speeds from 130 km/h to 30–60 km/h). Trains easily accumulate 6–12 hour delays.
- **Monsoon Disruptions (July – Sept):** Flooding, caution orders, and landslides in Konkan Railway (KR), Western Ghats, Mumbai suburban, and Northeast Frontier (NFR).
- **Festival Peak Surges (Oct – Nov: Diwali/Chhath, Mar: Holi):** Massive passenger surge leading to longer boarding halts (dwell times swell from 2 min to 10+ min at intermediate junctions) and hundreds of special duplicate trains competing for track slots.

---

### 2. The Multi-Tier Data Architecture

To balance bulk training and real-time responsiveness, industry-grade railway ETA systems use a **3-Tier Data Strategy**:

| Tier                                | Window                     | Source                                                         | Purpose                                                                                                                                                                                                        |
| :---------------------------------- | :------------------------- | :------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Tier 1: Baseline Priors**         | **Past 1 Year (365 Days)** | `erail.in` (`/delays` endpoint)                                | Computes stable prior probability distributions: $P(\text{delay} > 15 \mid \text{station})$, $p10, p50, p90$ historical delay added per segment. (Erail natively aggregates the last 365 days!).               |
| **Tier 2: Machine Learning Matrix** | **Rolling 90 to 180 Days** | Point-by-point station passages (`ir_point_delays_master.csv`) | Trains the non-linear gradient boosted tree (LightGBM/CatBoost) for **M1 Risk Classifier** and **M2 Quantile Regressor**. Captures current track conditions, recent maintenance blocks, and seasonal patterns. |
| **Tier 3: Live Telemetry**          | **Last 2 to 6 Hours**      | CRIS NTES (`/live` poller)                                     | Real-time state for inference: current delay, delay delta over the last 3 stops, origin departure punctuality, and route exceptions (rescheduled/diverted).                                                    |

---

### 3. Complete Feature Checklist: What You Need for SOTA Accuracy

To achieve state-of-the-art accuracy, your dataset must merge features across five distinct categories:

#### A. Temporal & Calendar Dynamics (Seasonality)

- `month` & `day_of_week` (Cyclical sin/cos encodings).
- `departure_hour_slot` (Morning peak 06:00–10:00 vs afternoon lull vs night 22:00–04:00).
- `is_winter_fog_season` (Binary: Dec 1 to Feb 15 in Northern/Eastern zones).
- `is_monsoon_season` (Binary: June 15 to Sept 30 in coastal/flood-prone divisions).
- `is_festival_window` (Diwali, Chhath Puja, Holi, Durga Puja, Kumbh Mela).
- `is_weekend` (Friday evening to Sunday night travel surges).

#### B. Rolling Stock & Train Operational Characteristics

- `has_lhb_coaches` (1 = LHB, 0 = ICF). Directly affects speed limit (130 vs 110 km/h) and acceleration/braking profile.
- `train_type_priority` (Categorical rank):
  1. _Priority 1_: Vande Bharat, Rajdhani, Shatabdi, Tejas, Duronto (Given absolute operational precedence by section controllers).
  2. _Priority 2_: Superfast Express, Mail/Express.
  3. _Priority 3_: Garib Rath, Jan Shatabdi, Antyodaya.
  4. _Priority 4_: Special Trains (0xxxx prefix — lowest precedence among express trains; heavily held at outer signals for regular express trains to pass).
  5. _Priority 5_: Passenger / MEMU / DEMU.
- `is_special_train` (Binary: detects seasonal overflow 0xxxx trains).
- `total_distance_km` & `journey_duration_scheduled_min`.
- `total_stops_count` (More stops = exponentially higher risk of dwell-time delay accumulation).

#### C. Topological & Track Infrastructure Features

- `zone_code` (e.g., NCR, NR, WCR, SR) — Northern and North-Central zones historically have ~3× the delay density of Southern or Western Railway.
- `division_code` (e.g., Prayagraj/PRYJ, Delhi/DLI, Mumbai/BCT).
- `is_junction` & `station_degree` (Number of converging track lines; major bottlenecks like Itarsi, Mughalsarai/DDU, Kanpur Central, Vijayawada).
- `scheduled_halt_min` (Stations with 2-min halts suffer high overrun percentages; stations with 20-min engine-reversal halts offer recovery cushion).
- `scheduled_speed_kmh` ($\text{Segment Distance} / \text{Scheduled Runtime}$). Trains scheduled near maximum permissible speed have zero recovery margin if delayed.
- `buffer_recovery_time_min` (Scheduled slack before the final destination or major crew-change points).

#### D. Live Dynamic Features (During Real-time Inference)

- `current_delay_min` (Delay at the most recently cleared station).
- `origin_delay_min` (Delay when departing source station — single highest feature importance in M1).
- `delay_delta_last_3_stops` ($\text{Delay}_{\text{current}} - \text{Delay}_{t-3}$): Is the train recovering time (negative delta) or losing time (positive delta)?
- `distance_covered_ratio` ($\text{Distance Completed} / \text{Total Distance}$).
- `rescheduled_time_min` (From NTES: official delayed start time announced by the control room).

#### E. External Environmental Context (Bonus Boosters)

- `visibility_meters` or `fog_index` (from Open-Meteo or IMD weather APIs for intermediate stations).
- `heavy_rain_flag` (> 20mm/hr precipitation along the route).

---

### 4. How Our Current Setup Aligns with This

Our newly built scraper and pipeline in `experiment/scraper-erail` is already positioned for this exact strategy:

1. **`pipeline/dataset_builder.py`:**
   - Already reconstructs the **44-feature master schema** matching `train_eta_model.py`.
   - Populates `has_lhb_coaches`, `is_special_train`, `train_type`, `route_historical_ontime_pct`, and station stop aggregations.
2. **`erail_scraper.py` (Station Delays):**
   - Automatically pulls **365-day trailing punctuality and delay distributions** for every station on every train's route.
3. **`darpan.sqlite` (`segments` table):**
   - Stores `hist_delay_added_p10`, `p50`, and `p90` per track segment, feeding directly into deterministic delay propagation (`services/api/app/domain/eta_engine.py`).

### 5. Recommended Next Action

To get your training dataset ready with optimal data quality:

1. **Catalog & Timetable Extraction:** Extract the active 14,000+ trains and 13,000+ stations from erail (reflecting the official 2024–2026 timetable).
2. **Trailing 1-Year Delays:** Run the delay scraper (`python cli.py delays --concurrency 5`) to pull the 365-day station punctuality distributions.
3. **Compile Model Datasets:** Run `python cli.py build-dataset` to generate:
   - `output/ir_train_real.csv` (for M1 Risk Classifier training).
   - `output/ir_point_delays_master.csv` (for M2 Segment Quantile Regressor).

Would you like to start extracting the catalog now, or would you like to add specific environmental or weather features into the pipeline first?
