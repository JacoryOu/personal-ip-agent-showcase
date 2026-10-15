# -*- coding: utf-8 -*-
"""Gate: coding-standard drift (file size, naming, bare excepts, prompt location).

Machine-enforced half of ``docs/architecture/09_Coding_Standards.md``.
Thresholds live in ``scripts/code_style/rules.py`` and MUST stay in sync with
section S4 of that document.

Usage::

    python scripts/check_code_style.py
    python scripts/check_code_style.py --base main
    python scripts/check_code_style.py --staged
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from code_style.checks import (  # noqa: E402
    check_baseline_sanity,
    check_file_sizes,
    check_frontend_naming,
    check_module_filenames,
    check_python_naming,
)
from code_style.io import iter_files  # noqa: E402
from code_style.rules import REPO_ROOT, SCAN_ROOTS  # noqa: E402

BASELINE_REL = "scripts/code_style_baseline.txt"


def _git(*args: str) -> list[str]:
    out = subprocess.run(["git", *args], cwd=REPO_ROOT,
                         capture_output=True, text=True, check=False)
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def changed_files(base: str | None, staged: bool) -> list[str]:
    if staged:
        return _git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    if not base:
        return []
    return _git("diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD")


def _filter_changed(findings, base: str | None, staged: bool):
    if not staged and not base:
        return findings
    touched = set(changed_files(base, staged))
    if not touched:
        return findings
    if BASELINE_REL in touched:
        # A staged change to the baseline must be validated as a whole.
        return findings
    return [f for f in findings if f.path in touched]


def collect_findings() -> list:
    findings: list = []
    check_baseline_sanity(findings)
    check_file_sizes(findings)
    check_module_filenames(findings)
    for path, rel in iter_files(SCAN_ROOTS):
        check_python_naming(path, rel, findings)
    check_frontend_naming(findings)
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Code style gate")
    parser.add_argument("--base", nargs="?", default=None,
                        help="only report findings for files changed against <base>")
    parser.add_argument("--staged", action="store_true",
                        help="only report findings for staged files (pre-commit)")
    args = parser.parse_args(argv)

    findings = _filter_changed(collect_findings(), args.base, args.staged)
    findings.sort(key=lambda f: (f.path, f.line, f.rule))
    for finding in findings:
        print(finding.render())

    blocking = [f for f in findings if f.blocking]
    scoped = bool(args.staged or args.base)
    print(f"\ncheck_code_style: {len(findings)} finding(s) "
          f"({len(blocking)} blocking) in "
          f"{len({f.path for f in findings})} flagged file(s)")
    print(f"scanned: {len(iter_files(SCAN_ROOTS))} file(s)"
          f"{' (findings limited to changed files)' if scoped else ''}")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
