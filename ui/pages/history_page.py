from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget

from core.models import HistoryEntry, HistoryKind
from core.safety import format_bytes


class HistoryPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._entries: list[HistoryEntry] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 26)
        title = QLabel("История")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по операциям…")
        self.search.textChanged.connect(self._render)
        controls.addWidget(self.search, 1)
        self.filter = QComboBox()
        self.filter.addItem("Все", "all")
        self.filter.addItem("AutoArchive", HistoryKind.ARCHIVE.value)
        self.filter.addItem("AutoExtract", HistoryKind.EXTRACT.value)
        self.filter.addItem("Ошибки", HistoryKind.ERROR.value)
        self.filter.currentIndexChanged.connect(self._render)
        controls.addWidget(self.filter)
        root.addLayout(controls)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setObjectName("Page")
        self.entries_layout = QVBoxLayout(container)
        self.entries_layout.setContentsMargins(0, 10, 0, 0)
        self.entries_layout.setSpacing(10)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

    def refresh(self, entries: list[HistoryEntry]) -> None:
        self._entries = entries
        self._render()

    def _render(self) -> None:
        while self.entries_layout.count():
            item = self.entries_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        query = self.search.text().casefold().strip()
        kind = self.filter.currentData()
        shown = 0
        for entry in self._entries:
            if kind == HistoryKind.ERROR.value:
                if entry.success and entry.kind != HistoryKind.ERROR:
                    continue
            elif kind != "all" and entry.kind.value != kind:
                continue
            haystack = f"{entry.title} {entry.details}".casefold()
            if query and query not in haystack:
                continue
            self.entries_layout.addWidget(self._entry_card(entry))
            shown += 1
        if not shown:
            empty = QLabel("Подходящих операций нет.")
            empty.setObjectName("Muted")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.entries_layout.addWidget(empty)
        self.entries_layout.addStretch(1)

    @staticmethod
    def _entry_card(entry: HistoryEntry) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        icon = QLabel("✓" if entry.success else "⚠")
        icon.setStyleSheet(f"font-size: 18pt; color: {'#17A673' if entry.success else '#D97706'};")
        layout.addWidget(icon)
        text = QVBoxLayout()
        title = QLabel(entry.title)
        title.setStyleSheet("font-weight: 650;")
        text.addWidget(title)
        details = QLabel(entry.details)
        details.setObjectName("Muted")
        details.setWordWrap(True)
        text.addWidget(details)
        layout.addLayout(text, 1)
        metadata = QVBoxLayout()
        try:
            time_text = datetime.fromisoformat(entry.timestamp).astimezone().strftime("%d.%m.%Y  %H:%M")
        except ValueError:
            time_text = entry.timestamp
        moment = QLabel(time_text)
        moment.setObjectName("Muted")
        metadata.addWidget(moment, alignment=Qt.AlignmentFlag.AlignRight)
        amount = QLabel(f"{entry.files_count} файлов • {format_bytes(entry.bytes_count)}")
        amount.setObjectName("Muted")
        metadata.addWidget(amount, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(metadata)
        return card

