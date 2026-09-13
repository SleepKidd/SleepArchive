from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget


class OnboardingDialog(QDialog):
    create_archive = Signal()
    create_extract = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Добро пожаловать в SleepArchive")
        self.setFixedSize(650, 430)
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 30, 34, 26)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._page("◐", "SleepArchive", "Автоматизируйте архивирование и распаковку файлов."))
        self.stack.addWidget(self._page("▣", "AutoArchive", "Старые файлы автоматически отправляются в проверенный архив."))
        self.stack.addWidget(self._page("⇩", "AutoExtract", "Новые архивы автоматически распаковываются без перезаписи данных."))
        self.stack.addWidget(self._finish_page())
        root.addWidget(self.stack, 1)
        navigation = QHBoxLayout()
        self.back = QPushButton("Назад")
        self.back.clicked.connect(self._back)
        self.back.setEnabled(False)
        self.next = QPushButton("Далее")
        self.next.setProperty("primary", True)
        self.next.clicked.connect(self._next)
        navigation.addWidget(self.back)
        navigation.addStretch()
        navigation.addWidget(self.next)
        root.addLayout(navigation)

    @staticmethod
    def _page(icon: str, title: str, text: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch()
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 48pt;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        heading = QLabel(title)
        heading.setObjectName("PageTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)
        body = QLabel(text)
        body.setObjectName("Muted")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)
        layout.addWidget(body)
        layout.addStretch()
        return page

    def _finish_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch()
        heading = QLabel("С чего начнём?")
        heading.setObjectName("PageTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)
        archive = QPushButton("Настроить AutoArchive")
        archive.setProperty("primary", True)
        archive.clicked.connect(self._archive)
        extract = QPushButton("Настроить AutoExtract")
        extract.clicked.connect(self._extract)
        later = QPushButton("Сделать позже")
        later.clicked.connect(self.accept)
        layout.addWidget(archive)
        layout.addWidget(extract)
        layout.addWidget(later)
        layout.addStretch()
        return page

    def _next(self) -> None:
        index = self.stack.currentIndex() + 1
        self.stack.setCurrentIndex(min(index, self.stack.count() - 1))
        self.back.setEnabled(self.stack.currentIndex() > 0)
        self.next.setVisible(self.stack.currentIndex() < self.stack.count() - 1)

    def _back(self) -> None:
        self.stack.setCurrentIndex(max(0, self.stack.currentIndex() - 1))
        self.back.setEnabled(self.stack.currentIndex() > 0)
        self.next.setVisible(True)

    def _archive(self) -> None:
        self.create_archive.emit()
        self.accept()

    def _extract(self) -> None:
        self.create_extract.emit()
        self.accept()
