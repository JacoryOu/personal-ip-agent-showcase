# Agent Map & Directory (V0.1 MVP)

This document serves as the top-level index for the multi-agent architecture of the Personal Cognitive IP Engine. Following the **Layered Context / Map Pattern**, this file provides brief definitions. For deep architecture details, see the architecture documents, and observe the specific constraints outlined below.

> **Status legend used in this document**
> - **Implemented** — the code exists in the repository and is wired into the pipeline.
> - **Partial** — the code exists but does not provide the full guarantee the name implies.
> - **Not implemented** — a target/idea only. Do not treat it as a property of the system yet.

## Core Agents Overview

### 1. Divergent Outline Agent (发散大纲智能体) — Implemented
- **Role**: Creative stimulator.
- **Function**: Takes a brief user topic and generates two divergent structural outlines (A and B).
- **Location**: `backend/app/engine/agents/outline_agent.py`

### 2. Draft Generation Agent (草稿生成智能体) — Implemented
- **Role**: Professional ghostwriter.
- **Function**: Takes the divergent outlines and expands them into complete, structurally distinct articles.
- **Location**: `backend/app/engine/agents/draft_agent.py`

### 3. Diff & DNA Extraction Agent (差异比对与DNA提取智能体) — Implemented
- **Role**: Cognitive analyst.
- **Function**: Compares the AI-generated draft against the user's final edited version to extract Thinking DNA (vocabulary, logic preferences, values).
- **Location**: `backend/app/engine/agents/diff_agent.py`

## Deeper Context & Constraints

The true power of these agents lies in their **Harness**—the code that wraps them. Do not rely solely on system prompts.

- **System Architecture & Layer Integration**: For details on how agents fit into the API, Services, and DB layers, see [08_Architecture_and_Modules.md](docs/architecture/08_Architecture_and_Modules.md).
- **System Prompts**: The actual LLM prompts are maintained in the codebase under `backend/app/engine/prompts/`.

### Harness Constraints — Implementation Status

The constraints below are the design intent for this engine. They are listed with
their real status so that no one assumes a guarantee the code does not provide.

#### Implemented

1. **Diff Baseline Gating** — Implemented.
   `backend/app/engine/agents/diff_agent.py` aborts before the LLM call when the
   AI draft and the human version are identical and no active viewpoint
   judgments were supplied.

2. **Code-Based Lexical Stripping** — Implemented.
   `backend/app/utils/lexical_filter.py` applies RegEx-based removal of
   "AI-style" filler and replacement patterns in code. It is called by
   `draft_agent.py` and `diff_agent.py`, so stripping does not depend on prompt
   adherence.

3. **DB Read-Only Engine for the Agent Read Path** — Implemented (partial scope).
   `backend/app/core/db.py` builds a second, independent `readonly_engine` and
   exposes `get_readonly_session()`, separate from the writable `engine` /
   `get_session()`. Read-only status is enforced by the database driver, not by
   prompt or Python convention:
   - SQLite: the connection is opened via the URI
     `sqlite:///file:<abs path>?mode=ro&uri=true` (driver-level read-only file
     handle) plus `PRAGMA query_only=ON` applied on every connect event.
   - PostgreSQL: each session runs
     `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY` and
     `SET default_transaction_read_only = on`.

   A write through a read-only session raises at the driver level. Unsupported
   backends (e.g. MySQL) and non-file SQLite (`:memory:`) **fail closed** with
   `UnsupportedReadOnlyBackendError` rather than degrading silently.

   Scope — what is and is not read-only:
   - Read-only: the Outline and Draft agents’ *input-context assembly* (IP bundle,
     DNA, profile, memory retrieval) via `CognitiveService.get_*_readonly` and
     `MemoryService.*_readonly`, which avoid `get_or_create_*` and all
     INSERT/UPDATE/COMMIT.
   - Intentionally writable: Draft archive persistence (separate writable session),
     and the Diff/DNA evolution flow, which writes draft, DNA and profile records.

   So the *entire* Draft workflow is **not** read-only — only the agent-facing read
   path is physically isolated. `get_readonly_session()` is a FastAPI dependency and
   must be injected wherever read-only isolation is intended; a handler that takes
   only `get_session()` still gets full write access.
   Regression coverage: `backend/tests/test_agent_db_readonly.py` (a write through
   the read-only session is proven to fail at the driver, not by convention).

#### Not implemented (target design, not current behaviour)

4. **OS-Level Skill Sandboxing (Windows Restricted Token)** — Partially implemented.
   The Skill Engine (`backend/app/core/skill_engine/windows_sandbox.py`) now really
   creates and uses a Windows **Restricted Token** through the ctypes bindings in
   `backend/app/core/skill_engine/restricted_token.py`. It still never launches
   `WindowsSandbox.exe` and does not create an AppContainer.

## Skill sandbox mode transparency

The Skill Engine runner makes its degradation explicit rather than overstating
isolation. `SandboxExecutionResult` reports:

- `requested_runner_mode` — what the caller or skill definition asked for.
- `runner_mode` — what was **actually** applied.
- `sandbox_enforced` — `True` only when a real restricted token was created and
  used to start the child process; `False` for every other mode.
- `warnings` — human-readable notes about any unmet guarantee.

Current behaviour:

- `restricted_token` → calls `CreateRestrictedToken(DISABLE_MAX_PRIVILEGE)` on the
  current process token, verifies the resulting token, then launches the child with
  `CreateProcessAsUserW`. On success: `runner_mode="restricted_token"` and
  `sandbox_enforced=True`.
- `restricted_token` failure → **fails closed** with
  `runner_mode="restricted_token_unavailable"`, `sandbox_enforced=False` and
  `success=False`. The skill is **not** executed as a plain subprocess.
- `wsb` → **fails closed** with `runner_mode="wsb_unsupported"`; `WindowsSandbox.exe`
  is never launched.
- Unknown modes → **fail closed** instead of silently degrading.

What the restricted token actually guarantees:

- All token privileges are disabled (`DISABLE_MAX_PRIVILEGE`).
- A restricting SID list is present, and its SIDs are marked
  `SE_GROUP_USE_FOR_DENY_ONLY` (typically the Administrators SID), so access
  checks outside that list are denied rather than allowed.
- The child process is genuinely created under that token via
  `CreateProcessAsUserW`.

What it does **not** guarantee (still not implemented):

- AppContainer token or package identity.
- Filesystem ACL isolation or a per-skill virtual filesystem.
- Network isolation.
- Registry, clipboard, or COM isolation.
- Child-process policy — no job object is configured.
- Windows Sandbox (`WindowsSandbox.exe`) virtualization.
- Enforcement of `SKILL.md` `permissions` metadata.

Regression coverage lives in `backend/tests/test_sandbox_mode_transparency.py`
and `backend/tests/test_restricted_token.py`.

## HARD RULE — Code must follow `docs/architecture/09_Coding_Standards.md`

`docs/architecture/09_Coding_Standards.md` is the single authoritative coding
standard for this repository. It applies to every agent and every worktree, and
it is **not** advisory — a machine gate enforces the mechanical part of it.

Enforced by `scripts/check_code_style.py` (blocking on hard caps, file growth over
a frozen baseline, malformed baselines, bare `except:`, prompt literals outside
`backend/app/engine/prompts/`, and naming violations in changed files):

- Python modules `snake_case`, classes `PascalCase`, functions/methods
  `snake_case`.
- Vue single-file components `PascalCase.vue`, except `index.vue`, `App.vue`,
  `main.vue` and `_`-prefixed files.
- Source files: ≤ 300 lines ideal, > 400 review, > 600 hard cap (blocking).
  Test files: ≤ 500 ideal, > 800 review, > 1000 hard cap (blocking).
- Prompt-like string literals belong in `backend/app/engine/prompts/`.

Legacy oversized files are tracked in `scripts/code_style_baseline.txt`:

- A baselined file may never grow beyond its recorded ceiling.
- When a file shrinks, the baseline entry **must** be lowered in the same commit.
- Deleted files **must** be removed from the baseline.
- New files may never be added to the baseline to dodge the hard cap.
- A malformed baseline fails closed.

Historical debt is not required to be cleared in one pass, but the baseline may
only ever go down. Never bypass the gate with `SKIP_DOC_CHECK` or by deleting a
finding; fix the code or record an explicit waiver in
`docs/.doc-coverage-waivers`.

## HARD RULE — Documentation must change with code

This is a blocking constraint, not a suggestion. It applies to every agent and
every worktree in this repository.

### 1. What counts as a public-surface change

Any add or modify of these paths is a **public-surface change** and triggers the
doc-coverage gate:

- `backend/app/api/*` (blueprints, routes, schemas)
- `backend/app/services/*`, `backend/app/models/*`
- `backend/app/core/*` (includes db, auth, crypto, guards, skill engine)
- `backend/app/engine/*` (agents, prompts that change behaviour)
- `frontend/src/components/*`, `frontend/src/views/*`, `frontend/src/services/*`,
  `frontend/src/router/*`, `frontend/src/main.*`, `frontend/package.json`
- `skills/*`
- `docs/architecture/*`

Permission / isolation changes are **extra-sensitive**. Any change under
`backend/app/core/skill_engine/*`, `backend/app/core/db.py`,
`backend/app/core/net_guard.py`, `backend/app/core/vault_path_guard.py`,
`backend/app/core/crypto/*`, or `backend/app/core/auth/*` must update
`docs/architecture/10_Sandbox_and_Permission_Model.md` or carry an explicit
waiver. The gate never waives this automatically.

### 2. Required documentation declaration

Every feature branch / worktree commit series must declare its documentation
impact. Accepted forms (all case-insensitive):

```text
Documentation Impact: Updated (docs/architecture/11_Feature_Map_v0.2.md, docs/architecture/12_Skill_Engine_Spec.md)
Documentation Impact: No impact (pure rename inside a private module; no public surface)
Documentation Impact: Deferred (tracked in docs/product/07_Task_Backlog_v0.1.md as IP-xxx)
```

The older `Doc-Impact:` spelling is also accepted by the gate.

### 3. How "no doc update needed" must be expressed

Never silently skip documentation. Use exactly one of:

1. A commit-message declaration (see the three forms above).
2. A waiver entry in `docs/.doc-coverage-waivers`, one per line:
   ```text
   path-or-glob :: concrete reason
   ```
3. A real doc update in `docs/architecture/`.

The gate does **not** auto-generate new Markdown for every small change. That
would only fragment `docs/`. Instead, the gate blocks *undeclared* drift and
forces a human/agent decision.

### 4. Where the truth lives (do not duplicate detail here)

- Feature inventory: `docs/architecture/11_Feature_Map_v0.2.md`
- Permission / sandbox reality and hardening plan:
  `docs/architecture/10_Sandbox_and_Permission_Model.md`
- Skill engine discovery, policy, gating, execution modes:
  `docs/architecture/12_Skill_Engine_Spec.md`
- Governance rules and merge checklist:
  `docs/architecture/13_Documentation_Governance.md`
- Module layering / API-service-DB structure:
  `docs/architecture/08_Architecture_and_Modules.md`

If one of those documents already describes the behaviour accurately, a doc
update usually means *editing that file*, not creating a new one.

### 5. Required commands before merging a worktree

Run from the worktree root:

```powershell
python scripts/check_doc_coverage.py --base main
python -m pytest backend/tests/test_doc_coverage.py -q
python scripts/check_code_style.py
python scripts/check_code_style.py --base main
python -m pytest backend/tests/test_code_style.py -q
```

All five must pass. Then install the local gate once per machine:

```powershell
pwsh -File scripts/install_git_hooks.ps1   # or: bash scripts/install_git_hooks.sh
```

The hook installs `pre-commit` (code-style gate on staged files), `commit-msg`
(blocking doc-coverage gate) and `post-merge` (soft) into the **shared** hooks
directory (`git rev-parse --git-common-dir`), so it also applies from every
worktree of this repository. The blocking gate runs at
`commit-msg`, not `pre-commit`, so that the real commit message — and therefore
a `Doc-Impact:` declaration — is available when the gate evaluates the commit.

### 6. Emergency bypass (must stay rare and be justified)

```powershell
$env:SKIP_DOC_CHECK = "1"; git commit -m "..."; Remove-Item Env:\SKIP_DOC_CHECK
```

```bash
SKIP_DOC_CHECK=1 git commit -m "..."
```

Use it only for a genuine emergency, never to silence a real drift.

### 7. Honesty rule

- Never present a plan item as implemented. Use the status legend at the top of
  this file.
- If you update a doc, the doc must match the code as it is in this branch, not
  as you wish it to be later.
- If a doc and the code disagree, code is the current fact — fix the doc
  immediately in the same branch.

### 8. Never commit these

- `.env`, `.env.*`
- database files (`*.db`, `*.sqlite*`)
- `.venv/`, `node_modules/`
- `backend/data/`
- test probes / scratch files

## Documentation (updated)

The old `08_Architecture_and_Modules.md` is legacy. Current references:
- `docs/architecture/11_Feature_Map_v0.2.md` — code-truth feature inventory.
- `docs/architecture/10_Sandbox_and_Permission_Model.md` — what is / is not isolated, and the Phase A/B hardening plan (sandbox account + NTFS ACL + OS network boundary).
- `docs/architecture/12_Skill_Engine_Spec.md` — skill discovery, policy, unattended gating, execution modes.
- `docs/architecture/13_Documentation_Governance.md` — branches must declare doc impact before merge.

Known honest gaps (do not overstate): sandbox isolation is partial (no account/ACL/OS network boundary); DB read-only covers the agent read path only; `style_fingerprint` is not yet fully consumed by `draft_agent.py`.
