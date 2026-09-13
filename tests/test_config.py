from __future__ import annotations

import json
from pathlib import Path

from core.models import ArchiveRule, ExtractRule
from services.config_service import AppConfig, ConfigService


def test_config_round_trip_with_rules(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    service = ConfigService(path)
    service.config.theme = "dark"
    service.config.archive_rules.append(ArchiveRule("Docs", str(tmp_path / "docs"), str(tmp_path / "out")))
    service.config.extract_rules.append(ExtractRule("Downloads", str(tmp_path / "downloads")))
    service.save()
    loaded = ConfigService(path).config
    assert loaded.theme == "dark"
    assert loaded.archive_rules[0].name == "Docs"
    assert loaded.extract_rules[0].name == "Downloads"


def test_missing_config_uses_defaults(tmp_path: Path) -> None:
    config = ConfigService(tmp_path / "missing.json").config
    assert config.theme == "system"
    assert config.archive_rules == []


def test_corrupt_config_is_backed_up_and_recovers(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{broken", encoding="utf-8")
    service = ConfigService(path)
    assert service.config == AppConfig()
    assert list(tmp_path.glob("config.corrupt-*.json"))


def test_unknown_fields_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"config_version": 1, "future_option": True}), encoding="utf-8")
    assert ConfigService(path).config.config_version == 1


def test_save_is_atomic_and_leaves_no_temp_file(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    service = ConfigService(path)
    service.save()
    assert path.exists()
    assert not path.with_suffix(".json.sleeparchive_tmp").exists()

