# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

PROJECT_ROOT = Path(SPECPATH)
hiddenimports = (
    collect_submodules("py7zr")
    + collect_submodules("watchdog")
    + ["watchdog.observers.winapi", "watchdog.observers.read_directory_changes"]
)
datas = [(str(PROJECT_ROOT / "assets"), "assets")] + collect_data_files("py7zr")

a = Analysis(
    [str(PROJECT_ROOT / "app.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SleepArchive",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    icon=str(PROJECT_ROOT / "assets" / "SleepArchive.ico"),
    version=str(PROJECT_ROOT / "version_info.txt"),
)
