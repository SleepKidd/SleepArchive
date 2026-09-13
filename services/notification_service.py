from __future__ import annotations

import time

from PySide6.QtWidgets import QSystemTrayIcon


class NotificationService:
    def __init__(self, tray_icon: QSystemTrayIcon) -> None:
        self.tray_icon = tray_icon
        self._last_key = ""
        self._last_shown_at = 0.0

    def show(self, title: str, message: str, key: str = "", error: bool = False) -> None:
        if key and key == self._last_key:
            return
        now = time.monotonic()
        if not error and now - self._last_shown_at < 3:
            return
        self._last_key = key
        self._last_shown_at = now
        icon = QSystemTrayIcon.MessageIcon.Critical if error else QSystemTrayIcon.MessageIcon.Information
        self.tray_icon.showMessage(title, message, icon, 5_000)
