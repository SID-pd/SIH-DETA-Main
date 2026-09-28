"""
Configuration settings for Get-info resilient transit information fetcher.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

# Paths
BASE_DIR = Path(__file__).resolve().parent
CACHE_DB_PATH = BASE_DIR / "getinfo_cache.sqlite"

# Provider URLs
CONFIRMTKT_PNR_API = "https://api.confirmtkt.com/api/pnr/status"
CONFIRMTKT_LIVE_PAGE = "https://www.confirmtkt.com/train-running-status"
CONFIRMTKT_WEB_PNR = "https://www.confirmtkt.com/pnr-status"

NTES_BASE_URL = "https://enquiry.indianrail.gov.in/mntes"
ERAIL_BASE_URL = "https://erail.in"
RAILYATRI_BASE_URL = "https://www.railyatri.in"

# Timeouts & Retries
DEFAULT_TIMEOUT_SEC = 8.0
MAX_RETRIES = 3
BACKOFF_FACTOR = 1.2
CIRCUIT_BREAKER_COOLDOWN_SEC = 60.0  # trip provider for 60s on 3 consecutive failures

# Cache TTL (Time To Live in seconds)
TTL_LIVE_STATUS_SEC = 45        # live train moves every minute
TTL_PNR_SEC = 120               # PNR status changes rarely within 2 mins
TTL_COACH_SEC = 86400           # coach composition stays static for journey
TTL_TIMELINE_SEC = 300          # 5 minutes
TTL_EXCEPTIONS_SEC = 900        # 15 minutes

# Realistic User-Agents for rotation
USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}
