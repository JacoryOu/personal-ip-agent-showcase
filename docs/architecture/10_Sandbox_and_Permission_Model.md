# Sandbox & Permission Model (Windows)

Status: **current architecture reference**. Last verified against code at `main@4d643ad`.

This document is the authoritative description of how the Skill Engine isolates
skill execution today, what it explicitly does *not* isolate, and the planned
hardening phases. Code paths are named so a reader can verify every claim.

## 1. Scope

Applies to any skill executed through
`backend/app/core/skill_engine/manager.py::SkillManager.execute_skill`, i.e.
interactive workbench runs and unattended scheduler runs.

## 2. Layers that exist today

| Layer | File | What it really does |
| --- | --- | --- |
| Permission declaration | `skill_engine/discovery.py` | Parses `SKILL.md` front matter (`name`, `description`, `entrypoint`, `permissions`). **Parsing is not enforcement** — see §3. |
| Policy gate | `skill_engine/policy.py` | Compares declared permissions against a configured allow/deny scope; resolves network policy and per-context capability sets. It *evaluates* the declaration; it does not by itself revoke OS authority. |
| Environment sanitisation | `skill_engine/windows_sandbox.py` | Strips sensitive env vars (patterns: `KEY`, `SECRET`, `TOKEN`, `PASSWORD`, `CREDENTIAL`, `AUTH`, `DATABASE_URL`, `POSTGRES`, `REDIS`, `AWS`, `OPENAI`, `ANTHROPIC`, `DEEPSEEK`, …) before spawning. |
| Process token | `skill_engine/restricted_token.py` | Real `CreateRestrictedToken(DISABLE_MAX_PRIVILEGE)` + `CreateProcessAsUserW`. Verified via `TokenIsRestricted` and deny-only restricting SIDs. |
| Network egress guard | `skill_engine/network_guard.py` | Installs an import hook (`sitecustomize`-style) that blocks non-allowlisted socket destinations **inside the Python child process**. |
| Truthful reporting | `skill_engine/windows_sandbox.py::SandboxExecutionResult` | Reports `requested_runner_mode`, `runner_mode`, `sandbox_enforced`, `warnings`. |
| Non-skill path guards | `core/net_guard.py`, `core/vault_path_guard.py` | SSRF checks and vault path confinement for API-level requests. |
| Server-side egress boundary | `core/net_guard.py` | The **single** server-side outbound HTTP path. Every in-process service that fetches a caller- or config-supplied URL goes through `safe_fetch` / `assert_url_allowed`; no parallel HTTP client is permitted. See §7. |

`restricted_token` cannot filter network traffic, so network control is layered as
policy declaration + child-process egress guard. Neither is OS-level.

## 3. Honest status table

| Capability | Status | Note |
| --- | --- | --- |
| Restricted token (privileges disabled, deny-only SIDs) | **Implemented** | `restricted_token.py`; tests in `backend/tests/test_restricted_token.py`. |
| Fail-closed degradation | **Implemented** | restricted-token failure → `restricted_token_unavailable`, `success=False`; `wsb` → `wsb_unsupported`; unknown mode → denied. |
| Env var scrubbing | **Implemented** | Pattern-based denylist. |
| Python-level egress guard | **Implemented** | Not kernel-enforced. |
| Permission policy gate incl. `UNATTENDED` | **Implemented (policy evaluation only)** | Unattended runs are gated by two independent env switches (see §5). The declaration is still not an OS authorisation boundary — see the row below. |
| Declared `permissions` enforced before launch | **Implemented (execution gate only)** | `windows_sandbox.py` evaluates the policy **before** creating the workspace, the restricted token or the child process; a `DENY` decision returns `success=False` with the denied capabilities. Regression coverage: `backend/tests/test_sandbox_permission_gate.py`. |
| Declared `permissions` act as an OS authorisation boundary | **Not implemented** | The gate stops the *runner* from starting a skill that over-declares, but it does not revoke OS authority: once a process runs it still inherits current-user filesystem/network reach. Tracked in `12_Skill_Engine_Spec.md` §7. |
| DB read-only session for agent read path | **Implemented (partial scope)** | See §6. |
| Vault traversal containment (no symlink/junction escape) | **Implemented** | `iter_safe_markdown_files()` in `vault_path_guard.py`; see §6a. |
| Skill entrypoint containment | **Implemented** | `resolve_entrypoint_path()` in `skill_engine/discovery.py`; see §6b. |
| Dedicated sandbox account | **Partial (declaration only)** | `sandbox_profile.py` accepts an account name / SID and refuses to pretend it was created. No account is provisioned and no stable per-skill token is derived; the token is still derived from the current user. |
| Scoped NTFS ACL per execution workspace | **Partial (real write, scoped only)** | `acl_guard.py` computes an ACE plan and, in `enforce` mode, really writes scoped allow ACEs via `SetNamedSecurityInfoW`, then verifies by read-back; verification failure fails closed and no child process is started. Default posture stays `dry_run` (plan only). `AclPlan.enforced` is `True` only after a verified apply. Best-effort rollback runs in the runner's `finally` block. Still not a container: no deny ACE on parent directories is enforced, the host account's own access is not removed, and a hard kill of the runner can leave ACEs behind. |
| OS-level network boundary | **Partial (planning only, dry-run)** | `os_network_boundary.py` plans Windows Firewall rules (`disabled` / `dry_run` / `enforce`); `enforce` returns a blocking error. No firewall rule is created, modified or deleted. `NetworkBoundaryPlan.enforced` is always `False`. |
| Unified server-side egress boundary (`core/net_guard.py`) | **Implemented (partial scope)** | Single entry point for server-side outbound fetches, with scheme / credential / host / DNS-range / port / redirect checks. In-process and cooperative only — see §7. |
| Job Object / child-process containment | **Implemented** | `job_object.py`; enabled by default on the restricted-token path. `KILL_ON_JOB_CLOSE`, no `BREAKAWAY_OK`; assignment failure terminates the just-created child and fails closed (no un-contained fallback); timeout calls `TerminateJobObject` to kill the whole tree. Reported separately as `job_object_enforced`. |
| AppContainer | **Not implemented, out of scope** | Deliberately not adopted. |
| Windows Sandbox (`.wsb`) | **Not implemented** | Profile generation only; `WindowsSandbox.exe` is never launched. |
| Per-skill dynamic firewall rules | **Not implemented, out of scope** | Deliberately not adopted. |

## 4. What the restricted token guarantees — and what it does not

Guarantees:
- All privileges disabled (`DISABLE_MAX_PRIVILEGE`).
- Restricting SID list present; its SIDs are deny-only (typically Administrators).
- Child is genuinely created under that token via `CreateProcessAsUserW`.

Does **not** guarantee:
- Filesystem confinement (no ACL, no per-skill VFS).
  The only filesystem guarantees are the explicit path-containment checks
  in §6a and §6b — a skill still inherits current-user read/write reach
  over the rest of the disk.
- Network isolation.
- Registry / clipboard / COM isolation.
- Descendant process containment is now provided by the Job Object on the restricted-token path only; other runner modes still have no containment.
- Virtualisation (`.wsb`).

## 5. Unattended (scheduler) policy

`ExecutionContext.UNATTENDED` represents batch/scheduled runs where no human can
answer a prompt. Two independent env switches gate it; both default to deny:

- `COG_SKILL_NETWORK_ALLOW_UNATTENDED` — network egress budget (also
  `NetworkPolicy.allow_unattended`).
- `COG_SKILL_UNATTENDED_ALLOW_PERMISSIONS` — the capability allowlist a
  scheduled job may use.

Any capability not in the pre-authorised unattended scope is denied; the caller
degrades. See `backend/tests/test_skill_permission_policy.py`.

## 6. Database isolation scope (read-only engine)

`backend/app/core/db.py` provides `get_readonly_session()` alongside the writable
`get_session()`. Read-only status is driver-enforced:
- SQLite: URI `file:<abs>?mode=ro&uri=true` plus `PRAGMA query_only=ON`.
- PostgreSQL: `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY` and
  `default_transaction_read_only = on`.
- Unsupported backends / `:memory:` fail closed (`UnsupportedReadOnlyBackendError`).

Scope of read-only:
- Outline/Draft agents’ input-context assembly (IP bundle, DNA, profile, memory
  retrieval) via `CognitiveService.get_*_readonly` and the `MemoryService`
  `*_readonly` entry points. The read-only memory implementations now live in
  `backend/app/services/memory_readonly.py` (`retrieve_relevant_stories_readonly`
  and siblings) and `backend/app/services/memory_dna_retrieval.py`
  (`hybrid_retrieve_dna_readonly`); `backend/app/services/memory_service.py`
  remains the stable facade and keeps the public class surface unchanged.
  **Implemented**: each read-only entry point requires an explicit session
  argument, never falls back to the writable engine, never creates a default
  user, and never commits. Overall DB read-only scope stays **Partial scope**
  (agent read path only).

Intentionally writable:
- Draft archive persistence, and the Diff/DNA evolution flow (writes draft, DNA,
  profile records).

So the whole Draft workflow is not read-only — only the agent-facing read path is
physically isolated. `get_readonly_session()` is a FastAPI dependency and must be
injected wherever read-only isolation is intended. Coverage:
`backend/tests/test_agent_db_readonly.py`.

## 6z. Error and information-disclosure boundary

Status: **Implemented for the audited private routers; the global boundary is still Partial.**

Code: `backend/app/core/errors.py`, `backend/app/core/request_id.py`,
application handlers in `backend/app/main.py`.

### What is enforced today

- One response shape for failures:
  `{"error": {"code", "message", "request_id"}, "detail"}`. The legacy
  `detail` key is kept so existing frontend code keeps working; it carries the
  same safe message, never the raw exception.
- `AppError` is the intended way for application code to raise a failure with
  a stable public code: `AUTH_REQUIRED`, `FORBIDDEN`, `NOT_FOUND`,
  `VALIDATION_ERROR`, `CONFLICT`, `DEPENDENCY_FAILURE`, `INTERNAL_ERROR`.
- 5xx never returns internal detail. A `HTTPException` with a 5xx status has
  its `detail` replaced by `Internal server error.`; an unhandled exception is
  converted to `INTERNAL_ERROR`. Tracebacks, DB errors, SDK errors, file paths
  and request payloads are written to the server log only.
- `RequestValidationError` no longer echoes the submitted payload back to the
  caller.
- `RequestIdMiddleware` accepts an inbound `X-Request-ID` only when it matches
  `^[A-Za-z0-9._-]{1,64}$`; otherwise a UUID hex value is generated. The value
  is stored on `request.state.request_id`, echoed on the response, and used to
  correlate logs. `error_response()` writes the header itself and does not trust
  a caller-supplied header, so the header is present even when an application
  handler converts an unhandled exception.
- Private routers audited on this branch resolve the acting user from the
  credential via `Depends(get_current_user)`; a `user_id` in the body or query
  is ignored for authorization.
- Object ownership is checked (Material, Persona/Product, Chat Lounge session,
  platform credential/account). A cross-user record, a missing record, and a
  malformed UUID all return the same redacted `404`, so existence is not
  disclosed. Chat Lounge does not echo the session id.
- Settings/BYOK endpoint URLs pass through `core/net_guard.py`, which also
  rejects the carrier-grade NAT (`100.64.0.0/10`), IETF protocol assignments
  (`192.0.0.0/24`) and benchmarking (`198.18.0.0/15`) ranges. Rejections use a
  fixed public message and never echo the configured address.
- The application identity header (`Authorization` / `X-Api-Key`) is distinct
  from the model BYOK header (`X-Model-Api-Key`); BYOK resolution order is
  `payload.api_key` -> `X-Model-Api-Key` -> `X-Api-Key`.

### What is NOT yet enforced

- There is still **no global authentication dependency**. `Depends(get_current_user)`
  is applied per handler, so a newly added handler can forget it. This remains
  the main residual risk and is why the app-level coverage is still Partial.
- `/api/images/*` is still unauthenticated.
- Scheduler per-user state is now DB-backed (see below). The remaining
  scheduler limitation is the process-level `DEFAULT_SCOPE` configuration
  used by the background loop, which is intentionally not persisted.
### 5a. Scheduler per-user state (DB-backed)

Four pieces of per-user scheduler state - settings, dismissed briefing date,
last quota decision, and last execution summary - are persisted in the
`scheduler_user_states` table (one row per user,
`backend/app/models/scheduler_state.py`), keyed by the authenticated user UUID.

Consequences:

- State survives a process restart and is consistent across workers.
- A malformed or absent user id never creates a row: the write path refuses
  any id that is not a real UUID, so no arbitrary user's state can be
  fabricated or overwritten.
- The background scheduler loop has no acting user and keeps using the
  process-level `DEFAULT_SCOPE` configuration, which stays in memory and is
  deliberately never written to the database (there is no `users` row to
  attach it to).

Regression coverage: `backend/tests/test_scheduler_state_persistence.py`.

## 6a. Vault traversal containment

The Obsidian bridge must never read Markdown from outside the user-approved vault.
`Path.rglob("*.md")` does not provide that guarantee on Windows, because it
follows reparse points: a junction planted inside the vault makes the walk
descend into an arbitrary directory outside it, and the scan then returns that
file's excerpt to the client (and inflates the vault note count reported by the
status endpoint).

`backend/app/core/vault_path_guard.py` therefore exposes
`iter_safe_markdown_files(vault_root)`, which is used by both call sites in
`backend/app/services/obsidian_service.py` (scan preview and status count).
It guarantees:

- **No link traversal.** The walk does not follow symlinks, directory
  junctions, or any other reparse point. A directory entry is skipped when
  `os.path.islink()` is true, or when its `st_file_attributes` carries
  `FILE_ATTRIBUTE_REPARSE_POINT` (or `FILE_ATTRIBUTE_DEVICE`).
- **Second-chance containment.** Every Markdown candidate is re-`resolve()`d and
  must satisfy `relative_to(vault_root_resolved)`. This catches escapes that the
  walk itself would not have flagged, e.g. a file symlink placed directly inside
  the vault.
- **Fail-quiet on unresolvable paths.** `resolve()` can raise (`OSError` for
  permission errors, `RuntimeError` for symlink loops). Such candidates are
  skipped rather than raising, so one hostile or broken link cannot fail the
  whole scan.
- **Stable ordering.** Results are sorted, so the scan preview stays
  deterministic.

Candidates that fail any check are dropped silently; they are never reported as
vault content. This is a *containment* guarantee, not a secrecy guarantee — it
says "these bytes are inside the approved vault", not "these bytes are safe".

## 6b. Skill entrypoint containment

A skill's `entrypoint` comes from `SKILL.md` YAML front matter, which is
untrusted repository-supplied content. It decides *which file the sandbox
executes*, and the restricted token does **not** restrict that choice — dropping
privileges and choosing an arbitrary script are independent problems. Containment
is therefore enforced separately, before any process is created.

`resolve_entrypoint_path(entrypoint, skill_dir)` in
`backend/app/core/skill_engine/discovery.py` returns a checked absolute path and
raises `SkillDefinitionError` (fail closed, no silent fallback) when:

- the skill directory cannot be resolved;
- the entrypoint cannot be resolved (`OSError` / `RuntimeError`, e.g. a symlink
  loop);
- the resolved path is not inside the resolved skill directory. This rejects
  `../../evil.py` traversal and absolute paths pointing elsewhere. An absolute
  path is *not* rejected by shape — it is accepted only when it genuinely
  resolves inside the skill directory;
- the resolved path is a directory.

The validated absolute path is what `windows_sandbox.py` passes to
`CreateProcessAsUserW`. Definitions that fail the check are not registered by
`parse_skill_markdown()`, and the runner additionally fails closed if it is ever
handed such a definition — so an unsafe entrypoint never reaches process
creation through either path.

A missing (non-existent) entrypoint file is not rejected by the resolver: the
runner's existing existence check fails closed on it without spawning anything.

## 7. Planned hardening (phases)

### Phase A — recommended (sandbox account + ACL layering)

**Status: Partial.** The policy/planning layer now exists; the privileged
enforcement does not. Nothing here elevates automatically.

1. Create a dedicated local account, e.g. `PiipSandboxRunner`, used solely as the
   restricted-token principal. — **Not implemented** (`sandbox_profile.py`
   only records the account name / SID).
2. Apply minimal NTFS ACLs:
   - workspace: write allowed for the runner account;
   - `.env`, credential vaults: no read;
   - database files: read-only;
   - temp/scratch dir: write.
   — **Partial**: `acl_guard.py` writes a **scoped allow ACE set on the
   per-execution workspace** in `enforce` mode and verifies it by read-back;
   verification failure fails closed. Rollback is best-effort on the normal
   cleanup path. The deny half of the plan (`.env` / vault / DB deny ACEs on
   parent directories) is still computed but **not** written.
3. Change the restricted-token principal from the current user to the runner
   account. — **Not implemented**.
4. Runner start-up validates the ACLs; mismatch → **fail closed**.
   — **Implemented for the scoped allow set**: the profile accepts
   `acl_mode=enforce` (it is no longer a blocking error), the runner applies
   the plan before spawning the child, and an ACL-plan or read-back failure
   aborts before the child process is started.

Rationale: a restricted token alone cannot remove the current user’s ambient
rights. A dedicated principal + ACL is what actually confines the filesystem.

### Phase B — deferred

- Separate online/offline runner accounts.
- Stable Windows Firewall rules for the runner account. (Planning only today — see §3.)
- Real `.wsb` virtualisation.

### Explicitly not doing

- AppContainer / package identity.
- Per-skill dynamic creation/deletion of firewall rules (adds admin-level risk
  without proportional gain).

Rationale for the deferrals: the restricted token + dedicated account + ACL gives
the substantive confinement we need; AppContainer and dynamic firewall churn add
complexity and admin fragility. Dynamic firewall rules per skill are rejected
because they require elevation and are easy to leave in an inconsistent state.

## 8. Rollout & verification

- Phase A planning layers ship default-off and default-dry-run; every
  administrator-level operation is explicit opt-in and fails closed without
  elevation.
- Acceptance (still open): a skill that attempts to read `.env` or write outside
  the workspace fails; a skill inside the workspace succeeds; ACL mismatch aborts
  the run.
- Tests present: `test_acl_guard.py`, `test_os_network_boundary.py`,
  `test_sandbox_profile.py`. Still to add once enforcement exists: real ACL
  validation, runner-account token creation, egress bypass attempts via
  non-Python children.

## 7. Server-side egress boundary (`core/net_guard.py`)

`core/net_guard.py` is the one place the backend is allowed to make an
outbound HTTP request whose URL came from outside the code. Callers must use
`safe_fetch()` (or `assert_url_allowed()` for validation only); constructing a
raw `httpx.AsyncClient` for a caller-supplied URL is a regression.

### 7.1 What is enforced

| Check | Rule |
| --- | --- |
| Scheme | `http` / `https` only. `file://`, `gopher://`, `data:` etc. are rejected. |
| Embedded credentials | `user:pass@host` is rejected outright. |
| Host allowlist | Optional. When non-empty, the host must match exactly or on a dotted label suffix. |
| Numeric IP spellings | Bare integer / octal / hex forms (`http://2130706433/`, `http://0x7f.1/`) are rejected as ambiguous, even when they would resolve to a valid address. |
| Metadata endpoints | Explicit host denylist (`169.254.169.254`, `metadata.google.internal`, `metadata.goog`, `100.100.100.200`, `metadata.azure.com`) plus blocked suffixes `.localhost` / `.local` / `.internal` when no host allowlist is configured. |
| DNS-resolved ranges | **Every** address the host resolves to is checked: loopback, private, link-local, multicast, reserved, unspecified, IPv4-mapped, 6to4, Teredo, IPv6 ULA (`fc00::/7`), and site-local. Literal IPs are checked directly. |
| **Port allowlist** | Only ports in `OutboundPolicy.allowed_ports`. Default is **443 only**. An omitted port falls back to the scheme default (443/80) and must itself be allowlisted, so `http://host/...` is denied under the default policy. Plain http/80 must be opted into explicitly. |
| Redirects | Followed manually, one hop at a time, capped by `max_redirects`. **Every hop is re-validated by the same function**, so a redirect cannot escape the scheme, credential, host, DNS-range or port policy. |
| Timeouts / body size | Connect+read timeout and a streaming response byte cap are always applied; oversized bodies are abandoned mid-stream rather than buffered first. |

### 7.2 Redirect policy: strict re-validation

The chosen strategy is **strict re-validation, not outright redirect denial**.
`safe_fetch` sets `follow_redirects=False` and walks the chain itself, calling
`assert_url_allowed` on each hop. This is deliberately not equivalent to
"following redirects": a `Location` header resolving to `169.254.169.254`, to
`10.0.0.0/8`, to a non-allowlisted port, or to `file://` is rejected exactly as
if the caller had supplied it directly.

**Known residual gap (not fully closed):** because re-resolution happens per
hop, a hostname whose DNS answer *flips between the validation lookup and the
actual connection* can still be mis-pinned. The guard re-resolves and rejects a
rebound answer on the next hop (covered by
`test_rebind_to_private_address_is_rejected`), but it does **not** pin the
validated IP for the socket connect. Closing that requires connecting to the
already-validated address with SNI/Host preserved, which is **not implemented**.

### 7.3 Who uses it

- `services/image_service.py` — the native Agnes image-generation POST. It no
  longer creates its own `httpx.AsyncClient`; it calls `safe_fetch` with
  `build_image_outbound_policy()`, which pins ports to 443 and derives its host
  allowlist from `settings.IMAGE_ALLOWED_BASE_URL_HOSTS`.
- The image-proxy API endpoint.

### 7.4 What this is not

`net_guard` is an **in-process, cooperative guard**, not a kernel boundary. It
constrains code that goes through it. It does not constrain a skill's child
process (see the sandbox rows in §3), does not filter traffic at the socket
layer for other processes, and does not survive a code path that opens its own
socket. The OS-level network boundary remains **Not implemented** in §3.

## 9. Internal module layout of the sandbox stack (2026-10 refactor)

The sandbox implementation was split by responsibility. This is a **pure
internal refactor**: no behaviour, guarantee, fail-closed rule or public import
path changed. All previous names remain importable from their original modules,
so callers and tests that monkeypatch e.g. `windows_sandbox.SandboxConfig` or
`restricted_token.<symbol>` are unaffected.

| Module | Responsibility |
| --- | --- |
| `skill_engine/windows_sandbox.py` | Facade and runner orchestration: `WindowsSandboxRunner`, `run_skill`, and the workspace / policy / ACL / Job Object flow. |
| `skill_engine/sandbox_config.py` | Configuration and result data models (`SandboxConfig`, `SandboxExecutionResult`, env-var scrubbing patterns). |
| `skill_engine/sandbox_process.py` | Low-level child-process spawn helpers used by the runner. It does **not** own `run_skill`, `SkillDefinition` or `ExecutionContext`. |
| `skill_engine/restricted_token.py` | Re-export facade: `RestrictedTokenError`, `RestrictedTokenUnsupportedPlatform`, `RestrictedTokenInfo`, `TokenProcessResult`, `create_restricted_token`, `restricted_token_supported`, `run_process_with_restricted_token`, `DISABLE_MAX_PRIVILEGE`. |
| `skill_engine/restricted_token_winapi.py` | Win32 constants, ctypes structures and API bindings only. |
| `skill_engine/restricted_token_api.py` | Token creation and introspection (`CreateRestrictedToken`, `TokenIsRestricted`, deny-only restricting-SID verification). |
| `skill_engine/restricted_token_process.py` | Child launch under the restricted token plus Job Object assignment and result reporting. |
| `skill_engine/acl_guard.py` | Re-export facade: `AclEntry`, `AclPlan`, `AclPlanError`, `AclRollbackHandle`, `SidHandle`, `build_acl_plan`, `get_acl_api`, `resolve_acl_target`, `rights_to_mask`. |
| `skill_engine/acl_types.py` | ACL data types, SID / right constants and ACE mask conversion. |
| `skill_engine/acl_guard_winapi_bindings.py` | ctypes bindings and the installable API surface used by the ACL layer. |
| `skill_engine/acl_guard_winapi_ace.py` | ACE construction and read-back verification helpers. |
| `skill_engine/acl_guard_winapi.py` | `SetNamedSecurityInfoW` apply plus rollback orchestration. |
| `skill_engine/job_object.py` | Job Object creation, `KILL_ON_JOB_CLOSE`, assignment, `TerminateJobObject`. |
| `skill_engine/os_network_boundary.py` | Windows Firewall **plan** builder only. It never writes firewall rules; `enforce` still fails closed. |
| `skill_engine/sandbox_profile.py` | Declares the sandbox account / SID; no account is provisioned. |

The status values in section 3 and section 4 are unchanged by this split. In
particular the split does **not** imply AppContainer support, a per-skill virtual
filesystem, an applied OS network boundary, or `WindowsSandbox.exe`
virtualization.

Regression coverage: `backend/tests/test_acl_guard.py`,
`backend/tests/test_restricted_token.py`,
`backend/tests/test_sandbox_mode_transparency.py`,
`backend/tests/test_sandbox_acl_integration.py`,
`backend/tests/test_sandbox_permission_gate.py`.

## 10. Workflow Permission & Approval Audit Layer

Status: **Implemented (partial coverage)** — added in this branch on top of the
existing auth boundary and Skill policy gate. This layer is deliberately *upstream*
of the Skill Engine: it answers "is this workflow action authorised, by whom, and
was it audited?", whereas the Skill policy answers "does this skill's declaration
match policy?".

Implementation: the `backend/app/core/workflow_permissions/` package
(split by concern: `vocabulary`, `declarations`, `audit`, `controller`,
`registry`, `catalogue`). `app.core.workflow_permissions` re-exports the full
public API, so `from app.core.workflow_permissions import ...` is unchanged.
Static gate: `scripts/check_workflow_permissions.py`

### 10.1 What it provides

- A centralised, extensible **action catalogue**. Each entry declares the
  permissions it needs and its risk level. Registered actions include
  `skill.execute`, `scheduler.unattended_run`, `image.remote_proxy`,
  `content.external_distribute`, `platform.crawl`, `credential.provider_sync`,
  `credential.export`, `vault.sensitive_file`, `upload.product_image`,
  `image.engine_connection_test`.
- A single authorisation entry point `require_authorization(...)` returning
  `allow` or raising `WorkflowDenied`. The audit record is written by the
  controller itself, so business code cannot approve an action without an audit
  trail — there is no "skip the audit" flag.
- Three explicit execution modes with distinct behaviour:
  - `interactive` — a human is present; an `ApprovalProvider` must return
    `allow`. The default provider is deny-all.
  - `pre_authorized` — allowed immediately if the action is inside the
    pre-authorization allowlist; otherwise denied.
  - `unattended` — no human is present. Only the pre-authorization allowlist is
    honoured; anything outside it is denied. No interactive prompt is ever
    attempted.
- Workflow permissions are kept **separate** from Skill capabilities. The
  workflow token is *not* passed into the Skill policy evaluator; a
  `skill:exec` requirement is delegated to the existing
  `backend/app/core/skill_engine/policy.py`.

### 10.2 Fail-closed guarantees (Implemented)

The following all deny by default — there is no "unknown means allow" path:

- unknown / unregistered action,
- action whose declaration is downgraded or mismatched,
- unknown `WorkflowMode`,
- unknown permission string in a declaration,
- exception raised by the permission evaluator,
- exception raised by the `ApprovalProvider`,
- exception while writing the audit record.

### 10.3 Audit record (Implemented, integrity-checked only)

Each authorization attempt produces a record with **who / what / when /
decision / reason**:

- `actor_id`, `action`, timestamp, `decision` (`allow` / `deny`), `reason`.
- `InMemoryAuditSink` for tests and `JsonlAuditSink` for persistence. The JSONL
- sink uses a process-local lock plus `flush`+`fsync`, and chains each record via
  a hash so `verify_chain()` can detect tampering or truncation.

### 10.4 Scheduler integration (Implemented)

`inspection_scheduler_service.py` now gates the unattended run through the
workflow permission controller **before** `execute_skill_sync()` is called. A
denial returns early and the skill is never started. The scheduler therefore has
three independent gates: quota/business budget → workflow permission + audit →
the existing Skill permission policy.

### 10.5 Static gate (Implemented, partial coverage)

`scripts/check_workflow_permissions.py` performs an AST scan of `backend/app`
and flags high-risk call sites (skill execution, `httpx`/`requests` egress,
publish, crawl, credential export/sync, sensitive vault paths) whose enclosing
function does not reference `require_authorization`,
`workflow_permission_guard`, or `declare_action`. Regression coverage:
`backend/tests/test_workflow_permission_gate.py`.

### 10.6 Honest limitations

**Partial:**

- **Historical high-risk call sites are not all migrated.** Several pre-existing
  files (API images/materials handlers, `cognitive_engine`,
  `credential_service`, `material_service`, `memory_service`,
  `platform_crawler_service`) still call high-risk operations without the
  workflow permission gate. They are recorded in a
  `KNOWN_UNDECLARED_BASELINE` inside the gate purely to keep it green and are
  **not** actually protected. The baseline is a migration tracker, not a
  security control.
- **Audit integrity is detection, not tamper-proofing.** The JSONL hash chain
  detects modification after the fact; it is not WORM storage. Anyone with write
  access to the sink can rewrite it, though the chain makes partial edits
  detectable.
- The sink lock is process-local; there is no cross-process / database
  transactional guarantee.
- `ApprovalProvider` is an interface only — no real identity, multi-signature, or
  signature verification is implemented.
- The action registry is process-local (no persistence, no dynamic registration
  from config).
- No API/UI surface exists to query audit records (query via `query_audit` in
  process only).
- No database / schema migration was performed.

**Not implemented:**

- WORM or distributed audit storage; signed approvals.
- Any new OS-level sandbox, sandbox account, NTFS ACL, or network boundary
  capability. This layer is purely an in-process authorisation + audit
  mechanism and adds nothing to §3's OS-isolation rows.
- Unification of workflow audit records with the Skill Engine ACL journal
  (`acl_guard` journal). The two records are stored independently and are not
  cross-referenced.

> Cross-branch note: this branch does **not** modify
> `backend/app/core/skill_engine/acl_guard.py` or any ACL-journal code.