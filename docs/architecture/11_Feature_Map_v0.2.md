# Feature Map v0.2 — code-truth inventory

Status: **current**. Verified against `main@8718926`. This file exists because the
original PRD/Roadmap/Backlog (v0.1) describe only the first three epics, while
`main` carries far more features they never mention. When code and v0.1 docs
disagree, **code is the current fact** and this map is the correction layer.

Status vocabulary: **Implemented** / **Partial** / **Not started** / **Planned**.

The `Design document` column names the feature-level design doc in
`docs/design/` that owns the behaviour. Every public surface listed here must
have an owning design doc; see `docs/design/README.md` and
`13_Documentation_Governance.md`.

## 1. Backend API blueprints — `backend/app/api/` (14 modules, `__init__.py` excluded)

| Blueprint | Primary capability | Status | Design document |
| --- | --- | --- | --- |
| `blueprints.py` | Generic blueprint registry over the agent workflow | Implemented | `docs/design/01_Creation_Pipeline.md` |
| `outlines.py` | Divergent outline generation (A/B) | Implemented | `docs/design/01_Creation_Pipeline.md` |
| `drafts.py` | Compatibility facade for draft generation, editing, archival, diff/DNA flow entry (see `draft_*` modules below); `POST /drafts/generate` accepts an optional owned `viral_analysis_id` (explicit id wins; otherwise `StyleSelectionService` auto-selects from the caller's own analysed records; below threshold falls back to Persona/DNA), resolved and ownership-checked in `backend/app/engine/cognitive_engine.py` before any LLM call | Implemented | `docs/design/01_Creation_Pipeline.md` |
| `dna.py` | Compatibility facade for Thinking DNA read/update (see `dna_*` modules below) | Implemented | `docs/design/02_Cognitive_Profile_and_DNA.md` |
| `dna_v2.py` | Compatibility facade for DNA 2.0 (personas, products, stories, timeline, supersede); implementation lives in the `dna_v2_*` responsibility modules listed below. Route paths, methods, schemas and fallbacks unchanged. | Implemented | `docs/design/02_Cognitive_Profile_and_DNA.md` |
| `viral_analysis.py` | Viral article semantic breakdown; its `style_fingerprint` reaches Draft via explicit id **or** automatic selection from the caller's own analysed records, with a below-threshold Persona/DNA fallback | Partial (thin API over service; Draft consumption and automatic selection implemented) | `docs/design/03_Viral_Semantic_Analysis.md` |
| `platforms.py` | Compatibility facade for multi-platform distribution (see `platforms_*` modules below) | Implemented | `docs/design/04_Distribution_and_Credentials.md` |
| `materials.py` | Compatibility facade for the material vault (see `materials_*` modules below) | Implemented | `docs/design/05_Material_Vault_and_Obsidian.md` |
| `obsidian.py` | Obsidian bridge, authenticated, one-way Vault -> DNA import | Implemented (API auth); Partial (server-wide vault roots, sync semantics) | `docs/design/05_Material_Vault_and_Obsidian.md` |
| `scheduler.py` | Scheduled inspection jobs | Implemented | `docs/design/06_Scheduler_and_Unattended_Skills.md` |
| `chat_lounge.py` | Compatibility facade for chat lounge / Cognitive Twin interaction (see `chat_lounge_*` modules below) | Implemented | `docs/design/07_Surfaces_and_Engagement.md` |
| `private_domain.py` | Compatibility facade for the private-domain funnel / hub (see `private_domain_*` modules below) | Implemented | `docs/design/07_Surfaces_and_Engagement.md` |
| `images.py` | Image generation/handling | Implemented | `docs/design/07_Surfaces_and_Engagement.md` |
| `settings.py` | Compatibility facade for model + app settings and local API identity (see `settings_*` modules below) | Implemented | `docs/design/07_Surfaces_and_Engagement.md` |

### 1a. API structural facades and responsibility modules

The oversized API blueprints below were split by responsibility as a **pure
structural refactor**. Each original module remains an importable compatibility
facade that re-exports its router, schemas, helpers and handlers under the same
names, so URL paths, HTTP methods, request/response schemas, dependency
injection, exception handling and fallback behaviour are unchanged. No
authentication, permission or sandbox guarantee was added or changed by this
split.

| Facade | Responsibility modules |
| --- | --- |
| `backend/app/api/drafts.py` | `backend/app/api/draft_common.py`, `backend/app/api/draft_generation.py`, `backend/app/api/draft_archive.py`, `backend/app/api/draft_feedback.py`, `backend/app/api/draft_lineage.py` |
| `backend/app/api/dna.py` | `backend/app/api/dna_common.py`, `backend/app/api/dna_extraction.py`, `backend/app/api/dna_portability.py`, `backend/app/api/dna_traits.py` |
| `backend/app/api/dna_v2.py` | `backend/app/api/dna_v2_common.py`, `backend/app/api/dna_v2_persona_schemas.py`, `backend/app/api/dna_v2_persona_extraction.py`, `backend/app/api/dna_v2_persona_extract.py`, `backend/app/api/dna_v2_product_helpers.py`, `backend/app/api/dna_v2_product_routes_a.py`, `backend/app/api/dna_v2_product_routes_b.py`, `backend/app/api/dna_v2_stories.py`, `backend/app/api/dna_v2_timeline.py`, `backend/app/api/dna_v2_supersede.py` |
| `backend/app/api/chat_lounge.py` | `backend/app/api/chat_lounge_common.py`, `backend/app/api/chat_lounge_crystallization.py`, `backend/app/api/chat_lounge_messages.py`, `backend/app/api/chat_lounge_prompts.py`, `backend/app/api/chat_lounge_sessions.py` |
| `backend/app/api/private_domain.py` | `backend/app/api/private_domain_common.py`, `backend/app/api/private_domain_community.py`, `backend/app/api/private_domain_fallback.py`, `backend/app/api/private_domain_moment.py`, `backend/app/api/private_domain_schemas.py`, `backend/app/api/private_domain_text.py` |
| `backend/app/api/platforms.py` | `backend/app/api/platforms_common.py`, `backend/app/api/platforms_routes.py` |
| `backend/app/api/materials.py` | `backend/app/api/materials_common.py`, `backend/app/api/materials_crud.py`, `backend/app/api/materials_item.py`, `backend/app/api/materials_collect.py` |
| `backend/app/api/settings.py` | `backend/app/api/settings_common.py`, `backend/app/api/settings_routes.py` |

## 2. Services — `backend/app/services/` (23 modules)

| Service | Responsibility | Status | Design document |
| --- | --- | --- | --- |
| `cognitive_service.py` | IP bundle, profile, read-only context assembly | Implemented | 01, 02 |
| `memory_service.py` | Stable facade for `MemoryService`: every public method signature is unchanged and delegates explicitly to the responsibility modules below. Module-level exports (`Mem0Operation`, `generate_embedding`, `hybrid_retrieve_dna`, `hybrid_retrieve_dna_readonly`, `naturalize_time_expression`, `supersede_dna_trait`) are re-exported so existing imports keep working. **Implemented** (structural split, no behaviour change) | 02 |
| `memory_common.py` | Shared `Mem0Operation` enum and `_parse_user_id` helper | Implemented | 02 |
| `memory_similarity.py` | String-similarity helper used by the DNA evolution path | Implemented | 02 |
| `memory_lifecycle.py` | Mem0 lifecycle application and user-work DNA ingestion | Implemented | 02 |
| `memory_benchmarks.py` | Viral/benchmark decomposition ingestion and conversation conflict capture | Implemented | 02 |
| `memory_blueprints.py` | Blueprint persistence / CRUD | Implemented | 02 |
| `backend/app/services/memory_conflicts.py` | Viewpoint conflict detection; imports and persists the `CognitiveTrait` model when a conflict decision updates traits | Implemented | 02 |
| `memory_context.py` | Context Thinking DNA assembly | Implemented | 02 |
| `memory_retrieval.py` | Relevant-story retrieval (writable session path) | Implemented | 02 |
| `memory_readonly.py` | `retrieve_relevant_stories_readonly` and the other `*_readonly` entry points used by the agent read path. Explicit read-only session is mandatory; there is **no** fallback to the writable engine and no default-user creation | Implemented | 02, `10_Sandbox_and_Permission_Model.md` |
| `memory_dna_retrieval.py` | Embedding generation and hybrid DNA retrieval (read-only and writable variants) | Implemented | 02 |
| `memory_evolution.py` | DNA trait supersession and naturalization of time expressions | Implemented | 02 |
| `cognitive_service.py` | Compatibility facade over the `cognitive_*_service` mixins (public methods and module-level `_parse_user_id` unchanged) | Implemented | 01, 02 |
| `cognitive_common.py` | Shared user-id parsing used by the cognitive service mixins | Implemented | 02 |
| `cognitive_profile_service.py` | Profile load/persist, default-user resolution, agent-facing readonly context assembly | Implemented | 02 |
| `cognitive_evolution_service.py` | DNA sync/evolution and Thinking Trait lifecycle (pin/suppress/toggle) | Implemented | 02 |
| `cognitive_portability_service.py` | Profile JSON import/export and generation-time DNA selection | Implemented | 02 |
| `memory_service.py` | Long/short-term memory, retrieval, read-only variants | Implemented | 02 |
| `feedback_service.py` | Learning feedback capture | Implemented | 02 |
| `viral_semantic_service.py` | Semantic viral decomposition (incl. `style_fingerprint`, `hook_strength`) | Implemented | 03 |
| `style_selection_service.py` | Ranks the caller's own analysed fingerprints by topic / IP / recent-work / transferability; configurable weights and acceptance threshold; returns a candidate id only, never style text; falls back to Persona/DNA when nothing qualifies | Implemented | 03 |
| `platform_crawler_service.py` | Compatibility facade over the `platform_crawler_*_service` mixins (public methods and module-level helpers unchanged) | Implemented | 04 |
| `platform_crawler_support_service.py` | UID parsing and fallback blueprint extraction | Implemented | 04 |
| `platform_crawler_account_service.py` | Benchmark account parse/serialize and CRUD | Implemented | 04 |
| `platform_crawler_feed_service.py` | Simulated feed items and account-post retrieval | Implemented | 04 |
| `platform_crawler_collect_service.py` | Batch benchmark collection and blueprint deconstruction | Implemented | 04 |
| `playwright_service.py` | Browser automation for crawling | Implemented | 04 |
| `credential_service.py` | Credential storage and encryption | Implemented | 04 |
| `material_service.py` | Material asset storage | Implemented | 05 |
| `obsidian_service.py` | Vault Markdown parsing/import -> DNARecord; scan/status use link-safe traversal (`iter_safe_markdown_files`) | Implemented | 05 |
| `inspection_scheduler_service.py` | Scheduling facade (public `InspectionSchedulerService` + `inspection_scheduler` singleton); keeps `engine` / `get_skill_manager` re-exports so existing monkeypatches keep working | Implemented | 06 |
| `inspection_scheduler_helpers.py` | Pure shared helpers (uid parsing, material serialization, `DEFAULT_SCOPE`, facade symbol resolution) | Implemented | 06 |
| `inspection_scheduler_state.py` | Per-user state + settings persistence (`scheduler_user_states`) | Implemented | 06 |
| `inspection_scheduler_wheels.py` | Scheduled wheel execution (unattended skill path) | Implemented | 06 |
| `inspection_scheduler_briefing.py` | Daily briefing aggregation and vault confirmation | Implemented | 06 |
| `inspection_scheduler_runtime.py` | Inspection cycle execution and the background scheduler loop | Implemented | 06 |
| `inspection_scheduler_status.py` | Status reporting, next-run calculation, quota authorization | Implemented | 06 |
| `inspection_quota_service.py` | Quota accounting for inspections | Implemented | 06 |
| `image_service.py` | Image generation; provider calls routed through `core/net_guard.py` (443-only port allowlist, redirect re-validation) | Implemented | 07, `10_Sandbox_and_Permission_Model.md` |


### Service decomposition notes (structural refactor, no behaviour change)

cognitive_service.py and platform_crawler_service.py are now thin
compatibility facades composed from mixins. This is a **structural refactor
only** - it adds no capability and changes no behaviour:

- CognitiveService keeps every previously public method, and the module-level
  _parse_user_id helper is still importable from cognitive_service.
- PlatformCrawlerService keeps every previously public method, and the
  module-level _parse_uid / xtract_fallback_blueprint helpers are still
  re-exported from platform_crawler_service.
- No method signature changed; no API route, request/response schema or
  persisted field changed; no schema migration.
- Crawler behaviour is unchanged, including the UUID fallback for uids and the
  fallback blueprint extraction path.
- The DB read-only scope did **not** widen: only the agent-facing read path
  (IP bundle / DNA / profile / memory retrieval) is read-only. Draft archival
  and the Diff/DNA evolution flow remain intentionally writable.
## 3. Models — `backend/app/models/` (14 model files, 15 tables)

`user`, `chat_session`, `persona`, `product`, `story`, `dna_record`, `draft`,
`feedback`, `material`, `viral_analysis`, `benchmark_account`, `credential`,
`inspection_quota`, `scheduler_state` (`scheduler_user_states`, new table).

All are Implemented. `persona` / `product` / `benchmark_account` /
`viral_analysis` / `inspection_quota` / `chat_session` have **no v0.1 PRD
entry** — concrete proof of documentation drift. Full field/relation/migration
reference: `docs/design/08_Data_Model_Reference.md`.

New this round: `backend/app/models/scheduler_state.py` adds the
`scheduler_user_states` table (one row per real user) backing durable per-user
scheduler settings, dismissed briefing date, quota decision and execution
summary.

## 4. Core / infrastructure — `backend/app/core/`

| Module | Role | Status | Design document |
| --- | --- | --- | --- |
| `config.py` | Settings/env | Implemented | 07 |
| `db.py` | Writable + read-only engines | Implemented (read-only scoped to agent read path) | 01, `10_Sandbox_and_Permission_Model.md` |
| `model_gateway.py` | LLM access | Implemented | 07 |
| `net_guard.py` | SSRF guard (scheme/credential/DNS/private/metadata checks, port allowlist, strict redirect re-validation); used by the image proxy and `image_service.py`, not by every outbound caller | Partial | 04, `10_Sandbox_and_Permission_Model.md` |
| `vault_path_guard.py` | Obsidian vault path containment + link-safe Markdown traversal | Implemented | 05 |
| `crypto/` | Credential encryption | Implemented | 04 |
| `auth/` | Local API identity helpers; only selected routers depend on it | Partial | 07 |
| `errors.py` | Shared error contract: `AppError`, stable public codes, `request_id` payload/header emission | Implemented | 07, `10_Sandbox_and_Permission_Model.md` |
| `request_id.py` | `RequestIdMiddleware`: validate/derive `X-Request-ID` (`^[A-Za-z0-9._-]{1,64}$`), store on `request.state`, log correlation | Implemented | 07 |
| `skill_engine/` | Skill discovery / policy / runner / restricted token | Implemented (partial isolation) | 06, `10_Sandbox_and_Permission_Model.md` |
Application entry point: `backend/app/main.py` builds the FastAPI app, installs
the CORS middleware from the `backend/app/core/config.py` settings
(`CORS_ORIGINS`, `CORS_ALLOW_METHODS`, `CORS_ALLOW_HEADERS`,
`CORS_ALLOW_LOCALHOST_REGEX`, `EXPOSE_UPLOADS`) and conditionally mounts
`/uploads`. Status: Implemented (explicit allowlists; no localhost origin regex
in production). Design documents: `08_Architecture_and_Modules.md`,
`docs/design/07_Surfaces_and_Engagement.md`.

## 4b. Engine layer — `backend/app/engine/`

| Module | Role | Status | Design document |
| --- | --- | --- | --- |
| `prompts/viral_prompts.py` | Viral decomposition prompts; injects the shared scoring rubric block into the LLM prompt | Implemented | 03 |
| `rubrics/viral_rubric.py` | Single code-truth source for the `hook_strength` / `tension_level` / `reuse_score` 0-5 anchors plus the evidence rule; scoring must be evidence-driven and downgraded when evidence is missing | Implemented | 03 |
| `rubrics/viral_benchmark.py` | Deterministic, LLM-free evaluator (`score_hook` / `score_tension` / `score_reuse`) plus per-dimension accuracy / MAE / exact-match reporting against the human-labelled benchmark; gate is MAE <= 0.8 and exact match >= 60% | Implemented (measures rubric-rule fidelity; production-model accuracy still **Partial**) | 03 |
| `rubrics/data/viral_rubric_benchmark_v1.json` | 43 human-annotated samples covering hook strength, tension, reuse, strong/weak extremes and 7 explicit boundary cases, with one annotation note per sample | Implemented (single annotator, no inter-annotator agreement; MVP scale) | 03 |
| `rubrics/__init__.py` | Package exports for the rubric definitions | Implemented | 03 |

## 5. Skill Engine — `backend/app/core/skill_engine/`

| Module | Role | Status |
| --- | --- | --- |
| `discovery.py` | Parse `SKILL.md` front matter into `SkillDefinition` | Implemented |
| `manager.py` | `SkillManager`: list / get / execute (async + sync) | Implemented |
| `policy.py` | Permission policy, network policy, `UNATTENDED` gating | Implemented |
| `windows_sandbox.py` | Facade / orchestration only: runner, permission policy, workspace lifecycle, result aggregation, rollback. Constants + result model in `sandbox_config.py`; child-process spawn in `sandbox_process.py` (which must not own `run_skill`). | Implemented (partial isolation, see sandbox doc) |
| `restricted_token.py` | Thin re-export facade over the three restricted-token modules below | Implemented |
| `restricted_token_api.py` | Errors, `RestrictedTokenInfo`, token introspection, `CreateRestrictedToken(DISABLE_MAX_PRIVILEGE)` | Implemented |
| `restricted_token_process.py` | `CreateProcessAsUserW` launch + Job Object containment under an already-created token | Implemented |
| `restricted_token_winapi.py` | Win32 constants, ctypes structures and API bindings only | Implemented |
| `job_object.py` | Job Object containment on the restricted-token path (`KILL_ON_JOB_CLOSE`, process-tree termination, fail closed on allocation failure) | Implemented |
| `network_guard.py` | Child-process egress guard | Implemented (not OS-level) |
| `sandbox_profile.py` | Sandbox account / SID profile parsing | Partial (no account creation) |
| `acl_guard.py` | Public re-export facade over the ACL modules below | Partial (same limits as `acl_guard_winapi`) |
| `acl_guard_winapi.py` | ACE plan computation, enforcement, read-back verification, rollback (`SetNamedSecurityInfoW`) | Partial (enforce writes scoped allow ACEs; default dry-run, no parent deny ACEs) |
| `acl_guard_winapi_ace.py` | ACE / ACL descriptor construction helpers | Implemented |
| `acl_guard_winapi_bindings.py` | advapi32 / kernel32 ctypes bindings for the ACL path | Implemented |
| `acl_types.py` | `AclEntry`, `AclPlan`, `AclPlanError`, `AclRollbackHandle`, `SidHandle` | Implemented |
| `os_network_boundary.py` | Windows Firewall rule planning | Partial (dry-run, never applies rules) |

## 6. Skills — `skills/` (5 skills)

`content-collector`, `content-multi-distributor`, `media-article-extractor`,
`trending-radar`, `viewpoint-insight-miner`. All Implemented and referenced by
`06_Scheduler_and_Unattended_Skills.md`. `SKILL.md` `permissions` is now gated
before launch (DENY short-circuits before workspace creation, restricted-token
creation and child spawn), but it is still **not** an OS-level authorization
boundary.

### 6.1 Internal script layout (entrypoints unchanged)

Two shipped skills were split by the code-debt pass. The Skill Engine still
calls the same entrypoints, and CLI arguments, stdout JSON schema, exit codes,
fallbacks and network behaviour are unchanged. Only the private module layout
changed.

| File | Responsibility |
| --- | --- |
| `skills/trending-radar/scripts/radar.py` | CLI entrypoint + compatibility re-exports |
| `skills/trending-radar/scripts/_data.py` | User agent, fallback topics, platform constants |
| `skills/trending-radar/scripts/_fetchers.py` | Per-platform fetch functions, `PLATFORM_FETCHERS` |
| `skills/trending-radar/scripts/_core.py` | Relevance scoring, `run_radar` orchestration |
| `skills/content-multi-distributor/scripts/distribute.py` | CLI entrypoint + compatibility re-exports |
| `skills/content-multi-distributor/scripts/_content.py` | Title/content cleaning, block parsing, key sentences, hashtags |
| `skills/content-multi-distributor/scripts/_markdown_links.py` | Markdown link / reference-definition parsing |
| `skills/content-multi-distributor/scripts/_references.py` | Footnote extraction, link-to-footnote replacement |
| `skills/content-multi-distributor/scripts/_formatters_xhs.py` | Xiaohongshu formatting, section illustrations; defines `clean_title_text` |
| `skills/content-multi-distributor/scripts/_formatters.py` | WeChat / Twitter / video formatting; defines `clean_title_text` and `extract_footnotes` |

The `_formatters.py` / `_formatters_xhs.py` helper import fix only restores
local formatting and preview; it does not mean any platform publish path is
implemented or verified against a live platform.

Splitting these files does **not** add any sandbox capability. Restricted-token
execution remains Partial; see `10_Sandbox_and_Permission_Model.md`.

## 7. Frontend — `frontend/src/` (22 components + API layer)

Components: workbench, creation history, topic input, outline/draft selection,
draft editor, DNA result, viewpoint review, feedback modal, cognitive profile,
timeline, chat lounge, daily briefing, model settings + model selector pill,
benchmark accounts, benchmark deconstruct, persona extraction, product
extraction, material vault, multi-platform distribute, private-domain hub.

Status: **all Implemented and wired to the API.** None are described in the v0.1
PRD/Roadmap. Ownership doc: `docs/design/07_Surfaces_and_Engagement.md`
(also covers `services/api/*`, i18n and renderer utils).

API layer: `frontend/src/services/*` is the single place where request headers are
chosen. Notably `frontend/src/services/modelSettings.ts` sends the model BYOK key
in `X-Model-Api-Key` and falls back to `X-Api-Key` / `Authorization`, matching the
backend resolution order `payload.api_key` -> `X-Model-Api-Key` -> `X-Api-Key`.
Auth headers must be present on every private call; a client-supplied `user_id`
in a payload is never an authorization input.

## 8. V0.1 docs vs. code — summary of gaps

| Area | v0.1 docs | Code |
| --- | --- | --- |
| Scheduler | absent | Implemented |
| Viral analysis | absent | Partial (API), Implemented (service) |
| Multi-platform distribution | absent | Implemented |
| Material vault / Obsidian | absent | Implemented (authenticated API ownership); Partial (server-wide Vault roots, misleading sync name, global status count) |
| Chat lounge / Cognitive Twin | absent | Implemented |
| Images | absent | Implemented (authenticated API); Partial (per-user ownership / persistence) |
| Private domain | absent | Implemented |
| Product vault | absent | Implemented |
| Persona extraction / DNA 2.0 | absent | Implemented |
| Memory service | absent | Implemented |
| Skill engine + sandbox | absent | Implemented (partial isolation) |
| Credential security / SSRF / quota | absent | Partial (ownership helpers and SSRF guard exist; auth/ownership coverage and global outbound enforcement incomplete) |
| DB read-only engine | absent | Implemented (agent read path only) |

## 9. Known partial / incomplete items (honest list)

1. Sandbox isolation is **partial**: a real restricted token plus a Job Object
   plus a scoped per-workspace NTFS allow ACE set (written and verified when
   `acl_mode=enforce`; best-effort rollback on cleanup). Still no sandbox
   account, no enforced deny ACEs on parent directories, and no OS-level
   network boundary (planning only); `wsb` still fails closed. Full truth:
   `10_Sandbox_and_Permission_Model.md`.
2. DB read-only covers the Outline/Draft agent **read path** only; Draft
   archival and the Diff/DNA evolution flow still use writable sessions.
3. Viral `style_fingerprint` **is** consumed by `draft_agent.py` both when the
   user explicitly selects an owned analysis via `viral_analysis_id` and, when no
   id is given, when `StyleSelectionService` auto-selects an owned record scoring
   at or above the `0.35` threshold; below threshold Draft falls back to
   Persona/DNA (**Implemented**). Remaining gap: style-recognition accuracy has
   not been measured.
4. `hook_strength` / `tension_level` / `reuse_score` share an explicit,
   evidence-driven 0-5 rubric (`backend/app/engine/rubrics/viral_rubric.py`)
   injected into the prompt, which removes the worst scoring ambiguity
   (**Implemented**). A 43-sample human-annotated benchmark
   (`rubrics/data/viral_rubric_benchmark_v1.json`) and a deterministic
   evaluator (`rubrics/viral_benchmark.py`) now measure agreement per
   dimension: accuracy 1.000, MAE 0.070, exact match 0.930 for all three
   dimensions, all passing the MAE <= 0.8 / exact match >= 60% gate. This
   measures **rubric-rule fidelity, not real-model accuracy**: there is no LLM
   replay, a single annotator with no inter-annotator agreement, no
   cross-model or cross-topic validation, and the human feature labels share the
   evaluator vocabulary (circular calibration). Real semantic scoring accuracy
   therefore remains **Partial**. See design doc 03 section 10.
4. `viral_analysis.py` API is thin; the semantic engine is the substance.
5. Schema is created with `SQLModel.metadata.create_all` — no migration
   history, so added columns are not applied to existing databases.
6. Frontend has no test suite and no router/store.
7. `AGENTS.md` previously pointed at `08_Architecture_and_Modules.md` as the
   architecture source of truth — now marked legacy (see governance doc).
8. Error/info-disclosure hardening is **partial**: the shared error contract
   (`core/errors.py`, `core/request_id.py`) and the application-level handlers
   are in place, and the audited private routers (chat lounge, materials,
   Obsidian, private domain, scheduler, settings/BYOK) no longer authorize on a
   client-supplied `user_id`. Skill sandboxing is still Partial.

## 10. API authentication boundary - Implemented

Authentication is now declared once, at the aggregation layer, instead of per
handler:

- `backend/app/api/auth_boundary.py` provides `create_private_router()` (which
  injects `Depends(get_current_user)`), `create_public_router()`, and the
  explicit anonymous allowlist `PUBLIC_ENDPOINTS`.
- `backend/app/api/__init__.py` builds `api_router` with
  `create_private_router(prefix="/api")` and mounts every business router below
  it, so a **new handler is authenticated by default**.
- Anonymous endpoints live in a separate public aggregate
  (`public_endpoints_router`). The only approved one is
  `GET /api/private-domain/templates` (static reference data: reads no user
  record, invokes no engine).
- Newly authenticated in this batch: `POST /api/images/generate`,
  `GET /api/images/proxy`, `POST /api/images/test-connection`,
  `GET /api/dna/skills`, `POST /api/drafts/distribute`. The image SSRF guard
  (base-URL allowlist, per-hop redirect checks, size and content-type limits) is
  unchanged.

Local gates (no CI wired yet):

```powershell
python scripts/check_api_auth.py             # static + runtime surface check
python scripts/check_api_auth.py --base main # api changes without gate change
python -m pytest backend/tests/test_api_auth_surface.py -q
```

Still not done (do not overstate):

- Per-user ownership for generated images. Note: the image provider config is a
  server-side global setting, not per-user state, so this is not a scheduler-style
  isolation gap.
- The background loop's `DEFAULT_SCOPE` scheduler configuration is still
  process-level only (it belongs to no user row, so it is intentionally not
  persisted). Per-user scheduler settings / dismissed date / quota decision /
  last summary are DB-backed in `scheduler_user_states`.
- `skills/*` `permissions` metadata is enforced as a **pre-launch gate** by the
  runner (a `DENY` decision blocks the launch), but it is not an OS-level
  authorisation boundary.
- Windows sandbox remains Partial: the Job Object is implemented on the
  restricted-token path, while sandbox account, NTFS ACL and OS network
  boundary are planning layers only; `wsb` fails closed.

## 11. Code-quality governance (not a product feature, still inventory-relevant)

| Item | Purpose | Status | Design document |
| --- | --- | --- | --- |
| `docs/architecture/09_Coding_Standards.md` | Single authoritative coding standard: naming (Python / TS / Vue), layering, error handling, secret-safe logging, file size, prompt placement, test/uv/Git rules | Implemented | `docs/architecture/09_Coding_Standards.md` |
| `scripts/check_code_style.py` + `scripts/code_style/` | Executable gate for naming, bare `except:`, prompt placement and file-size limits | Implemented | 09, 13 |
| `scripts/code_style_baseline.txt` | Frozen legacy file-size ceilings; ratcheting only (may shrink, never grow) | Implemented | 09 |
| `backend/tests/test_code_style.py` | Regression tests for the checker and the baseline ratchet | Implemented | 09 |
| Git hooks (`pre-commit` staged style, `commit-msg` doc coverage, `post-merge` soft doc coverage) | Local enforcement, shared across every worktree via `git rev-parse --git-common-dir` | Implemented (local only) | 13 |
| CI enforcement | Not wired | Not implemented | 13 |

Rules that bind feature work:

- New code must satisfy 09 without a baseline entry; `scripts/code_style_baseline.txt`
  is only for pre-existing debt, and any file that shrinks must lower its entry.
- A file over 300 lines (production) / 500 lines (tests) is a soft warning, over
  600 / 1000 is a blocking hard cap for new files. Current largest legacy files
  (`backend/app/services/memory_service.py`, `backend/app/core/skill_engine/acl_guard.py`,
  `backend/app/api/dna_v2.py`, `backend/app/services/inspection_scheduler_service.py`)
  are registered in the baseline and must shrink, not grow.
- Merge checklist additions live in `13_Documentation_Governance.md`; CI remains
  explicitly unimplemented, so gates are local-only by design.

## 11. Workflow permission & approval audit layer

Status: **Partial** (central layer implemented; historical call sites partially
migrated).

Implementation: the `backend/app/core/workflow_permissions/` package, split by
concern so no single module exceeds the file-size cap:

| Module | Responsibility |
| --- | --- |
| `workflow_permissions/vocabulary.py` | permission tokens, `WorkflowMode`, `RiskLevel`, `AuditDecision`, `WorkflowDenied` |
| `workflow_permissions/declarations.py` | `PermissionAction`, `ApprovalProvider` family |
| `workflow_permissions/audit.py` | `AuditRecord`, audit sinks, JSONL hash chain |
| `workflow_permissions/controller.py` | the allow / deny / approval decision engine |
| `workflow_permissions/results.py` | `AuthorizationResult`, `parse_pre_authorized` pre-authorization allowlist parsing |
| `workflow_permissions/registry.py` | process-wide catalogue of declared actions |
| `workflow_permissions/catalogue.py` | the declared high-risk actions of this repository |
| `workflow_permissions/__init__.py` | facade re-exporting the full public API |

Gate: `scripts/check_workflow_permissions.py`
Docs: `docs/architecture/10_Sandbox_and_Permission_Model.md` §8

**Implemented:**

- Central, extensible permission/action declaration layer. High-risk workflow
  actions declare required permissions and a risk level in one registry
  (`skill.execute`, `scheduler.unattended_run`, `image.remote_proxy`,
  `content.external_distribute`, `platform.crawl`,
  `credential.provider_sync`, `credential.export`, `vault.sensitive_file`,
  `upload.product_image`, `image.engine_connection_test`).
- Single authorisation entry point `require_authorization()`; approval and audit
  happen inside the controller so business code cannot bypass the audit trail.
- Three explicit modes: `interactive` (human present, approval provider
  required, deny-all by default), `pre_authorized` (allowlist hit passes),
  `unattended` (allowlist only, never prompts, out-of-scope denied).
- Fail-closed on unknown action / unknown mode / unknown permission /
  evaluator, approval-provider, or audit-sink failure.
- Approval audit records with who / what / when / decision / reason; in-memory
  and hash-chained JSONL sinks, plus `query_audit`.
- Scheduler integration: unattended runs are authorised and audited *before*
  `execute_skill_sync()`; denial prevents the skill from starting.
- Static AST gate flagging high-risk call sites whose function does not declare
  a workflow permission.

**Partial / not yet done (do not overstate):**

- Several historical high-risk call sites (image/material API handlers,
  `cognitive_engine`, `credential_service`, `material_service`,
  `memory_service`, `platform_crawler_service`) are recorded in the gate's
  `KNOWN_UNDECLARED_BASELINE` and are **not yet** gated. The baseline keeps the
  gate green while migration proceeds; it is not a security control.
- JSONL hash chain detects tampering after the fact; it is not WORM storage. The
  sink lock is process-local only.
- `ApprovalProvider` has no real identity / multi-sig / signature verification.
- Registry is process-local; no API/UI to query audit records; no schema
  migration.
- Workflow audit records are not unified with the Skill Engine ACL journal.