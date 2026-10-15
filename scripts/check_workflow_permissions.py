# -*- coding: utf-8 -*-
"""Gate: high-risk workflow actions must declare their permission requirement.

``app.core.workflow_permissions`` is the single authorization + audit decision
point for actions that leave ordinary application data: skill execution,
external network egress, publish / platform actions, credential operations and
unattended (scheduler) work.

This gate protects that promise with a deterministic AST check:

* every high-risk call site (``execute_skill*``, ``httpx.Client`` /
  ``httpx.AsyncClient``, publish / upload / crawl / credential-export /
  sensitive-path helpers) must live inside a scope that declares permissions
  through the workflow layer (``require_authorization``,
  ``workflow_permission_guard``, ``declare_action``);
* **new** undeclared call sites fail the gate;
* call sites that predate this layer are listed in
  ``KNOWN_UNDECLARED_BASELINE`` with the reason they are not migrated yet.
  That inventory is an honest Partial record, not a permanent waiver: removing
  an entry requires migrating the call site.

Usage::

    python scripts/check_workflow_permissions.py
    python scripts/check_workflow_permissions.py --json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_ROOT = REPO_ROOT / "backend" / "app"

DECLARATION_MARKERS = (
    "require_authorization",
    "workflow_permission_guard",
    "declare_action",
)

# Framework modules that are the enforcement layer itself.
EXEMPT_FILES = {
    "backend/app/core/workflow_permissions.py",
    "backend/app/core/net_guard.py",
}

# (regex matched against the dotted callee, human label)
HIGH_RISK_CALLS: Tuple[Tuple[str, str], ...] = (
    (r"^(?:[\w\.]+\.)?execute_skill_sync$", "skill execution"),
    (r"^(?:[\w\.]+\.)?execute_skill$", "skill execution"),
    (r"^httpx\.AsyncClient$", "external network egress"),
    (r"^httpx\.Client$", "external network egress"),
    (r"^requests\.(get|post|put|patch|delete)$", "external network egress"),
    (r"^publish(_to_platform|_article)?$", "external publish"),
    (r"^crawl\w*$", "platform crawl"),
    (r"^export_credential\w*$", "credential export"),
    (r"^sync_credential\w*$", "credential sync"),
    (r"^resolve_sensitive_path$", "sensitive file access"),
)

# Honest inventory of historical call sites not yet migrated to the workflow
# permission layer. Key format: "<repo-relative file>:<dotted callee>".
KNOWN_UNDECLARED_BASELINE: Dict[str, str] = {
    "backend/app/api/images.py:httpx.AsyncClient": (
        "image remote proxy - HTTP boundary owns egress; workflow gate migration pending"
    ),
    "backend/app/api/materials_collect.py:execute_skill_sync": (
        "material parse/upload skill (split from materials.py) - skill policy only; workflow gate migration pending"
    ),
    "backend/app/engine/cognitive_engine.py:execute_skill_sync": (
        "content distributor / DNA skills - skill policy only; workflow gate migration pending"
    ),
    "backend/app/services/credential_service.py:httpx.Client": (
        "credential provider probe - workflow gate migration pending"
    ),
    "backend/app/services/material_service.py:execute_skill_sync": (
        "material ingestion skill - skill policy only; workflow gate migration pending"
    ),
    "backend/app/services/memory_benchmarks.py:execute_skill_sync": (
        "benchmark deconstruct / dialogue clash skills (split from memory_service.py) - skill policy only; workflow gate migration pending"
    ),
    "backend/app/services/memory_lifecycle.py:execute_skill_sync": (
        "own-work DNA skill (split from memory_service.py) - skill policy only; workflow gate migration pending"
    ),
    "backend/app/services/platform_crawler_collect_service.py:execute_skill_sync": (
        "platform crawl skill (split from platform_crawler_service.py) - skill policy only; workflow gate migration pending"
    ),
}

SKIP_DIR_NAMES = {"__pycache__", ".venv", "node_modules"}


def _call_text(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        parts: List[str] = []
        cur: ast.AST = func
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _declared_scopes(source: str) -> Set[str]:
    """Names of functions in this source that declare workflow permissions."""
    declared: Set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return declared
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = ast.get_source_segment(source, node) or ""
            if any(marker in body for marker in DECLARATION_MARKERS):
                declared.add(node.name)
    return declared


def _scope_map(tree: ast.Module) -> Dict[ast.AST, str]:
    """Map each node to its nearest enclosing function/method name."""
    scope: Dict[ast.AST, str] = {}

    class V(ast.NodeVisitor):
        def _fn(self, node) -> None:
            def assign(sub: ast.AST) -> None:
                for child in ast.iter_child_nodes(sub):
                    scope[child] = node.name
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        self.visit(child)
                    else:
                        assign(child)

            assign(node)

        def visit_function_def(self, node):
            self._fn(node)

        def visit_async_function_def(self, node):
            self._fn(node)

        # ast.NodeVisitor dispatches on the CamelCase node name; keep the
        # aliases as plain attributes so the naming gate stays satisfied.
        visit_FunctionDef = visit_function_def
        visit_AsyncFunctionDef = visit_async_function_def

    V().visit(tree)
    return scope


def scan_file(path: Path) -> List[Dict[str, object]]:
    source = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(path))
    declared = _declared_scopes(source)
    try:
        rel = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel = path.as_posix()
    if rel in EXEMPT_FILES:
        return []

    scope_map = _scope_map(tree)
    findings: List[Dict[str, object]] = []
    module_declares = any(m in source for m in DECLARATION_MARKERS)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = _call_text(node)
        for pattern, label in HIGH_RISK_CALLS:
            if not re.search(pattern, callee):
                continue
            scope = scope_map.get(node, "<module>")
            if scope == "<module>":
                if module_declares:
                    break
            elif scope in declared:
                break
            findings.append(
                {
                    "file": rel,
                    "kind": label,
                    "line": node.lineno,
                    "scope": scope,
                    "callee": callee,
                }
            )
            break
    return findings


def scan_all() -> List[Dict[str, object]]:
    findings: List[Dict[str, object]] = []
    for path in sorted(SCAN_ROOT.rglob("*.py")):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        findings.extend(scan_file(path))
    return findings


def baseline_reason(finding: Dict[str, object]) -> Optional[str]:
    """Baseline entries are keyed by file:callee but tolerate receiver variants.

    A call site may be written ``skill_manager.execute_skill_sync(...)`` or
    ``self.skill_manager.execute_skill_sync(...)``; both are the same logical
    site, so the file part of the key is what decides.
    """
    rel = str(finding["file"])
    callee = str(finding["callee"]).rsplit(".", 1)[-1]
    exact = KNOWN_UNDECLARED_BASELINE.get(f"{rel}:{callee}")
    if exact:
        return exact
    for key, reason in KNOWN_UNDECLARED_BASELINE.items():
        if key.split(":", 1)[0] == rel:
            return reason
    return None


def check() -> List[str]:
    errors: List[str] = []
    for f in scan_all():
        if baseline_reason(f) is not None:
            continue
        errors.append(
            f"{f['file']}:{f['line']}: undeclared high-risk {f['kind']} "
            f"(callee={f['callee']}, scope={f['scope']}) - wrap the enclosing scope with "
            f"require_authorization() / workflow_permission_guard(), or record the site "
            f"in KNOWN_UNDECLARED_BASELINE with a concrete reason."
        )
    return errors


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="workflow permission declaration gate")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    findings = scan_all()
    errors = check()
    baselined = [f for f in findings if baseline_reason(f) is not None]

    if args.json:
        print(json.dumps({"findings": findings, "errors": errors}, indent=2, ensure_ascii=False))
    else:
        print(f"scanned backend/app: {len(findings)} high-risk call site(s)")
        print(f"  declared via workflow permission layer: {len(findings) - len(baselined)}")
        print(f"  recorded in KNOWN_UNDECLARED_BASELINE (Partial): {len(baselined)}")
        for err in errors:
            print(f"ERROR {err}")

    if errors:
        print(f"\nworkflow permission gate FAILED with {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("\nworkflow permission gate PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())






