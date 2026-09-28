# Dynamic Station-Level Train ETA & Delay Predictor

This package delivers an end-to-end Machine Learning and Data Scraping pipeline for **SIH Problem Statement 26028** (*Dynamic Forecast of Expected Time of Arrival for Coaching Trains*).

Unlike static delay persistence ($M_0: \text{ETA} = \text{Sched} + \text{Delay}$) or binary end-of-journey classifiers ($M_1$), this predictor operates at the **individual station-to-station segment level** ($M_2$). It continuously predicts:
1. **`delay_at_next_station_minutes`**: Whether the train will recover time, maintain headway, or lose minutes before clearing the next station.
2. **`travel_time_to_next_station_minutes`**: The actual physical transit duration on the upcoming section.
3. **90% Quantile Confidence Bounds ($p10$ to $p90$)**: Explaining arrival uncertainty (e.g., `20:45 ± 4 mins`).

---

## 1. The 31 Features (X) & Prediction Labels (Y)

The model is trained on a 31-dimensional feature vector combining static topology, kinematics, operational track bottlenecks, and real-time environmental context:

```
Features (X):
├── Train Attributes
│   ├── train_id                    (5-digit train number)
│   ├── train_type                  (Vande Bharat, Rajdhani, Shatabdi, Superfast, Mail/Express)
│   └── train_route                 (Corridor key, e.g. HWH-NDLS)
├── Topological & Spatial
│   ├── current_station             (Code of last station cleared)
│   ├── next_station                (Code of upcoming station)
│   └── distance_to_next_station    (Segment length in km)
├── Telemetry & Kinematics
│   ├── current_latitude            (GPS latitude)
│   ├── current_longitude           (GPS longitude)
│   ├── current_speed               (GPS / calculated speed in km/h)
│   └── average_speed               (Scheduled or rolling average speed in km/h)
├── Timings & Delays
│   ├── scheduled_arrival_time      (Next station arrival in minutes from midnight)
│   ├── scheduled_departure_time    (Current station departure in minutes from midnight)
│   ├── actual_arrival_time         (Actual arrival in minutes from midnight)
│   ├── actual_departure_time       (Actual departure in minutes from midnight)
│   ├── current_delay               (Delay at current station in minutes)
│   └── previous_station_delay      (Delay at previous station t-1)
├── Historical Priors (eTrain)
│   ├── historical_average_delay    (1-year trailing average delay for train at next station)
│   └── historical_section_travel_time (Median scheduled/empirical section travel time)
├── Halt Dynamics
│   ├── number_of_previous_halts   (Stops cleared so far)
│   ├── current_halt_duration       (Actual dwell time in minutes)
│   ├── scheduled_halt_duration     (Scheduled dwell time in minutes)
│   └── unscheduled_halt_flag       (1 if stopped at unscheduled loop/signal, else 0)
├── Operational & Route Realities
│   ├── signal_operational_delay    (Delay change between halts: current - previous)
│   ├── route_congestion_level      (Track capacity utilization index: 0.0 to 1.0)
│   └── weather                     (Adverse weather / fog index: 0.0 to 1.0)
├── Calendar & Commute Dynamics
│   ├── day_of_week                 (0 = Monday, 6 = Sunday)
│   ├── month_season                (Winter, Monsoon, Summer, Autumn)
│   ├── peak_off_peak_indicator     (1 during 06-10 or 17-21, else 0)
│   └── time_since_journey_start    (Elapsed journey minutes)
└── Journey Progress
    ├── remaining_distance          (Distance to final destination in km)
    └── number_of_remaining_stations (Scheduled halts remaining)

Labels (Y):
├── PRIMARY:   delay_at_next_station_minutes        (Continuous regression)
└── SECONDARY: travel_time_to_next_station_minutes (Continuous regression)
```

---

## 2. The "Past 3 Years" Scraping Strategy

Consumer train-tracking websites (`RailYatri`, `RunningStatus.in`, `TrainRunningStatus.live`, `NTES`) **only maintain active running data for the last 2 to 3 days** (today/yesterday). Querying dates from 2023 or 2024 returns 404/403 or empty results.

To legitimately train across multi-year distributions, our framework combines 4 sources:
1. **Trailing Multi-Year Delay Priors**: `predictor.scrapers.etrain_scraper.EtrainScraper` indexes 365-day station delay distributions from `etrain.info`.
2. **Multi-Year Empirical Journey Delays**: Incorporates the 6-year Kaggle Indian Railways dataset (`Datasets/ir_train.csv`, 2018–2024).
3. **Continuous Snapshot Harvester**: `predictor.scrapers.live_snapshot_daemon.LiveSnapshotDaemon` periodically polls live trains every 10–15 minutes and logs empirical station crossings into local SQLite/Parquet.
4. **Historical Weather Backfill**: `predictor.scrapers.weather_client.WeatherClient` queries Open-Meteo's Archive API for exact historical hourly temperature, precipitation, and visibility/fog by station coordinates over the past 3+ years.

---

## 3. Scrapers Included

| Scraper Module | Target / Endpoint | Capabilities |
| :--- | :--- | :--- |
| `confirmtkt_scraper.py` | `confirmtkt.com/train-running-status/{train}` | Extracts live timetable, passing stations, delays, and current position. |
| `runningstatus_scraper.py` | `runningstatus.in/status/{train}-on-{date}` | Full browser headers and HTML table parser for train running logs. |
| `railyatri_scraper.py` | `railyatri.in/live-train-status/{train}` | Crowdsourced mobile GPS position, speed, and intermediate ETAs. |
| `railradar_client.py` | `api.railradar.in/v1/trains/{number}/live` | Official REST client for real-time speed, bearing, and segment progress. |
| `etrain_scraper.py` | `etrain.info/train/{name}-{number}/history` | Multi-year punctuality distributions and historical station delays. |
| `weather_client.py` | `archive-api.open-meteo.com` / `api.open-meteo.com` | Multi-year historical & live weather (fog index, rainfall, temp). |
| `live_snapshot_daemon.py` | Continuous daemon | Logs live snapshots into `predictor/data/live_snapshots.sqlite`. |

---

## 4. CLI Usage

Run commands from the repository root:

```powershell
# 1. Build the 31-Feature Dataset (from darpan.sqlite & historical distributions)
python -m predictor.run_pipeline build-data --num-trains 120 --runs-per-train 10

# 2. Train the Quantile Regressors (p10, p50, p90)
python -m predictor.run_pipeline train

# 3. Predict Dynamic ETA for an upcoming segment
python -m predictor.run_pipeline predict `
    --train 12301 `
    --current-station CNB `
    --next-station PRYJ `
    --current-delay 25 `
    --sched-dep 00:55 `
    --sched-arr 02:35 `
    --distance 194

# 4. Scrape Live Status & Auto-Predict Next Station ETA
python -m predictor.run_pipeline scrape-live --train 12301 --predict-next

# 5. Run Entire End-to-End Pipeline
python -m predictor.run_pipeline all
```

---

## 5. Python API Usage

```python
from predictor.models.inference import StationETAPredictor

predictor = StationETAPredictor()

# Predict next station arrival
result = predictor.predict_next_station_eta(
    train_id="12301",
    train_name="Howrah - New Delhi Rajdhani Express",
    current_station="CNB",
    next_station="PRYJ",
    current_delay_minutes=25.0,
    scheduled_dep_curr="00:55",
    scheduled_arr_next="02:35",
    distance_to_next_km=194.0,
    month=12,  # Winter Fog Season
)

print("Predicted ETA:", result["predicted_eta"])
print("Expected Delay:", result["predicted_delay_at_next_station_minutes"], "minutes")
print("90% Confidence Interval:", result["eta_confidence_interval_90pct"])
print("Active Risk Factors:", result["risk_factors"])
```
