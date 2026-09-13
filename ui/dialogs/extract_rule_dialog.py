from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import (
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
    QSpinBox,
    QVBoxLayout,
)

from core.models import ExtractDestination, ExtractRule, OriginalAction


class ExtractRuleDialog(QDialog):
    def __init__(self, rule: ExtractRule | None = None, parent=None) -> None:
        super().__init__(parent)
        self.original = rule
        self.setWindowTitle("Изменить правило AutoExtract" if rule else "Новое правило AutoExtract")
        self.setMinimumWidth(620)
        root = QVBoxLayout(self)
        title = QLabel("Папка наблюдения")
        title.setObjectName("SectionTitle")
        root.addWidget(title)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("Например: Загрузки")
        form.addRow("Название", self.name)
        self.watch = QLineEdit()
        form.addRow("Откуда", self._path_row(self.watch, self._choose_watch))
        self.mode = QComboBox()
        self.mode.addItem("Рядом с архивом", ExtractDestination.BESIDE_ARCHIVE.value)
        self.mode.addItem("В выбранную папку", ExtractDestination.SELECTED_FOLDER.value)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        form.addRow("Куда", self.mode)
        self.destination = QLineEdit()
        self.destination_label = QLabel("Папка назначения")
        form.addRow(self.destination_label, self._path_row(self.destination, self._choose_destination))
        root.addLayout(form)
        advanced = QGroupBox("Дополнительные настройки")
        advanced.setCheckable(True)
        advanced.setChecked(bool(rule))
        advanced_form = QFormLayout(advanced)
        self.action = QComboBox()
        self.action.addItem("Оставить архив (рекомендуется)", OriginalAction.KEEP.value)
        self.action.addItem("Переместить в Archives", OriginalAction.MOVE.value)
        self.action.addItem("Удалить после проверки", OriginalAction.DELETE.value)
        self.action.currentIndexChanged.connect(self._action_changed)
        advanced_form.addRow("После распаковки", self.action)
        self.move_destination = QLineEdit()
        self.move_label = QLabel("Папка архивов")
        advanced_form.addRow(self.move_label, self._path_row(self.move_destination, self._choose_move))
        self.stability = QSpinBox()
        self.stability.setRange(1, 120)
        self.stability.setValue(3)
        self.stability.setSuffix(" сек")
        advanced_form.addRow("Проверка стабильности", self.stability)
        self.danger = QLabel("⚠ Архив удаляется только после проверки результата.")
        self.danger.setStyleSheet("color: #D92D20; font-weight: 600;")
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
        self._mode_changed()
        self._action_changed()

    @staticmethod
    def _path_row(field: QLineEdit, callback) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.addWidget(field, 1)
        button = QPushButton("Выбрать")
        button.clicked.connect(callback)
        layout.addWidget(button)
        return layout

    def _choose_watch(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Папка наблюдения", self.watch.text())
        if path:
            self.watch.setText(path)

    def _choose_destination(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Папка распаковки", self.destination.text())
        if path:
            self.destination.setText(path)

    def _choose_move(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Папка обработанных архивов", self.move_destination.text())
        if path:
            self.move_destination.setText(path)

    def _mode_changed(self) -> None:
        visible = self.mode.currentData() == ExtractDestination.SELECTED_FOLDER.value
        self.destination.setVisible(visible)
        self.destination_label.setVisible(visible)

    def _action_changed(self) -> None:
        action = self.action.currentData()
        moving = action == OriginalAction.MOVE.value
        self.move_destination.setVisible(moving)
        self.move_label.setVisible(moving)
        self.danger.setVisible(action == OriginalAction.DELETE.value)

    def _load(self, rule: ExtractRule) -> None:
        self.name.setText(rule.name)
        self.watch.setText(rule.watch_folder)
        self.mode.setCurrentIndex(max(0, self.mode.findData(rule.destination_mode.value)))
        self.destination.setText(rule.destination)
        self.action.setCurrentIndex(max(0, self.action.findData(rule.archive_action.value)))
        self.move_destination.setText(rule.archive_move_destination)
        self.stability.setValue(rule.stability_seconds)

    def _validate_and_accept(self) -> None:
        try:
            rule = self.rule()
            rule.validate()
            if not Path(rule.watch_folder).is_dir():
                raise ValueError("Папка наблюдения не существует.")
        except ValueError as exc:
            QMessageBox.warning(self, "Проверьте правило", str(exc))
            return
        self.accept()

    def rule(self) -> ExtractRule:
        values = dict(
            name=self.name.text().strip(),
            watch_folder=self.watch.text().strip(),
            destination_mode=ExtractDestination(self.mode.currentData()),
            destination=self.destination.text().strip(),
            archive_action=OriginalAction(self.action.currentData()),
            archive_move_destination=self.move_destination.text().strip(),
            stability_seconds=self.stability.value(),
        )
        return replace(self.original, **values) if self.original else ExtractRule(**values)

