"""
Base HTTP scraper with User-Agent rotation, exponential backoff, socket timeouts,
and automatic Circuit Breaker protection against upstream IP throttling / stalls.
"""

import hashlib
import logging
import random
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Optional

from config import (
    BACKOFF_FACTOR,
    CACHE_DIR,
    CIRCUIT_BREAKER_COOLDOWN,
    CIRCUIT_BREAKER_ERRORS,
    DEFAULT_DELAY,
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    DELAY_JITTER,
    MAX_RETRIES,
    SOCKET_TIMEOUT,
    USER_AGENTS,
)

# Global OS-level socket timeout: eliminates TCP connection hangs completely
socket.setdefaulttimeout(SOCKET_TIMEOUT)

logger = logging.getLogger("historical_scraper")


class BaseScraper:
    """Resilient, rate-limited HTTP fetching with Circuit Breaker and Zero-Hang guarantees."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        use_cache: bool = True,
        rate_limit_delay: float = DEFAULT_DELAY,
    ):
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.use_cache = use_cache
        self.rate_limit_delay = rate_limit_delay
        self._last_request_time = 0.0
        self._consecutive_rate_limits = 0

    def _get_cache_path(self, url: str) -> Path:
        """Generate a deterministic filename for cached URL."""
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        safe_name = "".join(c if c.isalnum() else "_" for c in url.split("/")[-1].split("?")[0])[:24]
        return self.cache_dir / f"{safe_name}_{url_hash}.html"

    def _read_cache(self, url: str, max_age_seconds: int = 86400) -> Optional[str]:
        """Read content from local file cache if within valid age."""
        if not self.use_cache:
            return None
        cache_path = self._get_cache_path(url)
        if cache_path.exists():
            try:
                age = time.time() - cache_path.stat().st_mtime
                if age < max_age_seconds:
                    logger.debug(f"Cache HIT for {url} (age: {age:.0f}s)")
                    return cache_path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                logger.warning(f"Error reading cache at {cache_path}: {e}")
        return None

    def _write_cache(self, url: str, content: str) -> None:
        """Save fetched HTML content to disk cache."""
        if not self.use_cache or not content:
            return
        cache_path = self._get_cache_path(url)
        try:
            cache_path.write_text(content, encoding="utf-8")
        except Exception as e:
            logger.warning(f"Error writing cache to {cache_path}: {e}")

    def _throttle(self) -> None:
        """Enforce polite rate-limiting with random jitter between sequential network calls."""
        elapsed = time.time() - self._last_request_time
        jitter = random.uniform(0, DELAY_JITTER)
        target_delay = self.rate_limit_delay + jitter
        if elapsed < target_delay:
            time.sleep(target_delay - elapsed)
        self._last_request_time = time.time()

    def _handle_circuit_breaker(self) -> None:
        """Triggers cooling period if multiple consecutive rate-limiting responses are received."""
        if self._consecutive_rate_limits >= CIRCUIT_BREAKER_ERRORS:
            logger.warning(
                f"🚨 Circuit Breaker Triggered ({self._consecutive_rate_limits} consecutive blocks/errors). "
                f"Entering polite cooldown for {CIRCUIT_BREAKER_COOLDOWN:.0f} seconds to protect connection..."
            )
            time.sleep(CIRCUIT_BREAKER_COOLDOWN)
            self._consecutive_rate_limits = 0
            logger.info("🟢 Circuit breaker cooldown complete. Resuming requests...")

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_cache_age: int = 86400,
    ) -> Optional[str]:
        """
        Execute an HTTP GET request with retry backoff, circuit breaking, and caching.
        Guaranteed to return (or None) within bounded time without hanging.
        """
        # 1. Local Cache Check
        cached = self._read_cache(url, max_age_seconds=max_cache_age)
        if cached:
            return cached

        # 2. Check Circuit Breaker
        self._handle_circuit_breaker()

        # 3. Build Request with rotated User-Agent
        req_headers = dict(DEFAULT_HEADERS)
        req_headers["User-Agent"] = random.choice(USER_AGENTS)
        if headers:
            req_headers.update(headers)

        # 4. Attempt Request with Backoff
        for attempt in range(1, MAX_RETRIES + 1):
            self._throttle()
            try:
                logger.debug(f"GET {url} (attempt {attempt}/{MAX_RETRIES})")
                req = urllib.request.Request(url, headers=req_headers)
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    raw_bytes = response.read()
                    charset = response.headers.get_content_charset() or "utf-8"
                    content = raw_bytes.decode(charset, errors="replace")

                    # Successful response: reset consecutive error tracker
                    self._consecutive_rate_limits = 0
                    self._write_cache(url, content)
                    return content

            except urllib.error.HTTPError as e:
                logger.warning(f"HTTP {e.code} for {url} on attempt {attempt}: {e.reason}")
                if e.code in (404, 410):
                    # Resource permanently not found (skip without retrying)
                    return None
                if e.code in (429, 503, 502, 504):
                    # Rate-limiting / upstream overload
                    self._consecutive_rate_limits += 1
                    sleep_time = (BACKOFF_FACTOR ** attempt) * 2.0
                    logger.info(f"Backing off for {sleep_time:.1f}s after HTTP {e.code}...")
                    time.sleep(sleep_time)
                else:
                    time.sleep(BACKOFF_FACTOR ** attempt)

            except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
                logger.warning(f"Network timeout/error for {url} on attempt {attempt}: {e}")
                time.sleep(BACKOFF_FACTOR ** attempt)

            except Exception as e:
                logger.error(f"Unexpected error requesting {url}: {e}")
                return None

        logger.warning(f"Failed to fetch {url} after {MAX_RETRIES} attempts.")
        return None
