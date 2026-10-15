# Skill Engine Specification

Status: **current**. Verified against `main@4d643ad`. Security boundary details
live in `10_Sandbox_and_Permission_Model.md`; this file specifies behaviour and
acceptance criteria.

## 1. Purpose

The Skill Engine lets the system discover and execute external skill packages
(a `SKILL.md` plus an entrypoint script) under a declared permission scope,
without granting them ambient authority.

## 2. Lifecycle

1. **Discovery** — `discovery.discover_skills()` scans a skills directory and
   parses each `SKILL.md` front matter into a `SkillDefinition`
   (`name`, `description`, `entrypoint`, `permissions`). The `entrypoint` is
   validated at parse time (see §2a); a definition that fails validation is
   logged and not registered.
2. **Registry** — `manager.SkillManager` caches the definitions and exposes
   `list_skills()`, `get_skill(name)`, `execute_skill()` (async) and
   `execute_skill_sync()`. `get_skill_manager()` returns the shared instance.
3. **Policy evaluation** — `policy.SkillPermissionPolicy` compares declared
   permissions against the configured allow/deny scope and network policy, per
   `ExecutionContext`.
4. **Execution** — `windows_sandbox` scrubs the environment, resolves the runner
   mode, and spawns the entrypoint. Outcome is reported truthfully. The path it
   spawns is the containment-checked absolute path from §2a, not a re-join of
   raw front matter.

## 2a. Entrypoint containment

`entrypoint` is read from `SKILL.md` YAML front matter, which is untrusted
repository content, and it determines *which file is executed*. The restricted
token lowers privileges but does not constrain that choice, so containment is
enforced independently by `resolve_entrypoint_path(entrypoint, skill_dir)` in
`backend/app/core/skill_engine/discovery.py`.

Rules (all violations **fail closed** with `SkillDefinitionError`):

| Case | Result |
| --- | --- |
| `run.py` (normal relative path) | Accepted, resolved to an absolute path. |
| `scripts/run.py` (nested, exists) | Accepted. |
| `../../evil.py` / `../evil.py` | **Rejected** — resolves outside the skill directory. |
| `C:\other\evil.py` (absolute, outside) | **Rejected** — resolves outside the skill directory. |
| Absolute path *inside* the skill directory | Accepted — the rule is containment, not "no drive letter". |
| A symlink inside the skill dir pointing outside | **Rejected** — the check runs on the resolved target. |
| Path resolves to a directory | **Rejected**. |
| Path cannot be resolved (`OSError` / `RuntimeError`, e.g. symlink loop) | **Rejected**. |
| Target does not exist | Not rejected here; the runner's existing existence check fails closed without spawning a process. |

The check is applied in two independent places, so neither alone is a single
point of failure:

1. `parse_skill_markdown()` validates on load — an unsafe definition is logged
   and never enters the registry.
2. `windows_sandbox.py` calls the same resolver via
   `SkillDefinition.entrypoint_path` immediately before execution and returns a
   structured failure (`success=False`, with a containment warning) instead of
   spawning anything.

The validated absolute path is what reaches `CreateProcessAsUserW`.

## 3. Permission model

Declared capabilities (constants in `policy.py`):
`network:read`, `network:write`, `filesystem:read`, `filesystem:write`,
`filesystem:isolated`, `exec`.

Contexts: `interactive` (a human can approve) and `unattended` (scheduler/batch).

Unattended gating — two independent switches, both deny-by-default:
- `COG_SKILL_NETWORK_ALLOW_UNATTENDED` — network egress budget.
- `COG_SKILL_UNATTENDED_ALLOW_PERMISSIONS` — capability allowlist for scheduled runs.

Anything outside the pre-authorised unattended scope is denied; the caller
degrades rather than prompting (nobody is present to answer).

## 4. Egress policy

`NetworkPolicy` resolves an allowlist of hosts (with a `*` wildcard option) and
`allow_unattended`. At run time `network_guard` installs an import hook in the
child Python process that blocks non-allowlisted socket destinations. This is
an **in-process guard**, not a kernel boundary; see the sandbox doc for the
planned OS-level phase.

Scope note: this child-process egress guard is **separate from**
`core/net_guard.py`. The skill engine's network policy is host-allowlist based
and has **no port allowlist**; `core/net_guard.py` is the server-side SSRF
boundary for in-process backend services and does not govern skill child
processes. Unifying the two — in particular giving skills a port allowlist and
the skill guard the same DNS-range checks — is **not implemented**. See
`10_Sandbox_and_Permission_Model.md` §3 and §7.

## 5. Execution modes

| Requested mode | Behaviour |
| --- | --- |
| `restricted_token` | Real restricted token + `CreateProcessAsUserW`, with a Job Object assigned by default; `sandbox_enforced=True` on success (token only), `job_object_enforced=True` when the Job was assigned. |
| `restricted_token` (failure) | **Fail closed** → `restricted_token_unavailable`, `success=False`. Not run as plain subprocess. |
| `wsb` | **Fail closed** → `wsb_unsupported`. `WindowsSandbox.exe` never launched. |
| `sanitized_subprocess` | Plain subprocess, inherits caller token, `sandbox_enforced=False`. |
| unknown | Denied. |

`SandboxExecutionResult` always distinguishes `requested_runner_mode` from the
applied `runner_mode`, plus `sandbox_enforced` and human-readable `warnings`.

## 6. Acceptance criteria (current)

- [x] `SKILL.md` permissions are **parsed** and evaluated by `policy.py`.
- [x] `SKILL.md` permissions are enforced as a **pre-launch gate**:
      `windows_sandbox.py` evaluates the policy before creating the workspace,
      the restricted token or the child process, and a `DENY` decision returns
      `success=False` with the denied capabilities
      (`backend/tests/test_sandbox_permission_gate.py`).
- [ ] `SKILL.md` permissions are an **OS-level authorisation boundary** at run
      time. The gate stops the *runner* from starting an over-declaring skill, but
      it does not revoke OS authority from a process that is already running. Do
      not read the checkbox above as full enforcement. (See section 7 and
      `10_Sandbox_and_Permission_Model.md`.)
- [x] Unattended runs cannot exceed the pre-authorised scope **as configured in
      code/environment** — i.e. the two `COG_SKILL_*` switches deny by default.
- [x] Restricted-token mode fails closed on error.
- [x] Sensitive env vars stripped from the child environment.
- [x] Execution result reports requested vs. applied mode honestly.

## 7. Open gaps (planned, not implemented)

- [x] Job Object bounding descendant processes — **Implemented** on the
      restricted-token path (`job_object.py`): `KILL_ON_JOB_CLOSE`, no
      `BREAKAWAY_OK`, assignment failure terminates the just-created child and
      fails closed (no un-contained fallback), timeout calls
      `TerminateJobObject` to kill the whole tree.
- [ ] Dedicated sandbox account as the restricted-token principal —
      **Partial**: `sandbox_profile.py` records the account name / SID only; no
      account is created and no stable per-skill token is derived.
- [x] Scoped NTFS ACL enforcement on the per-execution workspace
      (`.env`/vault/DB deny ACEs) — **Partial**: `acl_guard.py` really writes
      the scoped allow ACE set on the execution workspace via
      `SetNamedSecurityInfoW` in `enforce` mode, verifies it by read-back and
      fails closed if verification fails or no child is started. Default posture
      is `dry_run`. Best-effort rollback runs on the normal cleanup path. Still
      no deny ACE written on parent directories, no sandbox account, and a hard
      kill of the runner can leave ACEs behind.
- [ ] OS-level network boundary for the runner account — **Partial**:
      `os_network_boundary.py` plans Windows Firewall rules; `enforce` yields a
      blocking error and no rule is ever created, modified or deleted.
- [ ] Make the declared `permissions` list authoritative at the OS level, so a
      running skill cannot obtain a capability it did not declare.
- [ ] End-to-end style fingerprint consumption by `draft_agent.py`.

## 8. Tests

- `backend/tests/test_path_containment.py` — entrypoint containment (`..`
  traversal, absolute path outside the skill dir, absolute path inside it,
  directory target, unresolvable path, normal entrypoint) and vault traversal
  containment (junction/symlink escape does not surface outside content).
  Link-based tests skip when the host cannot create links.
- `backend/tests/test_restricted_token.py`
- `backend/tests/test_sandbox_mode_transparency.py`
- `backend/tests/test_skill_permission_policy.py`
- `backend/tests/test_agent_db_readonly.py`



## Skill script internal layout (2026-10)

Some Skill scripts were large single files and were split by responsibility.
This is an internal refactor only:

- The Skill Engine still discovers and invokes the frontmatter ntrypoint
  (e.g. skills/trending-radar/scripts/radar.py,
  skills/content-multi-distributor/scripts/distribute.py).
- The entrypoint stays a working CLI and re-exports the previous public helper
  names, so existing callers and tests keep working.
- Private helper modules use a leading underscore (_data.py, _fetchers.py,
  _core.py, _content.py, _references.py, _formatters.py, ...).
- CLI flags, stdout JSON schema, exit codes, fallback behaviour and network
  access patterns are unchanged.
- Code style: new skill modules must stay under 300 lines (enforced by
  scripts/check_code_style.py); skill scripts are not baselined in
  scripts/code_style_baseline.txt.

No new sandbox capability is implied by this layout. Execution guarantees stay
exactly as documented in docs/architecture/10_Sandbox_and_Permission_Model.md.

## 9. Engine module layout (2026-10 refactor)

Internal split only. Discovery, policy evaluation, permission gating, execution
modes, fail-closed rules and results are unchanged, and every previously public
name is still importable from its original module.

- `windows_sandbox.py` - runner facade and `run_skill` orchestration.
- `sandbox_config.py` - `SandboxConfig` / `SandboxExecutionResult` models.
- `sandbox_process.py` - low-level child spawn helpers (no `run_skill`).
- `restricted_token.py` - re-export facade for the restricted-token API.
- `restricted_token_winapi.py` - constants, ctypes structures, API bindings.
- `restricted_token_api.py` - token creation and introspection.
- `restricted_token_process.py` - launch under the token plus Job Object.
- `acl_guard.py` - re-export facade for the ACL layer.
- `acl_types.py`, `acl_guard_winapi_bindings.py`, `acl_guard_winapi_ace.py`,
  `acl_guard_winapi.py` - ACL types, bindings, ACE helpers, apply / rollback.

The guarantees described in section 5 and the open gaps in section 7 are exactly
the same before and after the split. This refactor adds **no** new sandbox
capability.
