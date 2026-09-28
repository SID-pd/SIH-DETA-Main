# 📦 Unpushed Large Assets & Databases Manifest (`SIH-DETA / Main`)

Because GitHub enforces a strict **50 MB warning / 100 MB hard file size limit** and discourages committing multi-hundred-megabyte binary SQLite databases, raw scrape caches, and generated CSV dumps, all files that **cannot be pushed to the GitHub repository** have been consolidated into [`Main/unpushed_assets/`](file:///c:/Users/Asus/Coding/SIH/ETA/Main/unpushed_assets/) (as well as their active runtime paths inside `Main/backend/`) and excluded via `.gitignore`.

---

## 1. Complete Inventory of Unpushed Files in `Main/unpushed_assets/`

| # | File Name in `unpushed_assets/` | Size | Records / Contents | Active Runtime Path in `Main/backend/` | Why It Cannot Be Pushed |
|---|---|---|---|---|---|
| **1** | `historical.db` | **691.22 MB** | `daily_station_delays` (**1,517,927 rows**)<br>`sectional_delay_records` (**1,446,490 rows**)<br>`sectional_profiles` (**73,342 rows**) | `Main/backend/sih_deta/Historical-Delay-Records/data/historical.db` | Exceeds GitHub 100 MB hard limit (6.9x limit). Binary SQLite WAL store. |
| **2** | `weather.db` | **579.96 MB** | `station_daily_weather` (**3,192,900 rows**)<br>`station_weather_observations` (**8,701 rows**) | `Main/backend/sih_deta/Weather-Environment/data/weather.db` | Exceeds GitHub 100 MB hard limit (5.8x limit). Binary SQLite WAL store. |
| **3** | `darpan.sqlite` | **96.40 MB** | `stations` (**8,990 rows**), `trains` (**5,208 rows**), `schedule_stops` (**417,080 rows**), `segments` (**16,509 rows**), `eta_snapshots`, `live_observations` | `Main/backend/data/darpan.sqlite` | Approaches GitHub 100 MB limit (triggers GH001 large file warning/rejection). |
| **4** | `stations.db` | **82.48 MB** | `stations` (**8,990 rows**, 96.7% geocoded)<br>`station_halts` (**420,345 rows** across 7,132 trains) | `Main/backend/sih_deta/Station-Halt Scraper/data/stations.db` | Exceeds GitHub 50 MB limit (82.5 MB binary SQLite database). |
| **5** | `datameet_schedules.json` | **82.17 MB** | Raw nationwide timetable schedule dump (420k+ stop entries) | `Main/backend/sih_deta/Station-Halt Scraper/data/cache/datameet_schedules.json` | Exceeds GitHub 50 MB limit; raw upstream cache file. |
| **6** | `ir_train_real.csv` | **81.36 MB** | 44-column real-world scraped train delay & feature matrix | `Main/backend/scraper/output/ir_train_real.csv` | Exceeds GitHub 50 MB limit (81.4 MB CSV dataset). |
| **7** | `station_delay_dataset_31f.csv` | **57.78 MB** | 31-feature station-to-station ML training matrix | `Main/backend/predictor/data/station_delay_dataset_31f.csv` | Exceeds GitHub 50 MB limit; generated tabular training artifact. |
| **8** | `anomalies.json` | **17.71 MB** | Exported JSON dump of **39,754** 3-sigma network incidents | `Main/backend/sih_deta/Network-Anomalies/data/exports/anomalies.json` | Redundant generated export from `anomalies.db`. |
| **9** | `anomalies.db` | **11.64 MB** | `network_incidents` (**39,754 rows**)<br>`junction_queue_profiles` (**1,200 rows**) | `Main/backend/sih_deta/Network-Anomalies/data/anomalies.db` | Binary SQLite database paired with the SIH-DETA data lake. |
| **10** | `anomalies.csv` | **6.98 MB** | CSV export of **39,754** mined network anomalies | `Main/backend/sih_deta/Network-Anomalies/data/exports/anomalies.csv` | Generated CSV export from `anomalies.db`. |
| **11** | `datameet_stations.json` | **3.02 MB** | Raw GeoJSON station coordinates catalog | `Main/backend/sih_deta/Station-Halt Scraper/data/cache/datameet_stations.json` | Raw scrape cache artifact. |
| **12** | `checkpoint.json` | **1.11 MB** | Crawl state checkpoint across 7,063 trains | `Main/backend/sih_deta/Historical-Delay-Records/data/checkpoint.json` | Ephemeral crawler state file. |
| **13** | `Historical-Delay-Records/data/cache/*.html` | **~950 MB (16,500+ files)** | Raw cached eTrain HTML pages from overnight crawl | `Server-ETA/SIH-DETA/Historical-Delay-Records/data/cache/` | 16,500+ raw HTML scrape cache files; already parsed into `historical.db`. |
| **14** | `frontend/node_modules/` | **~240 MB** | NPM package dependencies | `Main/frontend/node_modules/` | Standard Node dependency tree; restored via `npm install`. |

---

## 2. Databases & Model Artifacts Included vs. Ignored

### Tracked in Git (Small, Essential Artifacts $< 2\text{ MB}$):
- `Main/backend/ml/registry/eta_model_subset.joblib` (`923 KB` — $M_1$ Risk Classifier)
- `Main/backend/ml/registry/risk_clf_subset_card.json` (`4 KB` — $M_1$ Model Card)
- `Main/backend/predictor/artifacts/station_eta_model.joblib` (`1.32 MB` — $M_2$ 31-Feature Station Quantile Regressor)
- `Main/backend/sih_deta/Train-Scraper/data/trains.db` (`1.39 MB` — 5,209 Master Trains)
- `Main/backend/sih_deta/Live-Journey-Tracker/data/telemetry.db` (`110 KB` — 704 Approach Cabins & Live Telemetry Schema)

### Stored in `Main/unpushed_assets/` (Ignored by Git):
- `historical.db` (`691.22 MB`)
- `weather.db` (`579.96 MB`)
- `darpan.sqlite` (`96.40 MB`)
- `stations.db` (`82.48 MB`)
- `anomalies.db` (`11.64 MB`)
- `datameet_schedules.json` (`82.17 MB`)
- `datameet_stations.json` (`3.02 MB`)
- `station_delay_dataset_31f.csv` (`57.78 MB`)
- `anomalies.json` (`17.71 MB`) & `anomalies.csv` (`6.98 MB`)

---

## 3. How to Restore or Link Unpushed Files on a New Clone

If you clone this repository onto a new machine, place the files from `Main/unpushed_assets/` into their active runtime locations using PowerShell:

```powershell
# Run from the repository root (Main/)
Copy-Item "unpushed_assets\darpan.sqlite" "backend\data\darpan.sqlite" -Force
Copy-Item "unpushed_assets\historical.db" "backend\sih_deta\Historical-Delay-Records\data\historical.db" -Force
Copy-Item "unpushed_assets\weather.db" "backend\sih_deta\Weather-Environment\data\weather.db" -Force
Copy-Item "unpushed_assets\stations.db" "backend\sih_deta\Station-Halt Scraper\data\stations.db" -Force
Copy-Item "unpushed_assets\anomalies.db" "backend\sih_deta\Network-Anomalies\data\anomalies.db" -Force
Copy-Item "unpushed_assets\station_delay_dataset_31f.csv" "backend\predictor\data\station_delay_dataset_31f.csv" -Force
```

> [!NOTE]
> Even if the multi-hundred-megabyte `.db` files are absent on a fresh cloud deployment, the **SIH-DETA Data Bridge (`backend/app/sih_deta/data_bridge.py`)** automatically detects missing SQLite files and degrades gracefully using the bundled `trains.db`, `telemetry.db` (704 approach cabins), `station_eta_model.joblib`, and pre-computed corridor profiles so the API and UI never crash.
