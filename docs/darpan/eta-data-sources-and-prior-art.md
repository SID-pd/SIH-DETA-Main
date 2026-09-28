# ETA data sources, datasets & prior art (SIH26028)

Research pass across GitHub, Kaggle, and official data portals for building the dynamic ETA system.
Companion to [openrailwaymap-and-osm-data.md](./openrailwaymap-and-osm-data.md) (track infrastructure) —
this file covers **live train data, historical datasets, and existing implementations**.

## 1. Real-time data — the actual unlock for "dynamic" ETA

| Source | What it gives you | Notes |
|---|---|---|
| [x64vbhv/ntes-client](https://github.com/x64vbhv/ntes-client) | Hits the **actual official NTES endpoint** (`enquiry.indianrail.gov.in/crisns/AppServAnd`) — live train position, next-station ETA/ETD, platform, delay. | **No API key needed** — AES-128 encryption + MD5 signing NTES uses is already reverse-engineered here. This is the live feed. |
| [AniCrad/indian-rail-api](https://github.com/AniCrad/indian-rail-api) | Live running status, PNR, station info as clean REST endpoints. | 48★, 26 forks, actively maintained. |
| [RAJIV81205/RailKit](https://github.com/RAJIV81205/RailKit) | Node.js — live tracking + PNR + route details. | 47★, updated same-day at time of research. |
| ETrain.info scraping method (see [naijilaji dataset](https://www.kaggle.com/datasets/naijilaji/indian-railways-passenger-train-delays-dataset) below) | Shows how someone scraped per-station punctuality stats using `requests` + `BeautifulSoup`. | Good backup live source if NTES gets rate-limited during a demo. |

## 2. Static reference data — network topology + schedules

| Source | What it gives you |
|---|---|
| [datameet/railways](https://github.com/datameet/railways) | The most credible base dataset — GeoJSON: every station's lat/long, every train's route as a line geometry, full stop-by-stop schedules. 155★, 59 forks. |
| [Kaggle mirror (sripaadsrinivasan)](https://www.kaggle.com/datasets/sripaadsrinivasan/indian-railways-dataset) | Same content as above, CC0, easier to pull straight into a notebook. |
| [data.gov.in — Train Time Table](https://www.data.gov.in/catalog/indian-railways-train-time-table) | Official government schedule data — cite this over a scrape when it needs to look authoritative in the report/pitch. |
| [Year-wise Train Punctuality Index](https://dataful.in/datasets/1204/) | Official aggregate punctuality stats. |

## 3. Datasets for training/validating a delay model

| Source | Details |
|---|---|
| [Kaggle: Indian Railways Predict Train Delay](https://www.kaggle.com/competitions/indian-railways-predict-train-delay) | **1.5M journey records, 44 features** across Time / Geography / Route / Weather / Rolling-Stock / Operations groups (e.g. `zone_congestion_index`, `is_monsoon_season`, `late_incoming_rake`, `has_lhb_coaches`, `route_historical_ontime_pct`). Top leaderboard score **0.92** — confirms the feature set is genuinely learnable with standard GBM models. **Synthetic** (community-made, not real IR data) but a ready-made feature schema worth copying almost directly. |
| [naijilaji: Train Delays Dataset 2025](https://www.kaggle.com/datasets/naijilaji/indian-railways-passenger-train-delays-dataset) | **Real** scraped data — 1,900 train-station combos, avg delay + punctuality % per station, sourced from ETrain.info, Sept 2025. CC0, high usability score (9.41). Actual ground truth, unlike the competition dataset above. |
| [Prediction of Train Delay in Indian Railways through ML Techniques](https://www.researchgate.net/publication/332113402_Prediction_of_Train_Delay_in_Indian_Railways_through_Machine_Learning_Techniques) | Academic paper — cite for feature justification and benchmark accuracy in the report. |

## 4. Prior art / reference implementations (study, don't copy)

- **[zer-art/Railflow](https://github.com/zer-art/Railflow)** — "Sovereign IDSS for Indian Railways":
  hybrid **Reinforcement Learning (PPO) + Operations Research (MILP) + fine-tuned LLM for
  explainability**. Only a design blueprint, no working code — but the framing (RL for scheduling,
  OR as a safety shield, LLM explaining decisions) is genuinely SOTA-flavored. Worth borrowing the
  *pitch structure* for a "future work" slide, not the code.
- **[2510prem/Indian-Railways-Delay-Prediction](https://github.com/2510prem/Indian-Railways-Delay-Prediction)** —
  bare-minimum working reference: `RandomForestRegressor` + Streamlit UI. This is the floor — a
  weekend build. Useful as a sanity-check baseline, not a target.
- **[didi/heteta](https://github.com/didi/heteta)**, **[LibCity](https://github.com/LibCity/Bigscity-LibCity)**,
  **[Traffic-Prediction-Open-Code-Summary](https://github.com/aptx1231/Traffic-Prediction-Open-Code-Summary)** —
  ride-hailing/traffic ETA research (Didi, academic). Spatio-temporal graph embedding techniques
  transfer conceptually to trains-on-a-graph. Good citation for "we adapted techniques from
  production-scale ETA systems" in the pitch.
- SIGSPATIAL 2021 GISCUP ETA contest code — another benchmark methodology reference for feature
  engineering / model architecture choices.

## 5. The actual gap, and the plan around it

No public dataset has **real IR train trajectories + ground-truth ETA outcomes** at scale. What
exists is either synthetic (Kaggle competition — great for feature scaffolding) or aggregated
punctuality stats (ETrain scrape — real, but not per-journey). The plan:

1. Use `datameet/railways` for the static network graph (stations, routes, scheduled times).
2. Stand up the `ntes-client` poller **as early as possible** — every day it runs, it accumulates
   real (train, station, actual-arrival vs. scheduled) pairs. This becomes real training data by
   demo day, and doubles as the live inference feed. Data accumulation is time-bound, not
   effort-bound — this is the one piece that benefits from starting immediately regardless of what
   else is in progress.
3. Prototype/validate feature engineering against the Kaggle synthetic set first (fast iteration,
   known-good features), then swap in real accumulated NTES data once there's enough history.
4. Use the ETrain scrape as a redundant live source / cold-start data if NTES polling doesn't
   accumulate enough history in time.
