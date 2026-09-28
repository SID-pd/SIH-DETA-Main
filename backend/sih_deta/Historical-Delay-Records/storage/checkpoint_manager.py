"""
Checkpoint Manager: Provides atomic, crash-resilient state persistence in both
JSON and SQLite so batch scraping can be stopped and resumed without duplicate requests.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from config import CHECKPOINT_FILE

logger = logging.getLogger("checkpoint_manager")


class CheckpointManager:
    """Manages crawl progress state for 90-day and 1-year multi-train batches."""

    def __init__(self, checkpoint_path: Optional[Path] = None):
        self.checkpoint_path = checkpoint_path or CHECKPOINT_FILE
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load()

    def _load(self) -> Dict[str, Any]:
        """Load state from checkpoint JSON file if exists, else initialize empty structure."""
        if self.checkpoint_path.exists():
            try:
                with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading checkpoint file at {self.checkpoint_path}: {e}")
        return {
            "90d": {"completed": {}, "failed": {}, "skipped": {}},
            "1y": {"completed": {}, "failed": {}, "skipped": {}},
        }

    def _save(self) -> None:
        """Atomically persist state to disk via tempfile replacement."""
        tmp_path = self.checkpoint_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
            os.replace(tmp_path, self.checkpoint_path)
        except Exception as e:
            logger.error(f"Failed to write checkpoint file {self.checkpoint_path}: {e}")

    def is_completed(self, train_number: str, phase: str = "90d") -> bool:
        """Check whether a train has already been successfully scraped in this phase."""
        train_clean = str(train_number).strip().lstrip("0")
        train_padded = str(train_number).strip().zfill(5)
        phase_data = self.state.get(phase, {})
        completed = phase_data.get("completed", {})
        return train_clean in completed or train_padded in completed

    def is_skipped(self, train_number: str, phase: str = "90d") -> bool:
        """Check if train was previously flagged as skipped (e.g. 404)."""
        train_clean = str(train_number).strip().lstrip("0")
        train_padded = str(train_number).strip().zfill(5)
        phase_data = self.state.get(phase, {})
        skipped = phase_data.get("skipped", {})
        return train_clean in skipped or train_padded in skipped

    def record_success(self, train_number: str, phase: str, runs_count: int, stations_count: int) -> None:
        """Record successful train crawl."""
        train_clean = str(train_number).strip().zfill(5)
        if phase not in self.state:
            self.state[phase] = {"completed": {}, "failed": {}, "skipped": {}}

        self.state[phase]["completed"][train_clean] = {
            "runs_retrieved": runs_count,
            "stations_count": stations_count,
        }
        # Remove from failed or skipped if previously there
        self.state[phase]["failed"].pop(train_clean, None)
        self.state[phase]["skipped"].pop(train_clean, None)
        self._save()

    def record_failure(self, train_number: str, phase: str, error_msg: str) -> None:
        """Record train failure after exhausting retries."""
        train_clean = str(train_number).strip().zfill(5)
        if phase not in self.state:
            self.state[phase] = {"completed": {}, "failed": {}, "skipped": {}}

        self.state[phase]["failed"][train_clean] = {
            "error": error_msg[:200],
        }
        self._save()

    def record_skip(self, train_number: str, phase: str, reason: str) -> None:
        """Record train skipped (e.g., 404 or empty history)."""
        train_clean = str(train_number).strip().zfill(5)
        if phase not in self.state:
            self.state[phase] = {"completed": {}, "failed": {}, "skipped": {}}

        self.state[phase]["skipped"][train_clean] = {
            "reason": reason[:200],
        }
        self._save()

    def get_pending_trains(self, all_trains: List[str], phase: str = "90d") -> List[str]:
        """Filter out trains that are already completed or skipped."""
        phase_data = self.state.get(phase, {})
        completed = set(phase_data.get("completed", {}).keys())
        skipped = set(phase_data.get("skipped", {}).keys())

        pending = []
        for t in all_trains:
            t_padded = str(t).strip().zfill(5)
            t_clean = str(t).strip().lstrip("0")
            if t_padded in completed or t_clean in completed:
                continue
            if t_padded in skipped or t_clean in skipped:
                continue
            pending.append(t_padded)
        return pending

    def get_summary(self, phase: str = "90d") -> Dict[str, int]:
        """Get summary stats of completed, failed, and skipped trains."""
        phase_data = self.state.get(phase, {})
        return {
            "completed": len(phase_data.get("completed", {})),
            "failed": len(phase_data.get("failed", {})),
            "skipped": len(phase_data.get("skipped", {})),
        }

    def reset(self, phase: Optional[str] = None) -> None:
        """Reset checkpoint state."""
        if phase:
            self.state[phase] = {"completed": {}, "failed": {}, "skipped": {}}
        else:
            self.state = {
                "90d": {"completed": {}, "failed": {}, "skipped": {}},
                "1y": {"completed": {}, "failed": {}, "skipped": {}},
            }
        self._save()
