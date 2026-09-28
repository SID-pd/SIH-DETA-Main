"""
Resilient Async HTTP Client for scraper-erail.
Implements token-bucket rate limiting, automatic User-Agent rotation,
backoff retries on rate limits, and custom header injection.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Dict, Optional

import httpx

from config.settings import (
    BACKOFF_FACTOR,
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_RETRIES,
    USER_AGENTS,
)

logger = logging.getLogger("scraper_erail.http")


class TokenBucketRateLimiter:
    """Async token bucket rate limiter to prevent aggressive server flooding."""

    def __init__(self, rate: float, capacity: Optional[float] = None):
        self.rate = rate  # tokens added per second
        self.capacity = capacity if capacity is not None else rate * 2.0
        self.tokens = self.capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    # Add subtle random jitter (50ms - 150ms)
                    jitter = random.uniform(0.05, 0.15)
                    await asyncio.sleep(jitter)
                    return

                wait_time = (tokens - self.tokens) / self.rate
                await asyncio.sleep(wait_time)


class ResilientHttpClient:
    """Async HTTP client with resilience, connection pooling, and throttling."""

    def __init__(
        self,
        rate_limit_rps: float = 5.0,
        concurrency_limit: int = 5,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        base_url: Optional[str] = None,
    ):
        self.limiter = TokenBucketRateLimiter(rate=rate_limit_rps)
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.timeout = timeout
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "ResilientHttpClient":
        limits = httpx.Limits(
            max_keepalive_connections=20, max_connections=50, keepalive_expiry=30.0
        )
        self._client = httpx.AsyncClient(
            base_url=self.base_url or "",
            headers=DEFAULT_HEADERS,
            timeout=self.timeout,
            limits=limits,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_random_headers(self, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = dict(DEFAULT_HEADERS)
        headers["User-Agent"] = random.choice(USER_AGENTS)
        if extra_headers:
            headers.update(extra_headers)
        return headers

    async def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        retries: int = MAX_RETRIES,
    ) -> httpx.Response:
        if not self._client:
            raise RuntimeError("Client not initialized. Use `async with ResilientHttpClient():`")

        req_headers = self._get_random_headers(headers)

        for attempt in range(1, retries + 1):
            await self.limiter.acquire()
            async with self.semaphore:
                try:
                    response = await self._client.request(
                        method=method,
                        url=url,
                        params=params,
                        data=data,
                        headers=req_headers,
                    )

                    # Handle server backoff status codes
                    if response.status_code == 429:
                        backoff = (BACKOFF_FACTOR ** attempt) + random.uniform(1.0, 3.0)
                        logger.warning(
                            f"[429 Rate Limit] {url} - backing off for {backoff:.1f}s (attempt {attempt}/{retries})"
                        )
                        await asyncio.sleep(backoff)
                        continue

                    if response.status_code in (500, 502, 503, 504):
                        backoff = (BACKOFF_FACTOR ** attempt) + random.uniform(0.5, 1.5)
                        logger.warning(
                            f"[{response.status_code} Server Error] {url} - backing off for {backoff:.1f}s"
                        )
                        await asyncio.sleep(backoff)
                        continue

                    response.raise_for_status()
                    return response

                except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                    if attempt == retries:
                        logger.error(f"HTTP request failed permanently for {url}: {exc}")
                        raise
                    backoff = (BACKOFF_FACTOR ** attempt) + random.uniform(0.5, 1.5)
                    logger.debug(f"HTTP transient error for {url}: {exc}. Retrying in {backoff:.1f}s...")
                    await asyncio.sleep(backoff)

        raise RuntimeError(f"Exhausted {retries} retries requesting {url}")

    async def get_text(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> str:
        resp = await self.request("GET", url, params=params, headers=headers)
        return resp.text

    async def get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        resp = await self.request("GET", url, params=params, headers=headers)
        return resp.json()
