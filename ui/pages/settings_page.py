from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from services.config_service import AppConfig


class SettingsPage(QWidget):
    save_requested = Signal(dict)
    open_logs_requested = Signal()
    clear_history_requested = Signal()
    reset_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 26)
        root.setSpacing(14)
        title = QLabel("Настройки")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        cards = QHBoxLayout()
        cards.setSpacing(14)
        left = QVBoxLayout()
        right = QVBoxLayout()
        self.startup = QCheckBox("Запускать вместе с Windows")
        self.start_minimized = QCheckBox("Запускать свёрнутым")
        self.minimize_tray = QCheckBox("Закрытие окна = свернуть в tray")
        self.theme = QComboBox()
        self.theme.addItem("Как в системе", "system")
        self.theme.addItem("Светлая", "light")
        self.theme.addItem("Тёмная", "dark")
        self.language = QComboBox()
        self.language.addItem("Русский", "ru")
        left.addWidget(self._card("Основные", [self.startup, self.start_minimized, self.minimize_tray], [("Тема", self.theme), ("Язык", self.language)]))

        self.notify_success = QCheckBox("Успешные операции")
        self.notify_errors = QCheckBox("Ошибки")
        self.notify_warnings = QCheckBox("Предупреждения")
        left.addWidget(self._card("Уведомления", [self.notify_success, self.notify_errors, self.notify_warnings]))
        left.addStretch()

        self.confirm_delete = QCheckBox("Подтверждать удаление")
        self.show_preview = QCheckBox("Показывать предпросмотр")
        self.interval = QSpinBox()
        self.interval.setRange(1, 1440)
        self.interval.setSuffix(" мин")
        right.addWidget(self._card("Поведение", [self.confirm_delete, self.show_preview], [("Частота проверки", self.interval)]))

        advanced = QFrame()
        advanced.setObjectName("Card")
        advanced_layout = QVBoxLayout(advanced)
        advanced_layout.setContentsMargins(18, 16, 18, 16)
        advanced_title = QLabel("Дополнительно")
        advanced_title.setObjectName("SectionTitle")
        advanced_layout.addWidget(advanced_title)
        open_logs = QPushButton("Открыть папку логов")
        open_logs.clicked.connect(self.open_logs_requested)
        clear = QPushButton("Очистить историю")
        clear.clicked.connect(self.clear_history_requested)
        reset = QPushButton("Сбросить настройки")
        reset.setProperty("danger", True)
        reset.clicked.connect(self.reset_requested)
        advanced_layout.addWidget(open_logs)
        advanced_layout.addWidget(clear)
        advanced_layout.addWidget(reset)
        right.addWidget(advanced)
        right.addStretch()
        cards.addLayout(left, 1)
        cards.addLayout(right, 1)
        root.addLayout(cards, 1)
        save = QPushButton("Сохранить настройки")
        save.setProperty("primary", True)
        save.clicked.connect(self._emit_save)
        root.addWidget(save)

    @staticmethod
    def _card(title: str, checks: list[QCheckBox], fields: list[tuple[str, QWidget]] | None = None) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        heading = QLabel(title)
        heading.setObjectName("SectionTitle")
        layout.addWidget(heading)
        for check in checks:
            layout.addWidget(check)
        if fields:
            form = QFormLayout()
            for label, widget in fields:
                form.addRow(label, widget)
            layout.addLayout(form)
        return card

    def load(self, config: AppConfig) -> None:
        self.startup.setChecked(config.start_with_windows)
        self.start_minimized.setChecked(config.start_minimized)
        self.minimize_tray.setChecked(config.minimize_to_tray)
        self.theme.setCurrentIndex(max(0, self.theme.findData(config.theme)))
        self.language.setCurrentIndex(max(0, self.language.findData(config.language)))
        self.notify_success.setChecked(config.notifications_success)
        self.notify_errors.setChecked(config.notifications_errors)
        self.notify_warnings.setChecked(config.notifications_warnings)
        self.confirm_delete.setChecked(config.confirm_delete)
        self.show_preview.setChecked(config.show_preview)
        self.interval.setValue(config.check_interval_minutes)

    def _emit_save(self) -> None:
        self.save_requested.emit(
            {
                "start_with_windows": self.startup.isChecked(),
                "start_minimized": self.start_minimized.isChecked(),
                "minimize_to_tray": self.minimize_tray.isChecked(),
                "theme": self.theme.currentData(),
                "language": self.language.currentData(),
                "notifications_success": self.notify_success.isChecked(),
                "notifications_errors": self.notify_errors.isChecked(),
                "notifications_warnings": self.notify_warnings.isChecked(),
                "confirm_delete": self.confirm_delete.isChecked(),
                "show_preview": self.show_preview.isChecked(),
                "check_interval_minutes": self.interval.value(),
            }
        )

