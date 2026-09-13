from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

from core.models import ArchiveRule, ExtractRule
from services.config_service import ConfigService


class RuleManager:
    """Single mutation point for persisted automation rules."""

    def __init__(self, config_service: ConfigService) -> None:
        self.config_service = config_service

    @property
    def archive_rules(self) -> list[ArchiveRule]:
        return self.config_service.config.archive_rules

    @property
    def extract_rules(self) -> list[ExtractRule]:
        return self.config_service.config.extract_rules

    def save_archive(self, rule: ArchiveRule) -> ArchiveRule:
        rule.validate()
        self._upsert(self.archive_rules, rule)
        self.config_service.save()
        return rule

    def save_extract(self, rule: ExtractRule) -> ExtractRule:
        rule.validate()
        self._upsert(self.extract_rules, rule)
        self.config_service.save()
        return rule

    def archive(self, rule_id: str) -> ArchiveRule:
        return self._find(self.archive_rules, rule_id)

    def extract(self, rule_id: str) -> ExtractRule:
        return self._find(self.extract_rules, rule_id)

    def delete_archive(self, rule_id: str) -> None:
        self.config_service.config.archive_rules = [rule for rule in self.archive_rules if rule.id != rule_id]
        self.config_service.save()

    def delete_extract(self, rule_id: str) -> None:
        self.config_service.config.extract_rules = [rule for rule in self.extract_rules if rule.id != rule_id]
        self.config_service.save()

    def duplicate_archive(self, rule_id: str) -> ArchiveRule:
        source = deepcopy(self.archive(rule_id))
        copy = replace(source, id=uuid4().hex, name=f"{source.name} — копия", enabled=False, last_run=None)
        return self.save_archive(copy)

    def duplicate_extract(self, rule_id: str) -> ExtractRule:
        source = deepcopy(self.extract(rule_id))
        copy = replace(source, id=uuid4().hex, name=f"{source.name} — копия", enabled=False, last_run=None)
        return self.save_extract(copy)

    @staticmethod
    def _upsert(items: list[ArchiveRule] | list[ExtractRule], rule: ArchiveRule | ExtractRule) -> None:
        for index, current in enumerate(items):
            if current.id == rule.id:
                items[index] = rule
                return
        items.append(rule)

    @staticmethod
    def _find(items: list[ArchiveRule] | list[ExtractRule], rule_id: str):
        for rule in items:
            if rule.id == rule_id:
                return rule
        raise KeyError(f"Rule not found: {rule_id}")

