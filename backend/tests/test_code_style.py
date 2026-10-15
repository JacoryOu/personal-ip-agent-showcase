# -*- coding: utf-8 -*-
"""Regression tests for the code-style gate (scripts/check_code_style.py).

The tests build tiny fixture repositories in tmp_path and run the real CLI,
so they never touch the repository's own baseline file.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "scripts" / "check_code_style.py"


def _fixture(tmp_path: Path, files: dict[str, str], baseline: str = "") -> Path:
    """Create a minimal repo whose rules module points at tmp_path."""
    root = tmp_path / "repo"
    (root / "scripts" / "code_style").mkdir(parents=True)
    (root / "backend" / "app").mkdir(parents=True)
    (root / "backend" / "tests").mkdir(parents=True)
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    (root / "scripts" / "code_style_baseline.txt").write_text(
        baseline, encoding="utf-8")

    rules = REPO_ROOT / "scripts" / "code_style" / "rules.py"
    # Re-point REPO_ROOT/BASELINE_FILE at the fixture by copying the package
    # and patching the two constants with a tiny shim module.
    shim = (rules.read_text(encoding="utf-8")
            .replace("Path(__file__).resolve().parents[2]",
                     f"Path(r'{root}')")
            .replace('BASELINE_FILE = REPO_ROOT / "scripts" / '
                     '"code_style_baseline.txt"',
                     f'BASELINE_FILE = REPO_ROOT / "scripts" / '
                     f'"code_style_baseline.txt"'))
    (root / "scripts" / "code_style" / "rules.py").write_text(
        shim, encoding="utf-8")

    for name in ("__init__", "io", "baseline", "checks"):
        (root / "scripts" / "code_style" / f"{name}.py").write_text(
            (REPO_ROOT / "scripts" / "code_style" / f"{name}.py")
            .read_text(encoding="utf-8"), encoding="utf-8")

    entry = (GATE.read_text(encoding="utf-8")
             .replace("Path(__file__).resolve().parent",
                      f"Path(r'{root / 'scripts'}')")
             .replace("from code_style.", "from code_style."))
    (root / "scripts" / "check_code_style.py").write_text(
        entry, encoding="utf-8")
    return root


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(root / "scripts" / "check_code_style.py"), *args],
        cwd=root, capture_output=True, text=True, check=False)


def _source(lines: int, header: str = "# pad\n") -> str:
    return header + "".join(f"x{i} = {i}\n" for i in range(lines))


def test_new_source_over_hard_cap_fails(tmp_path):
    root = _fixture(tmp_path, {"backend/app/huge.py": _source(700)})
    result = _run(root)
    assert result.returncode == 1
    assert "file-size/hard-cap" in result.stdout


def test_new_test_over_hard_cap_fails(tmp_path):
    root = _fixture(tmp_path, {"backend/tests/huge_test.py": _source(1100)})
    result = _run(root)
    assert result.returncode == 1
    assert "file-size/test-hard-cap" in result.stdout


def test_source_in_review_band_blocks(tmp_path):
    root = _fixture(tmp_path, {"backend/app/mid.py": _source(450)})
    result = _run(root)
    assert result.returncode == 1
    assert "file-size/review" in result.stdout


def test_legacy_growth_blocks(tmp_path):
    root = _fixture(tmp_path,
                    {"backend/app/legacy.py": _source(320)},
                    baseline="backend/app/legacy.py 300\n")
    result = _run(root)
    assert result.returncode == 1
    assert "file-size/legacy-growth" in result.stdout


def test_legacy_shrink_requires_baseline_lowering(tmp_path):
    root = _fixture(tmp_path,
                    {"backend/app/legacy.py": _source(100)},
                    baseline="backend/app/legacy.py 300\n")
    result = _run(root)
    assert result.returncode == 1
    assert "baseline/too-loose" in result.stdout


def test_deleted_baseline_entry_blocks(tmp_path):
    root = _fixture(tmp_path, {},
                    baseline="backend/app/gone.py 300\n")
    result = _run(root)
    assert result.returncode == 1
    assert "baseline/stale" in result.stdout


@pytest.mark.parametrize("bad", [
    "backend/app/x.py\n",
    "backend/app/x.py abc\n",
    "backend/app/x.py 10\nbackend/app/x.py 20\n",
])
def test_illegal_baseline_format_blocks(tmp_path, bad):
    root = _fixture(tmp_path, {}, baseline=bad)
    result = _run(root)
    assert result.returncode == 1
    assert "baseline/illegal" in result.stdout


def test_bare_except_detected(tmp_path):
    root = _fixture(tmp_path, {
        "backend/app/bad.py": "def f():\n    try:\n        pass\n"
                              "    except:\n        pass\n"})
    result = _run(root)
    assert result.returncode == 1
    assert "error/bare-except" in result.stdout


def test_naming_violations_detected(tmp_path):
    root = _fixture(tmp_path, {"backend/app/badName.py":
                               "class badName:\n    def DoThing(self):\n"
                               "        pass\n"})
    result = _run(root)
    assert result.returncode == 1
    assert "naming/module-file" in result.stdout
    assert "naming/class" in result.stdout
    assert "naming/function" in result.stdout


def test_legal_names_pass(tmp_path):
    root = _fixture(tmp_path, {"backend/app/ok.py":
                               "class _FakeEngine:\n"
                               "    def do_GET(self):\n"
                               "        pass\n\n\n"
                               "def test_中文可以():\n"
                               "    pass\n"})
    result = _run(root)
    assert result.returncode == 0, result.stdout


def test_utf8_bom_file_is_parsed(tmp_path):
    root = _fixture(tmp_path, {})
    (root / "backend" / "app" / "bom.py").write_bytes(
        b"\xef\xbb\xbfclass Thing:\n    pass\n")
    result = _run(root)
    assert result.returncode == 0, result.stdout


def test_vue_component_filename(tmp_path):
    root = _fixture(tmp_path, {
        "frontend/src/components/myWidget.vue": "<template/>\n",
        "frontend/src/components/GoodWidget.vue": "<template/>\n",
    })
    result = _run(root)
    assert result.returncode == 1
    assert "naming/vue-component" in result.stdout


def test_docstring_is_not_a_prompt(tmp_path):
    root = _fixture(tmp_path, {"backend/app/mod.py":
                               '"""You are a helpful assistant.\n\n'
                               'Please follow the rules.\n"""\n'})
    result = _run(root)
    assert result.returncode == 0, result.stdout


def test_inline_prompt_blocks(tmp_path):
    root = _fixture(tmp_path, {"backend/app/agent.py":
                               "PROMPT = (\n"
                               '    "You are a senior writer. Write 2000 words "'
                               ' "about the topic and follow the rules.\\n"\n'
                               ")\n"})
    result = _run(root)
    assert result.returncode == 1
    assert "ai/prompt-location" in result.stdout


def test_prompt_directory_is_allowed(tmp_path):
    root = _fixture(tmp_path, {
        "backend/app/engine/prompts/writer.py":
            "PROMPT = (\n"
            '    "You are a senior writer. Write 2000 words "'
            ' "about the topic and follow the rules.\\n"\n'
            ")\n"})
    result = _run(root)
    assert result.returncode == 0, result.stdout
