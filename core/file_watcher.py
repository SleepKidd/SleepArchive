from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path

from core.models import ExtractRule
from core.safety import is_archive

LOGGER = logging.getLogger(__name__)
ExtractCallback = Callable[[ExtractRule, Path], bool]


class FileWatcher:
    """Watchdog-based archive queue with debounce and duplicate suppression."""

    def __init__(self, callback: ExtractCallback, debounce_seconds: float = 2.0) -> None:
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self._observer = None
        self._pending: dict[tuple[str, str], float] = {}
        self._rules: dict[str, ExtractRule] = {}
        self._processing: set[tuple[str, str]] = set()
        self._processed: OrderedDict[tuple[str, int, int], None] = OrderedDict()
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None

    def start(self, rules: list[ExtractRule]) -> None:
        self.stop()
        enabled = [rule for rule in rules if rule.enabled and Path(rule.watch_folder).is_dir()]
        if not enabled:
            return
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            LOGGER.error("watchdog is not installed; automatic extraction is unavailable")
            return

        watcher = self

        class Handler(FileSystemEventHandler):
            def __init__(self, rule_id: str) -> None:
                super().__init__()
                self.rule_id = rule_id

            def on_created(self, event) -> None:
                if not event.is_directory:
                    watcher.enqueue(self.rule_id, Path(event.src_path))

            def on_modified(self, event) -> None:
                if not event.is_directory:
                    watcher.enqueue(self.rule_id, Path(event.src_path))

            def on_moved(self, event) -> None:
                if not event.is_directory:
                    watcher.enqueue(self.rule_id, Path(event.dest_path))

        self._rules = {rule.id: rule for rule in enabled}
        observer = Observer()
        for rule in enabled:
            observer.schedule(Handler(rule.id), rule.watch_folder, recursive=False)
        observer.start()
        self._observer = observer
        self._stop_event.clear()
        self._worker = threading.Thread(target=self._queue_loop, name="SleepArchiveWatcherQueue", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=3)
            self._observer = None
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=3)
        with self._lock:
            self._pending.clear()
            self._processing.clear()

    def enqueue(self, rule_id: str, path: Path) -> None:
        if not is_archive(path) or path.name.startswith("."):
            return
        rule = self._rules.get(rule_id)
        if rule is not None:
            try:
                if path.resolve().parent != Path(rule.watch_folder).resolve():
                    return
            except OSError:
                return
        key = (rule_id, str(path.resolve()))
        with self._lock:
            if key not in self._processing:
                self._pending[key] = time.monotonic()

    def _queue_loop(self) -> None:
        while not self._stop_event.wait(0.25):
            now = time.monotonic()
            with self._lock:
                due = [key for key, changed in self._pending.items() if now - changed >= self.debounce_seconds]
                for key in due:
                    self._pending.pop(key, None)
                    self._processing.add(key)
            for rule_id, raw_path in due:
                self._process(rule_id, Path(raw_path))

    def _process(self, rule_id: str, path: Path) -> None:
        key = (rule_id, str(path))
        try:
            rule = self._rules.get(rule_id)
            if rule is None or not path.is_file():
                return
            stat_result = path.stat()
            fingerprint = (str(path), stat_result.st_size, stat_result.st_mtime_ns)
            with self._lock:
                if fingerprint in self._processed:
                    return
            if self.callback(rule, path):
                with self._lock:
                    self._processed[fingerprint] = None
                    self._processed.move_to_end(fingerprint)
                    while len(self._processed) > 1_000:
                        self._processed.popitem(last=False)
        except OSError:
            LOGGER.warning("Queued archive disappeared: %s", path)
        except Exception:
            LOGGER.exception("Unhandled watcher callback failure for %s", path)
        finally:
            with self._lock:
                self._processing.discard(key)
