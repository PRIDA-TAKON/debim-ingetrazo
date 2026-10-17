"""
Background File Watcher for debim-ingetrazo.
Monitors a target .debim file for changes and triggers viewport hot-reloading.
"""

import hashlib
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from debim_ingetrazo.builder import BuildingModel, build_geometry
from debim_ingetrazo.parser import parse_debim_file

logger = logging.getLogger("debim_ingetrazo.watcher")


class DebimWatcher:
    """
    Background file watcher thread monitoring a target .debim file.
    When changes are detected, re-parses and re-renders automatically.
    """

    def __init__(
        self,
        file_path: Optional[Union[str, Path]] = None,
        poll_interval: float = 0.5,
        on_file_changed: Optional[Callable[[Path, Dict[str, Any], BuildingModel], Any]] = None,
    ):
        self.file_path: Optional[Path] = Path(file_path).resolve() if file_path else None
        self.poll_interval = poll_interval
        self.on_file_changed = on_file_changed

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_mtime: float = 0.0
        self._last_hash: str = ""

    @property
    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    def set_target_file(self, file_path: Union[str, Path]) -> None:
        """Set or update the target .debim file path to monitor."""
        path = Path(file_path).resolve()
        self.file_path = path
        self._reset_file_state()

    def _reset_file_state(self) -> None:
        if self.file_path and self.file_path.exists():
            try:
                self._last_mtime = self.file_path.stat().st_mtime
                self._last_hash = self._calculate_hash(self.file_path)
            except Exception:
                self._last_mtime = 0.0
                self._last_hash = ""
        else:
            self._last_mtime = 0.0
            self._last_hash = ""

    @staticmethod
    def _calculate_hash(path: Path) -> str:
        try:
            with open(path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""

    def start(self) -> None:
        """Starts background file polling."""
        if self._running:
            return

        self._reset_file_state()
        self._running = True
        self._thread = threading.Thread(
            target=self._watch_loop, daemon=True, name="DebimFileWatcherThread"
        )
        self._thread.start()
        logger.info("DebimWatcher started for path: %s", self.file_path)

    def stop(self) -> None:
        """Stops background file polling."""
        if not self._running:
            return

        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        logger.info("DebimWatcher stopped.")

    def check_now(self) -> bool:
        """
        Manually trigger a check on the file mtime/hash.
        Returns True if a change was detected and processed, False otherwise.
        """
        if not self.file_path or not self.file_path.exists():
            return False

        try:
            current_mtime = self.file_path.stat().st_mtime
            if current_mtime != self._last_mtime:
                current_hash = self._calculate_hash(self.file_path)
                if current_hash != self._last_hash and current_hash != "":
                    self._last_mtime = current_mtime
                    self._last_hash = current_hash
                    self._trigger_change_event()
                    return True
                self._last_mtime = current_mtime
        except Exception as e:
            logger.error("Error checking target file %s: %s", self.file_path, e)

        return False

    def _watch_loop(self) -> None:
        while self._running:
            time.sleep(self.poll_interval)
            if not self._running:
                break
            self.check_now()

    def _trigger_change_event(self) -> None:
        if not self.file_path or not self.file_path.exists():
            return

        logger.info("File change detected: %s. Re-rendering viewport...", self.file_path)

        try:
            manifest_dict = parse_debim_file(self.file_path)
            building_model = build_geometry(manifest_dict)

            if self.on_file_changed:
                self.on_file_changed(self.file_path, manifest_dict, building_model)
        except Exception as e:
            logger.exception("Failed to re-render model from modified file %s: %s", self.file_path, e)
