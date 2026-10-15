# -*- coding: utf-8 -*-
"""Individual rule implementations for the code-style gate."""

from __future__ import annotations

import ast
from pathlib import Path

from .baseline import load_baseline
from .io import count_lines, iter_files, read_source
from .rules import (
    BASELINE_FILE,
    BASELINE_MAX_LINES,
    CLASS_RE,
    FFI_STRUCT_RE,
    Finding,
    FRONTEND_ROOTS,
    FUNC_RE,
    HTTP_HANDLER_RE,
    MODULE_RE,
    PROMPT_ALLOWED_PREFIXES,
    PROMPT_HINT_RE,
    REPO_ROOT,
    SCAN_ROOTS,
    SOURCE_SOFT,
    SOURCE_REVIEW,
    SOURCE_HARD,
    SOURCE_SUFFIXES,
    TEST_SOFT,
    TEST_REVIEW,
    TEST_HARD,
    VUE_COMPONENT_RE,
)


def thresholds(rel: str):
    if "/tests/" in rel or rel.startswith("backend/tests"):
        return TEST_SOFT, TEST_REVIEW, TEST_HARD, "test-hard-cap"
    return SOURCE_SOFT, SOURCE_REVIEW, SOURCE_HARD, "hard-cap"


# ------------------------------------------------------------- baseline

def check_baseline_sanity(findings: list[Finding]) -> None:
    illegal: list[str] = []
    baseline = load_baseline(illegal)
    for why in illegal:
        findings.append(Finding(
            BASELINE_FILE.name, 1, "baseline/illegal",
            f"malformed baseline entry {why}"))
    for rel, ceiling in baseline.items():
        if not (0 < ceiling <= BASELINE_MAX_LINES):
            findings.append(Finding(
                BASELINE_FILE.name, 1, "baseline/illegal",
                f"{rel}: implausible ceiling {ceiling}"))
            continue
        if rel.startswith("/") or ".." in rel.split("/"):
            findings.append(Finding(
                BASELINE_FILE.name, 1, "baseline/illegal",
                f"{rel}: baseline paths must be repo-relative"))
            continue
        target = REPO_ROOT / rel
        if not target.exists():
            findings.append(Finding(
                BASELINE_FILE.name, 1, "baseline/stale",
                f"{rel} no longer exists; drop it from the baseline"))
            continue
        actual = count_lines(target)
        if actual < ceiling:
            findings.append(Finding(
                BASELINE_FILE.name, 1, "baseline/too-loose",
                f"{rel} is now {actual} lines but baseline still allows {ceiling}; "
                "lower it to lock in the progress"))


# ------------------------------------------------------------ file sizes

def check_file_sizes(findings: list[Finding]) -> None:
    baseline = load_baseline()
    for path, rel in iter_files(SCAN_ROOTS):
        if path.suffix not in SOURCE_SUFFIXES:
            continue
        soft, review, hard, hard_rule = thresholds(rel)
        count = count_lines(path)
        ceiling = baseline.get(rel)
        if ceiling is not None:
            if count > ceiling:
                findings.append(Finding(
                    rel, 1, "file-size/legacy-growth",
                    f"{count} lines exceeds the frozen legacy ceiling {ceiling}; "
                    "split the file instead of raising the baseline"))
            continue
        if count > hard:
            findings.append(Finding(
                rel, 1, f"file-size/{hard_rule}",
                f"{count} lines exceeds the hard cap {hard}; split before merging"))
        elif count > review:
            rule = ("file-size/review" if hard_rule == "hard-cap"
                    else "file-size/test-review")
            findings.append(Finding(
                rel, 1, rule,
                f"{count} lines exceeds the review threshold {review}"))
        elif count > soft:
            findings.append(Finding(
                rel, 1, "file-size/soft",
                f"{count} lines exceeds the ideal ceiling {soft}"))


# --------------------------------------------------------------- naming

def _is_prompt_allowed(rel: str) -> bool:
    norm = rel.replace("\\", "/")
    return any(norm == p or norm.startswith(p + "/") or norm.startswith(p + "\\")
               for p in PROMPT_ALLOWED_PREFIXES)


def _maybe_prompt(rel: str, node: ast.Constant, findings: list[Finding]) -> None:
    if _is_prompt_allowed(rel):
        return
    text = node.value
    if len(text) < 80 or "\n" not in text:
        return
    if PROMPT_HINT_RE.search(text):
        findings.append(Finding(
            rel, node.lineno, "ai/prompt-location",
            "prompt-like string literal outside backend/app/engine/prompts/; "
            "move it into a prompt module"))


def check_python_naming(path: Path, rel: str, findings: list[Finding]) -> None:
    if path.suffix != ".py":
        return
    try:
        tree = ast.parse(read_source(path), filename=rel)
    except (SyntaxError, UnicodeDecodeError) as exc:
        findings.append(Finding(
            rel, getattr(exc, "lineno", 1) or 1, "syntax", str(exc)))
        return

    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if not (CLASS_RE.match(node.name) or FFI_STRUCT_RE.match(node.name)):
                findings.append(Finding(
                    rel, node.lineno, "naming/class",
                    f"class {node.name!r} must be PascalCase"))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            if HTTP_HANDLER_RE.match(name):
                continue  # BaseHTTPRequestHandler protocol method
            if not name.isidentifier():
                findings.append(Finding(
                    rel, node.lineno, "naming/function",
                    f"function {name!r} is not a valid identifier"))
            elif name.isascii() and not FUNC_RE.match(name):
                findings.append(Finding(
                    rel, node.lineno, "naming/function",
                    f"function {name!r} must be snake_case"))
        elif isinstance(node, ast.ExceptHandler) and node.type is None:
            findings.append(Finding(
                rel, node.lineno, "error/bare-except",
                "bare 'except:' swallows KeyboardInterrupt/SystemExit; "
                "catch a concrete exception"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                _maybe_prompt(rel, node, findings)


def check_module_filenames(findings: list[Finding]) -> None:
    for path, rel in iter_files(("backend/app", "backend/tests")):
        if path.suffix != ".py" or path.stem == "__init__":
            continue
        if not MODULE_RE.match(path.stem):
            findings.append(Finding(
                rel, 1, "naming/module-file",
                f"module filename {path.stem!r} must be snake_case"))


def check_frontend_naming(findings: list[Finding]) -> None:
    for path, rel in iter_files(FRONTEND_ROOTS):
        if path.suffix != ".vue":
            continue
        stem = path.stem
        if stem in ("index", "App", "main") or stem.startswith("_"):
            continue
        if not VUE_COMPONENT_RE.match(stem):
            findings.append(Finding(
                rel, 1, "naming/vue-component",
                f"single-file component {stem!r} should be PascalCase"))
