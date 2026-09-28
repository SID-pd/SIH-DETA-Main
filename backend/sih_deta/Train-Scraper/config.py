"""
Configuration settings for Indian Railways Web Scraper.
"""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = DATA_DIR / "exports"
DEFAULT_DB_PATH = DATA_DIR / "trains.db"

# Ensure data directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Data Sources
CONFIRMTKT_SEARCH_API = "https://api.confirmtkt.com/api/trains/search?text="
CONFIRMTKT_SCHEDULE_URL = "https://www.confirmtkt.com/train-schedule/"
ETRAIN_SUGGEST_API = "https://etrain.info/ajax.php?q=trnsuggst&v=3.4.11.0&term="
DATAMEET_TRAINS_URL = "https://raw.githubusercontent.com/datameet/railways/master/trains.json"

# Request Headers and User-Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]

DEFAULT_HEADERS = {
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
}

# Network and Rate-Limiting Controls
DEFAULT_TIMEOUT = 15  # seconds
DEFAULT_DELAY = 0.35  # seconds between requests to prevent rate-limiting
MAX_RETRIES = 3
BACKOFF_FACTOR = 1.5
DEFAULT_CONCURRENCY = 4  # workers for concurrent scraping
