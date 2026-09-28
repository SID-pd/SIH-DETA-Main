# Live Journey & Telemetry Tracker 🛰️

## Overview
The **Live Journey & Telemetry Tracker** (Module 3 of **SIH-DETA**) captures real-time train running telemetry across the Indian Railways network. It extracts live GPS coordinates, instantaneous delays ($\Delta t_0$), expected platform allocations, scheduled stops, and micro-topology track points (intermediate signal cabins, junctions, and loop lines).

This module bridges the gap between static timetable schedules and real-world dynamic movement, providing the foundational state vector for the **Dynamic ETA Prediction Engine**.

---

## Key Features
1. **Live GPS & Telemetry Scraper**: Fetches real-time running feeds (`ConfirmTkt` / `NTES`) with exponential backoff and User-Agent rotation.
2. **Intermediate Cabin & Micro-Topology Extraction**: Parses track-level signaling cabins between scheduled stops (e.g. *Juhi Outer Cabin* at Kanpur) with latitudes, longitudes, and distance markers.
3. **Kinematic & Delay Drift Analyzer**:
   - Calculates journey completion percentage.
   - Computes delay drift rate ($\frac{d\Delta t}{dx}$ per 100 km) to classify trends: `ACCUMULATING_DELAY`, `RECOVERING_DELAY`, or `MAINTAINING_PACE`.
4. **Outer Home Signal Bottleneck Detector**: Identifies trains experiencing sudden delay spikes ($\ge 15$ mins) between arrival and departure at station approaches, indicating platform congestion or signal hold-ups.
5. **SQLite Telemetry Engine & Exporters**:
   - Stores snapshots in `data/telemetry.db` with relational links to stops and intermediate cabins.
   - Exports snapshots to `data/exports/live_status.csv` and `data/exports/live_telemetry.json`.

---

## Directory Structure
```
Live-Journey-Tracker/
├── config.py                     # URLs, file paths, rate limits, headers
├── main.py                       # CLI application with formatted tables
├── requirements.txt              # Standard library (zero third-party dependencies)
├── README.md                     # Documentation & user guide
├── trackers/
│   ├── __init__.py
│   ├── base_tracker.py           # Resilient HTTP request handler
│   ├── live_journey_scraper.py   # Web scraper & JSON payload parser
│   └── telemetry_analyzer.py     # Kinematics, drift rates, & bottleneck logic
├── storage/
│   ├── __init__.py
│   ├── telemetry_db.py           # SQLite database layer (3 relational tables)
│   └── telemetry_exporter.py     # CSV and JSON exporter
├── tests/
│   └── test_live_tracker.py      # Unit test suite (parser, analyzer, db, export)
└── data/
    ├── telemetry.db              # SQLite telemetry database
    ├── exports/                  # CSV and JSON outputs
    └── cache/                    # Response cache for testing
```

---

## Data Schema

### 1. `live_snapshots` (Master Snapshot Table)
| Column | Type | Description |
|---|---|---|
| `snapshot_id` | INTEGER PRIMARY KEY | Unique snapshot ID |
| `train_number` | TEXT | 5-digit train number (e.g. `12004`) |
| `train_name` | TEXT | Train commercial name |
| `train_type` | TEXT | Train classification (`SHATABDI`, `RAJDHANI`, etc.) |
| `current_station_code` | TEXT | Last reported station / cabin code |
| `current_station_name` | TEXT | Last reported station name |
| `instantaneous_delay_mins`| INTEGER | Delay in minutes (+ late, - early) |
| `delay_trend` | TEXT | `ACCUMULATING_DELAY`, `RECOVERING_DELAY`, etc. |
| `delay_drift_rate_per_100km` | REAL | Delay change rate per 100 km |
| `journey_progress_pct`| REAL | Journey completion percentage (0-100%) |
| `next_station_code` | TEXT | Upcoming scheduled station code |
| `next_station_name` | TEXT | Upcoming scheduled station name |
| `next_station_distance_km` | REAL | Distance to next stop |
| `expected_platform` | TEXT | Predicted platform number |
| `outer_bottleneck_flag` | INTEGER | 1 if held up at outer signal, else 0 |
| `source_code` / `destination_code` | TEXT | Origin and destination codes |
| `timestamp` | TEXT | ISO-8601 recording timestamp |

### 2. `journey_stop_telemetry` (Station-by-Station Telemetry)
| Column | Type | Description |
|---|---|---|
| `train_number` | TEXT | Train number |
| `station_code` | TEXT | Station code |
| `stop_number` | INTEGER | Sequence order of stop |
| `scheduled_arrival` / `scheduled_departure` | TEXT | Timetable timings (HH:MM) |
| `arrival_delay_mins` / `departure_delay_mins` | INTEGER | Delays at station |
| `expected_platform` | TEXT | Predicted platform number |
| `distance_km` | REAL | Distance from journey origin |
| `latitude` / `longitude` | REAL | Station coordinates |
| `is_current` | INTEGER | 1 if train is currently at or departed here |

### 3. `intermediate_track_points` (Micro-Topology Cabins & Points)
| Column | Type | Description |
|---|---|---|
| `train_number` | TEXT | Train number |
| `parent_station_code` | TEXT | Approaching major station |
| `station_code` | TEXT | Intermediate cabin or flag station code |
| `station_name` | TEXT | Cabin/Point name (e.g., `Juhi Outer Cabin`) |
| `distance_km` | REAL | Distance from origin |
| `latitude` / `longitude` | REAL | GPS location |

---

## CLI Usage

### 1. Live Track a Single Train
Display real-time location, delay, platform, and complete station-by-station progress:
```bash
python3 main.py --track 12004
```
With specific journey date:
```bash
python3 main.py --track 12301 --date yesterday
```

### 2. Fleet Polling & Monitoring
Poll multiple high-priority trains concurrently:
```bash
python3 main.py --monitor 12004,12301,12043,12424 --count 1
```
Run continuous periodic monitoring every 30 seconds:
```bash
python3 main.py --monitor 12004,12301 --interval 30 --count 5
```

### 3. Outer Signal Bottleneck Report
Identify trains stuck at outer home signals waiting for platform clearance:
```bash
python3 main.py --outer-delays --surge 15
```

### 4. Fleet Telemetry Overview & Stats
```bash
python3 main.py --stats
```

### 5. Export Datasets to CSV & JSON
```bash
python3 main.py --export
```
Output files generated in `data/exports/`:
- `live_status.csv`
- `live_telemetry.json`

---

## Running Automated Unit Tests
```bash
python3 tests/test_live_tracker.py
```
Tests cover:
- Delay string parsing (`"07 Min"`, `"05 Min Early"`, `"RT"`).
- HTML JavaScript parsing (`data`, `currentStnCode`, `intermediateStations`).
- Kinematic calculations, delay drift trends, and bottleneck detection.
- SQLite persistence, retrieval, and multi-format dataset exports.
