# Station & Network Topology Module 🚉

## Overview
The **Station-Halt Scraper** is Module 2 of the **SIH-DETA** (Dynamic Estimated Time of Arrival) platform. It provides a production-grade catalog of **8,990 Indian Railway stations and network nodes**, their exact geospatial coordinates (latitude/longitude), official NSG/SG/HG classifications, division and zone hierarchies, platform counts, and the **all-India train halt schedule network (420,345 halt events across 7,132 trains)**.

This forms the node and edge topology required for graph-based routing, congestion modeling, loop line bottleneck analysis, and real-time ETA prediction.

---

## Current Catalog Overview (Production-Grade Sync)
| Metric | Value | Description |
|---|---|---|
| **Total Railway Network Nodes** | **8,990** | All-India network nodes (commercial + operational) |
| **├─ Active Passenger Stations** | **8,860** | Commercial stations with passenger train halts |
| **└─ Freight / Chords / Cabins** | **130** | Interlocking block posts, freight marshalling yards (`GMC`, `COP`), virtual chords (`XX-...`, `YY-...`) |
| **Geocoded Stations** | **8,697 (96.7%)** | Exact Latitude and Longitude coordinates |
| **Railway Junctions (3+ lines)** | **395** | Multi-corridor convergence points (e.g. `CNB`, `HWH`, `BPL`) |
| **Major Terminals & Central Hubs**| **93** | Origin/terminating hub stations (e.g. `NDLS`, `CSTM`, `MAS`) |
| **Official Halt & Flag Stations** | **423** | Rural, single-platform and passenger-only halts (`HG-2`) |
| **Amrit Bharat Redevelopment** | **92+ Stations** | Key stations flagged for Amrit Bharat modern infrastructure |
| **All-India Train Halt Records** | **420,345** | Complete nationwide timetable halt events |
| **Unique Trains with Halts** | **7,132** | Passenger, Express, Shatabdi, Rajdhani, and Special services |

---

## Directory Layout
```
Station-Halt Scraper/
├── README.md                     # Module documentation and usage
├── config.py                     # URLs, file paths, rate limits, headers
├── requirements.txt              # Dependencies (zero external required)
├── main.py                       # Unified CLI interface
├── data/
│   ├── cache/                    # GeoJSON and raw data cache
│   │   ├── datameet_stations.json   # 8,990 GeoJSON stations
│   │   └── datameet_schedules.json  # 417,080 raw timetable records
│   ├── exports/                  # Master CSV and JSON exports
│   │   ├── stations_master.csv   # 8,990 stations with all production fields (2.0 MB)
│   │   ├── stations_master.json  # 8,990 stations JSON (7.5 MB)
│   │   ├── station_halts.csv     # 420,345 all-India train halt records (41 MB)
│   │   ├── station_halts.json    # Train halt records JSON (160 MB)
│   │   └── network_topology_summary.json
│   └── stations.db               # SQLite database with production indices (38 MB)
├── scrapers/
│   ├── __init__.py
│   ├── base.py                   # Resilient HTTP client (retries, rate limiting)
│   ├── station_dataset_loader.py # GeoJSON station parser & bulk halt loader
│   └── station_live_scraper.py   # ConfirmTkt live station timetable scraper
├── storage/
│   ├── __init__.py
│   ├── db.py                     # SQLite database with stations & halts tables
│   └── exporter.py               # CSV & JSON export pipeline
└── tests/
    └── test_station_scraper.py   # Automated unit and integration test suite
```

---

## Production-Grade Data Schemas

### 1. `stations_master.csv` (8,990 stations)
| Column | Type | Description |
|---|---|---|
| `code` | TEXT (PK) | Official IR station code (`NDLS`, `CNB`, `HWH`, `GKP`) |
| `official_name` | TEXT | Official English station name |
| `hindi_name` | TEXT | Devnagari Hindi station name |
| `alternate_names` | TEXT | Regional / legacy station spellings |
| `state` | TEXT | Indian State / Union Territory |
| `zone` | TEXT | Railway Zone (`NR`, `WR`, `NCR`, `ER`, `SR`, etc.) |
| `division` | TEXT | Operational Division (`Delhi`, `Prayagraj`, `Howrah`, etc.) |
| `district` | TEXT | District location |
| `city` | TEXT | City / Town location |
| `latitude` | FLOAT | Decimal latitude coordinate |
| `longitude` | FLOAT | Decimal longitude coordinate |
| `elevation_meters` | FLOAT | Altitude above sea level (gradient modeling) |
| `ir_category` | TEXT | Official Indian Railways category (`NSG-1` to `NSG-6`, `HG-2`, `Operational / Chord`) |
| `is_junction` | INT | 1 if 3+ rail routes converge, 0 otherwise |
| `is_terminal` | INT | 1 if major origin/termination hub, 0 otherwise |
| `is_halt` | INT | 1 if passenger halt / flag station, 0 otherwise |
| `is_virtual_chord` | INT | 1 if block section / cabin / chord post, 0 otherwise |
| `platform_count` | INT | Number of operational passenger platforms (1 to 23) |
| `track_count` | INT | Operational through lines and loop tracks |
| `gauge` | TEXT | Track gauge (`Broad (1676mm)`, `Meter (1000mm)`, `Narrow`) |
| `electrification_status` | TEXT | `25kV AC Electrified` or `Non-Electrified` |
| `operational_status` | TEXT | `Active Passenger Station` or `Interlocking / Block Post / Virtual Chord` |
| `passenger_service` | INT | 1 for commercial passenger stations, 0 for goods/cabins |
| `amrit_bharat_station` | INT | 1 if included in Amrit Bharat Station Scheme, 0 otherwise |
| `total_halts_count` | INT | Number of scheduled train halts recorded at this station |
| `address` | TEXT | Postal / district address text |
| `data_source` | TEXT | Provenance identifier (`CRIS / Datameet / ConfirmTkt`) |
| `last_verified` | DATE | Data verification timestamp |
| `updated_at` | TIMESTAMP | Last database sync timestamp |

### 2. `station_halts.csv` (420,345 Train Halts)
| Column | Type | Description |
|---|---|---|
| `station_code` | TEXT (FK) | Station code where train halts |
| `train_number` | TEXT | 5-digit Indian Railways train number |
| `train_name` | TEXT | Train name (e.g. `Howrah Rajdhani`, `Shatabdi Exp`) |
| `arrival_time` | TEXT | Scheduled arrival time (`HH:MM:SS` or `Source`) |
| `departure_time` | TEXT | Scheduled departure time (`HH:MM:SS` or `Destinat`) |
| `halt_minutes` | INT | Duration of scheduled halt at this station |
| `day` | INT | Day number of train run (Day 1, 2, 3...) |
| `days_of_run` | TEXT | Days active (`M T W T F S S`) |
| `classes` | TEXT | Available coach classes (`1A 2A 3A SL CC`) |
| `platform` | TEXT | Assigned platform number |
| `distance_km` | FLOAT | Distance in km from source station |
| `source` | TEXT | Source identifier (`confirmtkt_live` or `datameet_master`) |

---

## Command-Line Usage (CLI)

```bash
cd "Station-Halt Scraper"

# 1. Sync All 8,990 Stations
python3 main.py --mode sync-master

# 2. Sync Complete All-India Train Halt Network (~420,000 halts)
python3 main.py --mode sync-halts

# 3. Live Scrape Real-Time Timetable for Any Station
python3 main.py --mode scrape-station --code NDLS
python3 main.py --mode scrape-station --code CNB
python3 main.py --mode scrape-station --code HWH

# 4. Search Stations (by Code, Name, Division, City, State)
python3 main.py --mode search --query "Kanpur"
python3 main.py --mode search --query "Prayagraj"

# 5. Query Halts at a Station
python3 main.py --mode halts --code CNB --limit 20

# 6. Trace All Stops Along a Train Route
python3 main.py --mode train --train 12301

# 7. View Major Junctions with Divisions and Platforms
python3 main.py --mode junctions --limit 25

# 8. View Production-Grade Statistics
python3 main.py --mode stats

# 9. Regenerate CSV & JSON Exports
python3 main.py --mode export
```

---

## Running the Automated Test Suite
```bash
python3 tests/test_station_scraper.py
```
Validates:
- Halt duration math, dot separators, midnight crossovers
- GeoJSON parsing and NSG-1 / HG-2 / Virtual Chord classifications
- SQLite schema, foreign keys, and division search
- ConfirmTkt live timetable scraping
- CSV and JSON export pipelines
