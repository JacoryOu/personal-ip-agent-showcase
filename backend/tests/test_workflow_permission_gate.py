# -*- coding: utf-8 -*-
"""Tests for the workflow-permission declaration gate.

The gate must fail when a *new* high-risk call site is added without declaring
its permission requirement, and must stay green on the current tree.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_workflow_permissions.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("check_workflow_permissions", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_workflow_permissions"] = module
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


def test_repo_tree_passes_gate():
    assert gate.check() == [], "current tree must satisfy the workflow permission gate"


def test_gate_flags_undeclared_skill_execution(tmp_path):
    sample = tmp_path / "backend" / "app" / "services" / "rogue_service.py"
    sample.parent.mkdir(parents=True)
    sample.write_text(
        "def run_something(skill_manager):\n"
        "    return skill_manager.execute_skill_sync('trending-radar', {})\n",
        encoding="utf-8",
    )
    findings = gate.scan_file(sample)
    assert findings, "undeclared execute_skill_sync must be reported"
    assert findings[0]["kind"] == "skill execution"
    assert findings[0]["scope"] == "run_something"


def test_gate_accepts_declared_scope(tmp_path):
    sample = tmp_path / "backend" / "app" / "services" / "good_service.py"
    sample.parent.mkdir(parents=True)
    sample.write_text(
        "from app.core.workflow_permissions import require_authorization\n"
        "\n"
        "def run_something(skill_manager, actor_id):\n"
        "    require_authorization('skill.execute', actor_id=actor_id)\n"
        "    return skill_manager.execute_skill_sync('trending-radar', {})\n",
        encoding="utf-8",
    )
    assert gate.scan_file(sample) == []


def test_undeclared_site_is_not_baselined_by_default():
    assert gate.KNOWN_UNDECLARED_BASELINE, "honest Partial inventory should not be empty"
    for key, reason in gate.KNOWN_UNDECLARED_BASELINE.items():
        assert ":" in key and key.endswith((".py:execute_skill_sync", ".py:httpx.Client", ".py:httpx.AsyncClient"))
        assert reason and len(reason) > 10, f"baseline entry {key} needs a concrete reason"


def test_baseline_only_silences_known_files():
    finding = {"file": "backend/app/services/rogue.py", "callee": "execute_skill_sync"}
    assert gate.baseline_reason(finding) is None


@pytest.mark.parametrize("callee", ["httpx.Client", "httpx.AsyncClient", "execute_skill_sync"])
def test_high_risk_patterns_are_recognised(callee):
    pattern_hit = any(
        __import__("re").search(p, callee) for p, _ in gate.HIGH_RISK_CALLS
    )
    assert pattern_hit, f"{callee} must be treated as high risk"
