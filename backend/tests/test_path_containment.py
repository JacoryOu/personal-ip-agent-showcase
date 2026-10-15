# -*- coding: utf-8 -*-
"""Regression tests for path containment.

Covers two arbitrary-file / arbitrary-execute primitives:

1. Vault traversal: ``Path.rglob()`` follows Windows junctions and symlinks, so
   a link planted inside an allowed vault used to let the Obsidian scan read
   Markdown *outside* the vault and return its excerpt to the client.
2. Skill entrypoint: the ``entrypoint`` value comes from ``SKILL.md`` YAML, and
   a restricted token lowers privileges without restricting *which file runs*.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.skill_engine.discovery import (
    SkillDefinition,
    SkillDefinitionError,
    parse_skill_markdown,
    resolve_entrypoint_path,
)
from app.core.vault_path_guard import iter_safe_markdown_files


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _write(path: Path, text: str = "# note\n\nbody\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _make_junction(link: Path, target: Path) -> bool:
    """Create a directory junction (or directory symlink) on Windows."""
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try:
            link.symlink_to(target, target_is_directory=True)
            return True
        except (OSError, NotImplementedError):
            return False
    try:
        # mklink /J needs no admin rights on Windows.
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True,
            capture_output=True,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        try:
            link.symlink_to(target, target_is_directory=True)
            return True
        except (OSError, NotImplementedError):
            return False


def _make_file_symlink(link: Path, target: Path) -> bool:
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target)
        return True
    except (OSError, NotImplementedError):
        return False


# --------------------------------------------------------------------------
# 1. Vault traversal containment
# --------------------------------------------------------------------------
def test_safe_iterator_returns_normal_files(tmp_path):
    vault = tmp_path / "vault"
    _write(vault / "a.md")
    _write(vault / "nested" / "b.md")
    _write(vault / "nested" / "c.txt")  # filtered: not markdown

    found = {p.name for p in iter_safe_markdown_files(vault)}
    assert found == {"a.md", "b.md"}


def test_safe_iterator_is_sorted_and_deterministic(tmp_path):
    vault = tmp_path / "vault"
    for name in ["z.md", "a.md", "M.md"]:
        _write(vault / name)

    first = iter_safe_markdown_files(vault)
    second = iter_safe_markdown_files(vault)
    assert [p.name for p in first] == [p.name for p in second]
    assert [p.name for p in first] == ["a.md", "M.md", "z.md"]


def test_junction_inside_vault_does_not_leak_outside_markdown(tmp_path):
    vault = tmp_path / "vault"
    _write(vault / "inside.md")

    outside = tmp_path / "outside"
    secret = _write(outside / "secret.md", "# secret\n\nTOP_SECRET_BODY\n")

    link = vault / "escape"
    if not _make_junction(link, outside):
        pytest.skip("cannot create junction/symlink on this host")

    # Sanity check: the link really does expose the file through rglob,
    # otherwise this test would prove nothing.
    naive = {p.resolve() for p in vault.rglob("*.md")}
    assert secret.resolve() in naive, "rglob no longer follows links; premise changed"

    found = {p.resolve() for p in iter_safe_markdown_files(vault)}
    assert secret.resolve() not in found
    assert {p.name for p in iter_safe_markdown_files(vault)} == {"inside.md"}


def test_symlinked_markdown_file_inside_vault_is_skipped(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside"
    secret = _write(outside / "secret.md", "# secret\n")

    if not _make_file_symlink(vault / "link.md", secret):
        pytest.skip("cannot create file symlink on this host")

    assert {p.name for p in iter_safe_markdown_files(vault)} == set()


def test_iterator_handles_missing_root_without_raising(tmp_path):
    assert iter_safe_markdown_files(tmp_path / "does-not-exist") == []
    f = _write(tmp_path / "not-a-dir.md")
    assert iter_safe_markdown_files(f) == []


def test_obsidian_scan_does_not_return_linked_outside_excerpt(tmp_path, monkeypatch):
    """End-to-end: the scan preview must not surface outside-vault content."""
    from app.services import obsidian_service

    vault = tmp_path / "vault"
    _write(vault / "real.md", "---\ntitle: Real\n---\n\nreal body\n")

    outside = tmp_path / "outside"
    _write(outside / "leak.md", "---\ntitle: Leak\ntags: [t]\n---\n\nLEAKED_BODY\n")

    if not _make_junction(vault / "escape", outside):
        pytest.skip("cannot create junction/symlink on this host")

    monkeypatch.setenv("OBSIDIAN_ALLOWED_ROOTS", str(tmp_path))
    monkeypatch.setattr(obsidian_service, "get_allowed_roots", lambda: [tmp_path.resolve()])

    preview = obsidian_service.ObsidianBridgeService.scan_vault(vault_path=str(vault))
    blob = repr(preview)
    assert "LEAKED_BODY" not in blob
    assert "leak.md" not in blob
    assert preview["total_files"] == 1


# --------------------------------------------------------------------------
# 2. Skill entrypoint containment
# --------------------------------------------------------------------------
def _make_skill(root: Path, entrypoint: str, *, name: str = "demo") -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\n"
        f"name: {name}\n"
        "description: test skill\n"
        f"entrypoint: {entrypoint}\n"
        "runner_mode: restricted_token\n"
        "---\n\n"
        "body\n",
        encoding="utf-8",
    )
    return skill_md


def test_valid_entrypoint_resolves_inside_skill_dir(tmp_path):
    skill_dir = tmp_path / "demo"
    _write(skill_dir / "run.py", "print('ok')\n")

    resolved = resolve_entrypoint_path("run.py", str(skill_dir))
    assert resolved == (skill_dir / "run.py").resolve()
    assert resolved.is_file()

    sub = resolve_entrypoint_path("scripts/run.py", str(skill_dir))
    assert sub == (skill_dir / "scripts" / "run.py").resolve()


def test_relative_traversal_entrypoint_is_rejected(tmp_path):
    skill_dir = tmp_path / "demo"
    skill_dir.mkdir(parents=True)
    evil = _write(tmp_path / "evil.py", "print('pwned')\n")

    with pytest.raises(SkillDefinitionError):
        resolve_entrypoint_path("../../evil.py", str(skill_dir))
    with pytest.raises(SkillDefinitionError):
        resolve_entrypoint_path("../evil.py", str(skill_dir))

    assert evil.exists()


def test_absolute_entrypoint_outside_skill_dir_is_rejected(tmp_path):
    skill_dir = tmp_path / "demo"
    skill_dir.mkdir(parents=True)
    evil = _write(tmp_path / "evil.py", "print('pwned')\n")

    with pytest.raises(SkillDefinitionError):
        resolve_entrypoint_path(str(evil), str(skill_dir))


def test_absolute_entrypoint_inside_skill_dir_is_accepted(tmp_path):
    """An absolute path is fine as long as it stays inside the skill dir."""
    skill_dir = tmp_path / "demo"
    script = _write(skill_dir / "run.py", "print('ok')\n")

    resolved = resolve_entrypoint_path(str(script), str(skill_dir))
    assert resolved == script.resolve()


def test_entrypoint_pointing_at_directory_is_rejected(tmp_path):
    skill_dir = tmp_path / "demo"
    (skill_dir / "sub").mkdir(parents=True)

    # relative_to() succeeds for the directory itself, so it needs its own check.
    with pytest.raises(SkillDefinitionError):
        resolve_entrypoint_path("sub", str(skill_dir))


def test_entrypoint_through_symlink_escape_is_rejected(tmp_path):
    skill_dir = tmp_path / "demo"
    skill_dir.mkdir(parents=True)
    evil = _write(tmp_path / "evil.py", "print('pwned')\n")

    link = skill_dir / "run.py"
    try:
        link.symlink_to(evil)
    except (OSError, NotImplementedError):
        pytest.skip("cannot create file symlink on this host")

    with pytest.raises(SkillDefinitionError):
        resolve_entrypoint_path("run.py", str(skill_dir))


def test_entrypoint_path_property_raises_on_escape(tmp_path):
    skill_dir = tmp_path / "demo"
    skill_dir.mkdir(parents=True)
    skill = SkillDefinition(
        name="demo",
        description="d",
        entrypoint="../../evil.py",
        skill_dir=str(skill_dir),
    )
    with pytest.raises(SkillDefinitionError):
        _ = skill.entrypoint_path


def test_parser_rejects_escaping_entrypoint(tmp_path):
    """parse_skill_markdown returns None when the entrypoint is unsafe."""
    evil = _write(tmp_path / "evil.py", "print('pwned')\n")
    skill_md = _make_skill(tmp_path, str(evil), name="abs")

    assert parse_skill_markdown(skill_md) is None

    skill_md2 = _make_skill(tmp_path, "../../evil.py", name="rel")
    assert parse_skill_markdown(skill_md2) is None


def test_parser_keeps_valid_skill(tmp_path):
    skill_dir = tmp_path / "demo"
    _write(skill_dir / "run.py", "print('ok')\n")
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\nname: demo\ndescription: d\nentrypoint: run.py\n---\n\nbody\n",
        encoding="utf-8",
    )

    skill = parse_skill_markdown(skill_md)
    assert skill is not None
    assert skill.entrypoint_path == (skill_dir / "run.py").resolve()


def test_sandbox_fails_closed_on_rejected_entrypoint(tmp_path):
    """The runner must return a structured failure, never execute the script."""
    from app.core.skill_engine.windows_sandbox import (
        WindowsSandboxRunner,
        ENTRYPOINT_CONTAINMENT_WARNING,
    )

    _write(tmp_path / "evil.py", "print('pwned')\n")
    skill_dir = tmp_path / "demo"
    skill_dir.mkdir(parents=True)

    skill = SkillDefinition(
        name="demo",
        description="d",
        entrypoint="../../evil.py",
        skill_dir=str(skill_dir),
    )

    runner = WindowsSandboxRunner()
    result = runner.run_skill_sync(skill=skill, args={}, runner_mode="restricted_token")

    assert result.success is False
    assert ENTRYPOINT_CONTAINMENT_WARNING in result.warnings
    assert "entrypoint" in (result.error or "").lower()
    assert result.sandbox_enforced is False
