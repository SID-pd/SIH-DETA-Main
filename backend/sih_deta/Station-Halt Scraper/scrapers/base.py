"""
Base HTTP scraper supporting requests with standard library urllib fallback,
user-agent rotation, automatic retries with exponential backoff, and polite rate-limiting.
"""

import json
import logging
import random
import time
import urllib.error
import urllib.parse
import urllib.request
import ssl
from typing import Any, Dict, Optional, Union

from config import (
    BACKOFF_FACTOR,
    DEFAULT_DELAY,
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    MAX_RETRIES,
    USER_AGENTS,
)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logger = logging.getLogger("station_scraper")


class BaseScraper:
    """Base scraper providing robust HTTP request handling and rate limiting."""

    def __init__(self, delay: float = DEFAULT_DELAY, timeout: int = DEFAULT_TIMEOUT):
        self.delay = delay
        self.timeout = timeout
        self.last_request_time = 0.0

        if HAS_REQUESTS:
            self.session = requests.Session()
        else:
            self.session = None

        self.ssl_context = ssl.create_default_context()

    def _get_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = dict(DEFAULT_HEADERS)
        headers["User-Agent"] = random.choice(USER_AGENTS)
        if custom_headers:
            headers.update(custom_headers)
        return headers

    def _rate_limit(self):
        """Polite rate limiting between consecutive network requests."""
        if self.delay <= 0:
            return
        elapsed = time.time() - self.last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request_time = time.time()

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        as_json: bool = False,
    ) -> Union[str, Dict[str, Any], list, None]:
        """
        Perform a GET request with retries and rate limiting.
        """
        if params:
            query_string = urllib.parse.urlencode(params)
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}{query_string}"

        req_headers = self._get_headers(headers)

        for attempt in range(1, MAX_RETRIES + 1):
            self._rate_limit()
            try:
                if HAS_REQUESTS:
                    resp = self.session.get(url, headers=req_headers, timeout=self.timeout)
                    if resp.status_code == 200:
                        if as_json:
                            return resp.json()
                        return resp.text
                    elif resp.status_code in (429, 500, 502, 503, 504):
                        sleep_time = (BACKOFF_FACTOR ** attempt) + random.uniform(0.5, 1.5)
                        logger.warning(
                            f"HTTP {resp.status_code} for {url}. Backing off {sleep_time:.2f}s (attempt {attempt}/{MAX_RETRIES})"
                        )
                        time.sleep(sleep_time)
                        continue
                    else:
                        logger.warning(f"Failed to fetch {url}, status: {resp.status_code}")
                        return None
                else:
                    # Standard library urllib fallback
                    req = urllib.request.Request(url, headers=req_headers, method="GET")
                    with urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_context) as response:
                        content_bytes = response.read()
                        charset = response.headers.get_content_charset() or "utf-8"
                        text = content_bytes.decode(charset, errors="replace")
                        if as_json:
                            return json.loads(text)
                        return text

            except (urllib.error.HTTPError, urllib.error.URLError, Exception) as e:
                status_code = getattr(e, "code", None)
                if status_code in (429, 500, 502, 503, 504) or isinstance(e, (TimeoutError, urllib.error.URLError)):
                    sleep_time = (BACKOFF_FACTOR ** attempt) + random.uniform(0.5, 1.5)
                    logger.warning(
                        f"Request error for {url}: {e}. Retrying in {sleep_time:.2f}s (attempt {attempt}/{MAX_RETRIES})"
                    )
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Error fetching {url}: {e}")
                    return None

        logger.error(f"Max retries reached for {url}")
        return None
