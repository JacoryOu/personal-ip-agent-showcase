# -*- coding: utf-8 -*-
"""Filesystem walking and baseline parsing for the code-style gate."""

from __future__ import annotations

from pathlib import Path

from .rules import REPO_ROOT, SKIP_DIRS


def _walk(directory: Path, prefix: str):
    for entry in sorted(directory.iterdir(), key=lambda p: p.name):
        if entry.is_dir():
            if entry.name in SKIP_DIRS:
                continue
            yield from _walk(entry, f"{prefix}/{entry.name}")
        else:
            yield entry, f"{prefix}/{entry.name}"


def iter_files(roots) -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for root_rel in roots:
        root = REPO_ROOT / root_rel
        if not root.exists():
            continue
        found.extend(_walk(root, root_rel))
    return found


def count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        return sum(1 for _ in handle)


def read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")
