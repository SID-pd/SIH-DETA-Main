"""Runtime configuration. All provider/infra choices are OPS config, never user config.

This module is the direct answer to defect H3/D1 in the plan: the old frontend let a
user pick a provider and paste an API key into localStorage. Provider selection and
credentials now live here, server-side, and the client cannot influence them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _find_path(rel_path: str) -> str:
    candidates = [
        os.path.join(REPO_ROOT, rel_path),
        os.path.join(os.path.dirname(__file__), "..", rel_path),
        os.path.join(os.path.dirname(__file__), "..", "..", rel_path),
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return os.path.join(REPO_ROOT, rel_path)


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    # --- surface ---
    api_port: int = _int("API_PORT", 8001)
    cors_origins: tuple[str, ...] = field(default_factory=lambda: tuple(
        os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,https://doorpost-smashing-regime.ngrok-free.dev").split(",")
    ))

    # --- data store (SQLite now, Postgres via the same repo interface later) ---
    db_path: str = os.environ.get("DARPAN_DB", _find_path(os.path.join("data", "darpan.sqlite")))

    # --- provider gateway (the only egress path) ---
    gateway_url: str = os.environ.get("GATEWAY_URL", "http://127.0.0.1:8081")
    gateway_timeout_s: float = float(os.environ.get("GATEWAY_TIMEOUT_S", "20"))

    # --- cache & Redis configuration ---
    redis_url: str | None = os.environ.get("REDIS_URL")
    ttl_live: int = _int("TTL_LIVE", 45)
    ttl_board: int = _int("TTL_BOARD", 60)
    ttl_train: int = _int("TTL_TRAIN", 7 * 24 * 3600)
    ttl_pnr: int = _int("TTL_PNR", 60)
    ttl_popular: int = _int("TTL_POPULAR", 300)
    # Serve-stale window AFTER expiry when the provider is unreachable. Stale data
    # labelled stale is acceptable; invented data never is (ADR-004).
    stale_grace_s: int = _int("STALE_GRACE_S", 900)

    # --- circuit breaker ---
    breaker_fail_threshold: int = _int("BREAKER_FAIL_THRESHOLD", 4)
    breaker_open_seconds: int = _int("BREAKER_OPEN_SECONDS", 30)

    # --- rate limiting (per client IP) ---
    rate_limit_per_min: int = _int("RATE_LIMIT_PER_MIN", 120)

    # --- ETA engine ---
    # Recovery modelling is OFF by default and deliberately so: a train's ability to
    # recover delay in halt padding varies hugely by route, and we have no measured
    # per-segment recovery until the nightly backfill has real observations. Inventing
    # a recovery constant would fabricate optimism. Pure persistence is the honest
    # baseline until segments.hist_delay_added_p50 is populated (plan §5.3 M0 -> M2).
    eta_recovery_enabled: bool = _bool("ETA_RECOVERY_ENABLED", False)
    eta_segment_min_obs: int = _int("ETA_SEGMENT_MIN_OBS", 5)

    # --- PNR privacy ---
    # Salt for the PNR cache key. A PNR is personal data; it must never appear in a
    # cache key, log line, or metric label in the clear (plan D7 / §8 Privacy).
    pnr_cache_salt: str = os.environ.get("PNR_CACHE_SALT", "darpan-dev-salt-change-me")

    # --- accuracy telemetry ---
    # Records every ETA served, so §7.2 can score us against reality later. Calendar-
    # bound like the harvester: predictions not recorded today cannot be scored later.
    record_snapshots: bool = _bool("RECORD_SNAPSHOTS", True)

    # --- model ---
    model_path: str = os.environ.get("ETA_MODEL", _find_path("eta_model.joblib"))
    model_enabled: bool = _bool("MODEL_ENABLED", True)


settings = Settings()
