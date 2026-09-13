from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from core.extract_engine import ExtractEngine
from core.models import ExtractDestination, ExtractRule, OriginalAction
from core.safety import SafetyError


def rule(folder: Path, **changes) -> ExtractRule:
    values = {"name": "Downloads", "watch_folder": str(folder), "stability_seconds": 1}
    values.update(changes)
    return ExtractRule(**values)


def test_extract_zip(tmp_path: Path) -> None:
    archive = tmp_path / "program.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("file1.txt", "hello")
        output.writestr("folder/file2.txt", "world")
    result = ExtractEngine().run(archive, rule(tmp_path), check_stability=False)
    assert result.success
    assert result.files_count == 2
    assert (tmp_path / "program" / "file1.txt").read_text() == "hello"
    assert archive.exists()


def test_existing_destination_gets_numbered_name(tmp_path: Path) -> None:
    (tmp_path / "program").mkdir()
    (tmp_path / "program" / "user.txt").write_text("safe")
    archive = tmp_path / "program.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("new.txt", "new")
    result = ExtractEngine().run(archive, rule(tmp_path), check_stability=False)
    assert result.output_paths[0].name == "program (2)"
    assert (tmp_path / "program" / "user.txt").read_text() == "safe"


def test_extract_tar_gz(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.tar.gz"
    payload = b"tar data"
    with tarfile.open(archive, "w:gz") as output:
        info = tarfile.TarInfo("nested/file.txt")
        info.size = len(payload)
        output.addfile(info, io.BytesIO(payload))
    result = ExtractEngine().run(archive, rule(tmp_path), check_stability=False)
    assert result.success
    assert (tmp_path / "bundle" / "nested" / "file.txt").read_bytes() == payload


def test_empty_zip_creates_empty_folder(tmp_path: Path) -> None:
    archive = tmp_path / "empty.zip"
    with zipfile.ZipFile(archive, "w"):
        pass
    result = ExtractEngine().run(archive, rule(tmp_path), check_stability=False)
    assert result.success
    assert result.files_count == 0
    assert (tmp_path / "empty").is_dir()


def test_corrupt_archive_is_reported_and_source_kept(tmp_path: Path) -> None:
    archive = tmp_path / "broken.zip"
    archive.write_bytes(b"not a zip")
    with pytest.raises(SafetyError, match="повреждён"):
        ExtractEngine().run(archive, rule(tmp_path), check_stability=False)
    assert archive.exists()
    assert not (tmp_path / "broken").exists()


def test_selected_destination(tmp_path: Path) -> None:
    watch = tmp_path / "watch"
    watch.mkdir()
    target = tmp_path / "target"
    archive = watch / "file.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("ok.txt", "ok")
    result = ExtractEngine().run(
        archive,
        rule(watch, destination_mode=ExtractDestination.SELECTED_FOLDER, destination=str(target)),
        check_stability=False,
    )
    assert result.output_paths[0] == target / "file"


def test_archive_moved_only_after_success(tmp_path: Path) -> None:
    archive = tmp_path / "done.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("ok.txt", "ok")
    moved = tmp_path / "processed"
    ExtractEngine().run(
        archive,
        rule(tmp_path, archive_action=OriginalAction.MOVE, archive_move_destination=str(moved)),
        check_stability=False,
    )
    assert not archive.exists()
    assert (moved / "done.zip").exists()


def test_7z_round_trip_when_dependency_available(tmp_path: Path) -> None:
    py7zr = pytest.importorskip("py7zr")
    payload = tmp_path / "payload.txt"
    payload.write_text("seven zip")
    archive = tmp_path / "data.7z"
    with py7zr.SevenZipFile(archive, "w") as output:
        output.write(payload, "payload.txt")
    payload.unlink()
    result = ExtractEngine().run(archive, rule(tmp_path), check_stability=False)
    assert result.success
    assert (tmp_path / "data" / "payload.txt").read_text() == "seven zip"

