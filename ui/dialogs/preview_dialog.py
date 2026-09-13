from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QListWidget, QVBoxLayout

from core.models import ArchivePreview, ArchiveRule
from core.safety import format_bytes


class PreviewDialog(QDialog):
    def __init__(self, preview: ArchivePreview, rule: ArchiveRule, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Предпросмотр AutoArchive")
        self.resize(620, 520)
        root = QVBoxLayout(self)
        title = QLabel("Что произойдёт")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        summary = QLabel(
            f"Будет обработано: {len(preview.included)} файлов\n"
            f"Общий размер: {format_bytes(preview.total_size)}\n"
            f"Оригиналы: {self._action_name(rule.original_action.value)}"
        )
        summary.setObjectName("SectionTitle")
        root.addWidget(summary)
        archives_title = QLabel("Будут созданы архивы")
        archives_title.setObjectName("SectionTitle")
        root.addWidget(archives_title)
        archives = QListWidget()
        for name, items in sorted(preview.archives.items()):
            archives.addItem(f"{name}.{rule.archive_format.value}  —  {len(items)} файлов")
        root.addWidget(archives)
        excluded = QLabel(f"Исключено: {len(preview.excluded)} файлов")
        excluded.setObjectName("Muted")
        root.addWidget(excluded)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Запустить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @staticmethod
    def _action_name(value: str) -> str:
        return {"keep": "оставить", "move": "переместить", "delete": "удалить после проверки"}.get(value, value)

