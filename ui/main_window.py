from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QStackedWidget,
    QSystemTrayIcon,
    QWidget,
)

from core.archive_engine import ArchiveEngine
from core.extract_engine import ExtractEngine
from core.file_watcher import FileWatcher
from core.models import (
    ArchiveRule,
    ExtractRule,
    HistoryEntry,
    HistoryKind,
    OperationResult,
    OriginalAction,
    utc_now_iso,
)
from core.recovery import clean_incomplete_operations, find_incomplete_operations
from core.rule_manager import RuleManager
from core.safety import is_archive
from core.scheduler import ArchiveScheduler
from services.config_service import ConfigService, application_data_dir
from services.history_service import HistoryService
from services.notification_service import NotificationService
from services.startup_service import StartupService
from services.tray_service import TrayService
from ui.dialogs.archive_rule_dialog import ArchiveRuleDialog
from ui.dialogs.extract_rule_dialog import ExtractRuleDialog
from ui.dialogs.onboarding_dialog import OnboardingDialog
from ui.dialogs.preview_dialog import PreviewDialog
from ui.pages.archive_page import ArchivePage
from ui.pages.dashboard_page import DashboardPage
from ui.pages.extract_page import ExtractPage
from ui.pages.history_page import HistoryPage
from ui.pages.settings_page import SettingsPage
from ui.sidebar import Sidebar
from ui.styles import apply_theme
from ui.widgets.progress_widget import ProgressDialog
from ui.workers import OperationWorker

LOGGER = logging.getLogger(__name__)


class AutomationBridge(QObject):
    scheduled_archive = Signal(object)
    watched_archive = Signal(object, object)


class MainWindow(QMainWindow):
    def __init__(
        self,
        config_service: ConfigService,
        history_service: HistoryService,
        version: str,
    ) -> None:
        super().__init__()
        self.config_service = config_service
        self.history_service = history_service
        self.rules = RuleManager(config_service)
        self.archive_engine = ArchiveEngine()
        self.extract_engine = ExtractEngine()
        self.thread_pool = QThreadPool.globalInstance()
        self.bridge = AutomationBridge(self)
        self._workers: dict[str, OperationWorker] = {}
        self._dialogs: dict[str, ProgressDialog | QProgressDialog] = {}
        self._allow_close = False
        self.version = version
        self.setWindowTitle("SleepArchive")
        self.resize(1150, 720)
        self.setMinimumSize(900, 600)
        self.setWindowIcon(self._app_icon())
        self._build_ui()
        self._connect_ui()

        self.tray = TrayService(
            self.windowIcon(),
            self.show_normal,
            self.run_all_checks,
            self.toggle_automation,
            lambda: self.show_page(4),
            self.quit_application,
        )
        self.notifications = NotificationService(self.tray.icon)
        self.watcher = FileWatcher(lambda rule, path: self._emit_watched(rule, path))
        self.scheduler = ArchiveScheduler(self._scheduled_rules, lambda rule: self.bridge.scheduled_archive.emit(rule))
        self.bridge.scheduled_archive.connect(lambda rule: self.start_archive(rule, preview=False, source="schedule"))
        self.bridge.watched_archive.connect(lambda rule, path: self.start_extract(rule, path, source="watcher"))
        self.tray.show()
        self.refresh_all()
        self.restart_automation()
        QTimer.singleShot(250, self._after_startup)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("AppRoot")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.sidebar = Sidebar(self.version)
        self.stack = QStackedWidget()
        self.dashboard = DashboardPage()
        self.archive_page = ArchivePage()
        self.extract_page = ExtractPage()
        self.history_page = HistoryPage()
        self.settings_page = SettingsPage()
        for page in (self.dashboard, self.archive_page, self.extract_page, self.history_page, self.settings_page):
            self.stack.addWidget(page)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

    def _connect_ui(self) -> None:
        self.sidebar.page_selected.connect(self.show_page)
        self.dashboard.create_archive.connect(self.create_archive_rule)
        self.dashboard.run_archives.connect(self.run_all_archives)
        self.dashboard.create_extract.connect(self.create_extract_rule)
        self.dashboard.run_extracts.connect(self.run_all_extracts)
        self.dashboard.pause_clicked.connect(self.toggle_automation)
        self.archive_page.create_clicked.connect(self.create_archive_rule)
        self.archive_page.run_clicked.connect(lambda rule_id: self.start_archive(self.rules.archive(rule_id)))
        self.archive_page.edit_clicked.connect(self.edit_archive_rule)
        self.archive_page.delete_clicked.connect(self.delete_archive_rule)
        self.archive_page.duplicate_clicked.connect(self.duplicate_archive_rule)
        self.archive_page.toggled.connect(self.toggle_archive_rule)
        self.extract_page.create_clicked.connect(self.create_extract_rule)
        self.extract_page.run_clicked.connect(self.run_extract_rule)
        self.extract_page.edit_clicked.connect(self.edit_extract_rule)
        self.extract_page.delete_clicked.connect(self.delete_extract_rule)
        self.extract_page.duplicate_clicked.connect(self.duplicate_extract_rule)
        self.extract_page.toggled.connect(self.toggle_extract_rule)
        self.settings_page.save_requested.connect(self.save_settings)
        self.settings_page.open_logs_requested.connect(self.open_logs)
        self.settings_page.clear_history_requested.connect(self.clear_history)
        self.settings_page.reset_requested.connect(self.reset_settings)

    def show_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        if 0 <= index < len(self.sidebar.buttons):
            self.sidebar.buttons[index].setChecked(True)
        if index == 3:
            self.history_page.refresh(self.history_service.list_entries())
        if index == 4:
            self.settings_page.load(self.config_service.config)
        self.show_normal()

    def show_normal(self) -> None:
        self.show()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def refresh_all(self) -> None:
        config = self.config_service.config
        history = self.history_service.list_entries()
        self.archive_page.refresh(config.archive_rules)
        self.extract_page.refresh(config.extract_rules)
        self.dashboard.refresh(config.archive_rules, config.extract_rules, history, config.automation_paused)
        self.history_page.refresh(history)
        self.settings_page.load(config)
        self.sidebar.set_paused(config.automation_paused)
        if hasattr(self, "tray"):
            self.tray.set_paused(config.automation_paused)

    def create_archive_rule(self) -> None:
        dialog = ArchiveRuleDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.rules.save_archive(dialog.rule())
            self.refresh_all()
            self.restart_automation()

    def edit_archive_rule(self, rule_id: str) -> None:
        dialog = ArchiveRuleDialog(self.rules.archive(rule_id), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.rules.save_archive(dialog.rule())
            self.refresh_all()
            self.restart_automation()

    def delete_archive_rule(self, rule_id: str) -> None:
        rule = self.rules.archive(rule_id)
        if QMessageBox.question(self, "Удалить правило?", f"Правило «{rule.name}» будет удалено. Файлы останутся без изменений.") == QMessageBox.StandardButton.Yes:
            self.rules.delete_archive(rule_id)
            self.refresh_all()
            self.restart_automation()

    def duplicate_archive_rule(self, rule_id: str) -> None:
        self.rules.duplicate_archive(rule_id)
        self.refresh_all()

    def toggle_archive_rule(self, rule_id: str, enabled: bool) -> None:
        rule = self.rules.archive(rule_id)
        rule.enabled = enabled
        self.rules.save_archive(rule)
        self.restart_automation()
        self.refresh_all()

    def create_extract_rule(self) -> None:
        dialog = ExtractRuleDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.rules.save_extract(dialog.rule())
            self.refresh_all()
            self.restart_automation()

    def edit_extract_rule(self, rule_id: str) -> None:
        dialog = ExtractRuleDialog(self.rules.extract(rule_id), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.rules.save_extract(dialog.rule())
            self.refresh_all()
            self.restart_automation()

    def delete_extract_rule(self, rule_id: str) -> None:
        rule = self.rules.extract(rule_id)
        if QMessageBox.question(self, "Удалить правило?", f"Правило «{rule.name}» будет удалено. Файлы останутся без изменений.") == QMessageBox.StandardButton.Yes:
            self.rules.delete_extract(rule_id)
            self.refresh_all()
            self.restart_automation()

    def duplicate_extract_rule(self, rule_id: str) -> None:
        self.rules.duplicate_extract(rule_id)
        self.refresh_all()

    def toggle_extract_rule(self, rule_id: str, enabled: bool) -> None:
        rule = self.rules.extract(rule_id)
        rule.enabled = enabled
        self.rules.save_extract(rule)
        self.restart_automation()
        self.refresh_all()

    def start_archive(self, rule: ArchiveRule, preview: bool = True, source: str = "manual") -> None:
        key = f"archive:{rule.id}"
        if key in self._workers:
            if source == "manual":
                QMessageBox.information(self, "Правило уже выполняется", "Дождитесь завершения текущей операции.")
            return
        if rule.original_action == OriginalAction.DELETE and not self._confirm_delete("оригиналы после архивации"):
            self.scheduler.mark_finished(rule.id)
            return
        if preview and self.config_service.config.show_preview:
            self._load_preview(rule)
            return
        self._run_archive_worker(rule)

    def _load_preview(self, rule: ArchiveRule) -> None:
        key = f"preview:{rule.id}"
        if key in self._workers:
            return
        dialog = QProgressDialog("Анализируем файлы…", "Отмена", 0, 0, self)
        dialog.setWindowTitle("Предпросмотр")
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        worker = OperationWorker(lambda _progress, _cancel: self.archive_engine.preview(rule))
        worker.signals.result.connect(
            lambda preview: None if worker.cancel_event.is_set() else self._preview_ready(rule, preview)
        )
        worker.signals.error.connect(lambda message: QMessageBox.warning(self, "Не удалось создать предпросмотр", message))
        worker.signals.finished.connect(lambda: self._finish_worker(key))
        dialog.canceled.connect(worker.cancel)
        self._workers[key] = worker
        self._dialogs[key] = dialog
        dialog.show()
        self.thread_pool.start(worker)

    def _preview_ready(self, rule: ArchiveRule, preview) -> None:
        if not preview.included:
            QMessageBox.information(self, "AutoArchive", "Подходящих файлов не найдено.")
            return
        if PreviewDialog(preview, rule, self).exec() == QDialog.DialogCode.Accepted:
            self._run_archive_worker(rule)

    def _run_archive_worker(self, rule: ArchiveRule) -> None:
        key = f"archive:{rule.id}"
        if key in self._workers:
            return
        dialog = ProgressDialog(f"Архивация — {rule.name}", self)
        worker = OperationWorker(lambda progress, cancel: self.archive_engine.run(rule, progress, cancel))
        worker.signals.progress.connect(dialog.update_progress)
        worker.signals.result.connect(lambda result: self._archive_done(rule, result))
        worker.signals.error.connect(
            lambda message: self._operation_error(
                rule.id, rule.name, HistoryKind.ARCHIVE, message, show_dialog=source == "manual"
            )
        )
        worker.signals.finished.connect(lambda: self._finish_worker(key, rule.id))
        dialog.cancel_requested.connect(worker.cancel)
        self._workers[key] = worker
        self._dialogs[key] = dialog
        dialog.show()
        self.thread_pool.start(worker)

    def _archive_done(self, rule: ArchiveRule, result: OperationResult) -> None:
        if result.success:
            rule.last_run = utc_now_iso()
            rule.processed_files += result.files_count
            rule.processed_bytes += result.bytes_count
            self.rules.save_archive(rule)
        self.history_service.add(
            HistoryEntry(
                HistoryKind.ARCHIVE if result.success else HistoryKind.WARNING,
                "Архивировано" if result.success else "Архивация отменена",
                result.message,
                result.success,
                files_count=result.files_count,
                bytes_count=result.bytes_count,
                rule_id=rule.id,
            )
        )
        if result.success and self.config_service.config.notifications_success:
            outputs = ", ".join(path.name for path in result.output_paths)
            self.notifications.show("SleepArchive — архив создан", f"{result.files_count} файлов\n{outputs}", key=f"archive:{rule.id}:{rule.last_run}")
        self.refresh_all()

    def run_extract_rule(self, rule_id: str) -> None:
        rule = self.rules.extract(rule_id)
        folder = Path(rule.watch_folder)
        try:
            archives = [path for path in folder.iterdir() if path.is_file() and is_archive(path)]
        except OSError:
            QMessageBox.warning(self, "Папка недоступна", "Папка наблюдения больше не существует или недоступна.")
            return
        if not archives:
            QMessageBox.information(self, "AutoExtract", "Новых поддерживаемых архивов в папке нет.")
            return
        for archive in archives:
            self.start_extract(rule, archive)

    def start_extract(self, rule: ExtractRule, archive_path: Path, source: str = "manual") -> None:
        key = f"extract:{rule.id}:{archive_path.resolve()}"
        if key in self._workers:
            return
        if rule.archive_action == OriginalAction.DELETE and not self._confirm_delete("архив после распаковки"):
            return
        dialog = ProgressDialog(f"Распаковка — {archive_path.name}", self)
        worker = OperationWorker(
            lambda progress, cancel: self.extract_engine.run(archive_path, rule, progress, cancel, check_stability=True)
        )
        worker.signals.progress.connect(dialog.update_progress)
        worker.signals.result.connect(lambda result: self._extract_done(rule, archive_path, result))
        worker.signals.error.connect(
            lambda message: self._operation_error(
                rule.id, archive_path.name, HistoryKind.EXTRACT, message, show_dialog=source == "manual"
            )
        )
        worker.signals.finished.connect(lambda: self._finish_worker(key))
        dialog.cancel_requested.connect(worker.cancel)
        self._workers[key] = worker
        self._dialogs[key] = dialog
        dialog.show()
        self.thread_pool.start(worker)

    def _extract_done(self, rule: ExtractRule, archive_path: Path, result: OperationResult) -> None:
        if result.success:
            rule.last_run = utc_now_iso()
            rule.processed_archives += 1
            rule.extracted_files += result.files_count
            self.rules.save_extract(rule)
        self.history_service.add(
            HistoryEntry(
                HistoryKind.EXTRACT if result.success else HistoryKind.WARNING,
                "Распаковано" if result.success else "Распаковка отменена",
                f"{archive_path.name}: {result.message}",
                result.success,
                files_count=result.files_count,
                bytes_count=result.bytes_count,
                rule_id=rule.id,
            )
        )
        if result.success and self.config_service.config.notifications_success:
            self.notifications.show(
                "SleepArchive — архив распакован",
                f"{archive_path.name}\n{result.files_count} файлов",
                key=f"extract:{archive_path}:{rule.last_run}",
            )
        self.refresh_all()

    def _operation_error(
        self, rule_id: str, title: str, kind: HistoryKind, message: str, show_dialog: bool = True
    ) -> None:
        self.history_service.add(HistoryEntry(HistoryKind.ERROR, title, message, False, rule_id=rule_id))
        if self.config_service.config.notifications_errors:
            self.notifications.show("SleepArchive — ошибка", message, key=f"error:{title}:{message}", error=True)
        if show_dialog:
            QMessageBox.warning(self, "Операция не выполнена", f"{message}\n\nПроверьте настройки правила и повторите попытку.")
        self.refresh_all()

    def _finish_worker(self, key: str, scheduled_rule_id: str = "") -> None:
        dialog = self._dialogs.pop(key, None)
        if dialog:
            dialog.accept() if isinstance(dialog, ProgressDialog) else dialog.close()
        self._workers.pop(key, None)
        if scheduled_rule_id:
            self.scheduler.mark_finished(scheduled_rule_id)

    def _confirm_delete(self, what: str) -> bool:
        if not self.config_service.config.confirm_delete:
            return True
        answer = QMessageBox.warning(
            self,
            "Подтвердите удаление",
            f"Будет удалён {what}, но только после успешной проверки результата. Продолжить?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Yes

    def run_all_archives(self) -> None:
        rules = [rule for rule in self.rules.archive_rules if rule.enabled]
        if not rules:
            QMessageBox.information(self, "AutoArchive", "Нет включённых правил.")
            return
        for rule in rules:
            self.start_archive(rule)

    def run_all_extracts(self) -> None:
        rules = [rule for rule in self.rules.extract_rules if rule.enabled]
        if not rules:
            QMessageBox.information(self, "AutoExtract", "Нет включённых правил.")
            return
        for rule in rules:
            self.run_extract_rule(rule.id)

    def run_all_checks(self) -> None:
        self.run_all_archives()
        self.run_all_extracts()

    def toggle_automation(self) -> None:
        config = self.config_service.config
        config.automation_paused = not config.automation_paused
        self.config_service.save()
        self.restart_automation()
        self.refresh_all()

    def restart_automation(self) -> None:
        self.scheduler.stop()
        self.watcher.stop()
        if not self.config_service.config.automation_paused:
            self.scheduler.start()
            self.watcher.start(self.rules.extract_rules)

    def _scheduled_rules(self) -> list[ArchiveRule]:
        if self.config_service.config.automation_paused:
            return []
        return list(self.rules.archive_rules)

    def _emit_watched(self, rule: ExtractRule, path: Path) -> bool:
        if self.config_service.config.automation_paused:
            return False
        self.bridge.watched_archive.emit(rule, path)
        return True

    def save_settings(self, values: dict) -> None:
        config = self.config_service.config
        old_theme = config.theme
        for key, value in values.items():
            setattr(config, key, value)
        try:
            StartupService().set_enabled(config.start_with_windows)
            self.config_service.save()
        except OSError:
            QMessageBox.warning(self, "Автозапуск", "Не удалось изменить автозапуск Windows. Остальные настройки сохранены.")
            self.config_service.save()
        if old_theme != config.theme:
            apply_theme(QApplication.instance(), config.theme)
        self.restart_automation()
        self.refresh_all()
        QMessageBox.information(self, "Настройки", "Настройки сохранены.")

    def open_logs(self) -> None:
        path = application_data_dir() / "logs"
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def clear_history(self) -> None:
        if QMessageBox.question(self, "Очистить историю?", "Записи истории будут удалены. Технические логи сохранятся.") == QMessageBox.StandardButton.Yes:
            self.history_service.clear()
            self.refresh_all()

    def reset_settings(self) -> None:
        answer = QMessageBox.warning(
            self,
            "Сбросить настройки?",
            "Будут удалены все правила и пользовательские настройки. Файлы на диске не изменятся.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.config_service.reset()
            self.restart_automation()
            apply_theme(QApplication.instance(), self.config_service.config.theme)
            self.refresh_all()

    def _after_startup(self) -> None:
        self._check_recovery()
        if not self.config_service.config.onboarding_complete:
            onboarding = OnboardingDialog(self)
            onboarding.create_archive.connect(lambda: QTimer.singleShot(0, self.create_archive_rule))
            onboarding.create_extract.connect(lambda: QTimer.singleShot(0, self.create_extract_rule))
            onboarding.exec()
            self.config_service.config.onboarding_complete = True
            self.config_service.save()

    def _check_recovery(self) -> None:
        roots = [Path(rule.destination) for rule in self.rules.archive_rules]
        roots.extend(Path(rule.watch_folder) for rule in self.rules.extract_rules)
        roots.extend(Path(rule.destination) for rule in self.rules.extract_rules if rule.destination)
        incomplete = find_incomplete_operations(roots)
        if not incomplete:
            return
        answer = QMessageBox.question(
            self,
            "Найдены незавершённые операции",
            f"Найдено временных объектов: {len(incomplete)}. Удалить их? Пользовательские файлы не затрагиваются.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            removed, errors = clean_incomplete_operations(incomplete)
            if errors:
                QMessageBox.warning(self, "Очистка завершена частично", f"Удалено: {removed}. Не удалось удалить: {len(errors)}.")

    def closeEvent(self, event: QCloseEvent) -> None:
        tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        if self._allow_close or not self.config_service.config.minimize_to_tray or not tray_available:
            self.shutdown()
            event.accept()
            if not self._allow_close:
                QTimer.singleShot(0, QApplication.quit)
            return
        event.ignore()
        self.hide()
        if self.config_service.config.show_tray_hint:
            self.tray.icon.showMessage(
                "SleepArchive продолжает работать",
                "Приложение свёрнуто в область уведомлений. Это сообщение больше не появится.",
                QSystemTrayIcon.MessageIcon.Information,
                5_000,
            )
            self.config_service.config.show_tray_hint = False
            self.config_service.save()

    def quit_application(self) -> None:
        if self._workers:
            answer = QMessageBox.warning(
                self,
                "Операции выполняются",
                "Безопасно отменить текущие операции и выйти?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._allow_close = True
        self.shutdown()
        QApplication.quit()

    def shutdown(self) -> None:
        self.scheduler.stop()
        self.watcher.stop()
        for worker in list(self._workers.values()):
            worker.cancel()
        self.thread_pool.waitForDone(5_000)
        self.tray.icon.hide()

    @staticmethod
    def _app_icon() -> QIcon:
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        icon_path = root / "assets" / "SleepArchive.ico"
        if icon_path.exists():
            return QIcon(str(icon_path))
        return QIcon()
