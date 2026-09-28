# Indian Railways All-Trains Web Scraper 🚆

A robust, modular Python web scraper designed to extract the complete list, metadata, routes, and timetables of all trains operating across India (Indian Railways / IRCTC network).

---

## 🌟 Features

- **Comprehensive Discovery**: Automatically traverses Indian Railways train number series (`0xxxx` to `9xxxx`) to discover all active passenger, express, superfast, Rajdhani, Shatabdi, Vande Bharat, and suburban trains.
- **Deep Timetable & Halts Scraper**: Scrapes complete station-by-station itinerary, arrival/departure times, distance (km), halt duration (mins), average delay, journey days, and service days.
- **Master Dataset Bootstrap**: Direct sync support for the open master Indian Railways dataset (thousands of pre-indexed trains with geographic coordinates and zones).
- **Multi-Format Exports**: Exports clean data simultaneously to:
  - 📄 **JSON** (`all_trains.json`, `train_schedules.json`)
  - 📊 **CSV** (`all_trains.csv`, `train_stops_detailed.csv`)
  - 🗄️ **SQLite** (`data/trains.db` with indexed search)
- **Polite & Resilient**: Built-in User-Agent rotation, exponential backoff retries on network/HTTP throttles, and configurable rate-limiting delays.
- **Zero-Dependency Fallback**: Runs with standard Python (`urllib`, `sqlite3`, `json`, `csv`, `re`) or takes advantage of `requests` and `beautifulsoup4` when installed.

---

## 🔢 Indian Railways Train Numbering Convention

Indian Railways uses a **5-digit numbering system**:
| Series | Category | Examples |
|---|---|---|
| **0xxxx** | Special trains (Summer/Holiday/Festival specials) | 04601, 09022 |
| **1xxxx** | Long-distance Mail, Express, Rajdhani, Shatabdi, Jan Shatabdi, Garib Rath | 12043 (Shatabdi), 12301 (Rajdhani) |
| **2xxxx** | Superfast, Vande Bharat, Amrit Bharat, Tejas | 22436 (Vande Bharat), 22120 (Tejas) |
| **5xxxx / 6xxxx / 7xxxx** | Conventional Passenger, MEMU, DEMU, Railbus | 54311, 64491 |
| **8xxxx** | Suvidha trains with dynamic pricing | 82301 |
| **9xxxx** | Suburban / Local EMU trains (Mumbai, Kolkata, Chennai, Delhi) | 91201 |

---

## 📁 Project Structure

```text
SIH-DETA/
├── config.py                     # URLs, User-Agents, timeouts, paths
├── requirements.txt              # Optional dependencies (requests, bs4, tqdm)
├── main.py                       # Unified CLI runner
├── scrapers/
│   ├── __init__.py
│   ├── base.py                   # Resilient HTTP client with rate-limiting
│   ├── confirmtkt_scraper.py     # Live discovery & detailed timetable scraper
│   ├── etrain_scraper.py         # Secondary live autocomplete scraper
│   └── dataset_loader.py         # Master open railway GeoJSON sync
├── storage/
│   ├── __init__.py
│   ├── db.py                     # SQLite database schema & queries
│   └── exporter.py               # JSON and CSV export logic
├── tests/
│   └── test_scraper.py           # Verification & test suite
└── data/
    ├── trains.db                 # SQLite database
    └── exports/                  # Exported CSV and JSON files
```

---

## 🚀 Quick Start

### 1. Installation (Optional)

The scraper works out-of-the-box with standard Python 3. If you want faster parsing with BeautifulSoup and requests, you can install:

```bash
pip install -r requirements.txt
```

### 2. Discover All Trains Across India

Traverses all 2-digit prefixes (`00` to `99`) to scrape all active train numbers and names:

```bash
python3 main.py --mode discover --concurrency 4 --delay 0.3
```

*Quick test run (first 5 prefixes):*
```bash
python3 main.py --mode discover --limit 5
```

Outputs will be saved to:
- `data/trains.db` (SQLite)
- `data/exports/all_trains.json`
- `data/exports/all_trains.csv`

---

### 3. Scrape Detailed Route & Halts for a Train

Scrapes complete timetable, all stop stations, halt times, delays, and service days:

```bash
# Example: 12043 (New Delhi to Moga Shatabdi Express)
python3 main.py --mode schedule --train 12043

# Example: 22436 (Vande Bharat Express)
python3 main.py --mode schedule --train 22436
```

Outputs will include:
- `data/exports/train_schedules.json`
- `data/exports/train_stops_detailed.csv` (all stations, arrival/departure, halt, distance)

---

### 4. Sync Complete Master Railway Dataset

Instantly downloads and imports thousands of trains across India with zone names, routes, duration, and coordinates:

```bash
python3 main.py --mode sync-master
```

---

### 5. Search Trains in Database or Live

Search by train number, train name, or station code:

```bash
python3 main.py --mode search --query "Vande Bharat"
python3 main.py --mode search --query "NDLS"
python3 main.py --mode search --query "12043"
```

---

### 6. View Database Statistics

```bash
python3 main.py --mode stats
```

---

## 🗄️ Database Schema

### `trains` Table
- `number`: Train number (e.g. `12043`, `22436`) [Primary Key]
- `name`: Official train name
- `type`: Train type (`SHATABDI`, `VANDE BHARAT`, `SUPERFAST`, `EXPRESS`, `PASSENGER`)
- `zone`: Railway Zone (`NR`, `WR`, `CR`, `SR`, `ECoR`, etc.)
- `route`: Summary route (`New Delhi → Moga`)
- `from_station_code` / `from_station_name`: Origin station
- `to_station_code` / `to_station_name`: Destination station
- `departure` / `arrival`: Origin departure & destination arrival times
- `travel_time`: Duration of journey
- `distance`: Distance in km
- `service_days`: Operational days of the week (`Mon, Wed, Fri`)
- `total_stops`: Number of halts
- `classes`: Coach classes (`1A, 2A, 3A, CC, EC, SL`)
- `pantry`: Pantry car availability (`Yes` / `No`)

### `train_stops` Table
- `train_number`: Foreign key to `trains.number`
- `sno`: Stop sequence number (1, 2, 3...)
- `station_code`: Station code (e.g. `NDLS`, `ROK`)
- `station_name`: Station name (e.g. `New Delhi`, `Rohtak Jn`)
- `arrival`: Arrival time at halt
- `departure`: Departure time from halt
- `halt`: Halt duration (e.g. `2m`)
- `distance`: Cumulative distance from origin (km)
- `avg_delay`: Average running delay (mins)
- `day`: Journey day (1, 2, 3)

---

## 🛡️ Best Practices & Rate Limiting

- Always keep `--delay` at **0.3s or higher** when scraping to be respectful of public railway servers.
- For bulk scheduling, use the `--limit` flag to batch your runs or run during off-peak hours.
