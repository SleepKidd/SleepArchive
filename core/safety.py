from __future__ import annotations

import fnmatch
import ctypes
import errno
import os
import re
import shutil
import stat
import sys
import time
from pathlib import Path, PurePosixPath
from typing import Iterable


class SafetyError(RuntimeError):
    """A user-readable error raised when an operation would be unsafe."""


ARCHIVE_SUFFIXES = (".zip", ".7z", ".tar", ".tar.gz", ".tgz")
WINDOWS_DRIVE = re.compile(r"^[a-zA-Z]:")


def is_archive(path: Path) -> bool:
    lower = path.name.lower()
    return any(lower.endswith(suffix) for suffix in ARCHIVE_SUFFIXES)


def require_readable_directory(path: Path, label: str) -> Path:
    try:
        resolved = path.expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise SafetyError(f"{label} больше не существует: {path}") from exc
    if not resolved.is_dir():
        raise SafetyError(f"{label} не является папкой: {path}")
    if not os.access(resolved, os.R_OK | os.X_OK):
        raise SafetyError(f"SleepArchive не может прочитать папку: {path}")
    return resolved


def require_writable_directory(path: Path, label: str) -> Path:
    path = path.expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise SafetyError(f"Не удалось подготовить папку «{label}»: {path}") from exc
    if not resolved.is_dir() or not os.access(resolved, os.W_OK | os.X_OK):
        raise SafetyError(f"SleepArchive не может записывать в папку: {path}")
    return resolved


def is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def validate_member_path(name: str, target: Path) -> Path:
    """Resolve an archive member beneath target or reject traversal/absolute paths."""
    normalized = name.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if not normalized or pure.is_absolute() or WINDOWS_DRIVE.match(normalized):
        raise SafetyError(f"Архив содержит небезопасный путь: {name}")
    if any(part in {"..", ""} for part in pure.parts):
        raise SafetyError(f"Архив содержит выход за целевую папку: {name}")
    candidate = target.joinpath(*pure.parts).resolve()
    if not is_within(candidate, target):
        raise SafetyError(f"Архив пытается записать файл за пределами папки: {name}")
    return candidate


def zip_member_is_symlink(external_attr: int) -> bool:
    mode = external_attr >> 16
    return stat.S_ISLNK(mode)


def ensure_free_space(target: Path, estimated_bytes: int, overhead: float = 1.1) -> None:
    usage = shutil.disk_usage(target)
    needed = int(max(estimated_bytes, 1) * overhead)
    if usage.free < needed:
        raise SafetyError(
            f"Недостаточно свободного места. Нужно примерно {format_bytes(needed)}, "
            f"доступно {format_bytes(usage.free)}."
        )


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    name = path.name
    if path.is_dir() or not path.suffix:
        stem, suffix = name, ""
    elif name.lower().endswith(".tar.gz"):
        stem, suffix = name[:-7], ".tar.gz"
    else:
        stem, suffix = path.stem, path.suffix
    number = 2
    while True:
        candidate = path.with_name(f"{stem} ({number}){suffix}")
        if not candidate.exists():
            return candidate
        number += 1


def atomic_move_no_replace(source: Path, target: Path) -> None:
    """Atomically move a generated result without replacing an existing path."""
    if target.exists():
        raise FileExistsError(target)
    if os.name == "nt":
        os.rename(source, target)
        return
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is not None:
            renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            renameat2.restype = ctypes.c_int
            result = renameat2(-100, os.fsencode(source), -100, os.fsencode(target), 1)
            if result == 0:
                return
            error = ctypes.get_errno()
            if error == errno.EEXIST:
                raise FileExistsError(target)
            if error not in {errno.ENOSYS, errno.EINVAL}:
                raise OSError(error, os.strerror(error), str(target))
    if source.is_file():
        os.link(source, target)
        source.unlink()
        return
    raise SafetyError("Файловая система не поддерживает безопасное атомарное перемещение папки.")


def path_matches(path: Path, relative: Path, patterns: Iterable[str]) -> bool:
    posix_relative = relative.as_posix()
    return any(
        fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(posix_relative, pattern)
        for pattern in patterns
        if pattern.strip()
    )


def wait_until_stable(
    path: Path,
    stable_seconds: int = 3,
    timeout_seconds: int = 120,
    poll_interval: float = 1.0,
) -> bool:
    """Wait until size and mtime remain unchanged for the requested interval."""
    deadline = time.monotonic() + timeout_seconds
    stable_since: float | None = None
    previous: tuple[int, int] | None = None
    while time.monotonic() < deadline:
        try:
            stat_result = path.stat()
            current = (stat_result.st_size, stat_result.st_mtime_ns)
        except OSError:
            stable_since = None
            previous = None
            time.sleep(poll_interval)
            continue
        if current == previous:
            stable_since = stable_since or time.monotonic()
            if time.monotonic() - stable_since >= stable_seconds:
                return True
        else:
            previous = current
            stable_since = None
        time.sleep(poll_interval)
    return False


def format_bytes(value: int) -> str:
    size = float(value)
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if size < 1024 or unit == "ТБ":
            return f"{size:.0f} {unit}" if unit == "Б" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} ТБ"
