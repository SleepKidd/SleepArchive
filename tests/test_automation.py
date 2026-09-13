from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.file_watcher import FileWatcher
from core.models import ArchiveRule, ExtractRule, ScheduleKind
from core.safety import wait_until_stable
from core.scheduler import ArchiveScheduler


def test_file_watcher_ignores_non_archives(tmp_path: Path) -> None:
    watcher = FileWatcher(lambda _rule, _path: True)
    watcher.enqueue("rule", tmp_path / "notes.txt")
    assert watcher._pending == {}


def test_file_watcher_debounces_same_archive(tmp_path: Path) -> None:
    watcher = FileWatcher(lambda _rule, _path: True)
    path = tmp_path / "data.zip"
    watcher.enqueue("rule", path)
    first = watcher._pending[("rule", str(path.resolve()))]
    time.sleep(0.01)
    watcher.enqueue("rule", path)
    assert watcher._pending[("rule", str(path.resolve()))] > first


def test_file_watcher_ignores_archive_moved_into_own_output(tmp_path: Path) -> None:
    watch = tmp_path / "Downloads"
    moved = watch / "Archives" / "data.zip"
    moved.parent.mkdir(parents=True)
    moved.write_bytes(b"archive")
    watcher = FileWatcher(lambda _rule, _path: True)
    rule = ExtractRule("Downloads", str(watch))
    watcher._rules[rule.id] = rule
    watcher.enqueue(rule.id, moved)
    assert watcher._pending == {}


def test_stability_check_accepts_unchanged_file(tmp_path: Path) -> None:
    path = tmp_path / "stable.zip"
    path.write_bytes(b"stable")
    assert wait_until_stable(path, stable_seconds=0, timeout_seconds=1, poll_interval=0.01)


def test_scheduler_due_logic() -> None:
    scheduler = ArchiveScheduler(lambda: [], lambda _rule: None)
    now = datetime.now(timezone.utc)
    daily = ArchiveRule("Daily", "/source", "/out", schedule=ScheduleKind.DAILY)
    assert scheduler._is_due(daily, now)
    daily.last_run = (now - timedelta(hours=1)).isoformat()
    assert not scheduler._is_due(daily, now)
    daily.last_run = (now - timedelta(days=2)).isoformat()
    assert scheduler._is_due(daily, now)


def test_scheduler_claim_prevents_overlap() -> None:
    scheduler = ArchiveScheduler(lambda: [], lambda _rule: None)
    assert scheduler._claim("same")
    assert not scheduler._claim("same")
    scheduler.mark_finished("same")
    assert scheduler._claim("same")
