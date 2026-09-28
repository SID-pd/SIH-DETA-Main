"""
Two-Tier Cache Manager (In-Memory + SQLite Persistent).
Ensures zero-latency duplicate lookups and protects external providers from rate limiting.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

from config import CACHE_DB_PATH

logger = logging.getLogger("getinfo.cache")


class TieredCache:
    """
    Two-tier cache:
    Level 1: In-memory LRU-like dictionary for microsecond lookups within process.
    Level 2: SQLite database for cross-process / persistent TTL caching.
    """

    def __init__(self, db_path: Path = CACHE_DB_PATH):
        self.db_path = db_path
        self._mem_cache: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache_store (
                        cache_key TEXT PRIMARY KEY,
                        value_json TEXT NOT NULL,
                        expires_at REAL NOT NULL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_store(expires_at)")
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to initialize SQLite cache at {self.db_path}: {e}")

    def get(self, key: str) -> Optional[Any]:
        """Retrieves cached value if present and not expired."""
        now = time.time()

        # Check Memory Cache first (Level 1)
        import copy
        with self._lock:
            if key in self._mem_cache:
                expires_at, val = self._mem_cache[key]
                if now < expires_at:
                    return copy.deepcopy(val)
                else:
                    del self._mem_cache[key]

        # Check SQLite Cache (Level 2)
        try:
            with sqlite3.connect(self.db_path, timeout=3.0) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT value_json, expires_at FROM cache_store WHERE cache_key = ?",
                    (key,),
                )
                row = cursor.fetchone()
                if row:
                    val_json, expires_at = row
                    if now < expires_at:
                        val = json.loads(val_json)
                        # Backfill into memory
                        with self._lock:
                            self._mem_cache[key] = (expires_at, val)
                        return val
                    else:
                        # Clean expired row
                        cursor.execute("DELETE FROM cache_store WHERE cache_key = ?", (key,))
                        conn.commit()
        except Exception as e:
            logger.debug(f"Cache read error for key {key}: {e}")

        return None

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        """Saves value into both Level 1 (memory) and Level 2 (SQLite) caches."""
        if ttl_seconds <= 0:
            return

        expires_at = time.time() + ttl_seconds

        # Set in Memory (Level 1)
        with self._lock:
            self._mem_cache[key] = (expires_at, value)

        # Set in SQLite (Level 2)
        try:
            val_json = json.dumps(value)
            with sqlite3.connect(self.db_path, timeout=3.0) as conn:
                conn.execute(
                    """
                    INSERT INTO cache_store (cache_key, value_json, expires_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        value_json = excluded.value_json,
                        expires_at = excluded.expires_at
                    """,
                    (key, val_json, expires_at),
                )
                conn.commit()
        except Exception as e:
            logger.debug(f"Cache write error for key {key}: {e}")

    def clear_expired(self) -> int:
        """Prunes expired entries from SQLite and memory."""
        now = time.time()
        with self._lock:
            expired_keys = [k for k, (exp, _) in self._mem_cache.items() if now >= exp]
            for k in expired_keys:
                del self._mem_cache[k]

        deleted_count = 0
        try:
            with sqlite3.connect(self.db_path, timeout=3.0) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM cache_store WHERE expires_at <= ?", (now,))
                deleted_count = cursor.rowcount
                conn.commit()
        except Exception as e:
            logger.debug(f"Error purging expired cache: {e}")
        return deleted_count

    def clear_all(self) -> int:
        """Completely flushes all cache entries from memory and SQLite."""
        with self._lock:
            self._mem_cache.clear()

        deleted_count = 0
        try:
            with sqlite3.connect(self.db_path, timeout=3.0) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM cache_store")
                deleted_count = cursor.rowcount
                conn.commit()
        except Exception as e:
            logger.debug(f"Error clearing cache: {e}")
        return deleted_count


# Global singleton instance
cache = TieredCache()
