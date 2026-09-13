from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from core.models import ProgressUpdate
from core.safety import SafetyError

LOGGER = logging.getLogger(__name__)


class WorkerSignals(QObject):
    progress = Signal(object)
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class OperationWorker(QRunnable):
    """Runs a cancellable file operation away from the UI thread."""

    def __init__(self, operation: Callable[[Callable[[ProgressUpdate], None], threading.Event], Any]) -> None:
        super().__init__()
        self.operation = operation
        self.cancel_event = threading.Event()
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.operation(self.signals.progress.emit, self.cancel_event)
            self.signals.result.emit(result)
        except SafetyError as exc:
            self.signals.error.emit(str(exc))
        except Exception:
            LOGGER.exception("Unhandled background operation failure")
            self.signals.error.emit("Произошла непредвиденная ошибка. Подробности записаны в технический журнал.")
        finally:
            self.signals.finished.emit()

    def cancel(self) -> None:
        self.cancel_event.set()

