# 🚆 scraper-erail: Indian Railways High-Performance Scraper Engine

> **Dual-Source Scraping & Data Harvesting for [eRail.in](https://erail.in) and [CRIS NTES](https://enquiry.indianrail.gov.in/mntes/)**  
> Designed for **DARPAN & SIH Train ETA Prediction System**

---

## 📌 1. Project Overview & Motivation

This engine addresses the time-gap and feature-deficiency issues in existing static railway datasets. By fusing high-speed data streams from **eRail.in** with official operational telemetry from the **National Train Enquiry System (NTES)**, it builds an up-to-date, rich feature store for predictive models ($M_0$ propagation, $M_1$ risk classifier, and $M_2$ segment regressor).

### 🎯 Key Gaps Resolved:
1. **Time-Gap / Timetable Drift**: Replaces pre-2020 static schedules with modern **2024–2026 working timetables** reflecting Zero-Based Timetable (ZBTT) revisions and updated section Maximum Permissible Speeds (MPS).
2. **Missing Modern Fleet**: Catalogs **14,000+ active trains**, including all Vande Bharat, Amrit Bharat, Tejas, and Special/Holiday trains (up from 5,208).
3. **Rake & Coach Compositions (LHB vs ICF)**: Extracts coach configurations (Loco, SLR, GS, 3E, 3A, 2A, 1A, CC, EC) and identifies rake types, directly restoring the 8 dropped ML features in DARPAN's risk classifier.
4. **Scheduled & Actual Platforms**: Ingests platform allocations across stations.
5. **Halt Durations & Passing Points**: Distinguishes between commercial passenger halts and operational through-passing points with precise dwell times.
6. **1-Year Empirical Punctuality Distributions**: Harvests per-station delay distributions (% on-time, slight, moderate, severe) to immediately pre-fill `hist_delay_added_p50/p90` on route segments without waiting months for live polls.
7. **Operational Exceptions**: Tracks real-time Rescheduled, Cancelled, and Diverted trains from CRIS NTES.

---

## 🏗️ 2. Architecture

```
                             ┌───────────────────────────────┐
                             │       CLI (cli.py)            │
                             └───────────────┬───────────────┘
                                             │
                      ┌──────────────────────┴──────────────────────┐
                      ▼                                             ▼
          ┌───────────────────────┐                     ┌───────────────────────┐
          │     eRail Scraper     │                     │     NTES Scraper      │
          │   (erail_scraper.py)  │                     │   (ntes_scraper.py)   │
          └───────────┬───────────┘                     └───────────┬───────────┘
                      │                                             │
                      ▼                                             ▼
          ┌───────────────────────┐                     ┌───────────────────────┐
          │     eRail Parser      │                     │      NTES Parser      │
          │   (parser_erail.py)   │                     │   (parser_ntes.py)    │
          └───────────┬───────────┘                     └───────────┬───────────┘
                      │                                             │
                      └──────────────────────┬──────────────────────┘
                                             ▼
                             ┌───────────────────────────────┐
                             │   Normalizer & Validator      │
                             │  (normalizer.py, validator.py)│
                             └───────────────┬───────────────┘
                                             │
                      ┌──────────────────────┴──────────────────────┐
                      ▼                                             ▼
          ┌───────────────────────┐                     ┌───────────────────────┐
          │  data/darpan.sqlite   │                     │   output/*.csv        │
          │  Unified SQLite Store │                     │   Modular Parquet/CSV │
          └───────────────────────┘                     └───────────────────────┘
```

---

## ⚡ 3. Core Features & Resilience

- **Token-Bucket Rate Limiter**: Independent token buckets for eRail (5 RPS) and NTES (2 RPS) with randomized jitter to prevent IP blocks.
- **SQLite Checkpoint Manager (`scrape_state.sqlite`)**: Tracks progress for all 14,000+ trains. If scraping is stopped or interrupted, it resumes instantly where it left off with zero duplicate requests.
- **User-Agent & Header Rotation**: Realistic modern browser fingerprints.
- **Exponential Backoff**: Automatic retry on `429 Too Many Requests` or transient HTTP 5xx errors.
- **Direct Segment Graph Derivation**: Automatically maps consecutive stops into directed edges with distance and runtimes for DARPAN's `segments` table.

---

## 🚀 4. Installation & Setup

```bash
cd experiment/scraper-erail

# Install dependencies
pip install -r requirements.txt
```

---

## 📖 5. CLI Usage Guide

The unified CLI (`cli.py`) provides commands for all operational flows:

### A. Scrape Master Catalogs (Trains & Stations)
Fetches the complete active directory of trains and stations from eRail:
```bash
python cli.py catalog
```

### B. Scrape Timetable Routes & Stops
Scrapes ordered halts, arrival/departure timings, halt durations, distance, and scheduled platforms:
```bash
# Scrape specific key trains
python cli.py route --trains 12301,12302,12002,22436,12951

# Or scrape all catalog trains in batches (with automatic resume)
python cli.py route --limit 500
```

### C. Scrape Coach Compositions & Rake Types
Extracts coach layouts (LHB vs. ICF vs. TRAIN18):
```bash
python cli.py coach --trains 12301,12002,22436
```

### D. Scrape Historical Punctuality & Delay Profiles
Fetches 1-year station delay metrics:
```bash
python cli.py delays --trains 12301,12002,22436
```

### E. Scrape NTES Live Running Status
Captures real-time station arrival/departure delays and passage times:
```bash
# Capture live status for today
python cli.py live --trains 12301,12002,22436

# Or query a specific journey date (DD-MM-YYYY)
python cli.py live --trains 12301 --date 03-09-2026
```

### F. Scrape Operational Exceptions (Rescheduled, Cancelled, Diverted)
```bash
python cli.py exceptions
```

### G. Compile Route Graph & Historical Delay Priors
Compiles consecutive stops in `schedule_stops` into topological segments and backfills empirical delay priors:
```bash
python cli.py compile
```

### H. Build ML Model-Ready Datasets (Without Mutating the Database)
Compiles the scraped relational tables into the exact 44-feature CSV expected by `train_eta_model.py`, as well as a point-to-point intermediate delay dataset:
```bash
# Build both journey-level and point-by-point datasets
python cli.py build-dataset --type all --days 30

# Outputs:
#  - output/ir_train_real.csv            (100% drop-in replacement for ir_train.csv)
#  - output/ir_point_delays_master.csv  (intermediate stop delays master)
# NOTE: data/darpan.sqlite remains completely untouched as the relational source of truth!
```

### I. Export All Relational Tables to CSV
Exports raw relational tables (`stations`, `trains`, `schedule_stops`, `coach_compositions`, etc.) to CSV:
```bash
python cli.py export
```

### J. Continuous Live Harvester
Runs the background live telemetry poller without consuming third-party API quotas:
```bash
python cli.py poll --interval 300 --trains 12301,12302,12002,22436
```

### K. View Checkpoint Progress
```bash
python cli.py status
```

---

## 🧪 6. Testing

Run unit and regression test suite:
```bash
pytest tests/ -v
```
