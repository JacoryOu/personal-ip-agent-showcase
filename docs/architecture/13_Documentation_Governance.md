# Documentation Governance

Status: **current**. This document exists to prevent the drift recorded in
`docs/audit/01_文档审计报告_v0.1.md` from recurring.

## 1. Problem this solves

`docs/` had only two commits while `main` accumulated 113 code commits. There was
no trigger that forced a documentation update, so features shipped undocumented
and v0.1 PRD/Roadmap/Backlog drifted far behind reality.

## 2. Rules

1. **Any change to an API blueprint, service, model, core module, skill engine
   behaviour, or permission/isolation behaviour must update or explicitly waive
   a doc update in the same branch.** A public surface has *two* independent
   documentation obligations: the architecture/Feature-Map layer *and* the
   feature-level design doc that owns that surface. Satisfying one does not
   satisfy the other.
2. **Feature branches must declare a documentation impact** — either the doc
   files they touched, or an explicit "no doc impact" with a reason.
3. **Merging a worktree/branch requires a doc-coverage check**: does every new
   or changed public surface appear in `11_Feature_Map_v0.2.md` (or a successor)?
4. **When code and docs disagree, code is the current fact** — but the drift is a
   bug to be fixed immediately, not a licence to keep the old doc.
5. **Legacy docs are marked, not deleted.** They get a status banner pointing at
   the current architecture document.
6. **Do not use a static "last updated" date as the only freshness signal.**
   Freshness is judged by whether the doc matches the code.

## 3. Ownership

- Architecture truth: `docs/architecture/`.
- Feature-level design: `docs/design/` (see `docs/design/README.md`). One doc
  per functional area, describing real behaviour, API surface, boundaries and
  known limitations. Security and sandbox guarantees are **not** duplicated
  here; those live only in `10_Sandbox_and_Permission_Model.md`.
- Feature inventory: `docs/architecture/11_Feature_Map_v0.2.md`.
- Security/permission truth: `docs/architecture/10_Sandbox_and_Permission_Model.md`.
- Skill engine behaviour: `docs/architecture/12_Skill_Engine_Spec.md`.
- Coding standards (naming, file size, layering, error handling):
  `docs/architecture/09_Coding_Standards.md`.
- Planning/backlog: `docs/product/07_Task_Backlog_v0.1.md`.
- Audit trail: `docs/audit/`.

## 4. Checklist before merge

- [ ] Doc impact declared in the branch description.
- [ ] Feature map updated if a public surface changed.
- [ ] The owning design doc under `docs/design/` updated **and** the changed
      file/module named in it, or a per-file waiver added.
- [ ] Sandbox doc updated if an isolation guarantee changed (and the change is
      reflected in the honest status table).
- [ ] No plan-only item is presented as implemented.
- [ ] New/changed code conforms to `09_Coding_Standards.md`: naming rules, file-size
      thresholds, no bare `except:`, no prompt literals outside
      `backend/app/engine/prompts/`.
- [ ] `scripts/code_style_baseline.txt` only shrank or stayed equal: entries
      lowered for files that shrank, entries removed for deleted files, no new
      entry added to dodge the hard cap.
- [ ] `python scripts/check_code_style.py --base main` and
      `python -m pytest backend/tests/test_code_style.py -q` pass.
- [ ] No secrets, `.env`, databases, `.venv`, `node_modules`, `backend/data/`
      are committed.

## 5. Enforcement (automated, not aspirational)

The rules above are enforced by a script, not by memory.

### 5.1 The gate

```
scripts/check_doc_coverage.py
```

It compares the branch diff against a base ref (default `main`) plus the
working tree and fails when:

1. a code-truth document is missing (fail closed);
2. a public-surface path changed with no doc update and no declaration;
3. a routed public surface changed with no update to the design doc that owns
   it — a Feature Map edit or a `Doc-Impact:` declaration does **not** bypass
   this, only a waiver does;
4. a permission/isolation file changed with no update to
   `10_Sandbox_and_Permission_Model.md` and no waiver (again, a `Doc-Impact:`
   declaration does not bypass it);
5. a waiver line is malformed (missing `::`, empty target, empty reason).

Edits limited to `docs/architecture/*` or `docs/design/*` are doc-only changes:
they never look like a public feature change and do not trip the gate.

It does **not** auto-write documentation. Auto-generating one Markdown file per
change would fragment `docs/`. The gate's job is to block *undeclared* drift
and force a decision: update the truth-source doc, declare no impact, or waive.

### 5.2 Manual run

```powershell
python scripts/check_doc_coverage.py --base main            # gate, fails on drift
python scripts/check_doc_coverage.py --base main --soft     # report only
```

Exit codes: `0` OK (or waived / soft), `1` failure.

### 5.2b API authentication boundary gate

```
scripts/check_api_auth.py
```

The doc-coverage gate only proves a change was *declared*. A second, separate
local gate proves the authentication boundary itself did not silently regress:

```powershell
python scripts/check_api_auth.py             # static + runtime surface check
python scripts/check_api_auth.py --base main # also flags api changes with no gate change
```

It fails when:

1. `app/api/__init__.py` does not build `api_router` with
   `create_private_router()` or `public_endpoints_router` with
   `create_public_router()`;
2. the private router factory no longer injects `Depends(get_current_user)`;
3. an API module is not mounted by `app/api/__init__.py`, or a module other
   than `private_domain.py` declares a `public_router`;
4. the real application exposes an `/api` route reachable without
   authentication that is not listed in
   `app.api.auth_boundary.PUBLIC_ENDPOINTS`;
5. `PUBLIC_ENDPOINTS` lists a route the application does not actually expose;
6. (`--base` only) files under `backend/app/api/` changed without the gate
   itself being touched.

Runtime coverage: `backend/tests/test_api_auth_surface.py` asserts 401 for the
private endpoints, anonymity for the single approved public endpoint, and that
the allowlist matches the application.

Adding an anonymous endpoint is therefore a deliberate, reviewable act: edit
`PUBLIC_ENDPOINTS`, update the owning doc, and let the gate check consistency.
This gate is **local only** for now — no CI job is wired.

### 5.3 Git hook installation

```powershell
pwsh -File scripts/install_git_hooks.ps1
```

```bash
bash scripts/install_git_hooks.sh
```

Enforcement is **local only** for now: the hooks above plus a manual run. CI is
deliberately not wired up yet, so a clone without the hooks is not protected —
treat this as an open item rather than a guarantee.

Both installers resolve the hooks directory via
`git rev-parse --git-common-dir`, so the hook is installed once for the whole
repository and applies from every linked worktree. If an existing hook of the
same name is present and is not ours, it is backed up to `<name>.bak` instead of
being silently overwritten (`-Force` overwrites).

| Hook | Command | Effect |
| --- | --- | --- |
| `pre-commit` | `python scripts/check_code_style.py --staged` | blocks the commit on naming / file size / bare `except:` in staged files |
| `commit-msg` | `python scripts/check_doc_coverage.py --base HEAD --staged --message-file <msg>` | blocks the commit |
| `post-merge` | `python scripts/check_doc_coverage.py --base main --soft` | reports drift after a merge |

Two blocking hooks with two different jobs: `pre-commit` judges the **code** and
needs no commit message, so it can enforce style while the change is still staged;
`commit-msg` judges the **declaration** and can only run once the final message
exists.

The doc-coverage gate deliberately runs at **`commit-msg`** rather than
`pre-commit`: only at that stage does the final commit message exist, so a
`Doc-Impact:` declaration in the actual message can be honoured. A `pre-commit`
doc gate would have to guess from history, and scanning history means a single old
commit that merely mentions `Doc-Impact:` would permanently waive every later
commit.

`pre-commit` is therefore used for the code-style gate instead, which needs no
commit message. Both installers resolve the repo root at run time via
`git rev-parse --show-toplevel`, so a hook invoked from a linked worktree or a
subdirectory still checks the right tree.

### 5.4 Declaration syntax

Commit-message declarations (case-insensitive prefix):

```text
Documentation Impact: Updated (docs/architecture/11_Feature_Map_v0.2.md)
Documentation Impact: No impact (internal rename only)
Documentation Impact: Deferred (tracked as IP-xxx in docs/product/07_Task_Backlog_v0.1.md)
Doc-Impact: none (reason)
```

Waiver file `docs/.doc-coverage-waivers`, one directive per line:

```text
<path-or-glob> :: <concrete reason>
```

Malformed lines (no `::`, empty target, or empty reason) fail closed.

### 5.5 Emergency bypass

```powershell
$env:SKIP_DOC_CHECK = "1"; git commit -m "..."; Remove-Item Env:\SKIP_DOC_CHECK
```

```bash
SKIP_DOC_CHECK=1 git commit -m "..."
```

Deliberately awkward. Emergency use only, and say so in the commit body.

### 5.6 Regression tests

```powershell
python -m pytest backend/tests/test_doc_coverage.py -q
```

### 5.7 Code-style and file-size gate

Documentation coverage proves a change was *described*. It does not prove the code
is shaped the way the standard says it must be. That is a separate local gate.

```
scripts/check_code_style.py
scripts/code_style_baseline.txt
```

The authoritative rules live in `docs/architecture/09_Coding_Standards.md`;
`scripts/code_style/rules.py` is the machine-readable mirror of its thresholds and
**must stay in sync** with it. The gate blocks on:

1. a source file above the hard cap (600 lines; 1000 for tests) that is not
   baselined;
2. a baselined legacy file growing past its frozen ceiling;
3. a baseline that is malformed, references a deleted file, is looser than the
   current line count, or carries an implausible ceiling;
4. bare `except:`;
5. prompt-like string literals outside `backend/app/engine/prompts/`;
6. naming violations (Python module/class/function, Vue component filename) in
   changed or staged files.

Manual run:

```powershell
python scripts/check_code_style.py              # whole repository
python scripts/check_code_style.py --base main  # only files changed against main
python scripts/check_code_style.py --staged     # only staged files
```

Legacy debt is handled by a **ratcheting baseline**, not by a one-off cleanup:
`scripts/code_style_baseline.txt` records the current line count of files that
already exceed the cap. A baselined file may not grow; when it shrinks, the entry
must be lowered in the same commit. New files may never be added to the baseline.
The baseline therefore only ever decreases, which makes progress permanent without
requiring a single blocking cleanup branch.

Regression tests: `python -m pytest backend/tests/test_code_style.py -q`.

Like the doc-coverage gate, this is **local only** for now — CI is deliberately not
wired.

## 6. Coverage granularity (per file, not per branch)

The gate is `per-file`, not `per-branch`. A documentation edit only covers a code
file when the doc that is allowed to describe that surface actually changed in
the branch **and** mentions the file:

| Public surface | Truth doc(s) that can cover it |
| --- | --- |
| `backend/app/api/*` | `08_Architecture_and_Modules.md`, `11_Feature_Map_v0.2.md` |
| `backend/app/engine/*` | `11_Feature_Map_v0.2.md`, `12_Skill_Engine_Spec.md` |
| `backend/app/services/*`, `models/*`, `core/*` | `11_Feature_Map_v0.2.md` (security surfaces also `10_Sandbox_and_Permission_Model.md`) |
| `frontend/src/*` | `11_Feature_Map_v0.2.md` |
| `skills/*` | `12_Skill_Engine_Spec.md`, `11_Feature_Map_v0.2.md` |
| `docs/architecture/*`, `docs/design/*` | doc-only: never triggers the gate |

The Feature Map table above is the *architecture* layer. The *design* layer is
routed per file by `DESIGN_DOC_MAP` in the gate script:

| Public surface | Owning design doc |
| --- | --- |
| `api/outlines.py`, `api/drafts.py`, `api/blueprints.py`, `engine/*` | `docs/design/01_Creation_Pipeline.md` |
| `api/dna.py`, `api/dna_v2.py`, `cognitive/memory/feedback` services | `docs/design/02_Cognitive_Profile_and_DNA.md` |
| `api/viral_analysis.py`, `viral_semantic_service.py` | `docs/design/03_Viral_Semantic_Analysis.md` |
| `api/platforms.py`, credential/crawler/playwright services, `core/crypto/*` | `docs/design/04_Distribution_and_Credentials.md` |
| `api/materials.py`, `api/obsidian.py`, material/obsidian services | `docs/design/05_Material_Vault_and_Obsidian.md` |
| `api/scheduler.py`, `core/skill_engine/*`, `skills/*` | `docs/design/06_Scheduler_and_Unattended_Skills.md` |
| chat / private_domain / images / settings APIs, `image_service`, `model_gateway.py`, `frontend/src/*` | `docs/design/07_Surfaces_and_Engagement.md` |
| `models/*`, `core/db.py` | `docs/design/08_Data_Model_Reference.md` |

Consequences that are intentional:

- Editing an unrelated architecture doc does **not** buy blanket coverage.
- Touching only `docs/.doc-coverage-waivers` is not coverage.
- A waiver is per file/glob; it covers only what it names.
- Untracked new public files are checked too, so a manual run catches them before staging.
- A design doc only covers a surface it names. Editing
  `docs/design/01_Creation_Pipeline.md` does not excuse an unrelated change in
  `07_Surfaces_and_Engagement.md`.

## Workflow permission gate (merge check)

Any change that adds or moves a high-risk operation (skill execution, external
network egress, publish/crawl, credential export/sync, sensitive vault access)
must declare a workflow permission before merging:

```powershell
& .venv\Scripts\python.exe scripts/check_workflow_permissions.py
& .venv\Scripts\python.exe -m pytest backend/tests/test_workflow_permission_gate.py -q
```

Requirements:

1. Register the action in the catalogue in
   the `PermissionAction` declared in `backend/app/core/workflow_permissions/`
with its permissions and risk level.
2. Call `require_authorization(...)` (or `workflow_permission_guard` /
   `declare_action`) before the side effect, using the correct mode
   (`interactive` / `pre_authorized` / `unattended`).
3. Audit-sink failure must fail closed; never swallow `WorkflowDenied`.
4. `KNOWN_UNDECLARED_BASELINE` exists only to track *pre-existing* unmigrated
   call sites, each with a concrete reason. Do not add new entries for new code,
   and do not use it to excuse a new high-risk call site.
5. Do not bypass the gate with `SKIP_DOC_CHECK`-style escape hatches.