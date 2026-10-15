# Coding Standards (代码规范)

> **Status: Implemented (enforced).** This document is the authoritative code
> standard for the repository. Every number in it is mirrored by
> `scripts/code_style/rules.py`; changing one without the other is documentation
> drift and will be rejected by review.
>
> Enforcement entry point: `scripts/check_code_style.py`
> (rules split across `scripts/code_style/`), tests in
> `backend/tests/test_code_style.py`.

## S0. Scope and enforcement model

| Area | Status |
| --- | --- |
| Python naming (module / class / function) | Implemented |
| Vue single-file component file naming | Implemented |
| Bare `except:` ban | Implemented |
| Prompt-location rule (heuristic) | Implemented (heuristic) |
| File-size thresholds + legacy baseline | Implemented |
| TypeScript identifier naming | Not implemented (advisory only) |
| Import layering / dependency direction | Not implemented (documented rule, review-enforced) |

Rules are split into two severities:

- **Blocking** — fails the gate and blocks the commit.
- **Advisory (`warn`)** — reported, does not block, never silenced.

Blocking rule ids: `baseline/illegal`, `baseline/stale`, `baseline/too-loose`,
`file-size/hard-cap`, `file-size/test-hard-cap`, `file-size/review`,
`file-size/legacy-growth`, `naming/module-file`, `naming/class`,
`naming/function`, `naming/vue-component`, `error/bare-except`,
`ai/prompt-location`, `syntax`.

Historical naming debt is **not** a global blocker: only files listed in
`scripts/code_style_baseline.txt` carry a frozen size ceiling, and new/modified
code must satisfy every naming rule.

## S1. Naming conventions

### Python (backend)

| Symbol | Style | Example |
| --- | --- | --- |
| Module file | `snake_case` | `draft_agent.py` |
| Class / Pydantic model / SQLModel | `PascalCase` | `DraftAgent`, `UserProfile` |
| Function, method, variable | `snake_case` | `extract_dna`, `is_draft_ready` |
| Module-level constant | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| Leading-underscore private | `_helper()` | `_normalize_text` |

Legal exceptions (explicitly whitelisted in the checker):

- `_FakeEngine` / `_*` prefixed classes — test doubles and private helpers.
- ctypes / FFI structure classes in `UPPER_SNAKE_CASE` (`PROCESS_INFORMATION`).
- `BaseHTTPRequestHandler` protocol methods `do_GET`, `do_POST`, ...
- Non-ASCII (e.g. Chinese) test function names are accepted in `backend/tests`.

`__init__.py` is exempt from the module-filename rule.

### Database

Tables and columns: `snake_case` (`user_dna`, `created_at`). Indexes:
`idx_<table>_<columns>`.

### Frontend (Vue 3 + TypeScript)

| Symbol | Style | Example |
| --- | --- | --- |
| SFC file | `PascalCase.vue` | `DraftEditor.vue` |
| Vue component in `<script setup>` | `PascalCase` (import) | `import DraftEditor from ...` |
| Composable | `useXxx` | `useDrafts.ts` |
| Pinia store | `camelCase` + `use` prefix | `useDraftStore.ts` |
| API service module | `camelCase` or `<domain>Service` | `draftService.ts` |
| Type / interface / enum | `PascalCase` | `DraftSummary` |
| Variable, function, prop | `camelCase` | `fetchDrafts`, `isDraftSelected` |
| Constant | `UPPER_SNAKE_CASE` | `API_BASE_URL` |

File-name exceptions for SFCs: `index.vue`, `App.vue`, `main.vue`, and any file
starting with `_` (private/non-component partials).

TypeScript identifier naming is **not yet machine-checked** (advisory only); it
is enforced by review against this table.

## S2. Architecture layering and dependency direction

```
frontend/src/views  ->  frontend/src/services  ->  HTTP
backend/app/api    ->  backend/app/services    ->  backend/app/models / core
```

- API layer (`backend/app/api/*`): routers, request/response schemas, auth
  dependencies. No business logic, no direct DB session beyond orchestration.
- Service layer (`backend/app/services/*`): all business logic and transactions.
- Model layer (`backend/app/models/*`): SQLModel/Pydantic tables and DTOs only.
- Core layer (`backend/app/core/*`): db, auth, crypto, guards, skill engine. Core
  must never import from `api` or `services`.
- Engine layer (`backend/app/engine/*`): agents and prompts. Agents receive
  context explicitly and never open their own DB session.

Dependencies flow strictly downward; cycles are not allowed.

## S3. Types, schemas, error handling

- Validate all external input with Pydantic (backend) / Zod (frontend).
- Raise domain-specific exceptions (`EngineError`, `DatabaseError`,
  `AgentExecutionError`) — never bare `except:`, which is a blocking rule.
- Never return raw stack traces to clients; use the standardized error payload
  `{"error_code": ..., "message": ..., "details": {}}`.
- Log with levels (`DEBUG`/`INFO`/`WARNING`/`ERROR`) and context (`user_id`,
  `session_id`, `trace_id`). Never log secrets, raw API keys, or PII.
- LLM calls must be idempotent where possible, retried with exponential
  backoff, and must log token counts for cost attribution.

## S4. File size thresholds

Production source (`.py`, `.ts`, `.js`, `.vue` under `backend/app`,
`frontend/src`, `scripts`):

| Lines | Severity |
| --- | --- |
| `<= 300` | Ideal |
| `> 300` | `file-size/soft` (warn) |
| `> 400` | `file-size/review` (**blocking**) |
| `> 600` | `file-size/hard-cap` (**blocking**) |

Test files (`backend/tests`):

| Lines | Severity |
| --- | --- |
| `<= 500` | Ideal |
| `> 500` | `file-size/soft` (warn) |
| `> 800` | `file-size/test-review` (warn) |
| `> 1000` | `file-size/test-hard-cap` (**blocking**) |

Baseline semantics (`scripts/code_style_baseline.txt`, one
`<path> <max lines>` per line):

- A listed file is **legacy debt** with a frozen ceiling.
- It may shrink; if its actual size drops below the ceiling, the baseline must
  be lowered in the same commit (`baseline/too-loose`, blocking).
- It may never grow (`file-size/legacy-growth`, blocking).
- A deleted file must be removed from the baseline (`baseline/stale`, blocking).
- New files cannot enter the baseline to dodge the hard cap; ceilings may only
  be raised with a documented reason in
  `docs/product/07_Task_Backlog_v0.1.md` and reviewer approval.
- A malformed baseline line is a blocking error — never silently ignored.

## S5. Prompt management

Prompt text belongs in `backend/app/engine/prompts/` (or test fixtures, or
`scripts/`). Long prompt-like string literals (multi-line, ≥ 80 chars, matching
the heuristic `You are / 请你 / 请按 / 扮演 / system prompt / ## Role`) elsewhere
trigger the blocking rule `ai/prompt-location`. This keeps behaviour overridable
and reviewable rather than buried in business logic.

## S6. Agent input/output contracts

- Every agent declares a typed input and output (Pydantic models).
- The draft agent must consume `style_fingerprint` when present.
- System prompts live in `backend/app/engine/prompts/`; the harness, not the
  prompt alone, enforces structural constraints (lexical stripping, diff
  baseline gating, read-only DB path).

## S7. Database and transaction rules

- The agent read path uses `get_readonly_session()` (driver-enforced read-only);
  only the intended write paths use the writable session. See
  `docs/architecture/10_Sandbox_and_Permission_Model.md` for exactly what is and
  is not isolated — do not overstate the guarantee.
- Handlers that intend read-only isolation must depend on
  `get_readonly_session`, not `get_session`.

## S8. Skill sandbox — honest status

The Windows skill sandbox is **Partial**: it creates a real restricted token
and launches the child under it, but provides **no** AppContainer, filesystem
ACL isolation, network isolation, or job object. Unknown or unavailable modes
fail closed. Read
`docs/architecture/10_Sandbox_and_Permission_Model.md` before making any claim
about isolation.

## S9. Tooling

- Backend deps / env: `uv` (`uv sync --project backend --all-groups`).
- Never commit `.env`, `.env.*`, `*.db`, `*.sqlite*`, `.venv/`,
  `node_modules/`, `backend/data/`, or scratch/probe files.

## S10. Tests

- New behaviour needs a regression test under `backend/tests/`.
- The gate's own tests: `backend/tests/test_code_style.py`.

## S11. Git, worktrees, and documentation

- Branch prefix `codex/`; one concern per worktree.
- Every commit touching a public surface must carry a
  `Documentation Impact:` declaration (see `AGENTS.md` and
  `docs/architecture/13_Documentation_Governance.md`).
- Required checks before merging (run from the worktree root):

```powershell
python scripts/check_code_style.py
python scripts/check_code_style.py --base main
python -m pytest backend/tests/test_code_style.py -q
python scripts/check_doc_coverage.py --base main
python -m pytest backend/tests/test_doc_coverage.py -q
```

Local hooks (installed once per machine into the shared hooks dir via
`scripts/install_git_hooks.ps1` / `.sh`) run the staged code-style gate at
`pre-commit` and the doc-coverage gate at `commit-msg`.

## S12. Historical debt migration

Legacy violations are tracked, not hidden:

1. Add the file to `scripts/code_style_baseline.txt` with its current size.
2. Refactor to shrink it.
3. Lower the ceiling in the same commit.
4. Delete the entry once the file is under the soft threshold.

The baseline may only decrease. A ceiling may never be raised to silence a
warning, and no violation may be exempted silently.

## S13. CI

CI is **Not implemented** by decision; enforcement today is local hooks plus
the required pre-merge commands above.
