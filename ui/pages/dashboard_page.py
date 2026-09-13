from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.models import ArchiveRule, ExtractRule, HistoryEntry
from core.safety import format_bytes
from ui.widgets.status_card import StatusCard


class DashboardPage(QWidget):
    create_archive = Signal()
    run_archives = Signal()
    create_extract = Signal()
    run_extracts = Signal()
    pause_clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 26)
        root.setSpacing(18)
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Добрый день")
        title.setObjectName("PageTitle")
        title_box.addWidget(title)
        subtitle = QLabel("SleepArchive поддерживает порядок в ваших файлах.")
        subtitle.setObjectName("Muted")
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()
        self.pause_button = QPushButton("Приостановить автоматизацию")
        self.pause_button.clicked.connect(self.pause_clicked)
        header.addWidget(self.pause_button)
        root.addLayout(header)

        self.cards_layout = QGridLayout()
        self.cards_layout.setSpacing(16)
        self.archive_card = StatusCard("▣", "AutoArchive", "Старые файлы аккуратно собраны в архивы", "Создать правило", "Запустить проверку")
        self.extract_card = StatusCard("⇩", "AutoExtract", "Новые архивы распаковываются автоматически", "Создать правило", "Проверить папки")
        self.archive_card.primary_clicked.connect(self.create_archive)
        self.archive_card.secondary_clicked.connect(self.run_archives)
        self.extract_card.primary_clicked.connect(self.create_extract)
        self.extract_card.secondary_clicked.connect(self.run_extracts)
        self.cards_layout.addWidget(self.archive_card, 0, 0)
        self.cards_layout.addWidget(self.extract_card, 0, 1)
        self.cards_layout.setColumnStretch(0, 1)
        self.cards_layout.setColumnStretch(1, 1)
        root.addLayout(self.cards_layout)

        recent_frame = QFrame()
        recent_frame.setObjectName("Card")
        recent_layout = QVBoxLayout(recent_frame)
        recent_layout.setContentsMargins(20, 18, 20, 18)
        recent_title = QLabel("Последние операции")
        recent_title.setObjectName("SectionTitle")
        recent_layout.addWidget(recent_title)
        self.recent = QVBoxLayout()
        recent_layout.addLayout(self.recent)
        root.addWidget(recent_frame, 1)
        self._compact = False

    def resizeEvent(self, event) -> None:
        compact = event.size().width() < 760
        if compact != self._compact:
            self._compact = compact
            if compact:
                self.cards_layout.addWidget(self.archive_card, 0, 0)
                self.cards_layout.addWidget(self.extract_card, 1, 0)
                self.cards_layout.setColumnStretch(1, 0)
                self.archive_card.setMinimumHeight(185)
                self.extract_card.setMinimumHeight(185)
            else:
                self.cards_layout.addWidget(self.archive_card, 0, 0)
                self.cards_layout.addWidget(self.extract_card, 0, 1)
                self.cards_layout.setColumnStretch(1, 1)
                self.archive_card.setMinimumHeight(230)
                self.extract_card.setMinimumHeight(230)
        super().resizeEvent(event)

    def refresh(
        self,
        archive_rules: list[ArchiveRule],
        extract_rules: list[ExtractRule],
        history: list[HistoryEntry],
        paused: bool,
    ) -> None:
        active_archives = sum(rule.enabled for rule in archive_rules)
        archive_files = sum(rule.processed_files for rule in archive_rules)
        archive_bytes = sum(rule.processed_bytes for rule in archive_rules)
        active_extracts = sum(rule.enabled for rule in extract_rules)
        extracted = sum(rule.extracted_files for rule in extract_rules)
        self.archive_card.update_state(
            bool(active_archives) and not paused,
            f"{active_archives} активных правил",
            f"{archive_files} файлов • {format_bytes(archive_bytes)} обработано",
        )
        self.extract_card.update_state(
            bool(active_extracts) and not paused,
            f"{active_extracts} папок под наблюдением",
            f"{extracted} файлов распаковано",
        )
        self.pause_button.setText("Возобновить автоматизацию" if paused else "Приостановить автоматизацию")
        while self.recent.count():
            item = self.recent.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for entry in history[:5]:
            try:
                moment = datetime.fromisoformat(entry.timestamp).astimezone().strftime("%H:%M")
            except ValueError:
                moment = "—"
            icon = "✓" if entry.success else "⚠"
            label = QLabel(f"{moment}   {icon}  {entry.title}  —  {entry.details}")
            label.setWordWrap(True)
            self.recent.addWidget(label)
        if not history:
            empty = QLabel("Операций пока нет. Создайте правило, чтобы начать.")
            empty.setObjectName("Muted")
            self.recent.addWidget(empty)
