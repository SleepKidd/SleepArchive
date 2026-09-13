from __future__ import annotations

import zipfile
import threading
from pathlib import Path

import pytest

from core.archive_engine import ArchiveEngine
from core.models import ArchiveRule, Grouping, OriginalAction
from core.safety import SafetyError


def make_rule(source: Path, destination: Path, **changes) -> ArchiveRule:
    values = {"name": "Test", "source": str(source), "destination": str(destination), "age_days": 0}
    values.update(changes)
    return ArchiveRule(**values)


def test_normal_zip_archiving_preserves_relative_paths(tmp_path: Path, old_file) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "archives"
    old_file(source / "one.txt", b"one")
    old_file(source / "nested" / "two.txt", b"two")
    result = ArchiveEngine().run(make_rule(source, destination, grouping=Grouping.SINGLE))
    assert result.success
    assert result.files_count == 2
    assert (source / "one.txt").exists()
    with zipfile.ZipFile(result.output_paths[0]) as archive:
        assert set(archive.namelist()) == {"one.txt", "nested/two.txt"}


def test_empty_directory_is_a_successful_noop(tmp_path: Path) -> None:
    source = tmp_path / "empty"
    source.mkdir()
    result = ArchiveEngine().run(make_rule(source, tmp_path / "out"))
    assert result.success
    assert result.files_count == 0
    assert not (tmp_path / "out").exists()


def test_missing_source_is_reported(tmp_path: Path) -> None:
    with pytest.raises(SafetyError, match="не существует"):
        ArchiveEngine().preview(make_rule(tmp_path / "missing", tmp_path / "out"))


def test_non_recursive_rule_skips_nested_files(tmp_path: Path, old_file) -> None:
    source = tmp_path / "source"
    old_file(source / "root.txt")
    old_file(source / "nested" / "child.txt")
    preview = ArchiveEngine().preview(make_rule(source, tmp_path / "out", recursive=False))
    assert [item.relative_path.as_posix() for item in preview.included] == ["root.txt"]


def test_exclusions_support_names_and_relative_globs(tmp_path: Path, old_file) -> None:
    source = tmp_path / "source"
    old_file(source / "keep.txt")
    old_file(source / "cache" / "skip.tmp")
    old_file(source / "other.tmp")
    preview = ArchiveEngine().preview(
        make_rule(source, tmp_path / "out", exclusions=["*.tmp", "cache/*"])
    )
    assert [item.relative_path.as_posix() for item in preview.included] == ["keep.txt"]
    assert len(preview.excluded) == 2


def test_existing_archive_is_never_overwritten(tmp_path: Path, old_file) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "out"
    destination.mkdir()
    old_file(source / "file.txt")
    existing = destination / "Archive.zip"
    existing.write_bytes(b"do not overwrite")
    result = ArchiveEngine().run(make_rule(source, destination, grouping=Grouping.SINGLE))
    assert existing.read_bytes() == b"do not overwrite"
    assert result.output_paths[0].name == "Archive (2).zip"


def test_destination_inside_source_is_automatically_excluded(tmp_path: Path, old_file) -> None:
    source = tmp_path / "source"
    destination = source / "Archive"
    old_file(source / "document.txt")
    old_file(destination / "old.zip")
    preview = ArchiveEngine().preview(make_rule(source, destination, grouping=Grouping.SINGLE))
    assert [item.relative_path.as_posix() for item in preview.included] == ["document.txt"]


def test_source_inside_destination_is_still_processed(tmp_path: Path, old_file) -> None:
    destination = tmp_path / "Archive"
    source = destination / "Documents"
    old_file(source / "document.txt")
    preview = ArchiveEngine().preview(make_rule(source, destination, grouping=Grouping.SINGLE))
    assert [item.relative_path.as_posix() for item in preview.included] == ["document.txt"]


def test_originals_deleted_only_after_verification(tmp_path: Path, old_file, monkeypatch) -> None:
    source = tmp_path / "source"
    file_path = old_file(source / "important.txt")
    engine = ArchiveEngine()
    monkeypatch.setattr(engine, "_verify_zip", lambda *_: (_ for _ in ()).throw(SafetyError("bad")))
    with pytest.raises(SafetyError):
        engine.run(make_rule(source, tmp_path / "out", grouping=Grouping.SINGLE, original_action=OriginalAction.DELETE))
    assert file_path.exists()


def test_originals_can_be_deleted_after_verified_archive(tmp_path: Path, old_file) -> None:
    source = tmp_path / "source"
    file_path = old_file(source / "old.txt")
    result = ArchiveEngine().run(
        make_rule(source, tmp_path / "out", grouping=Grouping.SINGLE, original_action=OriginalAction.DELETE)
    )
    assert result.success
    assert not file_path.exists()


def test_originals_can_be_moved_without_overwrite(tmp_path: Path, old_file) -> None:
    source = tmp_path / "source"
    old_file(source / "nested" / "old.txt")
    move_to = tmp_path / "moved"
    existing = old_file(move_to / "Test" / "nested" / "old.txt", b"existing")
    ArchiveEngine().run(
        make_rule(
            source,
            tmp_path / "out",
            grouping=Grouping.SINGLE,
            original_action=OriginalAction.MOVE,
            move_destination=str(move_to),
        )
    )
    assert existing.read_bytes() == b"existing"
    assert (move_to / "Test" / "nested" / "old (2).txt").exists()


def test_cancelled_archive_keeps_originals_and_no_output(tmp_path: Path, old_file) -> None:
    source = tmp_path / "source"
    file_path = old_file(source / "important.txt", b"important")
    cancelled = threading.Event()
    cancelled.set()
    result = ArchiveEngine().run(make_rule(source, tmp_path / "out", grouping=Grouping.SINGLE), cancel_event=cancelled)
    assert result.cancelled
    assert file_path.exists()
    assert list((tmp_path / "out").glob("*.zip")) == []


def test_7z_archiving_when_dependency_available(tmp_path: Path, old_file) -> None:
    py7zr = pytest.importorskip("py7zr")
    source = tmp_path / "source"
    old_file(source / "seven.txt", b"seven")
    rule = make_rule(source, tmp_path / "out", grouping=Grouping.SINGLE)
    from core.models import ArchiveFormat

    rule.archive_format = ArchiveFormat.SEVEN_ZIP
    result = ArchiveEngine().run(rule)
    assert result.success
    with py7zr.SevenZipFile(result.output_paths[0], "r") as archive:
        assert archive.getnames() == ["seven.txt"]
