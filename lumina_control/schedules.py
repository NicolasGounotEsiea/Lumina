"""Time-based schedule automation — apply a named profile during a time window."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field

log = logging.getLogger(__name__)


@dataclass
class Schedule:
    """Apply a named profile during a configurable time window.

    ``start_hour`` and ``end_hour`` are integers 0–23.
    When ``start_hour > end_hour`` the window wraps midnight
    (e.g. 22 → 7 means 22:00–06:59).
    ``days`` is a list of weekday integers: 0 = Monday … 6 = Sunday.
    """

    name:        str
    profile:     str          # name of the named profile to apply
    start_hour:  int          # 0–23 inclusive
    end_hour:    int          # 0–23 exclusive (next hour)
    days:        list[int] = field(default_factory=lambda: list(range(7)))
    enabled:     bool = True

    def is_active_now(self) -> bool:
        """Return True if this schedule should be active right now."""
        from datetime import datetime
        now = datetime.now()
        if now.weekday() not in self.days:
            return False
        h = now.hour
        if self.start_hour <= self.end_hour:
            return self.start_hour <= h < self.end_hour
        # Wraps midnight
        return h >= self.start_hour or h < self.end_hour


class ScheduleManager:
    """JSON persistence for Schedule objects."""

    def __init__(self, path: str) -> None:
        self._path = path

    def load(self) -> list[Schedule]:
        if not os.path.exists(self._path):
            return []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            result: list[Schedule] = []
            for d in data:
                result.append(Schedule(
                    name       = str(d.get("name", "")),
                    profile    = str(d.get("profile", "")),
                    start_hour = int(d.get("start_hour", 22)),
                    end_hour   = int(d.get("end_hour", 7)),
                    days       = list(d.get("days", list(range(7)))),
                    enabled    = bool(d.get("enabled", True)),
                ))
            return result
        except Exception as exc:
            log.warning("Cannot load schedules: %s", exc)
            return []

    def save(self, schedules: list[Schedule]) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump([asdict(s) for s in schedules], f, indent=2, ensure_ascii=False)
        except OSError as exc:
            log.warning("Cannot save schedules: %s", exc)
