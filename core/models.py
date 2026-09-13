from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4


class ArchiveFormat(StrEnum):
    ZIP = "zip"
    SEVEN_ZIP = "7z"


class Grouping(StrEnum):
    MONTH = "month"
    YEAR = "year"
    SINGLE = "single"


class OriginalAction(StrEnum):
    KEEP = "keep"
    MOVE = "move"
    DELETE = "delete"


class ExtractDestination(StrEnum):
    BESIDE_ARCHIVE = "beside"
    SELECTED_FOLDER = "selected"


class ScheduleKind(StrEnum):
    MANUAL = "manual"
    STARTUP = "startup"
    DAILY = "daily"
    WEEKLY = "weekly"


class RuleStatus(StrEnum):
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    DISABLED = "disabled"


class HistoryKind(StrEnum):
    ARCHIVE = "archive"
    EXTRACT = "extract"
    WARNING = "warning"
    ERROR = "error"


@dataclass(slots=True)
class ArchiveRule:
    name: str
    source: str
    destination: str
    id: str = field(default_factory=lambda: uuid4().hex)
    enabled: bool = True
    age_days: int = 30
    recursive: bool = True
    archive_format: ArchiveFormat = ArchiveFormat.ZIP
    compression_level: int = 6
    grouping: Grouping = Grouping.MONTH
    exclusions: list[str] = field(default_factory=list)
    schedule: ScheduleKind = ScheduleKind.MANUAL
    original_action: OriginalAction = OriginalAction.KEEP
    move_destination: str = ""
    last_run: str | None = None
    processed_files: int = 0
    processed_bytes: int = 0

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("Укажите название правила.")
        if self.age_days < 0:
            raise ValueError("Возраст файлов не может быть отрицательным.")
        if not 0 <= self.compression_level <= 9:
            raise ValueError("Уровень сжатия должен быть от 0 до 9.")
        if not self.source or not self.destination:
            raise ValueError("Выберите исходную папку и папку архива.")
        if Path(self.source).resolve() == Path(self.destination).resolve():
            raise ValueError("Исходная папка и папка архива должны отличаться.")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArchiveRule":
        allowed = {field_name for field_name in cls.__dataclass_fields__}
        clean = {key: value for key, value in data.items() if key in allowed}
        clean["archive_format"] = ArchiveFormat(clean.get("archive_format", "zip"))
        clean["grouping"] = Grouping(clean.get("grouping", "month"))
        clean["schedule"] = ScheduleKind(clean.get("schedule", "manual"))
        clean["original_action"] = OriginalAction(clean.get("original_action", "keep"))
        return cls(**clean)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExtractRule:
    name: str
    watch_folder: str
    id: str = field(default_factory=lambda: uuid4().hex)
    enabled: bool = True
    destination_mode: ExtractDestination = ExtractDestination.BESIDE_ARCHIVE
    destination: str = ""
    archive_action: OriginalAction = OriginalAction.KEEP
    archive_move_destination: str = ""
    stability_seconds: int = 3
    last_run: str | None = None
    processed_archives: int = 0
    extracted_files: int = 0

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("Укажите название правила.")
        if not self.watch_folder:
            raise ValueError("Выберите папку наблюдения.")
        if self.destination_mode == ExtractDestination.SELECTED_FOLDER and not self.destination:
            raise ValueError("Выберите папку распаковки.")
        if self.stability_seconds < 1:
            raise ValueError("Задержка стабильности должна быть не меньше секунды.")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExtractRule":
        allowed = {field_name for field_name in cls.__dataclass_fields__}
        clean = {key: value for key, value in data.items() if key in allowed}
        clean["destination_mode"] = ExtractDestination(clean.get("destination_mode", "beside"))
        clean["archive_action"] = OriginalAction(clean.get("archive_action", "keep"))
        return cls(**clean)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PreviewItem:
    source: Path
    relative_path: Path
    size: int
    group_name: str
    mtime_ns: int


@dataclass(slots=True)
class ArchivePreview:
    included: list[PreviewItem] = field(default_factory=list)
    excluded: list[Path] = field(default_factory=list)
    archives: dict[str, list[PreviewItem]] = field(default_factory=dict)

    @property
    def total_size(self) -> int:
        return sum(item.size for item in self.included)


@dataclass(slots=True)
class OperationResult:
    success: bool
    message: str
    files_count: int = 0
    bytes_count: int = 0
    output_paths: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cancelled: bool = False


@dataclass(slots=True)
class ProgressUpdate:
    current: int
    total: int
    current_file: str
    bytes_done: int
    bytes_total: int


@dataclass(slots=True)
class HistoryEntry:
    kind: HistoryKind
    title: str
    details: str
    success: bool
    id: str = field(default_factory=lambda: uuid4().hex)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    files_count: int = 0
    bytes_count: int = 0
    rule_id: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HistoryEntry":
        clean = dict(data)
        clean["kind"] = HistoryKind(clean.get("kind", "warning"))
        return cls(**clean)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
