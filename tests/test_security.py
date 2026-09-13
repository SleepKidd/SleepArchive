from __future__ import annotations

import io
import stat
import tarfile
import zipfile
from pathlib import Path

import pytest

from core.extract_engine import ExtractEngine
from core.models import ExtractRule
from core.safety import SafetyError, unique_path, validate_member_path


def rule(folder: Path) -> ExtractRule:
    return ExtractRule("Security", str(folder), stability_seconds=1)


@pytest.mark.parametrize("name", ["../../malicious.exe", "..\\..\\malicious.exe", "/absolute/evil.txt", "C:\\evil.txt"])
def test_zip_slip_is_blocked(tmp_path: Path, name: str) -> None:
    archive = tmp_path / "attack.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(name, "bad")
    with pytest.raises(SafetyError, match="небезопас|предел|выход"):
        ExtractEngine().run(archive, rule(tmp_path), check_stability=False)
    assert not (tmp_path.parent / "malicious.exe").exists()
    assert not (tmp_path / "attack").exists()


def test_zip_symlink_is_blocked(tmp_path: Path) -> None:
    archive = tmp_path / "link.zip"
    info = zipfile.ZipInfo("link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(info, "../../outside")
    with pytest.raises(SafetyError, match="ссылки"):
        ExtractEngine().run(archive, rule(tmp_path), check_stability=False)


def test_tar_traversal_is_blocked(tmp_path: Path) -> None:
    archive = tmp_path / "attack.tar"
    with tarfile.open(archive, "w") as output:
        info = tarfile.TarInfo("../../evil.txt")
        info.size = 3
        output.addfile(info, io.BytesIO(b"bad"))
    with pytest.raises(SafetyError):
        ExtractEngine().run(archive, rule(tmp_path), check_stability=False)
    assert not (tmp_path.parent / "evil.txt").exists()


def test_tar_symlink_is_blocked(tmp_path: Path) -> None:
    archive = tmp_path / "link.tar"
    with tarfile.open(archive, "w") as output:
        info = tarfile.TarInfo("link")
        info.type = tarfile.SYMTYPE
        info.linkname = "../../outside"
        output.addfile(info)
    with pytest.raises(SafetyError, match="Небезопасный"):
        ExtractEngine().run(archive, rule(tmp_path), check_stability=False)


def test_member_validation_keeps_paths_inside_target(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    assert validate_member_path("folder/file.txt", target) == target / "folder" / "file.txt"


def test_unique_path_never_reuses_existing_file(tmp_path: Path) -> None:
    original = tmp_path / "data.tar.gz"
    original.write_bytes(b"data")
    assert unique_path(original).name == "data (2).tar.gz"

