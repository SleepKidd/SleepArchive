from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout


class EmptyState(QFrame):
    action_clicked = Signal()

    def __init__(self, icon: str, title: str, message: str, action: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("EmptyState")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 38, 36, 38)
        layout.setSpacing(10)
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 34pt;")
        layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        heading = QLabel(title)
        heading.setObjectName("SectionTitle")
        layout.addWidget(heading, alignment=Qt.AlignmentFlag.AlignHCenter)
        body = QLabel(message)
        body.setObjectName("Muted")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(body)
        button = QPushButton(action)
        button.setProperty("primary", True)
        button.clicked.connect(self.action_clicked)
        layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignHCenter)
