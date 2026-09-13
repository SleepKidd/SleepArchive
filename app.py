from __future__ import annotations

import argparse
import logging
import sys

from PySide6.QtCore import QLockFile, QStandardPaths
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from services.config_service import ConfigService
from services.history_service import HistoryService
from services.logging_service import configure_logging
from ui.main_window import MainWindow
from ui.styles import apply_theme

APP_NAME = "SleepArchive"
VERSION = "1.0.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--minimized", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(debug=args.debug)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    app.setOrganizationName("SleepKidd")
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Segoe UI", 10))
    lock_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation) + "/SleepArchive.lock"
    lock = QLockFile(lock_path)
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, APP_NAME, "SleepArchive уже запущен.")
        return 0
    config = ConfigService()
    apply_theme(app, config.config.theme)
    window = MainWindow(config, HistoryService(), VERSION)
    if not (args.minimized or config.config.start_minimized):
        window.show()
    logging.getLogger(__name__).info("SleepArchive %s started", VERSION)
    result = app.exec()
    lock.unlock()
    return result


if __name__ == "__main__":
    raise SystemExit(main())

