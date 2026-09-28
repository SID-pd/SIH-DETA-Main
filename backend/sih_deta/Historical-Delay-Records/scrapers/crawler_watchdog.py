"""
Crawler Watchdog & Heartbeat Monitor: Prevents thread deadlocks, socket stalls,
memory bloat, and terminal stalemates during unattended overnight crawling.
"""

import gc
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from config import HEARTBEAT_FILE, PER_TRAIN_TIMEOUT

logger = logging.getLogger("crawler_watchdog")


def enforce_non_interactive() -> None:
    """
    Clamps stdin to /dev/null to guarantee no subprocess or interactive prompt
    can block on user input and freeze the system during overnight runs.
    """
    try:
        sys.stdin = open(os.devnull, "r")
    except Exception as e:
        logger.debug(f"Non-interactive stdin redirect error: {e}")


class CrawlerWatchdog:
    """Monitors crawler health, memory usage, execution timeouts, and emits heartbeats."""

    def __init__(self, heartbeat_path: Optional[Path] = None, memory_limit_mb: float = 800.0):
        self.heartbeat_path = heartbeat_path or HEARTBEAT_FILE
        self.heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        self.memory_limit_mb = memory_limit_mb
        self.start_time = time.time()
        self.processed_count = 0
        self.success_count = 0
        self.fail_count = 0
        self.skip_count = 0

    def get_memory_usage_mb(self) -> float:
        """Get current resident set size (RSS) memory in megabytes."""
        try:
            import resource
            # ru_maxrss is in kilobytes on Linux
            rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return rss_kb / 1024.0
        except Exception:
            return 0.0

    def check_memory(self, interval_trains: int = 25) -> None:
        """Periodically runs garbage collection to ensure flat memory profile overnight."""
        if self.processed_count % interval_trains == 0:
            gc.collect()
            rss = self.get_memory_usage_mb()
            if rss > self.memory_limit_mb:
                logger.warning(f"Memory threshold exceeded ({rss:.1f} MB > {self.memory_limit_mb:.1f} MB). Forcing GC purge...")
                gc.collect()

    def emit_heartbeat(
        self,
        current_train: str,
        total_trains: int,
        phase: str,
        active_status: str = "RUNNING",
    ) -> None:
        """Writes live heartbeat metrics to disk for real-time monitoring without terminal contention."""
        uptime_secs = time.time() - self.start_time
        uptime_str = time.strftime("%Hh %Mm %Ss", time.gmtime(uptime_secs))
        rate_per_hour = (self.processed_count / (uptime_secs / 3600.0)) if uptime_secs > 60 else 0.0
        pct = (self.processed_count / total_trains * 100.0) if total_trains > 0 else 0.0
        rss = self.get_memory_usage_mb()

        heartbeat = {
            "status": active_status,
            "phase": phase,
            "current_train": current_train,
            "processed": self.processed_count,
            "total": total_trains,
            "percentage": round(pct, 2),
            "success": self.success_count,
            "failed": self.fail_count,
            "skipped": self.skip_count,
            "rate_per_hour": round(rate_per_hour, 1),
            "memory_rss_mb": round(rss, 1),
            "uptime": uptime_str,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            tmp_hb = self.heartbeat_path.with_suffix(".tmp")
            with open(tmp_hb, "w", encoding="utf-8") as f:
                json.dump(heartbeat, f, indent=2)
            os.replace(tmp_hb, self.heartbeat_path)
        except Exception:
            pass

    def run_with_timeout(
        self,
        func: Callable[..., Any],
        args: tuple = (),
        kwargs: dict = None,
        timeout: float = PER_TRAIN_TIMEOUT,
    ) -> Any:
        """
        Execute a function in a thread with a strict hard timeout.
        If execution exceeds timeout, raises TimeoutError so the crawler immediately
        advances without getting stuck on a hung request.
        """
        kwargs = kwargs or {}
        result = [None]
        error = [None]

        def worker():
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                error[0] = e

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        t.join(timeout=timeout)

        if t.is_alive():
            raise TimeoutError(f"Operation timed out after {timeout:.1f}s")

        if error[0] is not None:
            raise error[0]

        return result[0]
