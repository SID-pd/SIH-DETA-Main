"""
Resilient HTTP Client with Circuit Breaker, Exponential Backoff, and User-Agent Rotation.
Guarantees fast failover and protects against provider degradation.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests
from config import (
    BACKOFF_FACTOR,
    CIRCUIT_BREAKER_COOLDOWN_SEC,
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT_SEC,
    MAX_RETRIES,
    USER_AGENTS,
)

logger = logging.getLogger("getinfo.http")


class CircuitBreaker:
    """
    Prevents hammering failing providers.
    If a provider fails consecutive times >= threshold, trips into OPEN state
    for `cooldown_seconds`, failing fast so secondary fallbacks run immediately.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = CIRCUIT_BREAKER_COOLDOWN_SEC,
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._failures: Dict[str, int] = {}
        self._tripped_until: Dict[str, float] = {}

    def is_available(self, provider_id: str) -> bool:
        now = time.time()
        tripped_time = self._tripped_until.get(provider_id, 0.0)
        if now < tripped_time:
            remaining = int(tripped_time - now)
            logger.warning(
                f"Circuit breaker OPEN for provider '{provider_id}' ({remaining}s remaining). Skipping."
            )
            return False
        return True

    def record_success(self, provider_id: str) -> None:
        self._failures[provider_id] = 0
        self._tripped_until.pop(provider_id, None)

    def record_failure(self, provider_id: str) -> None:
        count = self._failures.get(provider_id, 0) + 1
        self._failures[provider_id] = count
        if count >= self.failure_threshold:
            trip_until = time.time() + self.cooldown_seconds
            self._tripped_until[provider_id] = trip_until
            logger.error(
                f"Circuit breaker TRIPPED for provider '{provider_id}' after {count} consecutive failures. Cooldown {self.cooldown_seconds}s."
            )


class ResilientHttpClient:
    """Production HTTP client with retries, rotating User-Agents, and circuit breaker."""

    def __init__(self):
        self.session = requests.Session()
        self.circuit_breaker = CircuitBreaker()

    def _get_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        h = dict(DEFAULT_HEADERS)
        h["User-Agent"] = random.choice(USER_AGENTS)
        if custom_headers:
            h.update(custom_headers)
        return h

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        provider_name: Optional[str] = None,
    ) -> requests.Response:
        """Executes GET request with circuit breaker and retry logic."""
        domain = provider_name or urlparse(url).netloc

        if not self.circuit_breaker.is_available(domain):
            raise ConnectionError(f"Provider '{domain}' circuit breaker is currently open.")

        req_headers = self._get_headers(headers)
        last_exception: Optional[Exception] = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, params=params, headers=req_headers, timeout=timeout)
                if resp.status_code == 200:
                    self.circuit_breaker.record_success(domain)
                    return resp
                elif resp.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        f"Attempt {attempt}/{MAX_RETRIES} to {url} returned HTTP {resp.status_code}"
                    )
                    last_exception = requests.HTTPError(f"HTTP {resp.status_code}", response=resp)
                else:
                    # 400, 404 etc - not a network/server crash, return directly
                    return resp
            except (requests.RequestException, requests.Timeout) as exc:
                logger.warning(f"Attempt {attempt}/{MAX_RETRIES} to {url} error: {exc}")
                last_exception = exc

            if attempt < MAX_RETRIES:
                sleep_time = (BACKOFF_FACTOR ** attempt) + random.uniform(0.1, 0.5)
                time.sleep(sleep_time)

        self.circuit_breaker.record_failure(domain)
        raise last_exception or ConnectionError(f"Failed to fetch {url} after {MAX_RETRIES} attempts.")

    def get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        provider_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Convenience method returning parsed JSON."""
        resp = self.get(url, params=params, headers=headers, timeout=timeout, provider_name=provider_name)
        return resp.json()

    def get_text(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        provider_name: Optional[str] = None,
    ) -> str:
        """Convenience method returning response text."""
        resp = self.get(url, params=params, headers=headers, timeout=timeout, provider_name=provider_name)
        return resp.text


# Global client instance
http_client = ResilientHttpClient()
