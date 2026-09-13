from __future__ import annotations

from pathlib import Path

import pytest

from core.models import ArchiveRule, ExtractDestination, ExtractRule
from core.rule_manager import RuleManager
from services.config_service import ConfigService


def test_rule_manager_persists_and_updates(tmp_path: Path) -> None:
    service = ConfigService(tmp_path / "config.json")
    manager = RuleManager(service)
    rule = ArchiveRule("Docs", str(tmp_path / "source"), str(tmp_path / "out"))
    manager.save_archive(rule)
    rule.age_days = 90
    manager.save_archive(rule)
    assert len(manager.archive_rules) == 1
    assert ConfigService(service.path).config.archive_rules[0].age_days == 90


def test_duplicate_rule_gets_new_id_and_is_disabled(tmp_path: Path) -> None:
    manager = RuleManager(ConfigService(tmp_path / "config.json"))
    source = ArchiveRule("Docs", str(tmp_path / "source"), str(tmp_path / "out"))
    manager.save_archive(source)
    duplicate = manager.duplicate_archive(source.id)
    assert duplicate.id != source.id
    assert not duplicate.enabled
    assert "копия" in duplicate.name


def test_delete_rule_does_not_touch_files(tmp_path: Path) -> None:
    important = tmp_path / "important.txt"
    important.write_text("keep")
    manager = RuleManager(ConfigService(tmp_path / "config.json"))
    rule = ExtractRule("Watch", str(tmp_path))
    manager.save_extract(rule)
    manager.delete_extract(rule.id)
    assert important.read_text() == "keep"
    assert manager.extract_rules == []


def test_archive_rule_rejects_same_source_and_destination(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="должны отличаться"):
        ArchiveRule("Bad", str(tmp_path), str(tmp_path)).validate()


def test_selected_extract_destination_is_required(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="папку распаковки"):
        ExtractRule("Bad", str(tmp_path), destination_mode=ExtractDestination.SELECTED_FOLDER).validate()

