# Historical Delay Records & Punctuality Engine 📈

## Overview
The **Historical Delay Records & Punctuality Engine** (Module 4 of **SIH-DETA**) mines multi-day operational running histories across the Indian Railways network. It establishes section-by-section delay drift distributions, isolates timetable engineering slack (delay absorption), and constructs Markovian state transition matrices to replace naive $\text{ETA} = \text{STA} + \text{Delay}$ estimates with statistically grounded predictions.

---

## Why Historical Modeling is Essential for Dynamic ETA
1. **Engineering Slack & Delay Absorption**: Timetables intentionally incorporate slack buffer time before major junctions (e.g. Unnao to Lucknow). A train running 25 minutes late often absorbs 15 minutes of delay in these recovery sections.
2. **Bottleneck Compounding**: On overloaded saturated corridors (e.g. Ghaziabad–Tundla–Kanpur), delays cascade non-linearly due to preceding train block clearances and platform occupation.
3. **Punctuality State Transitions**: Models the Markovian transition probability $P(S_{t+1} \mid S_t)$ where:
   - `ON_TIME`: $\le 5$ mins (includes early arrivals)
   - `MINOR_DELAY`: 6–15 mins
   - `MODERATE_DELAY`: 16–45 mins
   - `SEVERE_DELAY`: $> 45$ mins

---

## Mathematical Formulations

### 1. Sectional Delay Delta ($\Delta \text{delay}$)
For a train traversing track section from station $u$ to station $v$:
$$\Delta \text{delay}_{u \to v} = \text{delay}_{\text{arr}}(v) - \text{delay}_{\text{dep}}(u)$$

* **Absorbed Delay** ($\Delta \text{delay} \le -2$ min): Train utilized speed margin or slack to make up time.
* **Accumulated Delay** ($\Delta \text{delay} \ge 3$ min): Train lost time due to signaling or track bottlenecks.
* **Maintained Pace** ($-2 < \Delta \text{delay} < 3$ min): Train held scheduled run time.

### 2. Corridor Distribution Parameters
For each section over the historical window ($N = 15$ days):
$$\mu_{\Delta t} = \frac{1}{N} \sum_{i=1}^N \Delta \text{delay}_i, \quad \sigma_{\Delta t} = \sqrt{\frac{1}{N}\sum_{i=1}^N (\Delta \text{delay}_i - \mu_{\Delta t})^2}$$

* **Corridor Classification**:
  - `SLACK_BUFFER`: $\mu_{\Delta t} < -2.0$ min
  - `BOTTLENECK`: $\mu_{\Delta t} > 3.0$ min
  - `NEUTRAL`: $-2.0 \le \mu_{\Delta t} \le 3.0$ min

---

## Directory Structure
```
Historical-Delay-Records/
├── config.py                     # URLs, rate limits, 15-day window, directories
├── main.py                       # Unified CLI with ASCII summary tables
├── requirements.txt              # Standard library only (zero external dependencies)
├── README.md                     # Documentation & formulations
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py           # Resilient HTTP requester with caching
│   └── historical_delay_scraper.py # Parses embedded JS date objects and delay arrays
├── analytics/
│   ├── __init__.py
│   ├── delay_matrix_engine.py    # Sectional delta math & Markov transition matrices
│   └── sectional_profiler.py     # Aggregated distributions (mean, std dev, absorption %)
├── storage/
│   ├── __init__.py
│   ├── historical_db.py          # SQLite engine (3 normalized tables)
│   └── historical_exporter.py    # CSV & JSON exporter
└── tests/
    └── test_historical_tracker.py # Automated unit test suite
```

---

## Data Schemas

### 1. `daily_station_delays`
| Column | Type | Description |
|---|---|---|
| `train_number` | TEXT | 5-digit train number |
| `journey_date` | TEXT | Date of journey (YYYY-MM-DD) |
| `station_code` | TEXT | Station code |
| `stop_order` | INTEGER | Order of station along route |
| `delay_minutes` | INTEGER | Signed minute delay (- early, + late) |
| `punctuality_bucket` | TEXT | `RIGHT_TIME`, `SLIGHT_DELAY`, `SIGNIFICANT_DELAY`, `SEVERE_DELAY` |
| `day_of_week` | INTEGER | 0=Monday, ..., 6=Sunday |
| `is_weekend` | INTEGER | 1 for Saturday/Sunday, else 0 |

### 2. `sectional_delay_records`
| Column | Type | Description |
|---|---|---|
| `train_number` | TEXT | Train number |
| `journey_date` | TEXT | Date of journey |
| `from_station` | TEXT | Departure station $u$ |
| `to_station` | TEXT | Arrival station $v$ |
| `section_order` | INTEGER | Sequence order of track section |
| `departure_delay` | INTEGER | Departure delay at $u$ |
| `arrival_delay` | INTEGER | Arrival delay at $v$ |
| `delay_delta` | INTEGER | $\Delta = \text{arrival\_delay} - \text{departure\_delay}$ |
| `status` | TEXT | `ABSORBED_DELAY`, `ACCUMULATED_DELAY`, `MAINTAINED_SCHEDULE` |
| `from_state` / `to_state` | TEXT | Markov delay states |
| `day_of_week` | INTEGER | Day of week |

### 3. `sectional_profiles` (Pre-Aggregated Feature Store)
| Column | Type | Description |
|---|---|---|
| `train_number` | TEXT | Train number |
| `from_station` / `to_station`| TEXT | Corridor endpoints |
| `sample_size_days` | INTEGER | Historical observations count (e.g. 15) |
| `mean_delay_delta` | REAL | Average delay drift in minutes ($\mu$) |
| `std_delay_delta` | REAL | Delay volatility / standard deviation ($\sigma$) |
| `median_delay_delta` | INTEGER | Median delay change |
| `min_delay_delta` / `max_delay_delta` | INTEGER | Extreme recovery and delay surge |
| `absorption_rate_pct` | REAL | % of runs where delay was reduced |
| `punctuality_rate_pct`| REAL | % of runs arriving with $\le 15$m delay |
| `corridor_type` | TEXT | `SLACK_BUFFER`, `BOTTLENECK`, `NEUTRAL` |

---

## CLI Usage & Autonomous Overnight Crawling

### 1. Check Server Hardware & Optimal Calibration
```bash
python3 main.py --mode system-check
```
Inspects CPU cores, available memory, disk headroom on `/scratch`, and displays auto-calibrated stability parameters.

### 2. Autonomous Overnight Batch Scraping (Zero-Hang Guaranteed)
Run full unattended crawling across all 5,208+ master trains. The crawler scrapes the 90-day horizon (`?d=3m`) first, partitions runs into 15-day bi-weekly sub-windows, and automatically transitions to the 1-year horizon (`?d=1y`):
```bash
# Recommended command for overnight run (detached daemon with log tracking):
nohup python3 main.py --mode batch --phase auto > crawler.log 2>&1 &
```
Or run directly in terminal:
```bash
python3 main.py --mode batch --phase auto
```

### 3. Check Live Checkpoint & Crawling Progress
```bash
python3 main.py --mode status
```
Displays total completed, skipped, and pending trains with percentage completion for both 90-day and 1-year phases.

### 4. Single Train Detailed Inspection (90-Day or 1-Year)
```bash
# 90-day horizon with 15-day sub-windows:
python3 main.py --mode train --train 12004 --horizon 3m

# 1-year horizon:
python3 main.py --mode train --train 12004 --horizon 1y
```
Displays:
- Station-by-station table comparing **STA (Ideal)** vs **ATA (Real)** arrival, and **STD (Ideal)** vs **ATD (Real)** departure timestamps.
- Station halt duration variance ($\Delta H$).
- Sectional delay drift, absorption rates, and corridor classification.

### 5. Reset Checkpoint (If Restarting Fresh)
```bash
python3 main.py --mode reset-checkpoint
```

---

## Automated Unit Testing
```bash
python3 tests/test_historical_tracker.py
```
Validates:
- Punctuality state categorization (`ON_TIME`, `MINOR`, `MODERATE`, `SEVERE`).
- Multi-horizon HTML/JS date array parsing and 15-day sub-window partitioning.
- TimetableMatcher ideal vs real arrival/departure timestamps and midnight rollover.
- CheckpointManager atomic state persistence and resume logic.
- CrawlerWatchdog thread timeout enforcement (deadlock prevention).
- System hardware capability diagnostic evaluator.

