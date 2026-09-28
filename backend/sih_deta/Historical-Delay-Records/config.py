"""
Configuration settings for Indian Railways Historical Delay Records & Punctuality Engine.
Optimized for autonomous, long-horizon (90-day & 1-year) overnight crawling with
deadlock-free concurrency, circuit breakers, and timetable matching.
"""

from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = DATA_DIR / "exports"
CACHE_DIR = DATA_DIR / "cache"
LOG_DIR = BASE_DIR / "logs"
DEFAULT_DB_PATH = DATA_DIR / "historical.db"

# State & Monitoring Paths
CHECKPOINT_FILE = DATA_DIR / "checkpoint.json"
HEARTBEAT_FILE = DATA_DIR / "crawler_heartbeat.json"
LOG_FILE = LOG_DIR / "crawler.log"

# Related Module Data Sources
STATIONS_DB_PATH = PROJECT_ROOT / "Station-Halt Scraper" / "data" / "stations.db"
STATION_HALTS_CSV = PROJECT_ROOT / "Station-Halt Scraper" / "data" / "exports" / "station_halts.csv"
MASTER_TRAINS_CSV = PROJECT_ROOT / "Train-Scraper" / "data" / "exports" / "master_trains.csv"
TRAINS_DB_PATH = PROJECT_ROOT / "Train-Scraper" / "data" / "trains.db"

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Historical Data Endpoints
ETRAIN_BASE_URL = "https://etrain.info"
ETRAIN_HISTORY_URL = "https://etrain.info/train/{train_no}/history"
ETRAIN_HORIZON_URL = "https://etrain.info/train/{train_no}/history?d={horizon}"

# Horizon Query Codes for etrain.info
HORIZON_WEEK = "1w"
HORIZON_MONTH = "1m"
HORIZON_90D = "3m"     # 90 Days (Last 3 Months)
HORIZON_6M = "6m"      # 180 Days (Last 6 Months)
HORIZON_1Y = "1y"      # 365 Days (Last 1 Year)

# Windowing Parameters
DEFAULT_HISTORY_DAYS = 15
SUB_WINDOW_DAYS = 15   # Bi-weekly partition slicing within 90-day & 1-year macro windows

# User-Agent rotation pool for polite, resilient scraping
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
}

# Network and Resilience Controls (Zero-Hang overnight settings)
SOCKET_TIMEOUT = 15.0       # Strict OS-level socket timeout
DEFAULT_TIMEOUT = 15.0      # HTTP request timeout (seconds)
PER_TRAIN_TIMEOUT = 45.0    # Hard watchdog limit per train (prevents stalling)
DEFAULT_DELAY = 1.5         # Base delay between sequential requests
DELAY_JITTER = 0.5          # Random delay variation (1.5s - 2.0s) to appear human
MAX_RETRIES = 2             # Retries per train before logging and continuing
BACKOFF_FACTOR = 2.0

# Circuit Breaker Protection (Prevents server overhaul / IP throttling)
CIRCUIT_BREAKER_ERRORS = 3       # Consecutive 429/503 errors before triggering cooldown
CIRCUIT_BREAKER_COOLDOWN = 180.0 # 3-minute sleep if rate-limited, then gently resumes
