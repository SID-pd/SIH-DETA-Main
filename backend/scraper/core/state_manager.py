"""
State and checkpoint manager for scraper-erail.
Ensures large batch scrapes (14,000+ trains) are 100% resumable and idempotent.
"""

from __future__ import annotations

import datetime
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

from config.settings import STATE_DB_PATH


class StateManager:
    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = Path(db_path) if db_path else STATE_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scrape_tasks (
                    task_key        TEXT PRIMARY KEY,
                    task_type       TEXT NOT NULL,
                    target_id       TEXT NOT NULL,
                    status          TEXT NOT NULL, -- PENDING, RUNNING, COMPLETED, FAILED
                    attempts        INTEGER DEFAULT 0,
                    error_message   TEXT,
                    updated_at      TEXT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_type ON scrape_tasks(task_type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_status ON scrape_tasks(status);")
            conn.commit()

    def is_completed(self, task_key: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT status FROM scrape_tasks WHERE task_key = ?;", (task_key,)
            )
            row = cur.fetchone()
            return row is not None and row["status"] == "COMPLETED"

    def mark_completed(self, task_key: str, task_type: str, target_id: str) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO scrape_tasks (task_key, task_type, target_id, status, attempts, error_message, updated_at)
                VALUES (?, ?, ?, 'COMPLETED', 1, NULL, ?)
                ON CONFLICT(task_key) DO UPDATE SET
                    status='COMPLETED',
                    attempts=attempts + 1,
                    error_message=NULL,
                    updated_at=excluded.updated_at;
                """,
                (task_key, task_type, target_id, now),
            )
            conn.commit()

    def mark_failed(
        self, task_key: str, task_type: str, target_id: str, error: str
    ) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO scrape_tasks (task_key, task_type, target_id, status, attempts, error_message, updated_at)
                VALUES (?, ?, ?, 'FAILED', 1, ?, ?)
                ON CONFLICT(task_key) DO UPDATE SET
                    status='FAILED',
                    attempts=attempts + 1,
                    error_message=excluded.error_message,
                    updated_at=excluded.updated_at;
                """,
                (task_key, task_type, target_id, str(error)[:500], now),
            )
            conn.commit()

    def get_completed_targets(self, task_type: str) -> Set[str]:
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT target_id FROM scrape_tasks WHERE task_type = ? AND status = 'COMPLETED';",
                (task_type,),
            )
            return {row["target_id"] for row in cur.fetchall()}

    def filter_pending_targets(
        self, task_type: str, all_targets: List[str]
    ) -> List[str]:
        completed = self.get_completed_targets(task_type)
        return [t for t in all_targets if t not in completed]

    def reset_failed(self, task_type: Optional[str] = None) -> int:
        with self._get_connection() as conn:
            if task_type:
                cur = conn.execute(
                    "DELETE FROM scrape_tasks WHERE task_type = ? AND status = 'FAILED';",
                    (task_type,),
                )
            else:
                cur = conn.execute(
                    "DELETE FROM scrape_tasks WHERE status = 'FAILED';"
                )
            conn.commit()
            return cur.rowcount

    def get_summary(self) -> Dict[str, Dict[str, int]]:
        with self._get_connection() as conn:
            cur = conn.execute(
                """
                SELECT task_type, status, COUNT(*) as cnt
                FROM scrape_tasks
                GROUP BY task_type, status;
                """
            )
            summary: Dict[str, Dict[str, int]] = {}
            for row in cur.fetchall():
                t_type = row["task_type"]
                status = row["status"]
                cnt = row["cnt"]
                if t_type not in summary:
                    summary[t_type] = {}
                summary[t_type][status] = cnt
            return summary
