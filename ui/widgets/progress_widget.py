from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QProgressBar, QPushButton, QVBoxLayout

from core.models import ProgressUpdate
from core.safety import format_bytes


class ProgressDialog(QDialog):
    cancel_requested = Signal()

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(500, 230)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        panel = QFrame()
        panel.setObjectName("ProgressPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 18, 20, 18)
        heading = QLabel(title)
        heading.setObjectName("SectionTitle")
        panel_layout.addWidget(heading)
        self.current_file = QLabel("Подготовка…")
        self.current_file.setObjectName("Muted")
        panel_layout.addWidget(self.current_file)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        panel_layout.addWidget(self.progress)
        self.details = QLabel("0 файлов")
        self.details.setObjectName("Muted")
        panel_layout.addWidget(self.details)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self._cancel)
        panel_layout.addWidget(cancel)
        layout.addWidget(panel)

    def update_progress(self, update: ProgressUpdate) -> None:
        ratio = update.bytes_done / update.bytes_total if update.bytes_total else update.current / max(update.total, 1)
        self.progress.setValue(min(1000, int(ratio * 1000)))
        self.current_file.setText(update.current_file)
        self.details.setText(
            f"{update.current} из {update.total} • {format_bytes(update.bytes_done)} из {format_bytes(update.bytes_total)}"
        )

    def _cancel(self) -> None:
        self.current_file.setText("Безопасная отмена…")
        self.cancel_requested.emit()

    def closeEvent(self, event) -> None:
        self.cancel_requested.emit()
        event.ignore()

