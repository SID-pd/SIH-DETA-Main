"""
Base HTTP scraper with resilient retries, rotating user-agents, and exponential backoff.
Supports requests if available, with urllib fallback.
"""

import json
import logging
import random
import time
from typing import Any, Dict, Optional
import urllib.request
import urllib.parse
import urllib.error

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from predictor.config import DEFAULT_HEADERS, USER_AGENTS

logger = logging.getLogger("predictor.scrapers.base")


class BaseScraper:
    """Base scraper providing rotating headers, exponential backoff, and robust HTTP fetching."""

    def __init__(self, timeout: int = 15, max_retries: int = 3, min_delay: float = 0.5, max_delay: float = 2.0):
        self.timeout = timeout
        self.max_retries = max_retries
        self.min_delay = min_delay
        self.max_delay = max_delay
        if HAS_REQUESTS:
            self.session = requests.Session()
        else:
            self.session = None

    def _get_random_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = dict(DEFAULT_HEADERS)
        headers["User-Agent"] = random.choice(USER_AGENTS)
        if custom_headers:
            headers.update(custom_headers)
        return headers

    def _polite_delay(self):
        """Sleep a polite random duration between requests."""
        sleep_sec = random.uniform(self.min_delay, self.max_delay)
        time.sleep(sleep_sec)

    def fetch_text(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Fetches raw text content from the URL with automatic retries."""
        headers = self._get_random_headers(custom_headers)
        backoff = 1.0

        for attempt in range(1, self.max_retries + 1):
            try:
                self._polite_delay()
                if HAS_REQUESTS:
                    resp = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
                    if resp.status_code == 200:
                        return resp.text
                    logger.warning(f"HTTP {resp.status_code} for {url} (attempt {attempt}/{self.max_retries})")
                else:
                    # Urllib fallback
                    req_url = url
                    if params:
                        req_url = f"{url}?{urllib.parse.urlencode(params)}"
                    req = urllib.request.Request(req_url, headers=headers)
                    with urllib.request.urlopen(req, timeout=self.timeout) as response:
                        return response.read().decode("utf-8", errors="replace")

            except Exception as exc:
                logger.warning(f"Fetch error on {url} (attempt {attempt}/{self.max_retries}): {exc}")

            time.sleep(backoff)
            backoff *= 2.0

        logger.error(f"Failed to fetch {url} after {self.max_retries} attempts.")
        return None

    def fetch_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetches and parses JSON from the URL."""
        text = self.fetch_text(url, params=params, custom_headers=custom_headers)
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as err:
            logger.warning(f"JSON decode failure for {url}: {err}")
            return None
