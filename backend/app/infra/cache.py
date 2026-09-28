"""
Cache with single-flight and stale-while-revalidate.

Why this module is load-bearing (plan §2.1.4, R1):
third-party rail APIs are quota-metered and slow (0.5-2.6s observed). Without
single-flight, 500 users tracking 12301 during a demo produce 500 upstream calls and
exhaust the daily budget in minutes. With it they produce ONE call per TTL window.

Two adapters behind one interface (ports & adapters):
    MemoryCache  - in-process, zero infrastructure, correct for a single API process
    RedisCache   - drop-in for multi-process/multi-instance deployment

`get_or_load` returns (value, state) where state is one of:
    "fresh"  - served from a live upstream call
    "cache"  - served from a valid cached entry
    "stale"  - upstream failed, served an EXPIRED entry within the grace window
Callers put this straight into the response envelope's meta.source, so a stale answer
is visibly stale to the user rather than silently wrong (ADR-004).
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol


@dataclass
class Entry:
    value: Any
    stored_at: float
    expires_at: float

    def is_fresh(self, now: float) -> bool:
        return now < self.expires_at

    def within_grace(self, now: float, grace_s: int) -> bool:
        return now < self.expires_at + grace_s


class CacheBackend(Protocol):
    async def get(self, key: str) -> Entry | None: ...
    async def set(self, key: str, entry: Entry) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def keys(self) -> list[str]: ...


class MemoryCache:
    """In-process cache. Bounded by `max_entries` with oldest-first eviction."""

    def __init__(self, max_entries: int = 5000) -> None:
        self._data: dict[str, Entry] = {}
        self._max = max_entries

    async def get(self, key: str) -> Entry | None:
        return self._data.get(key)

    async def set(self, key: str, entry: Entry) -> None:
        if len(self._data) >= self._max and key not in self._data:
            # Evict the entry that expired longest ago (or is closest to expiry).
            oldest = min(self._data.items(), key=lambda kv: kv[1].expires_at)[0]
            self._data.pop(oldest, None)
        self._data[key] = entry

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def keys(self) -> list[str]:
        return list(self._data)


class RedisCache:
    """
    Redis adapter. Not exercised in the current deployment (no Redis running yet),
    but present so the swap is a config change rather than a rewrite. Values are
    JSON-encoded; entries carry their own timestamps so the stale-grace logic works
    identically to MemoryCache (Redis TTL alone cannot express "expired but usable").
    """

    def __init__(self, url: str, namespace: str = "darpan") -> None:
        import redis.asyncio as aioredis  # imported lazily: optional dependency

        self._r = aioredis.from_url(url, decode_responses=True)
        self._ns = namespace

    def _k(self, key: str) -> str:
        return f"{self._ns}:{key}"

    async def get(self, key: str) -> Entry | None:
        import json

        raw = await self._r.get(self._k(key))
        if not raw:
            return None
        d = json.loads(raw)
        return Entry(d["v"], d["s"], d["e"])

    async def set(self, key: str, entry: Entry) -> None:
        import json

        payload = json.dumps({"v": entry.value, "s": entry.stored_at, "e": entry.expires_at})
        # Physical TTL is generous so an expired-but-usable entry survives for the
        # stale-grace path; logical freshness is decided by expires_at.
        ttl = max(60, int(entry.expires_at - time.time()) + 3600)
        await self._r.set(self._k(key), payload, ex=ttl)

    async def delete(self, key: str) -> None:
        await self._r.delete(self._k(key))

    async def keys(self) -> list[str]:
        return [k.split(":", 1)[1] for k in await self._r.keys(f"{self._ns}:*")]


class Cache:
    """Coordinator: TTL policy + single-flight + stale-while-revalidate + stats."""

    def __init__(self, backend: CacheBackend, stale_grace_s: int = 900) -> None:
        self.backend = backend
        self.stale_grace_s = stale_grace_s
        self._inflight: dict[str, asyncio.Task] = {}
        self.stats = {"hit": 0, "miss": 0, "stale": 0, "single_flight_joins": 0, "error": 0}

    def hit_ratio(self) -> float:
        served = self.stats["hit"] + self.stats["miss"] + self.stats["stale"]
        return round(self.stats["hit"] / served, 4) if served else 0.0

    async def get_or_load(
        self,
        key: str,
        ttl_s: int,
        loader: Callable[[], Awaitable[Any]],
        *,
        allow_stale: bool = True,
    ) -> tuple[Any, str]:
        now = time.time()
        entry = await self.backend.get(key)

        if entry and entry.is_fresh(now):
            self.stats["hit"] += 1
            return entry.value, "cache"

        # Single-flight: concurrent callers for the same key await one upstream call.
        existing = self._inflight.get(key)
        if existing is not None:
            self.stats["single_flight_joins"] += 1
            try:
                value = await asyncio.shield(existing)
                return value, "cache"
            except Exception:
                # The shared load failed; fall through to the stale path below.
                entry = await self.backend.get(key)
                if allow_stale and entry and entry.within_grace(time.time(), self.stale_grace_s):
                    self.stats["stale"] += 1
                    return entry.value, "stale"
                raise

        async def _run() -> Any:
            value = await loader()
            await self.backend.set(key, Entry(value, time.time(), time.time() + ttl_s))
            return value

        task = asyncio.create_task(_run())
        self._inflight[key] = task
        try:
            value = await task
            self.stats["miss"] += 1
            return value, "fresh"
        except Exception:
            self.stats["error"] += 1
            # Upstream failed. Serve expired data ONLY if labelled stale.
            if allow_stale and entry and entry.within_grace(time.time(), self.stale_grace_s):
                self.stats["stale"] += 1
                return entry.value, "stale"
            raise
        finally:
            self._inflight.pop(key, None)
