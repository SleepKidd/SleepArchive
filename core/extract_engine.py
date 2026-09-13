from __future__ import annotations

import logging
import os
import shutil
import tarfile
import threading
import zipfile
from collections.abc import Callable
from pathlib import Path

from core.models import ExtractDestination, ExtractRule, OperationResult, OriginalAction, ProgressUpdate
from core.safety import (
    SafetyError,
    atomic_move_no_replace,
    ensure_free_space,
    is_archive,
    is_within,
    require_writable_directory,
    unique_path,
    validate_member_path,
    wait_until_stable,
    zip_member_is_symlink,
)

ProgressCallback = Callable[[ProgressUpdate], None]
LOGGER = logging.getLogger(__name__)
MAX_ARCHIVE_MEMBERS = 100_000
MAX_UNCOMPRESSED_BYTES = 2 * 1024**4


class ExtractEngine:
    """Safely extracts supported formats without overwriting user files."""

    def run(
        self,
        archive_path: Path,
        rule: ExtractRule,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
        check_stability: bool = True,
    ) -> OperationResult:
        rule.validate()
        cancel_event = cancel_event or threading.Event()
        archive_path = archive_path.expanduser().resolve()
        if not archive_path.is_file():
            raise SafetyError("Архив больше не существует.")
        if not is_archive(archive_path):
            raise SafetyError("Этот формат архива не поддерживается.")
        if check_stability and not wait_until_stable(archive_path, rule.stability_seconds):
            raise SafetyError("Архив всё ещё изменяется или загружается. Попробуйте позже.")

        root = archive_path.parent if rule.destination_mode == ExtractDestination.BESIDE_ARCHIVE else Path(rule.destination)
        root = require_writable_directory(root, "Папка распаковки")
        base_name = self._base_name(archive_path)
        final_path = unique_path(root / base_name)
        temporary = root / f".{base_name}.{os.getpid()}.sleeparchive_tmp"
        temporary = unique_path(temporary)
        temporary.mkdir(parents=False, exist_ok=False)

        try:
            lower = archive_path.name.lower()
            if lower.endswith(".zip"):
                count, total = self._extract_zip(archive_path, temporary, progress, cancel_event)
            elif lower.endswith(".7z"):
                count, total = self._extract_7z(archive_path, temporary, progress, cancel_event)
            else:
                count, total = self._extract_tar(archive_path, temporary, progress, cancel_event)
            if cancel_event.is_set():
                raise _Cancelled
            self._verify_output(temporary, count)
            atomic_move_no_replace(temporary, final_path)
            self._handle_archive(archive_path, rule)
            return OperationResult(
                True,
                f"Архив распакован: {count} файлов.",
                files_count=count,
                bytes_count=total,
                output_paths=[final_path],
            )
        except _Cancelled:
            shutil.rmtree(temporary, ignore_errors=True)
            return OperationResult(False, "Распаковка отменена. Неполные файлы удалены.", cancelled=True)
        except SafetyError:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        except (zipfile.BadZipFile, tarfile.TarError) as exc:
            shutil.rmtree(temporary, ignore_errors=True)
            raise SafetyError("Архив повреждён или имеет неверный формат.") from exc
        except PermissionError as exc:
            shutil.rmtree(temporary, ignore_errors=True)
            LOGGER.exception("Extraction permission failure")
            raise SafetyError("SleepArchive не может записать файлы в выбранную папку.") from exc
        except OSError as exc:
            shutil.rmtree(temporary, ignore_errors=True)
            LOGGER.exception("Extraction failed")
            raise SafetyError("Не удалось распаковать архив. Исходный архив не изменён.") from exc

    @staticmethod
    def _base_name(path: Path) -> str:
        lower = path.name.lower()
        if lower.endswith(".tar.gz"):
            return path.name[:-7]
        if lower.endswith(".tgz"):
            return path.name[:-4]
        return path.stem

    def _extract_zip(
        self,
        source: Path,
        target: Path,
        progress: ProgressCallback | None,
        cancel_event: threading.Event,
    ) -> tuple[int, int]:
        with zipfile.ZipFile(source, "r") as archive:
            members = archive.infolist()
            files = [member for member in members if not member.is_dir()]
            total = self._validate_zip_members(files, target)
            ensure_free_space(target, total)
            done = 0
            bytes_done = 0
            for member in members:
                if cancel_event.is_set():
                    raise _Cancelled
                destination = validate_member_path(member.filename, target)
                if member.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member, "r") as input_stream, destination.open("xb") as output_stream:
                    shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)
                done += 1
                bytes_done += member.file_size
                if progress:
                    progress(ProgressUpdate(done, len(files), member.filename, bytes_done, total))
            bad_file = archive.testzip()
            if bad_file:
                raise SafetyError(f"Архив повреждён: {bad_file}")
        return done, total

    @staticmethod
    def _validate_zip_members(members: list[zipfile.ZipInfo], target: Path) -> int:
        if len(members) > MAX_ARCHIVE_MEMBERS:
            raise SafetyError("В архиве слишком много файлов.")
        total = 0
        for member in members:
            validate_member_path(member.filename, target)
            if zip_member_is_symlink(member.external_attr):
                raise SafetyError(f"Символические ссылки в ZIP запрещены: {member.filename}")
            total += member.file_size
            if member.compress_size > 0 and member.file_size > 100 * 1024**2:
                if member.file_size / member.compress_size > 1_000:
                    raise SafetyError("Архив имеет подозрительно высокий коэффициент сжатия.")
        if total > MAX_UNCOMPRESSED_BYTES:
            raise SafetyError("Распакованный архив превышает безопасный лимит размера.")
        return total

    def _extract_tar(
        self,
        source: Path,
        target: Path,
        progress: ProgressCallback | None,
        cancel_event: threading.Event,
    ) -> tuple[int, int]:
        with tarfile.open(source, "r:*") as archive:
            members = archive.getmembers()
            files = [member for member in members if member.isfile()]
            if len(files) > MAX_ARCHIVE_MEMBERS:
                raise SafetyError("В архиве слишком много файлов.")
            total = sum(member.size for member in files)
            if total > MAX_UNCOMPRESSED_BYTES:
                raise SafetyError("Распакованный архив превышает безопасный лимит размера.")
            for member in members:
                validate_member_path(member.name, target)
                if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                    raise SafetyError(f"Небезопасный объект в TAR: {member.name}")
                if not (member.isfile() or member.isdir()):
                    raise SafetyError(f"Неподдерживаемый объект в TAR: {member.name}")
            ensure_free_space(target, total)
            done = 0
            bytes_done = 0
            for member in members:
                if cancel_event.is_set():
                    raise _Cancelled
                destination = validate_member_path(member.name, target)
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                input_stream = archive.extractfile(member)
                if input_stream is None:
                    raise SafetyError(f"Не удалось прочитать файл из TAR: {member.name}")
                with input_stream, destination.open("xb") as output_stream:
                    shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)
                done += 1
                bytes_done += member.size
                if progress:
                    progress(ProgressUpdate(done, len(files), member.name, bytes_done, total))
        return done, total

    def _extract_7z(
        self,
        source: Path,
        target: Path,
        progress: ProgressCallback | None,
        cancel_event: threading.Event,
    ) -> tuple[int, int]:
        try:
            import py7zr
        except ImportError as exc:
            raise SafetyError("Для распаковки 7Z установите зависимость py7zr.") from exc
        try:
            with py7zr.SevenZipFile(source, "r") as archive:
                entries = archive.list()
                names = [entry.filename for entry in entries]
                if len(names) > MAX_ARCHIVE_MEMBERS:
                    raise SafetyError("В архиве слишком много файлов.")
                total_expected = 0
                for entry in entries:
                    validate_member_path(entry.filename, target)
                    if entry.is_symlink:
                        raise SafetyError(f"Символические ссылки в 7Z запрещены: {entry.filename}")
                    if entry.is_file:
                        total_expected += entry.uncompressed
                if total_expected > MAX_UNCOMPRESSED_BYTES:
                    raise SafetyError("Распакованный архив превышает безопасный лимит размера.")
                ensure_free_space(target, total_expected)
                if cancel_event.is_set():
                    raise _Cancelled
                archive.extractall(path=target)
            files = [path for path in target.rglob("*") if path.is_file()]
            total = sum(path.stat().st_size for path in files)
            if total != total_expected:
                raise SafetyError("Проверка размера распакованного 7Z-архива не пройдена.")
            for path in target.rglob("*"):
                if path.is_symlink() or not is_within(path, target):
                    raise SafetyError("7Z-архив содержит небезопасную ссылку или путь.")
            if progress:
                progress(ProgressUpdate(len(files), len(files), source.name, total, total))
            return len(files), total
        except py7zr.Bad7zFile as exc:
            raise SafetyError("7Z-архив повреждён или имеет неверный формат.") from exc

    @staticmethod
    def _verify_output(target: Path, expected_files: int) -> None:
        actual = 0
        for path in target.rglob("*"):
            if path.is_symlink() or not is_within(path, target):
                raise SafetyError("Результат распаковки содержит небезопасный путь.")
            if path.is_file():
                actual += 1
        if actual != expected_files:
            raise SafetyError("Проверка результата распаковки не пройдена.")

    @staticmethod
    def _handle_archive(path: Path, rule: ExtractRule) -> None:
        if rule.archive_action == OriginalAction.KEEP:
            return
        if rule.archive_action == OriginalAction.DELETE:
            path.unlink()
            return
        destination = (
            Path(rule.archive_move_destination)
            if rule.archive_move_destination
            else Path(rule.watch_folder) / "Archives"
        )
        destination = require_writable_directory(destination, "Папка обработанных архивов")
        shutil.move(str(path), str(unique_path(destination / path.name)))


class _Cancelled(Exception):
    pass
