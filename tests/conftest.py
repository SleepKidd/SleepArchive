from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def old_file():
    def create(path: Path, content: bytes = b"content") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        old = 1_600_000_000
        os.utime(path, (old, old))
        return path

    return create

