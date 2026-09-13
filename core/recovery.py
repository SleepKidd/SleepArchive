from __future__ import annotations

from pathlib import Path


def find_incomplete_operations(roots: list[Path]) -> list[Path]:
    found: list[Path] = []
    visited: set[Path] = set()
    for root in roots:
        try:
            resolved = root.expanduser().resolve()
            if resolved in visited or not resolved.is_dir():
                continue
            visited.add(resolved)
            found.extend(resolved.glob("*.sleeparchive_tmp"))
            found.extend(resolved.glob(".*.sleeparchive_tmp"))
        except OSError:
            continue
    return sorted(set(found))


def clean_incomplete_operations(paths: list[Path]) -> tuple[int, list[str]]:
    removed = 0
    errors: list[str] = []
    for path in paths:
        try:
            if path.is_dir():
                import shutil

                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
            removed += 1
        except OSError:
            errors.append(str(path))
    return removed, errors

