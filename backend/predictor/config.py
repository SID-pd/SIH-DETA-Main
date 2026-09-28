"""
Configuration settings for Predictor ML & Data Scraping Pipeline.
SIH Problem Statement 26028.
"""

from pathlib import Path

# Base Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PREDICTOR_DIR = PROJECT_ROOT / "predictor"
DATA_DIR = PREDICTOR_DIR / "data"
ARTIFACTS_DIR = PREDICTOR_DIR / "artifacts"
SCRAPERS_DIR = PREDICTOR_DIR / "scrapers"

# External Data Source Paths
DARPAN_DB_PATH = PROJECT_ROOT / "data" / "darpan.sqlite"
ETRAIN_DELAYS_CSV = PROJECT_ROOT / "Datasets" / "etrain_delays.csv"
KAGGLE_IR_TRAIN_CSV = PROJECT_ROOT / "indian-railways-predict-train-delay" / "ir_train.csv"
SNAPSHOTS_DB_PATH = DATA_DIR / "live_snapshots.sqlite"
MASTER_DATASET_CSV = DATA_DIR / "station_delay_dataset_31f.csv"
MODEL_ARTIFACT_PATH = ARTIFACTS_DIR / "station_eta_model.joblib"

# Scraper Endpoints
CONFIRMTKT_LIVE_URL = "https://www.confirmtkt.com/train-running-status"
RUNNINGSTATUS_BASE_URL = "https://runningstatus.in/status"
RAILYATRI_BASE_URL = "https://www.railyatri.in"
ETRAIN_BASE_URL = "https://etrain.info/train"
OPENMETEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPENMETEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
RAILRADAR_API_URL = "https://api.railradar.in/v1"

# Request Headers
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENTS[0],
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# The 31 Features (X) requested for the model
FEATURE_COLUMNS_31 = [
    # 1. Train Attributes
    "train_id",
    "train_type",
    "train_route",
    # 2. Topological Stations
    "current_station",
    "next_station",
    "distance_to_next_station",
    # 3. Telemetry & Location
    "current_latitude",
    "current_longitude",
    "current_speed",
    "average_speed",
    # 4. Timings & Delays
    "scheduled_arrival_time",
    "scheduled_departure_time",
    "actual_arrival_time",
    "actual_departure_time",
    "current_delay",
    "previous_station_delay",
    # 5. Historical Priors
    "historical_average_delay",
    "historical_section_travel_time",
    # 6. Halt Dynamics
    "number_of_previous_halts",
    "current_halt_duration",
    "scheduled_halt_duration",
    "unscheduled_halt_flag",
    # 7. Operational & Track Realities
    "signal_operational_delay",
    "route_congestion_level",
    "weather",
    # 8. Temporal / Calendar
    "day_of_week",
    "month_season",
    "peak_off_peak_indicator",
    "time_since_journey_start",
    # 9. Journey Remaining Metrics
    "remaining_distance",
    "number_of_remaining_stations",
]

# Primary and Secondary Labels (Y)
PRIMARY_LABEL = "delay_at_next_station_minutes"
SECONDARY_LABEL = "travel_time_to_next_station_minutes"

# Categorical columns that need encoding
CATEGORICAL_FEATURES = [
    "train_id",
    "train_type",
    "train_route",
    "current_station",
    "next_station",
    "month_season",
]

# Numerical columns
NUMERICAL_FEATURES = [col for col in FEATURE_COLUMNS_31 if col not in CATEGORICAL_FEATURES]
