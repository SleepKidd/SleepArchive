from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


class TrayService:
    def __init__(
        self,
        icon: QIcon,
        open_window: Callable[[], None],
        run_checks: Callable[[], None],
        toggle_pause: Callable[[], None],
        open_settings: Callable[[], None],
        quit_app: Callable[[], None],
    ) -> None:
        self.icon = QSystemTrayIcon(icon)
        self.icon.setToolTip("SleepArchive — автоматизация работает")
        menu = QMenu()
        title = QAction("SleepArchive", menu)
        title.setEnabled(False)
        menu.addAction(title)
        menu.addSeparator()
        self.archive_status = QAction("AutoArchive: работает", menu)
        self.archive_status.setEnabled(False)
        menu.addAction(self.archive_status)
        self.extract_status = QAction("AutoExtract: работает", menu)
        self.extract_status.setEnabled(False)
        menu.addAction(self.extract_status)
        menu.addSeparator()
        open_action = menu.addAction("Открыть SleepArchive")
        open_action.triggered.connect(open_window)
        check_action = menu.addAction("Запустить проверку")
        check_action.triggered.connect(run_checks)
        self.pause_action = menu.addAction("Приостановить автоматизацию")
        self.pause_action.triggered.connect(toggle_pause)
        settings_action = menu.addAction("Настройки")
        settings_action.triggered.connect(open_settings)
        menu.addSeparator()
        quit_action = menu.addAction("Выход")
        quit_action.triggered.connect(quit_app)
        self.icon.setContextMenu(menu)
        self.icon.activated.connect(
            lambda reason: open_window() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None
        )

    def show(self) -> None:
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.icon.show()

    def set_paused(self, paused: bool) -> None:
        state = "приостановлен" if paused else "работает"
        self.archive_status.setText(f"AutoArchive: {state}")
        self.extract_status.setText(f"AutoExtract: {state}")
        self.pause_action.setText("Возобновить автоматизацию" if paused else "Приостановить автоматизацию")
        self.icon.setToolTip(f"SleepArchive — {state}")

