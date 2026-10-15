# 06 — Scheduler and Unattended Skills

Status: **Implemented (partial isolation)**. Verified against `main@4d643ad`.
The only path that runs skills without a human present. It is also the path with
the strongest permission requirements, because "unattended" means no one can
approve at call time.

## 1. Scope and code paths

| Path | Role |
| --- | --- |
| `backend/app/services/inspection_scheduler_service.py` | Public facade: `InspectionSchedulerService` + `inspection_scheduler` singleton. Re-exports `engine` and `get_skill_manager` so existing monkeypatch-based tests keep working; contains no scheduling logic itself |
| `backend/app/services/inspection_scheduler_runtime.py` | Inspection cycle execution + background loop / lifecycle
| `backend/app/services/inspection_scheduler_status.py` | Status reporting, next-run calculation, quota authorization |
| `backend/app/services/inspection_scheduler_wheels.py` | Inspection cycle wheels and wheel dispatch |
| `backend/app/services/inspection_scheduler_briefing.py` | Daily briefing assembly |
| `backend/app/services/inspection_scheduler_state.py` | Per-user durable settings, dismissed date, quota decision, last-run summary |
| `backend/app/services/inspection_scheduler_helpers.py` | Shared helpers plus the facade `engine` / `get_skill_manager` resolvers used by the sibling modules |
| `backend/app/services/inspection_quota_service.py` | Daily / per-run budget + grant state |
| `backend/app/models/inspection_quota.py` | `InspectionQuota` |
| `backend/app/models/scheduler_state.py` | `SchedulerUserState` - durable per-user settings / dismissed date / quota decision / last summary |
| `backend/app/models/__init__.py` | Model registry that exposes `SchedulerUserState` to `SQLModel.metadata` |
| `backend/app/api/scheduler.py` | Settings, status, trigger, briefing, quota |
| `backend/app/core/skill_engine/discovery.py` | `SKILL.md` → `SkillDefinition` |
| `backend/app/core/skill_engine/manager.py` | `SkillManager`: list / get / execute |
| `backend/app/core/skill_engine/policy.py` | `ExecutionContext`, `NetworkPolicy`, `PolicyDecision` |
| `backend/app/core/skill_engine/windows_sandbox.py` | Runner + `SandboxExecutionResult` |
| `backend/app/core/skill_engine/restricted_token.py` | Real restricted token via ctypes |
| `backend/app/core/skill_engine/network_guard.py` | Child-process egress guard |
| `backend/app/core/skill_engine/job_object.py` | Windows Job Object containment (`KILL_ON_JOB_CLOSE`, process-tree termination) — **Implemented** |
| `backend/app/core/skill_engine/sandbox_profile.py` | Sandbox account / SID profile parsing only — **Partial** (no account creation) |
| `backend/app/core/skill_engine/acl_guard.py` | NTFS ACE plan computation plus scoped per-workspace apply (`SetNamedSecurityInfoW` + read-back verification) — **Partial** (`enforce` writes scoped allow ACEs; default posture is `dry_run`) |
| `backend/app/core/skill_engine/os_network_boundary.py` | Windows Firewall rule planning — **Partial** (dry-run, never applies rules) |
| `skills/content-collector`, `content-multi-distributor`, `media-article-extractor`, `trending-radar`, `viewpoint-insight-miner` | The five shipped skills |
| `frontend/src/components/DailyBriefingModal.vue` | Briefing surface |
| `skills/trending-radar/scripts/radar.py` | Wheel-1 entrypoint; re-exports `_data`/`_fetchers`/`_core` helpers |
| `skills/trending-radar/scripts/_data.py` | User agent, fallback topics, platform constants |
| `skills/trending-radar/scripts/_fetchers.py` | Per-platform fetchers and `PLATFORM_FETCHERS` |
| `skills/trending-radar/scripts/_core.py` | Relevance scoring and `run_radar` |
| `skills/content-multi-distributor/scripts/distribute.py` | Wheel-2 entrypoint; re-exports the private helper modules |
| `skills/content-multi-distributor/scripts/_content.py` | Title/content cleaning, block parsing, key sentences, hashtags |
| `skills/content-multi-distributor/scripts/_markdown_links.py` | Markdown link / reference-definition parsing |
| `skills/content-multi-distributor/scripts/_references.py` | Footnote extraction and link-to-footnote replacement |
| `skills/content-multi-distributor/scripts/_formatters_xhs.py` | Xiaohongshu formatting, section illustrations |
| `skills/content-multi-distributor/scripts/_formatters.py` | WeChat / Twitter / video formatting |

The wheel entrypoints, their CLI arguments, stdout JSON schema, exit codes and
fallback behaviour are unchanged by the split; only the private module layout
differs. No new sandbox guarantee comes with this layout.


Security truth is **not** restated here. Read
`../architecture/10_Sandbox_and_Permission_Model.md`.

## 2. Scheduler loop

```
start() → _scheduler_loop()
  ├─ wheel 1: collect     (content-collector / trending-radar)
  └─ wheel 2: distribute  (content-multi-distributor)
       → run_inspection_cycle() → quota gate → SkillManager.execute()
       → run_wheel_1() / run_wheel_2()
  → get_today_briefing()
       ├─ confirm_briefing_into_vault()
       └─ mark_briefing_read()
```

`calculate_next_run_time()` derives the next wake-up from scheduler settings, so
the loop is interval-driven, not cron-expression-driven.

## 3. Quota and pre-authorization

`InspectionQuota` is the gate that makes unattended execution accountable:

| Field | Meaning |
| --- | --- |
| `enabled` | Master switch for scheduler-driven external calls |
| `authorized` | Explicit pre-authorization; unattended runs are refused without it |
| `daily_limit`, `per_run_limit` | Budgets, rolled by `_roll_day()` / `reset_run()` |
| `used_today`, `used_this_run` | Counters for the current UTC day / run |
| `last_denied_at`, `last_denial_reason` | Why the last run was refused |
| `total_runs`, `total_denied` | Long-run observability |

`_deny()` records the reason instead of silently skipping, so a refused run is
visible in `GET /api/scheduler/status`.

### 3.1 Workflow permission gate (Implemented)

Budget authorization is not authorization. Before any unattended skill child
process is started, the scheduler calls the centralized workflow permission layer:

```python
require_authorization(
    ACTION_SCHEDULER_UNATTENDED,
    actor_id=str(target_uid),
    mode=WorkflowMode.UNATTENDED,
    detail={"skill": "trending-radar", "trigger": "inspection_scheduler"},
)
```

Behaviour:

- The call happens **after** the quota gate and **before** `SkillManager.execute()`,
  so a denial never degrades into an execution attempt.
- Two gates run independently and both must pass: the workflow permission layer
  (pre-authorization allowlist + approval audit) and the existing
  `skill_engine/policy.py` decision. A missing authorization in **either** layer
  fails closed.
- `WorkflowMode.UNATTENDED` executes only inside its pre-authorized allowlist;
  anything outside it is refused rather than prompted, because there is no human
  present to prompt.
- Unknown action, unknown permission, unknown mode, evaluator failure, approval
  provider failure or audit write failure all **fail closed**. There is no
  "unknown means allow" path.
- A refusal is written to the workflow audit stream (who / what / when /
  decision / reason) and is logged; the cycle returns no material instead of
  running the skill.

**Not implemented:** the workflow audit records and the skill-engine ACL journal
are not stored in a shared store and cannot be correlated by `execution_id`. See
`../architecture/10_Sandbox_and_Permission_Model.md` for the workflow permission
layer and its honest limits.


## 4. Skill execution

```
SkillManager.execute(skill, context)
  → policy.PolicyDecision          # permissions + network policy + UNATTENDED gate
  → windows_sandbox.SandboxExecutionResult
       requested_runner_mode / runner_mode / sandbox_enforced / warnings
```

`SkillManager` exposes async and sync execution. `policy.py` is what decides
whether an `UNATTENDED` skill may run at all; `windows_sandbox.py` is what
actually launches the child.

### 4.1 Skill entrypoint containment (implemented)

A restricted token reduces the child's privileges. It does **not** decide *which
file* gets executed, so entrypoint containment is enforced separately, at
discovery time, in `discovery.py`:

- `resolve_entrypoint_path(entrypoint, skill_dir)` resolves the raw
  `SKILL.md` frontmatter value against the resolved skill directory;
- the resolved path must satisfy `relative_to(skill_root_resolved)` — a
  `../../evil.py` or `../evil.py` traversal is rejected;
- an **absolute** frontmatter path is accepted only when it still lands inside
  the skill directory; anything else is rejected;
- a symlink whose target escapes the skill directory is rejected by the same
  post-`resolve()` check;
- a directory target is rejected;
- any failure to resolve either side raises `SkillDefinitionError` — the
  definition is **not** silently degraded to a different file.

This check runs twice, and both layers fail closed: `parse_skill_markdown()`
refuses to produce a `SkillDefinition` with an escaping entrypoint, and
`windows_sandbox.py` consumes `SkillDefinition.entrypoint_path` (the validated
absolute path) rather than re-joining the raw string, returning a structured
failure with `success=False` instead of spawning a process.

The resolved entrypoint is not required to exist at discovery time; existence is
checked in the runner, which still fails closed.

## 5. API surface

All scheduler routes are **authenticated**: they take `Depends(get_current_user)`
and resolve the acting user from the trusted identity (`_resolve_acting_user_id`).
A client-supplied `user_id` in body or query is **ignored** and is never used as
an authorization input. Per-user job state (quota, schedules, briefing state) is
isolated **in-process only** — it is lost on restart and is not consistent across
multiple worker processes.

`GET|PUT /api/scheduler/quota`, `GET /api/scheduler/status`,
`POST /api/scheduler/trigger`, `POST /api/scheduler/settings`,
`GET /api/scheduler/briefing/today`, `POST /api/scheduler/briefing/mark-read`,
`POST /api/scheduler/briefing/confirm`

## 6. Honest gaps

1. **Isolation is partial.** A real restricted token is used, and the
   restricted-token path now always creates and assigns a Job Object
   (`KILL_ON_JOB_CLOSE`, no breakaway); allocation failure terminates the child
   and fails closed rather than running without containment. There is still no
   sandbox account, no filesystem ACL layer and no OS-level network boundary —
   those three are planning/dry-run layers only. See the sandbox document for the
   exact guarantee list.
2. **`SKILL.md` `permissions` is gated before launch, but is not an OS
   authorisation boundary.** A DENY decision is returned before workspace
   creation, restricted-token creation and child spawn. The declaration is not
   enforced by NTFS ACLs, firewall rules or the restricted token itself.
3. **The briefing is a report, not an approval gate.** Confirming a briefing moves
   material into the vault; it does not gate the next cycle.
4. **Scheduler settings are global**, not per-user, while quota is per-user. That
   asymmetry is intentional but undocumented in code and easy to trip over.
5. **Per-user isolation is in-process only.** Scheduler state is held in memory:
   it does not survive a restart, and with multiple uvicorn workers two requests
   for the same user can be handled by processes that disagree. A shared store
   (DB-backed) is required before this can be described as durable isolation.

## 7. Related

- `04_Distribution_and_Credentials.md` — the credentials the distributor uses.
- `08_Data_Model_Reference.md` — `InspectionQuota`.
- `../architecture/10_Sandbox_and_Permission_Model.md` — isolation truth.
- `../architecture/12_Skill_Engine_Spec.md` — engine specification.

## 8. Execution-path module layout (2026-10 refactor)

The scheduler uses the same engine code as interactive runs. That engine was
split by responsibility in 2026-10. The modules now are:

- `backend/app/core/skill_engine/windows_sandbox.py` - runner facade and
  `run_skill` orchestration.
- `backend/app/core/skill_engine/sandbox_config.py` - config / result models.
- `backend/app/core/skill_engine/sandbox_process.py` - low-level child spawn.
- `backend/app/core/skill_engine/restricted_token.py` - re-export facade.
- `backend/app/core/skill_engine/restricted_token_winapi.py` - constants,
  ctypes structures, API bindings.
- `backend/app/core/skill_engine/restricted_token_api.py` - token creation and
  introspection.
- `backend/app/core/skill_engine/restricted_token_process.py` - launch under
  the token plus Job Object.
- `backend/app/core/skill_engine/acl_guard.py` - re-export facade.
- `backend/app/core/skill_engine/acl_types.py` - ACL types and masks.
- `backend/app/core/skill_engine/acl_guard_winapi_bindings.py` - ctypes bindings.
- `backend/app/core/skill_engine/acl_guard_winapi_ace.py` - ACE helpers.
- `backend/app/core/skill_engine/acl_guard_winapi.py` - apply / rollback.

The split is internal only: the scheduler still calls `SkillManager.execute(...)`,
the permission gate still runs before any workspace, token or child process is
created, and the fail-closed rules listed in sections 4 and 6 are unchanged. See
`docs/architecture/10_Sandbox_and_Permission_Model.md` for the full table.

## 2026-10-15 defect fix: wheel-2 formatter helpers

The wheel-2 (`content-multi-distributor`) formatter modules `_formatters.py` and
`_formatters_xhs.py` called `clean_title_text` / `extract_footnotes` without
defining or importing them, so any local formatting/preview run failed at call
time with `NameError`. Both modules now define the helpers they use. No new
sandbox guarantee, no new capability, and no real-platform publishing is implied:
this only restores the local formatting/preview path.
