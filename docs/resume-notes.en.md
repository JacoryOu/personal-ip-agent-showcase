# Resume notes (AI Agent application development engineer)

> [中文](resume-notes.md) | English

This file extracts material for a resume. It deliberately separates
**what the code proves** from **what only you can confirm**. Nothing here
claims users, revenue, latency improvements, or model-training experience
that the repository cannot evidence.

## 1. Project background (code-verified framing)

A personal content-production engine that repeatedly runs a user's own writing
"DNA" through a fixed multi-stage LLM pipeline:

`topic -> outline A/B -> full draft -> user edit -> diff-based Thinking-DNA
extraction -> profile evolution -> multi-platform formatting`

The value proposition the code implements is *reusability of personal writing
style across many articles*, plus a governance layer (permission gates, prompt
separation, code-style and doc-coverage CI gates) that keeps the pipeline
maintainable.

Project type facts, taken from the code:

- Monorepo: FastAPI backend + Vue 3 / TypeScript frontend + Python `skills/`.
- Headless engine (`backend/app/engine/cognitive_engine.py`) driven by a thin API
  layer, so the same flow can be called from API, CLI or tests.
- Storage: SQLModel over SQLite by default, PostgreSQL-compatible.

## 2. Contribution boundary

### Confirmed by you (2026-10-15)

- **Requirements analysis and system / architecture design: you.**
- **Code review: you** — you review the implementation code produced inside this
  repository (which includes AI-assisted code).
- **Functional testing of the overall system: you** — you run and judge the
  end-to-end behaviour, including the real-model demo run documented in
  `docs/demo.md`.
- **Project feature and rule management: you** — you own the feature inventory,
  the coding standard (`docs/architecture/09_Coding_Standards.md`), the sandbox /
  permission model documentation, and the doc-coverage / code-style gate rules
  that encode them.
- **Solo project.** You are the only human owner; the implementation code was
  produced with AI assistance and reviewed by you.

Your role is therefore **requirements + system / architecture design, feature and
engineering-rule management, code review, and end-to-end functional
verification** — not "I wrote every module".

Wording rules that follow from that:

- Use verbs like *designed / defined / specified / owned / reviewed / verified*.
- Avoid verbs like *implemented / developed / built* for modules you did not write
  yourself.
- Do not delete the technical bullets (2-5) because they are the strongest
  evidence you can defend: reviewing and verifying a mechanism is real work, and
  each one is traceable to a code path.

### Still to be confirmed by you

| Area | Status |
| --- | --- |
| Backend implementation authorship (agents, services, DB, auth, skill engine) | to be confirmed by you |
| Frontend implementation authorship (Vue views/services/router) | to be confirmed by you |
| Test authoring vs. reviewing / maintaining existing tests | to be confirmed by you |
| Release / deployment / CI operations | to be confirmed by you |
| Feature inventory / coding standard / doc & style gate ownership | **confirmed: you** |
| Solo project or team project | **confirmed: solo project** |

AI-assisted and third-party split (safe to state):

- AI assistance: an AI coding agent (`codex` commits) contributed code and
  documentation inside this repository; you performed the code review on it.
- Reference / framework conventions: SQLModel CRUD layout, FastAPI router layout,
  pytest fixtures follow public framework documentation. No third-party source
  repository was vendored (see `PROVENANCE.md`).
- Third-party components (not your work): FastAPI, SQLModel/SQLAlchemy,
  Pydantic, Vue, Vite, Tailwind, Playwright, trafilatura, `openai` SDK, OS-level
  Windows APIs via `ctypes`.
## 3. Key technical problems and how they were solved

These are all traceable to code; pick the ones you can defend in an interview.

1. **Keeping agent reads physically read-only instead of "please don't write".**
   - Problem: an agent needs profile / DNA / memory context, but that same path
     also archives drafts and evolves DNA, which must write.
   - Solution: a second, independent engine in `backend/app/core/db.py`. SQLite
     connections use `sqlite:///file:<abs>?mode=ro&uri=true` plus
     `PRAGMA query_only=ON` on every connect; PostgreSQL runs
     `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY` and
     `default_transaction_read_only = on`. Unsupported backends and
     `:memory:` fail closed with `UnsupportedReadOnlyBackendError`.
   - Scope honesty: read-only covers only the Outline/Draft input-context
     assembly. Draft archiving and DNA/profile evolution stay writable by
     design. Verified by `tests/test_agent_db_readonly.py`, which proves a write
     raises at the driver, not by convention.

2. **Not paying for an LLM call that cannot learn anything.**
   - `backend/app/engine/agents/diff_agent.py` compares the AI draft with the
     user's final text and aborts *before* the model call when the texts are
     identical and no viewpoint judgments were supplied.
   - This is a cost/latency guard implemented in Python, not as a prompt
     instruction.

3. **Style drift / "AI filler" that prompts alone did not fix.**
   - `backend/app/utils/lexical_filter.py` performs RegEx-based removal of
     filler and replacement patterns. Both `draft_agent.py` and `diff_agent.py`
     call it in code, so stripping does not depend on model compliance.
   - The "AI-speak" problem was addressed by deterministic post-processing
     rather than by asking the model to behave.

4. **Hybrid retrieval without a vector database.**
   - `backend/app/services/memory_retrieval.py` and
     `memory_dna_retrieval.py` rank stories / DNA traits by
     `0.5 * lexical + 0.5 * cosine(embedding) + confidence * 0.1`.
   - Honest limitation: no reranker, no vector store, no retrieval metric
     evaluation. See `docs/evaluation.md`.

5. **Prompt governance as a build gate.**
   - All prompt text lives in `backend/app/engine/prompts/`.
   - `scripts/check_code_style.py` blocks prompt-like string literals in Python
     outside that directory, and enforces file-size caps against a
     baseline that may only ever shrink. This turns a convention into a CI gate.

6. **SSRF protection on any user-supplied URL.**
   - `backend/app/core/net_guard.py` validates scheme / DNS resolution /
     private and reserved address ranges before the crawler or image service
     fetches a URL. Covered by `tests/test_net_guard*.py`,
     `tests/test_settings_ssrf.py`.

7. **Refusing to pretend a sandbox exists.**
   - `backend/app/core/skill_engine/restricted_token.py` really calls
     `CreateRestrictedToken(DISABLE_MAX_PRIVILEGE)` and launches the child with
     `CreateProcessAsUserW`.
   - `SandboxExecutionResult` reports `requested_runner_mode`, the
     actually-applied `runner_mode`, `sandbox_enforced`, and `warnings`.
   - If the restricted token cannot be created, the runner **fails closed**
     rather than executing the skill as a plain subprocess. `wsb` mode is
     rejected outright; `WindowsSandbox.exe` is never launched.
   - Not implemented and must not be claimed: AppContainer, filesystem ACL
     isolation, network isolation, registry / clipboard / COM isolation, child
     job-object policy, `SKILL.md` `permissions` enforcement.

8. **Credential handling.**
   - API credentials are encrypted at rest (`backend/app/core/crypto/`) and
     never returned in plaintext; error contracts are covered by
     `tests/test_security_*.py` and `tests/test_error_contract.py`.

## 4. Verifiable results (state them exactly like this)

- Local test suite, 2026-10-15, single process, no CI:
  **18 failed, 992 passed, 3 skipped, 85 warnings**.
  - This is a **mock-heavy, local, SQLite-default** run. It proves the harness
    and the contracts work. It is not a statement about model quality,
    production readiness, or real-user behaviour.
  - 18 failures are honest defects, three of them one-line import bugs
    (`clean_title_text` in the multi-distributor formatters, `CognitiveTrait` in
    `memory_conflicts.py`, `status` in `draft_generation.py`) plus one
    sys.path issue in `test_api_auth_surface.py`. Details in
    `docs/evaluation.md`.
- Rule-based viral-rubric benchmark against 43 human-labeled samples
  (code thresholds: MAE <= 0.8, exact match >= 0.60).
  - Caveat you must understand before claiming it: it measures whether the
    deterministic rubric reproduces human labels. It says nothing about LLM
    output quality, and the provenance of those 43 labels is unconfirmed.

Do **not** claim: performance improvement, cost reduction percentage, user
count, published-post count, hours saved, or any production metric. There is
no evidence for any of these in the repository.

## 5. Resume bullet candidates (pick 3-5)

Choose the ones matching what you can defend. Each is grounded in code, and
bullets 1-4 are written from the **requirement / design + review + verification**
angle confirmed in section 2 — reword them to "implemented" only for the parts
you confirm you wrote yourself.

1. **(role-fit) Designed the requirements, architecture and engineering rules for a FastAPI + Vue 3 personal content engine that runs a user's extracted writing "DNA" through a fixed four-stage LLM pipeline (divergent outline A/B -> draft -> user edit -> diff-based DNA extraction), with the model gateway and all prompts separated so roles, models and prompt versions are independently configurable and testable.
2. Reviewed and verified driver-level agent-read isolation (SQLite `mode=ro` + `query_only`, PostgreSQL read-only transactions) instead of relying on prompt or code convention, and confirmed the write failure path with regression tests.
3. Verified that prompt-level style guidance was replaced by a deterministic RegEx lexical filter applied in code on both draft and diff paths, plus a pre-LLM gate that skips the model call when the human edit is byte-identical to the draft.
4. **(review) Reviewed and boundary-documented a Windows skill sandbox built on real Restricted Tokens (`CreateRestrictedToken` + `CreateProcessAsUserW`) that fails closed and reports the actually-enforced isolation level instead of silently degrading, with explicit documentation of what is still not isolated (no AppContainer, no filesystem ACL or network boundary).
5. **(rule ownership) Authored the enforcement rules for the repository governance gates (prompt-literal placement, file-size baselines that may only shrink, commit-time documentation-coverage gate) and ran the end-to-end demo path against a real model on an isolated database to confirm the wired pipeline actually executes, not just its unit tests.

6. Owned feature scope and engineering rules for the repo: kept the
   code-truth feature inventory, the coding standard (file-size baseline that may
   only shrink, prompt literals confined to `engine/prompts/`), the sandbox /
   permission reality doc, and a commit-time documentation-coverage gate, turning
   conventions into blocking checks instead of review comments.
7. (role-honest variant, safe with what you confirmed) Owned requirements
   analysis and system design for the engine, reviewed the AI-assisted
   implementation code, and validated the full content pipeline (outline ->
   draft -> feedback -> DNA persistence) with a real model on a dedicated demo
   database, capturing UI evidence for three core screens.

Deliberately avoided in these bullets: "autonomous planning agent",
"multi-agent collaboration", "complete sandbox", "multi-platform auto-publishing",
"LoRA fine-tuning", and any percentage-improvement or user metric.

## 6. Statements you should NOT put on a resume today

- "Built an autonomous / self-planning Agent" - this is a fixed orchestrated
  pipeline. There is no planner, router, reflection loop, or LLM function
  calling, and no inter-agent negotiation.
- "Fine-tuned a model with LoRA/QLoRA" - not implemented. At most: understands
  LoRA/QLoRA principles and the basic workflow.
- "Multi-platform content distribution" - currently only formatting/preview,
  and it is currently broken by a missing import.
- "Sandboxed skill execution" without qualification - only a restricted token
  on Windows; no OS-level file or network isolation.
- "Improved conversion rate by X%" or any business outcome - unmeasured.

## 7. What you still need to supply (three items, in priority order)

1. **Nothing blocking for the design/leadership framing.** Requirements analysis, system / architecture design, feature and engineering-rule management, code review and overall functional testing are all confirmed as yours, and the project is confirmed solo (see section 2). The only genuinely open items are narrower: whether you personally wrote any backend or frontend modules, whether you authored or only reviewed the test code, and whether you handled CI / deployment. Leaving these as "to be confirmed" is honest and costs you little, because the bullets you can defend already do not depend on them.
2. **Real-run trace, if you want to show it.** One real-model end-to-end run with three UI screenshots now exists (`docs/demo.md`, `docs/images/`). It uses synthetic input on a throwaway SQLite file and is a functional demonstration only, not a quality or performance evaluation.
3. **Environment and usage reality.** Whether it ever ran against real
   PostgreSQL, real outbound crawling, or real usage, and whether the 43 rubric
   labels are yours, a colleague's, or an external source. This determines which
   environment claims and which benchmark claim you are allowed to make.




