# Architecture (code-verified, 2026-10-15)

> This document describes what the code actually does. Where the code and the
> original design docs disagree, the code is the fact.

## 1. Layering

```
frontend/ (Vue 3 + TS + Vite)
   |  HTTP (fetch wrappers in src/services/api/*.ts)
   v
backend/app/api/          FastAPI routers
   - public_router: explicit PUBLIC_ENDPOINTS whitelist (health, auth entry)
   - private_router: every route depends on get_current_user
   v
backend/app/engine/       Headless core (no FastAPI imports)
   - CognitiveEngine (facade, singleton via get_cognitive_engine)
   - agents/{outline,draft,diff}_agent.py
   - model_gateway.py (role -> model, structured output, fallback)
   - prompts/ (all prompt text lives here, enforced by the code-style gate)
   v
backend/app/services/     Business logic (memory, cognitive, style, crawler, creds)
backend/app/core/         db (+ readonly engine), auth, net_guard, crypto,
                          vault_path_guard, skill_engine
skills/<name>/SKILL.md    Declarative skill definitions + python scripts
```

Key boundary: `CognitiveEngine` does not import FastAPI. The API layer is a thin
adapter; the engine is callable from tests or a CLI.

## 2. The core loop (fixed orchestration, NOT an autonomous planner)

There is **no** planner, router, reflection loop, or LLM function-calling in this
codebase. The pipeline is an explicit sequence in `cognitive_engine.py`:

```
POST /api/outlines/generate
  -> OutlineAgent.generate_outlines()
       - ModelGateway(role=outline) -> structured OutlineOutput
       - lexical_filter.clean()
       -> outline A / outline B

POST /api/drafts/generate
  -> ownership checks (_get_owned_draft, _reject_body_user_id)
  -> DraftAgent
       - assemble IP bundle on a READ-ONLY session:
           Persona, ThinkingDNA 2.0, cognitive traits, episodic stories,
           blueprints, viewpoint conflicts, style fingerprint
       - ModelGateway(role=draft)
       - lexical_filter.clean()
       - archive draft on a SEPARATE WRITABLE session + lineage record

user edits the draft in the UI, submits the final text

POST /api/dna/extract
  -> DiffAgent
       - zero-diff gate: if AI text == human text AND no viewpoint judgments
         were supplied, abort BEFORE calling the LLM
       - ModelGateway(role=diff)
       - write back DNA records / cognitive profile (writable path)

(optional) POST /api/drafts/distribute
  -> skills/content-multi-distributor
       -> wechat / xiaohongshu / x / short-video formatting
```

The agents hand data to each other through Pydantic objects, DB rows and service
calls. They do not talk to each other, do not share a blackboard, and do not
critique each other's output.

## 3. Model gateway

`backend/app/engine/model_gateway.py`:

- Maps a logical role (outline / draft / diff / image / ...) to a model name and
  temperature from settings.
- Uses `AsyncOpenAI` against an OpenAI-compatible endpoint
  (`OPENAI_BASE_URL` is supported, so DeepSeek / OneAPI / Azure work).
- Parses structured output through Pydantic schemas with a fallback path.

## 4. Prompt management

All prompt-like string literals live in `backend/app/engine/prompts/`. The
code-style gate (`scripts/check_code_style.py`) fails the build if a prompt
literal appears in a `.py` file outside that directory. This is a real
enforcement, not a convention.

## 5. Memory and retrieval

- `memory_service.py` is a facade over responsibility modules
  (`memory_retrieval`, `memory_dna_retrieval`, `memory_blueprints`,
  `memory_conflicts`, `memory_evolution`, `memory_lifecycle`, `memory_similarity`).
- Episodic-story retrieval (`memory_retrieval.retrieve_relevant_stories`) is a
  **hybrid** score: `0.5 * lexical_overlap + 0.5 * cosine(embedding) + confidence*0.1`.
  The lexical side is keyword / bigram / trigram matching over CJK text.
- There is **no** learned re-ranker and no vector database. Similarity is plain
  cosine over stored embedding bytes.
- Context assembly happens on the read-only session; the write path is separate.

## 6. Read-only DB engine (agent read path only)

`backend/app/core/db.py` builds a second engine, `readonly_engine`:

- SQLite: opened with `?mode=ro&uri=true` plus `PRAGMA query_only=ON` on connect.
- PostgreSQL: `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY` and
  `default_transaction_read_only = on`.
- Unsupported backends (MySQL) and `:memory:` SQLite **fail closed** with
  `UnsupportedReadOnlyBackendError`.

Regression proof: `backend/tests/test_agent_db_readonly.py` shows that a write
through the read-only session fails at the driver, not by convention.

Scope (be precise in interviews): the read-only session covers input-context
assembly. Draft archiving and DNA/profile evolution are intentionally writable.

## 7. Security boundaries

| Boundary | Implementation | Notes |
| --- | --- | --- |
| Public vs private routes | `api/auth_boundary.py`, `PUBLIC_ENDPOINTS` whitelist | covered by `tests/test_api_auth_surface.py` |
| Ownership | every service method takes `user_id` and checks it | `tests/test_auth_and_ownership.py` |
| SSRF | `core/net_guard.py`: scheme whitelist -> reject credentialed URLs -> host allowlist -> resolve DNS and validate every IP -> port whitelist -> per-hop redirect re-check -> timeout -> response size cap | `tests/test_net_guard*.py` |
| Credential storage | `core/crypto/secret_box.py` (Fernet-style via `cryptography`) | `tests/test_credential_encryption.py` |
| Prompt-injection / secret leakage | tests assert that prompts never echo raw user secrets, tracebacks, or foreign users' data | `tests/test_security_*.py` |

## 8. Skill engine and sandbox (partial)

`backend/app/core/skill_engine/`:

- Discovery reads `skills/*/SKILL.md` (name, description, `permissions`).
- Policy gates whether an unattended (scheduler-driven) run is allowed.
- The runner reports exactly what it did:
  `requested_runner_mode`, `runner_mode`, `sandbox_enforced`, `warnings`.
- `restricted_token`: creates a real Windows Restricted Token
  (`CreateRestrictedToken(DISABLE_MAX_PRIVILEGE)` + restricting SID list marked
  deny-only) and launches the child with `CreateProcessAsUserW`. On success
  `sandbox_enforced=True`.
- If the restricted token cannot be created, it **fails closed**
  (`runner_mode="restricted_token_unavailable"`, `success=False`). It never
  silently falls back to a plain subprocess.
- `wsb` fails closed (`wsb_unsupported`); `WindowsSandbox.exe` is never launched.

What it does **not** guarantee: AppContainer, filesystem ACL isolation, network
isolation, registry/clipboard/COM isolation, child-process job policy.

Regression: `tests/test_restricted_token.py`,
`tests/test_sandbox_mode_transparency.py`, `tests/test_sandbox_acl_integration.py`,
`tests/test_os_network_boundary.py`, `tests/test_job_object.py`.

## 9. Unattended scheduler

`api/scheduler.py` + `services/inspection_scheduler_*.py` run skills on a timer
and persist state so a restart does not double-run a task
(`tests/test_scheduler_state_persistence.py`). Scheduler-driven runs must pass the
permission policy gate (`tests/test_workflow_permission_gate.py`).

## 10. Design trade-offs the code actually makes

These are code facts, not opinions. Whether they were deliberate product
decisions needs your confirmation.

1. **Fixed sequence instead of a planner.** Simpler to reason about and cheaper,
   but it cannot recover from an unexpected intermediate failure on its own.
2. **Zero-diff gate before the LLM call.** Saves one paid call when nothing
   changed; at the cost of not producing a "no-op" analysis record.
3. **Code-based lexical filtering instead of prompt-only instructions.** Makes
   the guarantee independent of model compliance.
4. **A second physical DB engine for reads.** Stronger than a session flag, but
   doubles connection management and complicates SQLite file handling.
5. **Fail closed everywhere in the security layer.** Safer, but a missing
   Windows primitive turns into a hard failure rather than a degraded mode.
