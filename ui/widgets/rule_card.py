from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class RuleCard(QFrame):
    run_clicked = Signal(str)
    edit_clicked = Signal(str)
    delete_clicked = Signal(str)
    duplicate_clicked = Signal(str)
    toggled = Signal(str, bool)

    def __init__(self, rule_id: str, title: str, path: str, summary: str, last_run: str, enabled: bool, parent=None) -> None:
        super().__init__(parent)
        self.rule_id = rule_id
        self.setObjectName("RuleCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        top = QHBoxLayout()
        heading = QLabel(title)
        heading.setObjectName("SectionTitle")
        top.addWidget(heading)
        top.addStretch()
        toggle = QCheckBox("Включено")
        toggle.setChecked(enabled)
        toggle.toggled.connect(lambda value: self.toggled.emit(self.rule_id, value))
        top.addWidget(toggle)
        layout.addLayout(top)
        path_label = QLabel(path)
        path_label.setObjectName("Muted")
        path_label.setTextInteractionFlags(path_label.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(path_label)
        summary_label = QLabel(summary)
        layout.addWidget(summary_label)
        last_label = QLabel(last_run)
        last_label.setObjectName("Muted")
        layout.addWidget(last_label)
        actions = QHBoxLayout()
        run = QPushButton("Запустить")
        run.setProperty("primary", True)
        run.clicked.connect(lambda: self.run_clicked.emit(self.rule_id))
        edit = QPushButton("Изменить")
        edit.clicked.connect(lambda: self.edit_clicked.emit(self.rule_id))
        duplicate = QPushButton("Дублировать")
        duplicate.clicked.connect(lambda: self.duplicate_clicked.emit(self.rule_id))
        remove = QPushButton("Удалить")
        remove.setProperty("danger", True)
        remove.clicked.connect(lambda: self.delete_clicked.emit(self.rule_id))
        for button in (run, edit, duplicate, remove):
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
