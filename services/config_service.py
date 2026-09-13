from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.models import ArchiveRule, ExtractRule


CONFIG_VERSION = 1
LOGGER = logging.getLogger(__name__)


def application_data_dir() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "SleepArchive"


@dataclass(slots=True)
class AppConfig:
    config_version: int = CONFIG_VERSION
    theme: str = "system"
    language: str = "ru"
    start_with_windows: bool = False
    start_minimized: bool = False
    minimize_to_tray: bool = True
    show_tray_hint: bool = True
    confirm_delete: bool = True
    show_preview: bool = True
    check_interval_minutes: int = 15
    notifications_success: bool = True
    notifications_errors: bool = True
    notifications_warnings: bool = True
    automation_paused: bool = False
    onboarding_complete: bool = False
    archive_rules: list[ArchiveRule] = field(default_factory=list)
    extract_rules: list[ExtractRule] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AppConfig":
        allowed = {field_name for field_name in cls.__dataclass_fields__}
        data = {key: value for key, value in raw.items() if key in allowed}
        data["archive_rules"] = [ArchiveRule.from_dict(item) for item in raw.get("archive_rules", [])]
        data["extract_rules"] = [ExtractRule.from_dict(item) for item in raw.get("extract_rules", [])]
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConfigService:
    """Versioned, atomic JSON settings with corrupt-file recovery."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.path = config_path or application_data_dir() / "config.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.config = self.load()

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                raw = json.load(stream)
            if not isinstance(raw, dict):
                raise ValueError("config root must be an object")
            if int(raw.get("config_version", 0)) > CONFIG_VERSION:
                raise ValueError("unsupported config version")
            return AppConfig.from_dict(raw)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            LOGGER.exception("Configuration is invalid; restoring defaults")
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = self.path.with_name(f"config.corrupt-{stamp}.json")
            try:
                shutil.copy2(self.path, backup)
            except OSError as exc:
                LOGGER.error("Unable to back up corrupt configuration: %s", exc)
            return AppConfig()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.sleeparchive_tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(self.config.to_dict(), stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)

    def reset(self) -> AppConfig:
        self.config = AppConfig(onboarding_complete=True)
        self.save()
        return self.config
