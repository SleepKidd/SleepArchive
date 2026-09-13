from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from core.models import ArchiveFormat, ArchiveRule, Grouping, OriginalAction, ScheduleKind


class ArchiveRuleDialog(QDialog):
    def __init__(self, rule: ArchiveRule | None = None, parent=None) -> None:
        super().__init__(parent)
        self.original = rule
        self.setWindowTitle("Изменить правило AutoArchive" if rule else "Новое правило AutoArchive")
        self.setMinimumWidth(620)
        root = QVBoxLayout(self)
        title = QLabel("Основные параметры")
        title.setObjectName("SectionTitle")
        root.addWidget(title)
        form = QFormLayout()
        form.setSpacing(12)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Например: Документы")
        form.addRow("Название", self.name)
        self.source = QLineEdit()
        form.addRow("Исходная папка", self._path_row(self.source, "Выбрать", self._choose_source))
        self.destination = QLineEdit()
        form.addRow("Папка архива", self._path_row(self.destination, "Выбрать", self._choose_destination))
        self.age = QSpinBox()
        self.age.setRange(0, 36_500)
        self.age.setValue(30)
        self.age.setSuffix(" дней")
        form.addRow("Старше", self.age)
        root.addLayout(form)

        advanced = QGroupBox("Дополнительные настройки")
        advanced.setCheckable(True)
        advanced.setChecked(bool(rule))
        advanced_form = QFormLayout(advanced)
        self.recursive = QCheckBox("Учитывать подпапки")
        self.recursive.setChecked(True)
        advanced_form.addRow(self.recursive)
        self.format = QComboBox()
        self.format.addItem("ZIP", ArchiveFormat.ZIP.value)
        self.format.addItem("7Z", ArchiveFormat.SEVEN_ZIP.value)
        advanced_form.addRow("Формат", self.format)
        self.compression = QSlider(Qt.Orientation.Horizontal)
        self.compression.setRange(0, 9)
        self.compression.setValue(6)
        self.compression_label = QLabel("6")
        self.compression.valueChanged.connect(lambda value: self.compression_label.setText(str(value)))
        compression_row = QHBoxLayout()
        compression_row.addWidget(self.compression, 1)
        compression_row.addWidget(self.compression_label)
        advanced_form.addRow("Сжатие", compression_row)
        self.grouping = QComboBox()
        self.grouping.addItem("По месяцам", Grouping.MONTH.value)
        self.grouping.addItem("По годам", Grouping.YEAR.value)
        self.grouping.addItem("Один общий архив", Grouping.SINGLE.value)
        advanced_form.addRow("Группировка", self.grouping)
        self.exclusions = QLineEdit()
        self.exclusions.setPlaceholderText("*.tmp; cache/*; ~*")
        advanced_form.addRow("Исключения", self.exclusions)
        self.schedule = QComboBox()
        self.schedule.addItem("Только вручную", ScheduleKind.MANUAL.value)
        self.schedule.addItem("При запуске", ScheduleKind.STARTUP.value)
        self.schedule.addItem("Ежедневно", ScheduleKind.DAILY.value)
        self.schedule.addItem("Еженедельно", ScheduleKind.WEEKLY.value)
        advanced_form.addRow("Расписание", self.schedule)
        self.action = QComboBox()
        self.action.addItem("Оставить оригиналы (рекомендуется)", OriginalAction.KEEP.value)
        self.action.addItem("Переместить оригиналы", OriginalAction.MOVE.value)
        self.action.addItem("Удалить после проверки", OriginalAction.DELETE.value)
        self.action.currentIndexChanged.connect(self._action_changed)
        advanced_form.addRow("После архивации", self.action)
        self.move_destination = QLineEdit()
        self.move_row_label = QLabel("Куда переместить")
        self.move_row = self._path_row(self.move_destination, "Выбрать", self._choose_move)
        advanced_form.addRow(self.move_row_label, self.move_row)
        self.danger = QLabel("⚠ Удаление выполняется только после полной проверки архива.")
        self.danger.setStyleSheet("color: #D92D20; font-weight: 600;")
        self.danger.setWordWrap(True)
        advanced_form.addRow(self.danger)
        root.addWidget(advanced)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        if rule:
            self._load(rule)
        self._action_changed()

    @staticmethod
    def _path_row(field: QLineEdit, text: str, callback) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.addWidget(field, 1)
        button = QPushButton(text)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return layout

    def _choose_source(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Исходная папка", self.source.text())
        if path:
            self.source.setText(path)

    def _choose_destination(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Папка архива", self.destination.text())
        if path:
            self.destination.setText(path)

    def _choose_move(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Папка для оригиналов", self.move_destination.text())
        if path:
            self.move_destination.setText(path)

    def _action_changed(self) -> None:
        action = self.action.currentData()
        moving = action == OriginalAction.MOVE.value
        self.move_destination.setVisible(moving)
        self.move_row_label.setVisible(moving)
        self.danger.setVisible(action == OriginalAction.DELETE.value)

    def _load(self, rule: ArchiveRule) -> None:
        self.name.setText(rule.name)
        self.source.setText(rule.source)
        self.destination.setText(rule.destination)
        self.age.setValue(rule.age_days)
        self.recursive.setChecked(rule.recursive)
        self.format.setCurrentIndex(max(0, self.format.findData(rule.archive_format.value)))
        self.compression.setValue(rule.compression_level)
        self.grouping.setCurrentIndex(max(0, self.grouping.findData(rule.grouping.value)))
        self.exclusions.setText("; ".join(rule.exclusions))
        self.schedule.setCurrentIndex(max(0, self.schedule.findData(rule.schedule.value)))
        self.action.setCurrentIndex(max(0, self.action.findData(rule.original_action.value)))
        self.move_destination.setText(rule.move_destination)

    def _validate_and_accept(self) -> None:
        try:
            rule = self.rule()
            rule.validate()
            if not Path(rule.source).is_dir():
                raise ValueError("Исходная папка не существует.")
        except ValueError as exc:
            QMessageBox.warning(self, "Проверьте правило", str(exc))
            return
        self.accept()

    def rule(self) -> ArchiveRule:
        exclusions = [part.strip() for part in re.split(r"[;,]", self.exclusions.text()) if part.strip()]
        values = dict(
            name=self.name.text().strip(),
            source=self.source.text().strip(),
            destination=self.destination.text().strip(),
            age_days=self.age.value(),
            recursive=self.recursive.isChecked(),
            archive_format=ArchiveFormat(self.format.currentData()),
            compression_level=self.compression.value(),
            grouping=Grouping(self.grouping.currentData()),
            exclusions=exclusions,
            schedule=ScheduleKind(self.schedule.currentData()),
            original_action=OriginalAction(self.action.currentData()),
            move_destination=self.move_destination.text().strip(),
        )
        return replace(self.original, **values) if self.original else ArchiveRule(**values)

