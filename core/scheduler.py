from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from core.models import ArchiveRule, ScheduleKind

LOGGER = logging.getLogger(__name__)
RunCallback = Callable[[ArchiveRule], None]


class ArchiveScheduler:
    """Small background scheduler that never overlaps the same rule."""

    def __init__(self, rules_provider: Callable[[], list[ArchiveRule]], run_callback: RunCallback) -> None:
        self._rules_provider = rules_provider
        self._run_callback = run_callback
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running: set[str] = set()
        self._lock = threading.Lock()
        self._startup_dispatched: set[str] = set()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name="SleepArchiveScheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def mark_finished(self, rule_id: str) -> None:
        with self._lock:
            self._running.discard(rule_id)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            now = datetime.now(timezone.utc)
            for rule in self._rules_provider():
                if self._stop_event.is_set():
                    break
                if rule.enabled and self._is_due(rule, now) and self._claim(rule.id):
                    try:
                        self._run_callback(rule)
                    except Exception:
                        self.mark_finished(rule.id)
                        LOGGER.exception("Unable to dispatch scheduled rule %s", rule.id)
            self._stop_event.wait(30)

    def _claim(self, rule_id: str) -> bool:
        with self._lock:
            if rule_id in self._running:
                return False
            self._running.add(rule_id)
            return True

    def _is_due(self, rule: ArchiveRule, now: datetime) -> bool:
        if rule.schedule == ScheduleKind.MANUAL:
            return False
        if rule.schedule == ScheduleKind.STARTUP:
            if rule.id in self._startup_dispatched:
                return False
            self._startup_dispatched.add(rule.id)
            return True
        if not rule.last_run:
            return True
        try:
            last_run = datetime.fromisoformat(rule.last_run)
            if last_run.tzinfo is None:
                last_run = last_run.replace(tzinfo=timezone.utc)
        except ValueError:
            return True
        interval = timedelta(days=1 if rule.schedule == ScheduleKind.DAILY else 7)
        return now - last_run >= interval

