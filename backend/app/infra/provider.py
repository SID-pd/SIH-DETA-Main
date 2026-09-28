"""
Provider client — the single egress path to volatile rail data.

All calls go through the rail-gateway (never directly to a vendor), so this class
knows nothing about RailKit: it speaks canonical DTOs. Swapping or adding a provider
is a gateway change, invisible here (plan ADR-001, risk R2).

Adds a circuit breaker on top of the gateway's own retry/quota handling: when the
provider is broadly failing, we stop trying for a cooling-off period instead of
burning quota and making every user wait for a timeout. An open breaker is a
first-class, reportable state (surfaced at /v1/health/providers) — not a silent
switch to fabricated data.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx


class ProviderError(Exception):
    def __init__(self, code: str, message: str, status: int = 502, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.retryable = retryable


@dataclass
class Breaker:
    """Standard three-state breaker: closed -> open -> half-open -> closed."""

    fail_threshold: int = 4
    open_seconds: int = 30
    failures: int = 0
    opened_at: float | None = None
    half_open: bool = False
    trips: int = 0

    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        if time.time() - self.opened_at >= self.open_seconds:
            return "half-open"
        return "open"

    def allow(self) -> bool:
        st = self.state()
        if st == "open":
            return False
        if st == "half-open":
            self.half_open = True  # let exactly one probe through
        return True

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None
        self.half_open = False

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.fail_threshold and self.opened_at is None:
            self.opened_at = time.time()
            self.trips += 1
        elif self.half_open:
            # The probe failed: re-open for another full cooling period.
            self.opened_at = time.time()
            self.half_open = False


@dataclass
class CallStat:
    calls: int = 0
    errors: int = 0
    total_latency_ms: int = 0

    def avg_latency_ms(self) -> int:
        return round(self.total_latency_ms / self.calls) if self.calls else 0


class ProviderClient:
    def __init__(self, base_url: str, timeout_s: float = 20.0,
                 fail_threshold: int = 4, open_seconds: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout_s)
        self.breaker = Breaker(fail_threshold=fail_threshold, open_seconds=open_seconds)
        self.stats: dict[str, CallStat] = {}
        self.last_error: str | None = None
        self.gateway_quota: dict | None = None

    async def aclose(self) -> None:
        await self._client.aclose()

    def _stat(self, endpoint: str) -> CallStat:
        return self.stats.setdefault(endpoint, CallStat())

    async def _get(self, path: str, params: dict, endpoint: str) -> dict:
        if not self.breaker.allow():
            raise ProviderError(
                "BREAKER_OPEN",
                f"provider circuit breaker is open (retry in "
                f"{max(0, int(self.breaker.open_seconds - (time.time() - (self.breaker.opened_at or 0))))}s)",
                503, True,
            )

        stat = self._stat(endpoint)
        t0 = time.time()
        try:
            resp = await self._client.get(f"{self.base_url}{path}", params=params)
        except httpx.HTTPError as exc:
            stat.calls += 1
            stat.errors += 1
            self.breaker.record_failure()
            self.last_error = f"{type(exc).__name__}: {exc}"
            raise ProviderError("GATEWAY_UNREACHABLE", f"rail-gateway unreachable: {exc}", 503, True)

        latency = int((time.time() - t0) * 1000)
        stat.calls += 1
        stat.total_latency_ms += latency

        try:
            body = resp.json()
        except ValueError:
            stat.errors += 1
            self.breaker.record_failure()
            raise ProviderError("GATEWAY_BAD_RESPONSE", "gateway returned non-JSON", 502, True)

        if resp.status_code >= 400 or not body.get("ok"):
            err = body.get("error") or {}
            code = err.get("code", "PROVIDER_ERROR")
            retryable = bool(err.get("retryable"))
            # A 4xx is the provider answering correctly ("no such train"), not an
            # outage — it must NOT count toward opening the breaker.
            if resp.status_code >= 500 or code in ("GATEWAY_UNREACHABLE", "PROVIDER_TIMEOUT"):
                stat.errors += 1
                self.breaker.record_failure()
                self.last_error = f"{code}: {err.get('message')}"
            else:
                self.breaker.record_success()
            raise ProviderError(code, err.get("message", "provider call failed"),
                                resp.status_code, retryable)

        self.breaker.record_success()
        return body

    def _get_getinfo(self):
        if not hasattr(self, "_getinfo_adapter") or self._getinfo_adapter is None:
            try:
                from app.providers.getinfo_adapter import GetInfoAdapter
                self._getinfo_adapter = GetInfoAdapter()
            except Exception as e:
                self._getinfo_adapter = False
        return self._getinfo_adapter if self._getinfo_adapter else None

    # --- canonical calls --------------------------------------------------

    async def live_status(self, train_number: str, date: str | None = None) -> dict:
        params = {"train": train_number}
        if date:
            params["date"] = date
        try:
            return (await self._get("/internal/live", params, "live"))["data"]
        except ProviderError as exc:
            if exc.code in ("QUOTA_EXHAUSTED", "PROVIDER_QUOTA", "BREAKER_OPEN", "GATEWAY_UNREACHABLE", "PROVIDER_TIMEOUT", "PROVIDER_ERROR"):
                adapter = self._get_getinfo()
                if adapter:
                    try:
                        return adapter.live_status(train_number, date)
                    except Exception:
                        pass
            raise

    async def train_info(self, train_number: str) -> dict:
        try:
            return (await self._get("/internal/train", {"train": train_number}, "train"))["data"]
        except ProviderError as exc:
            if exc.code in ("QUOTA_EXHAUSTED", "PROVIDER_QUOTA", "BREAKER_OPEN", "GATEWAY_UNREACHABLE", "PROVIDER_TIMEOUT", "PROVIDER_ERROR"):
                adapter = self._get_getinfo()
                if adapter:
                    try:
                        return adapter.train_info(train_number)
                    except Exception:
                        pass
            raise

    async def station_board(self, station_code: str, hours: int = 2) -> dict:
        return (await self._get("/internal/board",
                                {"station": station_code, "hours": hours}, "board"))["data"]

    async def pnr(self, pnr: str) -> dict:
        try:
            return (await self._get("/internal/pnr", {"pnr": pnr}, "pnr"))["data"]
        except ProviderError as exc:
            if exc.code in ("QUOTA_EXHAUSTED", "PROVIDER_QUOTA", "BREAKER_OPEN", "GATEWAY_UNREACHABLE", "PROVIDER_TIMEOUT", "PROVIDER_ERROR"):
                adapter = self._get_getinfo()
                if adapter:
                    try:
                        return adapter.pnr(pnr)
                    except Exception:
                        pass
            raise

    async def health(self) -> dict:
        """Gateway health incl. its quota counters. Never raises: health must not 500."""
        try:
            resp = await self._client.get(f"{self.base_url}/health", timeout=5.0)
            body = resp.json()
            self.gateway_quota = body.get("quota")
            return {"reachable": True, **body}
        except Exception as exc:  # noqa: BLE001 - health degrades, never fails
            return {"reachable": False, "error": f"{type(exc).__name__}: {exc}"}

    def snapshot(self) -> dict:
        return {
            "breaker": {
                "state": self.breaker.state(),
                "failures": self.breaker.failures,
                "trips": self.breaker.trips,
                "threshold": self.breaker.fail_threshold,
            },
            "endpoints": {
                k: {"calls": v.calls, "errors": v.errors, "avgLatencyMs": v.avg_latency_ms()}
                for k, v in self.stats.items()
            },
            "lastError": self.last_error,
            "gatewayQuota": self.gateway_quota,
        }
