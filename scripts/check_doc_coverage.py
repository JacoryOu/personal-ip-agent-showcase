#!/usr/bin/env python3
"""Documentation coverage gate.

Verifies that code changes touching public surfaces are reflected in the
code-truth documentation set. Runs from the local commit-msg / post-merge Git
hooks, or manually. CI enforcement is deliberately not wired up yet.

Design principles:
- Code is the current fact; this gate catches *drift*, it does not judge design.
- A change may legitimately need no doc update. That must be *declared*, not silent.
- Fail closed on internal errors (bad git state, missing docs) so the gate cannot
  be bypassed by accident.

Usage:
    python scripts/check_doc_coverage.py [--base <ref>] [--staged] [--soft]

Exit codes:
    0  coverage OK (or explicitly waived / soft mode)
    1  coverage failure (missing doc updates, missing declaration, parse error)
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The policy module lives next to this script; make it importable both when the
# script is run directly and when it is loaded by path (tests, hooks).
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from doc_coverage_policy import (  # noqa: F401  (re-exported for callers/tests)
    AGENTS_DOC,
    ARCHITECTURE_DOC,
    CODE_TRUTH_DOCS,
    DECLARATION_PREFIXES,
    DESIGN_CREATION,
    DESIGN_DATA_MODEL,
    DESIGN_DISTRIBUTION,
    DESIGN_DIR,
    DESIGN_DOC_MAP,
    DESIGN_DOCS,
    DESIGN_INDEX,
    DESIGN_MATERIALS,
    DESIGN_SCHEDULER,
    DESIGN_SURFACES,
    DESIGN_VIRAL,
    DOC_ONLY_GLOBS,
    FEATURE_MAP,
    IGNORED_PATH_PARTS,
    PACKAGE_METADATA_SUFFIXES,
    PUBLIC_SURFACE_GLOBS,
    SANDBOX_DOC,
    SANDBOX_SENSITIVE,
    SECURITY_GLOBS,
    SKILL_DOC,
    SURFACE_DOC_MAP,
    TRUTH_DOCS_MUTABLE,
    WAIVER_FILE,
)


def log(msg: str = "") -> None:
    print(msg, flush=True)


@dataclass
class Result:
    exit_code: int = 0
    checked: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    message_text: str = ""


def run_git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout


def normalize(path: str) -> str:
    p = path.replace(chr(92), "/").strip()
    if p.startswith("./"):
        p = p[2:]
    return p


def is_ignored(path: str) -> bool:
    return any(part in IGNORED_PATH_PARTS for part in Path(path).parts)


def matches_any(path: str, globs: list[str]) -> bool:
    for pattern in globs:
        if fnmatch.fnmatch(path, pattern):
            return True
        # fnmatch treats "*" as matching "/" too, which is what we want here.
    return False


def collect_changed_files(base: str, staged: bool = False) -> list[str]:
    """Collect changed files.

    staged=True  -> only what is about to be committed (pre-commit path).
    staged=False -> branch diff vs base plus working tree (CI / manual path).
    """
    files: set[str] = set()

    if staged:
        try:
            out = run_git(["diff", "--cached", "--name-only"])
            files.update(normalize(x) for x in out.splitlines() if x.strip())
        except RuntimeError:
            pass
        return sorted(f for f in files if f and not is_ignored(f))

    # Committed diff vs base.
    try:
        out = run_git(["diff", "--name-only", f"{base}...HEAD"])
        files.update(normalize(x) for x in out.splitlines() if x.strip())
    except RuntimeError:
        # No common ancestor (e.g. base is a fresh branch name): fall back.
        out = run_git(["diff", "--name-only", base])
        files.update(normalize(x) for x in out.splitlines() if x.strip())

    # Staged + unstaged working tree changes.
    try:
        out = run_git(["diff", "--name-only", "HEAD"])
        files.update(normalize(x) for x in out.splitlines() if x.strip())
    except RuntimeError:
        pass

    # Untracked (not yet added) files. Without this, a brand-new public file is
    # invisible until it is staged, so a manual/CI run would miss new features.
    try:
        out = run_git(["ls-files", "--others", "--exclude-standard"])
        files.update(normalize(x) for x in out.splitlines() if x.strip())
    except RuntimeError:
        pass

    return sorted(f for f in files if f and not is_ignored(f))


def doc_changes(files: list[str]) -> list[str]:
    return [
        f
        for f in files
        if f.startswith("docs/") or f == AGENTS_DOC or f.startswith("docs/.doc-coverage")
    ]


def is_public_surface(path: str) -> bool:
    if matches_any(path, DOC_ONLY_GLOBS):
        return False
    return matches_any(path, PUBLIC_SURFACE_GLOBS) and not is_ignored(path)


def is_package_metadata(path: str) -> bool:
    """True for package initialisers, which need no design-doc route."""
    return normalize(path).endswith(PACKAGE_METADATA_SUFFIXES)


def design_docs_for(path: str) -> tuple[str, ...]:
    """Design docs allowed to describe this surface.

    Returns () when the surface is not routed to any design doc, in which case
    the design-doc requirement does not apply.
    """
    if is_package_metadata(path):
        return ()
    for prefix, docs in DESIGN_DOC_MAP:
        if path.startswith(prefix):
            return docs
    return ()


def design_documents(path: str, files: list[str]) -> bool:
    """True when a design doc owning this surface changed in this branch and
    mentions the surface. A commit-message declaration never satisfies this."""
    allowed = design_docs_for(path)
    if not allowed:
        return True
    for doc in allowed:
        if doc in files and file_mentioned_in(doc, path):
            return True
    return False


def is_security_sensitive(path: str) -> bool:
    return matches_any(path, SECURITY_GLOBS)


def changed_public_files(files: list[str]) -> list[str]:
    return [f for f in files if is_public_surface(f)]


def load_waivers() -> list[tuple[str, str]]:
    """Parse the waiver file. Format: one '<glob-or-file> :: <reason>' per line."""
    path = REPO_ROOT / WAIVER_FILE
    if not path.exists():
        return []
    entries: list[tuple[str, str]] = []
    for lineno, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "::" not in line:
            raise RuntimeError(f"{WAIVER_FILE}:{lineno} missing '::' separator")
        target, reason = line.split("::", 1)
        target = target.strip()
        reason = reason.strip()
        if not target or not reason:
            raise RuntimeError(f"{WAIVER_FILE}:{lineno} has empty target or reason")
        entries.append((target, reason))
    return entries


def waiver_matches(path: str, waivers: list[tuple[str, str]]) -> str | None:
    for target, reason in waivers:
        if target == path or fnmatch.fnmatch(path, target):
            return reason
    return None


def commit_message_declarations(message=None) -> list[str]:
    """Return explicit Doc-Impact declarations from THIS commit message only.

    History is deliberately never scanned: an old commit that merely mentioned
    Doc-Impact must not permanently waive future commits.
    """
    found: list[str] = []
    for raw in (message or "").splitlines():
        stripped = raw.strip()
        for prefix in DECLARATION_PREFIXES:
            if stripped.lower().startswith(prefix.lower()):
                value = stripped.split(":", 1)[1].strip()
                if value:
                    found.append(value)
                break
    return found


def changed_doc_text(files: list[str]) -> dict[str, str]:
    """Content of the docs that actually changed in this branch, plus the
    feature map as the canonical index of described features."""
    text: dict[str, str] = {}
    docs = doc_changes(files)
    for doc in docs:
        p = REPO_ROOT / doc
        if p.exists() and p.is_file():
            text[doc] = p.read_text(encoding="utf-8", errors="replace")
    for doc in CODE_TRUTH_DOCS:
        p = REPO_ROOT / doc
        if p.exists() and p.is_file():
            text.setdefault(doc, p.read_text(encoding="utf-8", errors="replace"))
    return text


def file_mentioned_in(doc: str, path: str) -> bool:
    content = (REPO_ROOT / doc).read_text(encoding="utf-8", errors="replace")
    base_name = Path(path).name
    stem = Path(path).stem
    # Full repo-relative path or file name. Directory-only mentions are too
    # loose: every API file lives under backend/app/api.
    return bool(path in content or base_name in content or stem in content)


def surface_documents(
    path: str, files: list[str], doc_text: dict[str, str]
) -> bool:
    """True when at least one doc allowed to cover this surface was changed in
    this branch *and* mentions the surface (or is the feature map that indexes
    it)."""
    if path.startswith("docs/architecture/"):
        # Architecture doc edits are self-documenting.
        return True
    # Security-relevant behaviour is documented in the sandbox/permission doc.
    if SANDBOX_DOC in files and is_security_sensitive(path):
        return True
    allowed: tuple[str, ...] = ()
    for prefix, docs in SURFACE_DOC_MAP:
        if path.startswith(prefix):
            allowed = docs
            break
    if not allowed:
        allowed = (FEATURE_MAP,)
    for doc in allowed:
        if doc in files:
            if file_mentioned_in(doc, path):
                return True
    return False


def check(res: Result, base: str, staged: bool, soft: bool) -> None:
    # 1. Code-truth docs must exist (fail closed).
    for doc in CODE_TRUTH_DOCS:
        if not (REPO_ROOT / doc).exists():
            res.failures.append(f"required code-truth doc is missing: {doc}")
    if res.failures:
        _finish(res, soft)
        return

    for doc in DESIGN_DOCS:
        if not (REPO_ROOT / doc).exists():
            res.failures.append(f"required design doc is missing: {doc}")
    if res.failures:
        _finish(res, soft)
        return

    waivers = load_waivers()
    files = collect_changed_files(base, staged=staged)
    res.checked = files

    public = changed_public_files(files)
    docs = doc_changes(files)

    if not public:
        res.notes.append("no public-surface changes detected")
        _finish(res, soft)
        return

    declaration_texts = commit_message_declarations(res.message_text or None)
    declarations = bool(declaration_texts)
    doc_text = changed_doc_text(files)

    # 2. Per-file coverage. A doc edit only covers a code file if the doc that
    #    is allowed to describe that surface actually changed in this branch
    #    and mentions it. Unrelated doc churn no longer buys blanket coverage.
    waived: dict[str, str] = {}
    uncovered: list[str] = []
    covered: list[str] = []
    for f in public:
        reason = waiver_matches(f, waivers)
        if reason:
            waived[f] = reason
            continue
        if declarations:
            continue
        if surface_documents(f, files, doc_text):
            covered.append(f)
        else:
            uncovered.append(f)

    if declaration_texts:
        for value in declaration_texts:
            res.notes.append(f"doc-impact declared in commit message: {value}")
    elif declarations:
        res.notes.append("doc-impact declared in commit message")
    for f, reason in waived.items():
        res.notes.append(f"waived: {f} :: {reason}")
    if covered:
        res.notes.append(f"documented public surfaces: {_bullets(covered)}")
    if uncovered:
        res.failures.append(
            "public-surface changes detected but no documentation was updated "
            "for them.\n"
            f"  uncovered public surfaces: {_bullets(uncovered)}\n"
            "  fix: mention the file/module in its matching truth doc, add a "
            f"per-file waiver to {WAIVER_FILE}, or declare 'Doc-Impact: <what "
            "and why no doc was needed>' in the commit message."
        )

    # 2b. Design-doc coverage: an INDEPENDENT requirement from the Feature Map.
    #     Neither a Feature Map update nor a commit-message declaration can
    #     replace it; only an explicit waiver can.
    design_covered: list[str] = []
    design_uncovered: list[str] = []
    for f in public:
        if waiver_matches(f, waivers):
            continue
        if design_documents(f, files):
            design_covered.append(f)
        else:
            design_uncovered.append(f)
    if design_covered:
        res.notes.append(f"design-doc updated: {_bullets(design_covered)}")
    routed = [f for f in design_uncovered if design_docs_for(f)]
    if routed:
        res.failures.append(
            "public-surface changes are not reflected in the design doc that "
            "owns them. Updating the Feature Map alone is not sufficient, and "
            "a 'Doc-Impact:' declaration cannot bypass this requirement.\n"
            f"  design-doc-less surfaces: {_bullets(routed)}\n"
            f"  fix: update the owning doc(s) under {DESIGN_DIR}/ and mention "
            f"the file/module, or add a per-file waiver to {WAIVER_FILE}."
        )
    unrouted = [f for f in design_uncovered if not design_docs_for(f)]
    if unrouted:
        res.notes.append(
            "no design-doc route for these surfaces (Feature Map rule still "
            f"applies): {_bullets(unrouted)}"
        )

    # 3. Security / permission behaviour changes must touch the sandbox doc.
    security = [f for f in public if is_security_sensitive(f)]
    if security:
        sandbox_doc_touched = SANDBOX_DOC in docs
        sandbox_undeclared = [f for f in security if not waiver_matches(f, waivers)]
        if not sandbox_doc_touched and sandbox_undeclared:
            res.failures.append(
                "security/permission behaviour changed without updating "
                f"{SANDBOX_DOC} and without a waiver.\n"
                f"  security-sensitive files: {_bullets(sandbox_undeclared)}\n"
                "  note: a Doc-Impact declaration does not bypass this "
                "requirement; update the doc or add a waiver."
            )

    # 4. Informational: surfaces absent from the feature map.
    missing_map = [f for f in public if not file_mentioned_in(FEATURE_MAP, f)]
    if missing_map:
        res.notes.append(f"not mentioned in {FEATURE_MAP}: {_bullets(missing_map)}")

    _finish(res, soft)


def _bullets(items: list[str], limit: int = 10) -> str:
    shown = items[:limit]
    tail = f" (+{len(items) - limit} more)" if len(items) > limit else ""
    return "".join(f"\n    - {i}" for i in shown) + tail


def _finish(res: Result, soft: bool) -> None:
    for n in res.notes:
        log(f"[note] {n}")
    if res.failures:
        for f in res.failures:
            log(f"[FAIL] {f}")
        res.exit_code = 1
    if soft and res.exit_code != 0:
        log("[soft] failure suppressed by --soft")
        res.exit_code = 0
        res.failures.clear()
    log(
        f"\ndoc-coverage: "
        f"{'OK' if res.exit_code == 0 else 'FAILED'} "
        f"(checked {len(res.checked)} changed files)"
    )
    sys.exit(res.exit_code)


def main() -> None:
    ap = argparse.ArgumentParser(description="Documentation coverage gate")
    ap.add_argument(
        "--base",
        default="main",
        help="base ref for diff (default: main)",
    )
    ap.add_argument(
        "--staged",
        action="store_true",
        help="check only staged changes (pre-commit path)",
    )
    ap.add_argument("--soft", action="store_true", help="report only, never fail")
    ap.add_argument(
        "--message-file",
        help="read Doc-Impact declarations from this commit message file "
        "(used by the commit-msg hook)",
    )
    args = ap.parse_args()

    if os.environ.get("SKIP_DOC_CHECK") == "1":
        log("[skip] SKIP_DOC_CHECK=1 - doc-coverage gate bypassed")
        sys.exit(0)

    try:
        res = Result()
        if args.message_file:
            mf = Path(args.message_file)
            if mf.is_file():
                res.message_text = mf.read_text(encoding="utf-8", errors="replace")
        check(res, args.base, args.staged, args.soft)
    except RuntimeError as exc:
        log(f"[FAIL] internal error: {exc}")
        if args.soft:
            log("[soft] failure suppressed by --soft")
            sys.exit(0)
        sys.exit(1)


if __name__ == "__main__":
    main()
