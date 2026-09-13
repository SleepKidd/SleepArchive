from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class StatusCard(QFrame):
    primary_clicked = Signal()
    secondary_clicked = Signal()

    def __init__(self, icon: str, title: str, description: str, primary: str, secondary: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setMinimumHeight(230)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        header = QHBoxLayout()
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 24pt;")
        header.addWidget(icon_label)
        header.addStretch()
        self.state = QLabel("● Включён")
        self.state.setStyleSheet("color: #17A673; font-weight: 650;")
        header.addWidget(self.state)
        layout.addLayout(header)
        heading = QLabel(title)
        heading.setObjectName("SectionTitle")
        layout.addWidget(heading)
        info = QLabel(description)
        info.setObjectName("Muted")
        layout.addWidget(info)
        self.metric_label = QLabel("0")
        self.metric_label.setObjectName("Metric")
        self.metric_label.setWordWrap(True)
        layout.addWidget(self.metric_label)
        self.detail = QLabel("Пока нет операций")
        self.detail.setObjectName("Muted")
        layout.addWidget(self.detail)
        layout.addStretch()
        actions = QHBoxLayout()
        primary_button = QPushButton(primary)
        primary_button.setProperty("primary", True)
        primary_button.clicked.connect(self.primary_clicked)
        secondary_button = QPushButton(secondary)
        secondary_button.clicked.connect(self.secondary_clicked)
        actions.addWidget(primary_button)
        actions.addWidget(secondary_button)
        actions.addStretch()
        layout.addLayout(actions)

    def update_state(self, enabled: bool, metric: str, detail: str) -> None:
        self.state.setText("● Включён" if enabled else "● Выключен")
        self.state.setStyleSheet(
            "color: #17A673; font-weight: 650;" if enabled else "color: #667085; font-weight: 650;"
        )
        self.metric_label.setText(metric)
        self.detail.setText(detail)
