# Personal Cognitive IP Engine (showcase copy)

> [中文](README.md) | English

A personal content-production engine that turns a user's writing DNA into a
repeated AI pipeline:

**topic -> two divergent outlines (A/B) -> full draft -> user edits ->
diff-based Thinking-DNA extraction -> profile evolution -> multi-platform output**

This is a **desensitized showcase copy**. See `PROVENANCE.md` for what was removed
and what still needs confirmation.

> Status honesty note: this repository is a local development project. It is
> **not** deployed to production, has **no** real users, and has **no** measured
> performance or business metrics. Only test-suite numbers reported in
> `docs/evaluation.md` are real; everything else is "not measured".

## What it actually does (code-verified)

| Capability | Status | Where |
| --- | --- | --- |
| Divergent outline generation (A/B) | implemented | `backend/app/engine/agents/outline_agent.py` |
| Draft generation with persona / DNA / memory context | implemented | `backend/app/engine/agents/draft_agent.py` |
| Diff-based Thinking-DNA extraction | implemented | `backend/app/engine/agents/diff_agent.py` |
| Zero-diff baseline gating (skips LLM when nothing changed) | implemented | `diff_agent.py` |
| Code-based "AI filler" lexical stripping | implemented | `backend/app/utils/lexical_filter.py` |
| Driver-level read-only DB engine for the agent read path | implemented (partial scope) | `backend/app/core/db.py` |
| Episodic memory + blueprint + viewpoint-conflict memory | implemented | `backend/app/services/memory_*.py` |
| Hybrid retrieval (lexical + embedding cosine) for stories/DNA | implemented | `backend/app/services/memory_retrieval.py`, `memory_dna_retrieval.py` |
| Viral style-fingerprint analysis (rule-based + LLM) | implemented | `backend/app/engine/...viral`, `backend/app/api/viral_analysis.py` |
| Rule-based rubric benchmark (43 labeled samples) | implemented | `backend/app/engine/rubrics/` |
| Skill engine with restricted-token sandbox | implemented (partial isolation) | `backend/app/core/skill_engine/` |
| WeChat / Xiaohongshu / X / short-video formatting | **broken** (NameError) | `skills/content-multi-distributor/scripts/_formatters*.py` |
| Viewpoint-conflict detection | **broken** (NameError) | `backend/app/services/memory_conflicts.py` |
| WeChat chat-record import | not found | — |
| Multi-platform auto-publishing (not just formatting) | not implemented | — |
| Fine-tuning (LoRA / QLoRA) training | not implemented | — |

## Architecture in one picture

```
Vue 3 frontend
   |
FastAPI  (private router requires auth; public router is a whitelist)
   |
CognitiveEngine (headless facade; fixed orchestration, not an autonomous planner)
   |-- OutlineAgent  -> ModelGateway (role -> model)
   |-- DraftAgent    -> ModelGateway + read-only context assembly
   |-- DiffAgent     -> ModelGateway + writable DNA write-back
   |-- Viral semantic pipeline
   |
Services (memory, cognitive profile, style selection, crawler, credentials)
Core (db + readonly engine, auth, net_guard SSRF, crypto, skill engine)
Skills (SKILL.md + python scripts executed by the sandbox runner)
```

See `docs/architecture.md` for the detailed flow.

## Tech stack

- Backend: Python 3.13, FastAPI, SQLModel / SQLAlchemy, Pydantic v2,
  pydantic-settings, `openai` (AsyncOpenAI, OpenAI-compatible), `cryptography`,
  `playwright`, `trafilatura`, `qrcode`, `uvicorn`.
- Frontend: Vue 3 + TypeScript + Vite, Tailwind CSS 4, jszip.
- Database: SQLite by default (PostgreSQL supported; read-only sessions are
  enforced at the driver level for both).
- Tests: pytest + pytest-asyncio (55 test files under `backend/tests` plus 18 root-level `backend/test_*.py` files).
- Windows-only: the Skill sandbox uses a real Windows Restricted Token via ctypes.

## Requirements to run

- Python >= 3.13, Node >= 20.
- An OpenAI-compatible API key (`OPENAI_API_KEY`). **The showcase cannot call a
  real model without your own key.**
- Windows 10/11 for the restricted-token sandbox; on other platforms the skill
  runner fails closed (by design).

## Quick start

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -e .
Copy-Item ..\.env.example .env        # then fill in OPENAI_API_KEY
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

```powershell
cd frontend
npm install
npm run dev      # http://localhost:5173
```

- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/api/health (public endpoint)

Run the tests (no credentials needed):

```powershell
cd backend
.\.venv\Scripts\python -m pytest -q
```

## Showcase entry points

| What to look at | File |
| --- | --- |
| Fixed multi-agent pipeline | `backend/app/engine/cognitive_engine.py` |
| The three agents | `backend/app/engine/agents/*.py` |
| Model gateway (role -> model, structured output, fallback) | `backend/app/engine/model_gateway.py` |
| Prompts (kept out of Python for safety) | `backend/app/engine/prompts/` |
| Lexical filter | `backend/app/utils/lexical_filter.py` |
| Read-only DB engine | `backend/app/core/db.py` |
| SSRF guard | `backend/app/core/net_guard.py` |
| Restricted token sandbox | `backend/app/core/skill_engine/restricted_token.py` |
| Memory retrieval | `backend/app/services/memory_retrieval.py` |
| Private/public route boundary | `backend/app/api/auth_boundary.py` |

## Contribution (as confirmed by the project owner)

- **Requirements analysis and system / architecture design: yours.**
- **Code review: yours** (implementation code in this repo is largely AI-assisted).
- **Functional testing of the overall system: yours**, including the real-model
  demo run below.
- **Solo project** — the only human owner; implementation code was
  AI-assisted and reviewed by you.

You also own project feature and rule management: the feature inventory, the
coding standard, the sandbox / permission documentation, and the doc-coverage /
code-style gates that enforce them.

Modules you authored yourself, test authorship and CI / deployment ownership
are still listed as "to be confirmed" in `docs/resume-notes.md`.

## Screenshots (real model, synthetic data)

Captured on 2026-10-15 by driving the real browser UI against the real
backend and a **dedicated demo SQLite database**
(`demo-data/job-demo.db`, deleted after capture) with an OpenAI-compatible
model (`deepseek-v4-flash-0731`). No mock, no static mock page, no design
mock-up. The topic text is synthetic.

### 1. Topic input — `docs/images/01-topic-input.png`

- **Input (synthetic):** `AI Agent 工作流的可评估性：如何把重复工作变成可追溯的自动化流程`
- **Output:** the topic plus demo context are posted to
  `POST /api/outlines/generate`.
- **Capability shown:** the Vue workbench is wired to the FastAPI private router
  (`backend/app/api/outline_generation.py`), and outline generation is a fixed
  orchestrated step rather than an autonomous planner.

![Topic input](docs/images/01-topic-input.png)

### 2. Divergent A/B outlines — `docs/images/02-divergent-outlines.png`

- **Input:** the same synthetic topic.
- **Output:** two structurally different outlines returned by
  `OutlineAgent` (`backend/app/engine/agents/outline_agent.py`) from a real model
  call, with an explicit "选择方案 B / 选定此方向并扩写初稿" decision step.
- **Capability shown:** divergent ideation + user selection gating the next
  stage; the outline is a contract object (`outline_schemas.py`) passed into
  draft generation, not free text.

![Divergent outlines](docs/images/02-divergent-outlines.png)

### 3. Generated draft — `docs/images/03-draft-generated.png`

- **Input:** outline **B**, selected in step 2.
- **Output:** a full draft (1301 words in this run) archived through
  `POST /api/drafts/generate`, shown in the draft editor together with the
  refinement-diff view, archive action, multi-platform reformat action,
  Thinking-DNA extraction action and the viewpoint review panel.
- **Capability shown:** `DraftAgent` assembles persona / DNA / memory context on
  the driver-level read-only session
  (`backend/app/core/db.py`, `CognitiveService.get_*_readonly`) while the archive
  write happens on a separate writable session; code-based lexical stripping
  (`backend/app/utils/lexical_filter.py`) runs in code, not only in prompts.

![Generated draft](docs/images/03-draft-generated.png)

Not captured (not implemented or not verified in this pass): multi-platform
distribution, WeChat record import, autonomous tool-planning agent, LoRA/QLoRA
fine-tuning.
## Known limitations (stated honestly)

- **Not an autonomous agent.** The pipeline is a fixed orchestration of four
  stages. There is no planner, no router, no reflection loop, no LLM tool
  calling, and no inter-agent negotiation.
- **Not deployed, no real users.** No production environment, no traffic, no
  business metrics, no measured latency or cost improvement.
- **Sandbox isolation is partial.** The Windows skill runner uses a real
  Restricted Token (`CreateRestrictedToken` + `CreateProcessAsUserW`) and fails
  closed when it cannot. It does *not* provide an AppContainer, filesystem ACL
  isolation, network isolation, registry/clipboard/COM isolation, or
  `WindowsSandbox.exe` virtualization, and it does not enforce `SKILL.md`
  `permissions` metadata.
- **Read-only DB covers the agent read path only.** Outline/Draft context
  assembly is physically read-only. Draft archiving and the Diff/DNA evolution
  flow are intentionally writable.
- **Two features are currently broken** by an unresolved `NameError`:
  viewpoint-conflict detection (`backend/app/services/memory_conflicts.py`) and
  multi-platform distribution formatting
  (`skills/content-multi-distributor/scripts/_formatters*.py`).
- **WeChat chat-record import: not found in the repository.** Do not assume it
  exists.
- **No multi-platform auto-publishing.** Only local formatting/preview, and that
  path is currently broken anyway.
- **No LoRA/QLoRA fine-tuning.** At most, an understanding of the principles.

## Scope of this public copy

This is a **partial, desensitized export**, not a byte-for-byte reproduction of
the working tree. Its purpose is to let a reviewer read and understand the core
pipeline, the three agents, the engineering mechanisms described above, and the
real-run evidence, without exposing anything sensitive.

### What is included

- Backend application code (`backend/app/`): API, services, models, engine and
  the three agents, core (db / readonly engine, auth, net_guard, crypto, skill
  engine).
- Backend tests (`backend/tests/` and `backend/test_*.py`).
- Frontend source (`frontend/src/`) and its build configuration.
- `skills/` skill definitions and their scripts.
- `scripts/` repository governance gates.
- Documentation: `docs/architecture.md`, `docs/demo.md`, `docs/evaluation.md`,
  `docs/resume-notes.md`, `docs/feature-status.md`, plus `docs/architecture/`
  and `docs/design/`.
- `docs/images/`: three real-run UI screenshots (synthetic input data).
- `.env.example` with variable names and empty values only.

### What is deliberately excluded

- `.git/` (the original repository history).
- `.env` and every other real environment file; only the placeholder
  `.env.example` is shipped.
- All `*.db`, `*.sqlite`, `*.sqlite3` database files (including the
  `backend/app.db` that was present in the working tree).
- All `*.log` files and the original working tree's `logs/` directory.
- All credentials and secrets stores.
- All caches: `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`,
  `.mypy_cache/`, `.vite/`.
- Virtual environments: `.venv/`, `venv/`.
- `node_modules/`, `dist/`, and all build output.
- `backend/data/` (local uploads).

### Known residual scanner hits (not secrets)

A secret-pattern scan over this export reports two categories of hit. Both are
deliberate and safe:

- `sk-...`-shaped strings inside `backend/tests/test_security_*.py` and
  `backend/test_windows_sandbox.py`. These are **negative-test fixtures** —
  fake strings used to prove the redaction / DLP code works. They are not
  credentials.
- `C:\Users\admin\vault\...` inside the same test files. Same purpose:
  synthetic input for the scanner tests.

The image-service host `apihub.agnes-ai.com` appears in
`backend/app/core/config.py` and the frontend model-settings list. It is a
public third-party API endpoint that the code allow-lists for image generation.
It is not a private host and contains no credential.

### Reproduction scope

You can install dependencies and run the test suite from this copy without any
credentials. To exercise the actual LLM pipeline you must supply your own
OpenAI-compatible API key via `OPENAI_API_KEY`; this copy ships no key and
cannot call a real model on its own.

