"""
Configuration and settings for scraper-erail.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

# Base Paths
SCRAPER_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRAPER_DIR.parent.parent
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = SCRAPER_DIR / "output"
STATE_DB_PATH = SCRAPER_DIR / "scrape_state.sqlite"
DEFAULT_DARPAN_DB_PATH = Path(os.environ.get("DARPAN_DB", DATA_DIR / "darpan.sqlite"))

# Ensure directories exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Target URLs
ERAIL_BASE_URL = "https://erail.in"
NTES_BASE_URL = "https://enquiry.indianrail.gov.in/mntes"

# Rate Limiting & Concurrency
# erail.in handles modest concurrency well; NTES requires polite throttling
ERAIL_RPS_LIMIT = 5.0
ERAIL_CONCURRENCY = 8
NTES_RPS_LIMIT = 2.0
NTES_CONCURRENCY = 3

DEFAULT_TIMEOUT_SECONDS = 20.0
MAX_RETRIES = 3
BACKOFF_FACTOR = 1.5

# Realistic Browser User Agents for Rotation
USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "DNT": "1",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}
