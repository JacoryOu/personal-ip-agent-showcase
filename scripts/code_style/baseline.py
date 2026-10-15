# -*- coding: utf-8 -*-
"""Legacy file-size baseline handling.

The baseline records a frozen ceiling for files that already exceeded the
thresholds when the gate was introduced. Ceilings may only go down.
"""

from __future__ import annotations

from .rules import BASELINE_FILE


def _illegal(illegal: list[str] | None, lineno: int, raw: str, why: str) -> None:
    if illegal is not None:
        illegal.append(f"line {lineno}: {raw.strip()!r}: {why}")


def load_baseline(illegal: list[str] | None = None) -> dict[str, int]:
    """Parse ``code_style_baseline.txt``.

    Malformed lines are never silently ignored: when ``illegal`` is given, a
    human-readable reason is appended for each rejected line so the gate can
    block instead of losing a ceiling.
    """
    baseline: dict[str, int] = {}
    if not BASELINE_FILE.exists():
        return baseline
    for lineno, raw in enumerate(
            BASELINE_FILE.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            _illegal(illegal, lineno, raw,
                     "expected exactly '<path> <max lines>'")
            continue
        rel, value = parts
        rel = rel.replace("\\", "/")
        if rel in baseline:
            _illegal(illegal, lineno, raw, f"duplicate entry for {rel}")
            continue
        try:
            ceiling = int(value)
        except ValueError:
            _illegal(illegal, lineno, raw, f"{value!r} is not an integer")
            continue
        baseline[rel] = ceiling
    return baseline
