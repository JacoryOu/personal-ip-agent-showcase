# -*- coding: utf-8 -*-
"""Constants, thresholds and finding model for the code-style gate.

Every value here is mirrored by ``docs/architecture/09_Coding_Standards.md``.
Changing a number here without updating that document is documentation drift.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_FILE = REPO_ROOT / "scripts" / "code_style_baseline.txt"

# --- S4 file-size thresholds --------------------------------------------
SOURCE_SOFT, SOURCE_REVIEW, SOURCE_HARD = 300, 400, 600
TEST_SOFT, TEST_REVIEW, TEST_HARD = 500, 800, 1000
BASELINE_MAX_LINES = 10000

SCAN_ROOTS = ("backend/app", "backend/tests", "scripts")
FRONTEND_ROOTS = ("frontend/src",)
SKIP_DIRS = {
    "__pycache__", ".venv", "node_modules", "dist", "build",
    ".pytest_cache", ".ruff_cache", ".mypy_cache",
}
SOURCE_SUFFIXES = (".py", ".ts", ".js", ".vue")

MODULE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
CLASS_RE = re.compile(r"^_?[A-Z][A-Za-z0-9]*$")          # _FakeAgent is legal
FFI_STRUCT_RE = re.compile(r"^_?[A-Z][A-Z0-9_]*$")      # ctypes.Structure subclasses
FUNC_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
HTTP_HANDLER_RE = re.compile(r"^do_[A-Z]+$")            # do_GET, do_POST
VUE_COMPONENT_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
PROMPT_HINT_RE = re.compile(
    r"(You are\b|请你|请按|扮演|system prompt|##\s*(Role|角色|任务))",
    re.IGNORECASE,
)
PROMPT_ALLOWED_PREFIXES = ("backend/app/engine/prompts", "backend/tests", "scripts")

# Rules that fail the gate. Everything else is advisory only.
BLOCKING_RULES = frozenset({
    "baseline/illegal", "baseline/stale", "baseline/too-loose",
    "file-size/hard-cap", "file-size/legacy-growth", "file-size/review",
    "file-size/test-hard-cap",
    "naming/module-file", "naming/class", "naming/function",
    "naming/vue-component", "error/bare-except", "ai/prompt-location",
    "syntax",
})


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    message: str

    @property
    def blocking(self) -> bool:
        return self.rule in BLOCKING_RULES

    def render(self) -> str:
        tag = "BLOCK" if self.blocking else "warn "
        return f"{self.path}:{self.line}: [{tag} {self.rule}] {self.message}"
