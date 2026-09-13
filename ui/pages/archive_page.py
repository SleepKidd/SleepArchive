from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from core.models import ArchiveRule
from core.safety import format_bytes
from ui.widgets.empty_state import EmptyState
from ui.widgets.rule_card import RuleCard


class ArchivePage(QWidget):
    create_clicked = Signal()
    run_clicked = Signal(str)
    edit_clicked = Signal(str)
    delete_clicked = Signal(str)
    duplicate_clicked = Signal(str)
    toggled = Signal(str, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 26)
        heading = QLabel("AutoArchive")
        heading.setObjectName("PageTitle")
        root.addWidget(heading)
        subtitle = QLabel("Архивируйте старые файлы автоматически и безопасно.")
        subtitle.setObjectName("Muted")
        root.addWidget(subtitle)
        create = QPushButton("+  Создать правило")
        create.setProperty("primary", True)
        create.clicked.connect(self.create_clicked)
        root.addWidget(create, alignment=Qt.AlignmentFlag.AlignLeft)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.container.setObjectName("Page")
        self.cards = QVBoxLayout(self.container)
        self.cards.setContentsMargins(0, 12, 0, 0)
        self.cards.setSpacing(12)
        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll, 1)

    def refresh(self, rules: list[ArchiveRule]) -> None:
        self._clear()
        if not rules:
            empty = EmptyState(
                "▣",
                "AutoArchive пока не настроен",
                "Создайте первое правило, и SleepArchive будет автоматически архивировать старые файлы.",
                "Создать правило",
            )
            empty.action_clicked.connect(self.create_clicked)
            self.cards.addWidget(empty)
        for rule in rules:
            card = RuleCard(
                rule.id,
                rule.name,
                rule.source,
                f"Старше {rule.age_days} дней  →  {rule.destination}  •  {rule.archive_format.value.upper()}",
                f"Последний запуск: {rule.last_run or 'ещё не запускалось'}  •  {rule.processed_files} файлов, {format_bytes(rule.processed_bytes)}",
                rule.enabled,
            )
            card.run_clicked.connect(self.run_clicked)
            card.edit_clicked.connect(self.edit_clicked)
            card.delete_clicked.connect(self.delete_clicked)
            card.duplicate_clicked.connect(self.duplicate_clicked)
            card.toggled.connect(self.toggled)
            self.cards.addWidget(card)
        self.cards.addStretch(1)

    def _clear(self) -> None:
        while self.cards.count():
            item = self.cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
