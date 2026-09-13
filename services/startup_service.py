from __future__ import annotations

import os
import sys
from pathlib import Path


class StartupService:
    REGISTRY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    VALUE_NAME = "SleepArchive"

    @staticmethod
    def is_supported() -> bool:
        return os.name == "nt"

    def set_enabled(self, enabled: bool) -> None:
        if not self.is_supported():
            return
        import winreg

        command = self._command()
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            self.REGISTRY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                winreg.SetValueEx(key, self.VALUE_NAME, 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, self.VALUE_NAME)
                except FileNotFoundError:
                    return

    @staticmethod
    def _command() -> str:
        if getattr(sys, "frozen", False):
            return f'"{Path(sys.executable)}" --minimized'
        app = Path(__file__).resolve().parents[1] / "app.py"
        executable = Path(sys.executable)
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.exists():
            executable = pythonw
        return f'"{executable}" "{app}" --minimized'
