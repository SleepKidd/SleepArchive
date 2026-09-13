from __future__ import annotations

import logging
import os
import shutil
import threading
import zipfile
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.models import (
    ArchiveFormat,
    ArchivePreview,
    ArchiveRule,
    Grouping,
    OperationResult,
    OriginalAction,
    PreviewItem,
    ProgressUpdate,
)
from core.safety import (
    SafetyError,
    atomic_move_no_replace,
    ensure_free_space,
    is_within,
    path_matches,
    require_readable_directory,
    require_writable_directory,
    unique_path,
)

ProgressCallback = Callable[[ProgressUpdate], None]
LOGGER = logging.getLogger(__name__)


class ArchiveEngine:
    """Creates verified archives transactionally before touching originals."""

    def preview(self, rule: ArchiveRule, now: datetime | None = None) -> ArchivePreview:
        rule.validate()
        source = require_readable_directory(Path(rule.source), "Исходная папка")
        destination = Path(rule.destination).expanduser().resolve()
        destination_inside_source = is_within(destination, source)
        cutoff = (now or datetime.now(timezone.utc)).timestamp() - timedelta(days=rule.age_days).total_seconds()
        result = ArchivePreview()

        for root, directories, filenames in os.walk(source, followlinks=False):
            root_path = Path(root)
            directories[:] = [
                name
                for name in directories
                if not (root_path / name).is_symlink()
                and not (destination_inside_source and is_within((root_path / name), destination))
            ]
            if not rule.recursive and root_path != source:
                directories[:] = []
                continue
            for filename in filenames:
                path = root_path / filename
                try:
                    if path.is_symlink() or not path.is_file():
                        result.excluded.append(path)
                        continue
                    relative = path.relative_to(source)
                    if (destination_inside_source and is_within(path, destination)) or path_matches(path, relative, rule.exclusions):
                        result.excluded.append(path)
                        continue
                    stat_result = path.stat()
                    if stat_result.st_mtime > cutoff:
                        continue
                    group_name = self._group_name(rule.grouping, stat_result.st_mtime)
                    item = PreviewItem(path, relative, stat_result.st_size, group_name, stat_result.st_mtime_ns)
                    result.included.append(item)
                    result.archives.setdefault(group_name, []).append(item)
                except (OSError, ValueError) as exc:
                    LOGGER.warning("Skipping unreadable candidate %s: %s", path, exc)
                    result.excluded.append(path)
        return result

    def run(
        self,
        rule: ArchiveRule,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> OperationResult:
        cancel_event = cancel_event or threading.Event()
        preview = self.preview(rule)
        if not preview.included:
            return OperationResult(True, "Подходящих файлов не найдено.")

        destination = require_writable_directory(Path(rule.destination), "Папка архива")
        ensure_free_space(destination, preview.total_size, overhead=1.05)
        created: list[Path] = []
        processed = 0
        bytes_done = 0

        try:
            for group_name, items in sorted(preview.archives.items()):
                if cancel_event.is_set():
                    raise _Cancelled
                final_path = unique_path(destination / f"{group_name}.{rule.archive_format.value}")
                temporary = final_path.with_name(f".{final_path.name}.sleeparchive_tmp")
                if temporary.exists():
                    temporary.unlink()
                try:
                    if rule.archive_format == ArchiveFormat.ZIP:
                        processed, bytes_done = self._create_zip(
                            temporary,
                            items,
                            rule.compression_level,
                            processed,
                            bytes_done,
                            len(preview.included),
                            preview.total_size,
                            progress,
                            cancel_event,
                        )
                        self._verify_zip(temporary, items)
                    else:
                        processed, bytes_done = self._create_7z(
                            temporary,
                            items,
                            rule.compression_level,
                            processed,
                            bytes_done,
                            len(preview.included),
                            preview.total_size,
                            progress,
                            cancel_event,
                        )
                        self._verify_7z(temporary, items)
                    self._verify_sources_unchanged(items)
                    atomic_move_no_replace(temporary, final_path)
                    created.append(final_path)
                except Exception:
                    temporary.unlink(missing_ok=True)
                    raise

            if cancel_event.is_set():
                raise _Cancelled
            self._verify_sources_unchanged(preview.included)
            self._handle_originals(rule, preview.included)
            return OperationResult(
                True,
                f"Архивирование завершено: {len(preview.included)} файлов.",
                files_count=len(preview.included),
                bytes_count=preview.total_size,
                output_paths=created,
                warnings=[f"Исключено или недоступно: {len(preview.excluded)}"] if preview.excluded else [],
            )
        except _Cancelled:
            for output in created:
                output.unlink(missing_ok=True)
            return OperationResult(
                False,
                "Операция отменена. Оригиналы не изменены.",
                files_count=processed,
                bytes_count=bytes_done,
                cancelled=True,
            )
        except SafetyError:
            for output in created:
                output.unlink(missing_ok=True)
            raise
        except PermissionError as exc:
            for output in created:
                output.unlink(missing_ok=True)
            LOGGER.exception("Archive permission failure")
            raise SafetyError("SleepArchive не может получить доступ к одному из файлов. Проверьте права доступа.") from exc
        except OSError as exc:
            for output in created:
                output.unlink(missing_ok=True)
            LOGGER.exception("Archive operation failed")
            raise SafetyError("Не удалось завершить архивацию. Оригиналы не были удалены.") from exc
        except Exception as exc:
            for output in created:
                output.unlink(missing_ok=True)
            LOGGER.exception("Unexpected archive operation failure")
            raise SafetyError("Не удалось завершить архивацию. Оригиналы не были изменены.") from exc

    @staticmethod
    def _group_name(grouping: Grouping, timestamp: float) -> str:
        date = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        if grouping == Grouping.MONTH:
            return date.strftime("%Y-%m")
        if grouping == Grouping.YEAR:
            return date.strftime("%Y")
        return "Archive"

    @staticmethod
    def _create_zip(
        path: Path,
        items: list[PreviewItem],
        level: int,
        processed: int,
        bytes_done: int,
        total_files: int,
        total_bytes: int,
        progress: ProgressCallback | None,
        cancel_event: threading.Event,
    ) -> tuple[int, int]:
        compression = zipfile.ZIP_STORED if level == 0 else zipfile.ZIP_DEFLATED
        with zipfile.ZipFile(path, "x", compression=compression, compresslevel=level or None, allowZip64=True) as archive:
            for item in items:
                if cancel_event.is_set():
                    raise _Cancelled
                archive.write(item.source, item.relative_path.as_posix())
                processed += 1
                bytes_done += item.size
                if progress:
                    progress(ProgressUpdate(processed, total_files, str(item.relative_path), bytes_done, total_bytes))
        return processed, bytes_done

    @staticmethod
    def _verify_zip(path: Path, items: list[PreviewItem]) -> None:
        expected = {item.relative_path.as_posix(): item.size for item in items}
        with zipfile.ZipFile(path, "r") as archive:
            bad_file = archive.testzip()
            if bad_file:
                raise SafetyError(f"Проверка архива не пройдена: повреждён файл {bad_file}")
            actual = {info.filename: info.file_size for info in archive.infolist() if not info.is_dir()}
        if actual != expected:
            raise SafetyError("Содержимое созданного архива не совпадает с ожидаемым. Оригиналы сохранены.")

    @staticmethod
    def _create_7z(
        path: Path,
        items: list[PreviewItem],
        level: int,
        processed: int,
        bytes_done: int,
        total_files: int,
        total_bytes: int,
        progress: ProgressCallback | None,
        cancel_event: threading.Event,
    ) -> tuple[int, int]:
        try:
            import py7zr
        except ImportError as exc:
            raise SafetyError("Для формата 7Z установите зависимость py7zr.") from exc
        filters = [{"id": py7zr.FILTER_LZMA2, "preset": level}]
        with py7zr.SevenZipFile(path, "x", filters=filters) as archive:
            for item in items:
                if cancel_event.is_set():
                    raise _Cancelled
                archive.write(item.source, item.relative_path.as_posix())
                processed += 1
                bytes_done += item.size
                if progress:
                    progress(ProgressUpdate(processed, total_files, str(item.relative_path), bytes_done, total_bytes))
        return processed, bytes_done

    @staticmethod
    def _verify_7z(path: Path, items: list[PreviewItem]) -> None:
        try:
            import py7zr
        except ImportError as exc:
            raise SafetyError("Для проверки 7Z установите зависимость py7zr.") from exc
        expected = {item.relative_path.as_posix() for item in items}
        with py7zr.SevenZipFile(path, "r") as archive:
            actual = {name.replace("\\", "/") for name in archive.getnames() if not name.endswith("/")}
            tested = archive.test()
        if tested is False or actual != expected:
            raise SafetyError("Проверка созданного 7Z-архива не пройдена. Оригиналы сохранены.")

    @staticmethod
    def _verify_sources_unchanged(items: list[PreviewItem]) -> None:
        for item in items:
            try:
                current = item.source.stat()
                if current.st_size != item.size or current.st_mtime_ns != item.mtime_ns:
                    raise SafetyError(f"Файл изменился во время архивации: {item.source.name}")
            except FileNotFoundError as exc:
                raise SafetyError(f"Файл исчез во время архивации: {item.source.name}") from exc

    @staticmethod
    def _handle_originals(rule: ArchiveRule, items: list[PreviewItem]) -> None:
        if rule.original_action == OriginalAction.KEEP:
            return
        if rule.original_action == OriginalAction.DELETE:
            for item in items:
                if not os.access(item.source.parent, os.W_OK):
                    raise SafetyError(f"Нет прав для удаления файла: {item.source.name}")
            for item in items:
                item.source.unlink()
            return
        move_root = Path(rule.move_destination) if rule.move_destination else Path(rule.destination) / "Originals"
        move_root = require_writable_directory(move_root / rule.name, "Папка оригиналов")
        for item in items:
            target = unique_path(move_root / item.relative_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item.source), str(target))


class _Cancelled(Exception):
    pass
