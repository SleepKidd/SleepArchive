from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_qt_ui_smoke_in_isolated_process(tmp_path: Path) -> None:
    script = r'''
from pathlib import Path
from PySide6.QtWidgets import QApplication
from core.models import ArchiveRule
from services.config_service import ConfigService
from services.history_service import HistoryService
from ui.dialogs.archive_rule_dialog import ArchiveRuleDialog
from ui.dialogs.extract_rule_dialog import ExtractRuleDialog
from ui.main_window import MainWindow
from ui.styles import apply_theme

root = Path(r"__ROOT__")
app = QApplication([])
config = ConfigService(root / "config.json")
config.config.onboarding_complete = True
config.save()
apply_theme(app, "light")
window = MainWindow(config, HistoryService(root / "history.json"), "test")
window.resize(900, 600)
window.show()
app.processEvents()
assert window.stack.count() == 5
assert window.dashboard._compact
archive_dialog = ArchiveRuleDialog()
extract_dialog = ExtractRuleDialog()
assert archive_dialog.windowTitle() == "Новое правило AutoArchive"
assert extract_dialog.windowTitle() == "Новое правило AutoExtract"
archive_dialog.close()
extract_dialog.close()

class CapturingPool:
    def start(self, worker):
        self.worker = worker

    def waitForDone(self, _timeout):
        return True

pool = CapturingPool()
window.thread_pool = pool
rule = ArchiveRule("Broken", str(root / "source"), str(root / "out"))
window._run_archive_worker(rule, source="schedule")
pool.worker.signals.error.emit("expected failure")
pool.worker.signals.finished.emit()
app.processEvents()
assert window.history_service.list_entries()[0].details == "expected failure"

window._allow_close = True
window.close()
app.processEvents()
print("ui-smoke-ok")
'''.replace("__ROOT__", str(tmp_path).replace("\\", "\\\\"))
    environment = dict(os.environ)
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "ui-smoke-ok" in result.stdout
