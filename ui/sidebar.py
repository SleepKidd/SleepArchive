from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QLabel, QPushButton, QVBoxLayout


class Sidebar(QFrame):
    page_selected = Signal(int)

    ITEMS = [
        ("⌂", "Главная"),
        ("▣", "AutoArchive"),
        ("⇩", "AutoExtract"),
        ("◷", "История"),
        ("⚙", "Настройки"),
    ]

    def __init__(self, version: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(244)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 22, 18, 18)
        layout.setSpacing(8)
        brand = QLabel("◐  SleepArchive")
        brand.setObjectName("Brand")
        layout.addWidget(brand)
        subtitle = QLabel("Порядок без лишних действий")
        subtitle.setObjectName("Muted")
        layout.addWidget(subtitle)
        layout.addSpacing(24)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: list[QPushButton] = []
        for index, (icon, label) in enumerate(self.ITEMS):
            button = QPushButton(f"{icon}   {label}")
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, page=index: self.page_selected.emit(page))
            self.group.addButton(button)
            self.buttons.append(button)
            layout.addWidget(button)
        self.buttons[0].setChecked(True)
        layout.addStretch(1)
        self.status = QLabel("●  Фоновый сервис работает")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #17A673; font-weight: 600;")
        layout.addWidget(self.status)
        version_label = QLabel(f"Версия {version}")
        version_label.setObjectName("Muted")
        layout.addWidget(version_label)

    def select(self, index: int) -> None:
        if 0 <= index < len(self.buttons):
            self.buttons[index].setChecked(True)
            self.page_selected.emit(index)

    def set_paused(self, paused: bool) -> None:
        self.status.setText("●  Автоматизация на паузе" if paused else "●  Фоновый сервис работает")
        self.status.setStyleSheet(
            "color: #D97706; font-weight: 600;" if paused else "color: #17A673; font-weight: 600;"
        )
