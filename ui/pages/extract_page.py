from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from core.models import ExtractDestination, ExtractRule
from ui.widgets.empty_state import EmptyState
from ui.widgets.rule_card import RuleCard


class ExtractPage(QWidget):
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
        heading = QLabel("AutoExtract")
        heading.setObjectName("PageTitle")
        root.addWidget(heading)
        subtitle = QLabel("Следите за папками и распаковывайте новые архивы без повторной обработки.")
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

    def refresh(self, rules: list[ExtractRule]) -> None:
        self._clear()
        if not rules:
            empty = EmptyState(
                "⇩",
                "AutoExtract пока не настроен",
                "Добавьте папку наблюдения — новые ZIP, 7Z и TAR будут безопасно распакованы.",
                "Создать правило",
            )
            empty.action_clicked.connect(self.create_clicked)
            self.cards.addWidget(empty)
        for rule in rules:
            target = "рядом с архивом" if rule.destination_mode == ExtractDestination.BESIDE_ARCHIVE else rule.destination
            card = RuleCard(
                rule.id,
                rule.name,
                rule.watch_folder,
                f"Распаковка: {target}  •  архив после: {rule.archive_action.value}",
                f"Последнее действие: {rule.last_run or 'ещё не запускалось'}  •  {rule.processed_archives} архивов",
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
