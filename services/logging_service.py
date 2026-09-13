from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from services.config_service import application_data_dir


def configure_logging(log_dir: Path | None = None, debug: bool = False) -> Path:
    destination = log_dir or application_data_dir() / "logs"
    destination.mkdir(parents=True, exist_ok=True)
    log_path = destination / "sleeparchive.log"
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    if not any(isinstance(handler, RotatingFileHandler) for handler in root.handlers):
        handler = RotatingFileHandler(
            log_path,
            maxBytes=2 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
        root.addHandler(handler)
    return log_path

