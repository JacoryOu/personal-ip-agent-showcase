"""Tests for scripts/check_doc_coverage.py (documentation coverage gate).

These tests exercise the gate as a library (importlib) so the decision logic
can be checked without spawning git. The git-facing plumbing is covered by the
manual verification runs described in
docs/architecture/13_Documentation_Governance.md.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_doc_coverage.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_doc_coverage", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_doc_coverage"] = mod
    spec.loader.exec_module(mod)
    return mod


cdc = _load_module()


# --------------------------------------------------------------------------
# normalize / matching
# --------------------------------------------------------------------------


def test_normalize_converts_windows_separators():
    assert cdc.normalize(r"backend\app\api\routes.py") == "backend/app/api/routes.py"


def test_normalize_strips_leading_dot_slash():
    assert cdc.normalize("./AGENTS.md") == "AGENTS.md"


def test_is_public_surface_true_for_core_and_skills():
    assert cdc.is_public_surface("backend/app/core/db.py")
    assert cdc.is_public_surface("skills/reviewer/SKILL.md")
    assert cdc.is_public_surface("frontend/src/router/index.ts")


def test_is_public_surface_false_for_tests_and_scripts():
    assert not cdc.is_public_surface("backend/tests/test_doc_coverage.py")
    assert not cdc.is_public_surface("scripts/check_doc_coverage.py")
    # Scratch/backup files under a public directory are still in that
    # directory, so the gate keeps flagging them: they must not be committed.
    assert cdc.is_public_surface("backend/app/services/__init__.py.orig")


def test_ignored_paths_excluded():
    assert cdc.is_ignored("backend/app/core/__pycache__/x.pyc")
    assert cdc.is_ignored(".venv/lib/foo.py")


# --------------------------------------------------------------------------
# waivers
# --------------------------------------------------------------------------


def test_load_waivers_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(cdc, "REPO_ROOT", tmp_path)
    assert cdc.load_waivers() == []


def test_load_waivers_parses_comments_and_entries(monkeypatch, tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / ".doc-coverage-waivers").write_text(
        "# comment\n\nfoo/bar.py :: internal only\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cdc, "REPO_ROOT", tmp_path)
    assert cdc.load_waivers() == [("foo/bar.py", "internal only")]


@pytest.mark.parametrize(
    "line",
    [
        "missing-separator\n",
        ":: empty target\n",
        "target :: \n",
    ],
)
def test_load_waivers_rejects_malformed(monkeypatch, tmp_path, line):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / ".doc-coverage-waivers").write_text(line, encoding="utf-8")
    monkeypatch.setattr(cdc, "REPO_ROOT", tmp_path)
    with pytest.raises(RuntimeError):
        cdc.load_waivers()


def test_waiver_matches_exact_and_glob():
    waivers = [("backend/app/services/__init__.py", "init"), ("docs/*", "doc")]
    assert cdc.waiver_matches("backend/app/services/__init__.py", waivers) == "init"
    assert cdc.waiver_matches("docs/architecture/x.md", waivers) == "doc"
    assert cdc.waiver_matches("backend/app/api/x.py", waivers) is None


def test_waiver_template_file_is_comments_only():
    text = (REPO_ROOT / cdc.WAIVER_FILE).read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        assert "::" in stripped, f"unexpected live waiver line: {stripped!r}"


# --------------------------------------------------------------------------
# doc changes
# --------------------------------------------------------------------------


def test_doc_changes_recognises_agents_and_docs():
    files = ["AGENTS.md", "docs/architecture/11_Feature_Map_v0.2.md", "backend/app/api/x.py"]
    assert cdc.doc_changes(files) == files[:2]


# --------------------------------------------------------------------------
# security sensitivity
# --------------------------------------------------------------------------


def test_security_sensitive_paths():
    assert cdc.is_security_sensitive("backend/app/core/skill_engine/runner.py")
    assert cdc.is_security_sensitive("backend/app/core/db.py")
    assert cdc.is_security_sensitive("backend/app/core/crypto/secret_box.py")
    assert not cdc.is_security_sensitive("backend/app/api/routes.py")


# --------------------------------------------------------------------------
# code-truth documents exist
# --------------------------------------------------------------------------


def test_code_truth_docs_exist():
    for doc in cdc.CODE_TRUTH_DOCS:
        assert (REPO_ROOT / doc).exists(), f"missing code-truth doc: {doc}"


# --------------------------------------------------------------------------
# end-to-end check() behaviour with synthetic file lists
# --------------------------------------------------------------------------


class _Recorder:
    def __init__(self, changed):
        self.changed = changed

    def __call__(self, base, staged=False):
        return list(self.changed)


def _run_check(monkeypatch, changed, *, waivers=None, declares=False, soft=False):
    monkeypatch.setattr(cdc, "collect_changed_files", _Recorder(changed))
    monkeypatch.setattr(cdc, "load_waivers", lambda: waivers or [])
    message = "feat: x\n\nDoc-Impact: synthetic test waiver\n" if declares else ""
    res = cdc.Result(message_text=message)
    with pytest.raises(SystemExit) as exc:
        cdc.check(res, "main", staged=False, soft=soft)
    return exc.value.code, res


def test_public_change_without_doc_or_declaration_fails(monkeypatch):
    code, res = _run_check(monkeypatch, ["backend/app/api/routes.py"])
    assert code == 1
    assert any("no documentation was updated" in f for f in res.failures)


def test_public_change_with_doc_passes(monkeypatch):
    # blueprints.py is routed to the creation-pipeline design doc, so a Feature
    # Map edit alone is not enough any more.
    code, res = _run_check(
        monkeypatch,
        [
            "backend/app/api/blueprints.py",
            cdc.FEATURE_MAP,
            cdc.DESIGN_CREATION,
        ],
    )
    assert code == 0


def test_public_change_with_declaration_passes(monkeypatch):
    # routes.py has no design-doc route, so the Feature-Map layer can still be
    # satisfied by an explicit declaration.
    assert cdc.design_docs_for("backend/app/api/routes.py") == ()
    code, _ = _run_check(monkeypatch, ["backend/app/api/routes.py"], declares=True)
    assert code == 0


def test_declaration_cannot_bypass_design_doc_requirement(monkeypatch):
    code, res = _run_check(
        monkeypatch,
        ["backend/app/api/blueprints.py", cdc.FEATURE_MAP],
        declares=True,
    )
    assert code == 1
    assert any("design doc that owns them" in f for f in res.failures)


def test_no_public_change_is_ok(monkeypatch):
    code, _ = _run_check(monkeypatch, ["README.md"])
    assert code == 0


def test_skill_engine_change_without_sandbox_doc_fails(monkeypatch):
    code, res = _run_check(
        monkeypatch,
        [
            "backend/app/core/skill_engine/runner.py",
            "docs/architecture/12_Skill_Engine_Spec.md",
        ],
    )
    assert code == 1
    assert any("security/permission behaviour changed" in f for f in res.failures)


def test_skill_engine_change_with_sandbox_doc_passes(monkeypatch):
    code, _ = _run_check(
        monkeypatch,
        [
            "backend/app/core/skill_engine/runner.py",
            cdc.SANDBOX_DOC,
            cdc.DESIGN_SCHEDULER,
        ],
    )
    assert code == 0


def test_skill_engine_change_with_waiver_passes(monkeypatch):
    code, _ = _run_check(
        monkeypatch,
        ["backend/app/core/skill_engine/runner.py"],
        waivers=[("backend/app/core/skill_engine/runner.py", "comment-only change")],
    )
    assert code == 0


def test_sandbox_sensitive_name_alone_does_not_waive(monkeypatch):
    """A file merely named *sandbox* must still require the sandbox doc."""
    code, res = _run_check(
        monkeypatch,
        ["backend/app/core/net_guard.py", cdc.SKILL_DOC],
    )
    assert code == 1
    assert any("security/permission behaviour changed" in f for f in res.failures)


def test_soft_mode_reports_but_exits_zero(monkeypatch):
    code, _ = _run_check(monkeypatch, ["backend/app/api/routes.py"], soft=True)
    assert code == 0


def test_missing_required_doc_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(cdc, "REPO_ROOT", tmp_path)
    res = cdc.Result()
    with pytest.raises(SystemExit) as exc:
        cdc.check(res, "main", staged=False, soft=False)
    assert exc.value.code == 1


# --------------------------------------------------------------------------
# SKIP_DOC_CHECK
# --------------------------------------------------------------------------


def test_skip_env_bypasses(monkeypatch):
    monkeypatch.setenv("SKIP_DOC_CHECK", "1")
    monkeypatch.setattr(
        sys, "argv", ["check_doc_coverage.py", "--base", "main"]
    )
    with pytest.raises(SystemExit) as exc:
        cdc.main()
    assert exc.value.code == 0


# --------------------------------------------------------------------------
# per-file coverage granularity (regression: unrelated doc churn used to
# satisfy the gate for every public file on the branch)
# --------------------------------------------------------------------------


def test_unrelated_arch_doc_does_not_cover_public_code(monkeypatch):
    code, res = _run_check(
        monkeypatch,
        [
            "backend/app/api/_unrelated_new_endpoint.py",
            "docs/architecture/08_Architecture_and_Modules.md",
        ],
    )
    assert code == 1
    assert any("no documentation was updated" in f for f in res.failures)


def test_waiver_template_file_only_is_not_coverage(monkeypatch):
    code, res = _run_check(
        monkeypatch,
        ["backend/app/api/_unrelated_new_endpoint.py", "docs/.doc-coverage-waivers"],
    )
    assert code == 1
    assert any("no documentation was updated" in f for f in res.failures)


def test_matching_feature_map_content_covers_file(monkeypatch):
    # 11_Feature_Map_v0.2.md lists blueprints.py in the real repo.
    code, _ = _run_check(
        monkeypatch,
        [
            "backend/app/api/blueprints.py",
            cdc.FEATURE_MAP,
            cdc.DESIGN_CREATION,
        ],
    )
    assert code == 0


def test_per_file_waiver_covers_only_that_file(monkeypatch):
    code, res = _run_check(
        monkeypatch,
        ["backend/app/api/routes.py", "backend/app/services/orphan.py"],
        waivers=[("backend/app/api/routes.py", "internal refactor")],
    )
    assert code == 1
    assert any("backend/app/services/orphan.py" in f for f in res.failures)


def test_security_surface_covers_via_sandbox_doc(monkeypatch):
    code, _ = _run_check(
        monkeypatch,
        ["backend/app/core/db.py", cdc.SANDBOX_DOC, cdc.DESIGN_DATA_MODEL],
    )
    assert code == 0


def test_declaration_cannot_bypass_sandbox_doc_requirement(monkeypatch):
    code, res = _run_check(
        monkeypatch,
        ["backend/app/core/skill_engine/runner.py"],
        declares=True,
    )
    assert code == 1
    assert any(
        "a Doc-Impact declaration does not bypass this requirement" in f
        for f in res.failures
    )


def test_surface_doc_map_covers_all_public_prefixes():
    prefixes = [p for p, _ in cdc.SURFACE_DOC_MAP]
    for sample in (
        "backend/app/api/routes.py",
        "backend/app/services/svc.py",
        "backend/app/models/m.py",
        "backend/app/core/db.py",
        "backend/app/engine/agents/draft_agent.py",
        "frontend/src/components/A.vue",
        "skills/reviewer/SKILL.md",
    ):
        assert any(sample.startswith(p) for p in prefixes), sample


# --------------------------------------------------------------------------
# commit-message scoping: only THIS message can waive, history must not
# --------------------------------------------------------------------------


def test_commit_message_declarations_requires_real_reason():
    assert cdc.commit_message_declarations(
        "feat: x\n\nDoc-Impact: no docs because private test fixture"
    ) == ["no docs because private test fixture"]


def test_commit_message_declarations_empty_message_has_none():
    assert cdc.commit_message_declarations("feat: x") == []
    assert cdc.commit_message_declarations("") == []
    assert cdc.commit_message_declarations(None) == []


def test_commit_message_declaration_ignores_history(monkeypatch):
    """An old commit mentioning Doc-Impact must not waive new commits."""
    def _boom(*a, **k):
        raise AssertionError("history must not be scanned")

    monkeypatch.setattr(cdc, "run_git", _boom)
    assert cdc.commit_message_declarations("feat: unrelated change") == []


def test_commit_message_declaration_multiple_lines(monkeypatch):
    res = cdc.Result(
        message_text="feat: x\n\nDoc-Impact: reason one\nDocumentation Impact: reason two\n"
    )
    assert cdc.commit_message_declarations(res.message_text) == [
        "reason one",
        "reason two",
    ]


# --------------------------------------------------------------------------
# design-doc routing completeness: every real public surface must be routed
# --------------------------------------------------------------------------


def _tracked_public_surfaces() -> list[str]:
    """All public-surface files that actually exist in the repository."""
    out: set[str] = set()
    for pattern in cdc.PUBLIC_SURFACE_GLOBS:
        for f in cdc.REPO_ROOT.glob(pattern):
            if f.is_file():
                out.add(cdc.normalize(str(f.relative_to(cdc.REPO_ROOT))))
    return sorted(out)


def test_every_public_surface_has_a_design_doc_route():
    unrouted = [
        f
        for f in _tracked_public_surfaces()
        # Package initialisers are exempt by design (see
        # PACKAGE_METADATA_SUFFIXES): they declare a package, not behaviour.
        if not cdc.is_package_metadata(f) and not cdc.design_docs_for(f)
    ]
    assert not unrouted, (
        "public surfaces with no design-doc route (add them to "
        f"DESIGN_DOC_MAP): {unrouted}"
    )


def test_package_metadata_exemption_is_limited_to_init_files():
    assert cdc.is_package_metadata("backend/app/api/__init__.py")
    assert cdc.is_package_metadata("backend/app/core/auth/__init__.py")
    # Anything that is not a bare package initialiser still needs a route.
    assert not cdc.is_package_metadata("backend/app/core/config.py")
    assert not cdc.is_package_metadata("backend/app/main.py")
    assert not cdc.is_package_metadata("frontend/package.json")
    assert not cdc.is_package_metadata("backend/app/core/db.py")


def test_design_doc_map_targets_all_exist():
    missing = sorted(
        {
            doc
            for _, docs in cdc.DESIGN_DOC_MAP
            for doc in docs
            if not (cdc.REPO_ROOT / doc).exists()
        }
    )
    assert not missing, f"DESIGN_DOC_MAP points at missing docs: {missing}"


def test_design_docs_that_name_a_public_surface_also_route_it():
    """If a design doc names a concrete public-surface path, the gate must be
    able to resolve that path -- otherwise the doc describes code the gate
    cannot enforce."""
    import re

    pattern = re.compile(
        r"\b((?:backend|frontend|skills)/[A-Za-z0-9_./-]+\.(?:py|vue|ts|json|md))\b"
    )
    offenders: list[str] = []
    for doc in cdc.DESIGN_DOCS:
        text = (cdc.REPO_ROOT / doc).read_text(encoding="utf-8", errors="replace")
        for raw in set(pattern.findall(text)):
            path = raw.rstrip(".,;)")
            if not cdc.is_public_surface(path):
                continue
            if cdc.is_package_metadata(path):
                continue  # package initialisers are exempt from doc routing
            if not (cdc.REPO_ROOT / path).exists():
                continue  # historical / planned path, not current code
            if not cdc.design_docs_for(path):
                offenders.append(f"{doc} -> {path}")
    assert not offenders, (
        "design docs name public surfaces the gate cannot route: "
        f"{sorted(offenders)}"
    )
