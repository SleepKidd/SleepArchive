from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from core.models import HistoryEntry
from services.config_service import application_data_dir

LOGGER = logging.getLogger(__name__)


class HistoryService:
    def __init__(self, path: Path | None = None, limit: int = 2_000) -> None:
        self.path = path or application_data_dir() / "history.json"
        self.limit = limit
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_entries(self) -> list[HistoryEntry]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                raw = json.load(stream)
            if not isinstance(raw, list):
                return []
            entries: list[HistoryEntry] = []
            for item in raw:
                try:
                    entries.append(HistoryEntry.from_dict(item))
                except (TypeError, ValueError) as exc:
                    LOGGER.warning("Skipping invalid history entry: %s", exc)
                    continue
            return entries
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("Unable to read operation history: %s", exc)
            return []

    def add(self, entry: HistoryEntry) -> None:
        entries = self.list_entries()
        entries.insert(0, entry)
        self._write(entries[: self.limit])

    def clear(self) -> None:
        self._write([])

    def _write(self, entries: list[HistoryEntry]) -> None:
        temporary = self.path.with_suffix(".json.sleeparchive_tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump([entry.to_dict() for entry in entries], stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)
