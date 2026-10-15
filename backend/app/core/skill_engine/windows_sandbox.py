"""Windows Skill Execution Runner.

IMPORTANT HONESTY NOTE
----------------------
Two of the three isolation levels are real, one is deliberately refused:

- ``restricted_token`` (**real**): a genuine Windows Restricted Token is
  created with ``CreateRestrictedToken(DISABLE_MAX_PRIVILEGE)``, verified
  (``TokenIsRestricted`` + at least one deny-only restricting SID) and attached
  to the skill process via ``CreateProcessAsUserW``. The child therefore holds
  no privileges and cannot use the group memberships Windows placed on the
  restricted SID list (typically Administrators). This is what
  ``sandbox_enforced=True`` means -- and only this.
  See :mod:`app.core.skill_engine.restricted_token` for the exact Win32 calls
  and for the full list of what is still NOT enforced.
- ``wsb``: **not implemented**. A ``.wsb`` profile can be generated for
  diagnostics, but ``WindowsSandbox.exe`` is never launched, so nothing is
  virtualized. The runner fails closed instead of pretending.
- ``sanitized_subprocess`` (**not isolation**): a plain subprocess used for the
  non-Windows / unavailable path. It inherits the caller's token and is always
  reported with ``sandbox_enforced=False``.

A restricted token cannot filter network traffic, so every run is additionally
gated on the skill's declared ``permissions``
(:mod:`app.core.skill_engine.policy`) and gets a Python interpreter-level
network egress guard (:mod:`app.core.skill_engine.network_guard`). Neither of
those is OS-level network isolation.

To keep the reported execution mode truthful, ``SandboxExecutionResult``
separates the requested mode (``requested_runner_mode``) from the mode that
was actually applied (``runner_mode``), and adds ``sandbox_enforced`` plus
human-readable ``warnings``.
"""

import asyncio
import json
import os
from pathlib import Path
import shutil
import sys

import tempfile
from typing import Any, Dict, List, Optional

from app.core.skill_engine.acl_guard import (
    AclPlanError,
    build_acl_plan,
)
from app.core.skill_engine.os_network_boundary import (
    NetworkBoundaryError,
    build_network_boundary_plan,
)
from app.core.skill_engine.sandbox_profile import (
    SandboxProfileError,
    load_profile,
)
from app.core.skill_engine.discovery import (
    SkillDefinition,
    SkillDefinitionError,
)
from app.core.skill_engine.network_guard import (
    ENV_ALLOW_HOSTS,
    install_network_guard_dir,
    prepend_guard_to_pythonpath,
)
from app.core.skill_engine.policy import (
    Decision,
    ExecutionContext,
    SkillPermissionPolicy,
    execution_context_from_env,
)
from app.core.skill_engine.restricted_token import (
    RestrictedTokenError,
    create_restricted_token,
    run_process_with_restricted_token,
)
from app.core.skill_engine.sandbox_config import (
    EFFECTIVE_MODE_RESTRICTED_TOKEN,
    EFFECTIVE_MODE_RESTRICTED_TOKEN_UNAVAILABLE,
    EFFECTIVE_MODE_SANITIZED_SUBPROCESS,
    EFFECTIVE_MODE_WSB_UNSUPPORTED,
    ENTRYPOINT_CONTAINMENT_WARNING,
    MODE_RESTRICTED_TOKEN,
    MODE_WSB,
    RESTRICTED_TOKEN_FALLBACK_WARNING,
    RESTRICTED_TOKEN_SCOPE_WARNING,
    SAFE_ENV_WHITELIST,
    SENSITIVE_PATTERNS,
    SUPPORTED_REQUESTED_MODES,
    UNKNOWN_MODE_ERROR,
    WSB_UNSUPPORTED_ERROR,
    SandboxExecutionResult,
    build_sanitized_env,
    generate_wsb_config,
)
from app.core.skill_engine.sandbox_process import (
    spawn_restricted_token_subprocess,
    spawn_sanitized_subprocess,
)


class WindowsSandboxRunner:
    """Facade over the sandbox primitives.

    The heavy lifting lives in :mod:`sandbox_config` (pure configuration and
    the result model) and :mod:`sandbox_process` (process creation). This class
    keeps the historical public surface, including the ``_spawn_*`` methods
    that tests monkeypatch.
    """

    def __init__(
        self,
        default_timeout: float = 15.0,
        permission_policy: Optional[SkillPermissionPolicy] = None,
    ):
        self.default_timeout = default_timeout
        # None means "rebuild from environment on each run" (see the
        # permission gate below). A policy passed in here is used verbatim.
        self.permission_policy = permission_policy

    def build_sanitized_env(self, custom_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Constructs an isolated, minimal environment stripped of any API keys or secrets."""
        return build_sanitized_env(custom_env)

    def generate_wsb_config(
        self,
        skill: SkillDefinition,
        args_payload: Dict[str, Any],
        temp_work_dir: Path,
    ) -> str:
        """Generates a dynamic Windows Sandbox (.wsb) XML profile (diagnostic only)."""
        return generate_wsb_config(skill, args_payload, temp_work_dir)

    def _spawn_sanitized_subprocess(
        self,
        command: List[str],
        cwd: Path,
        env: Dict[str, str],
        input_data: Optional[str] = None,
        timeout: float = 15.0,
    ) -> SandboxExecutionResult:
        """Runs a plain subprocess with a sanitized env and watchdog timeout.

        This is NOT process-level isolation; the result always reports
        ``runner_mode='sanitized_subprocess'`` and ``sandbox_enforced=False``.
        """
        return spawn_sanitized_subprocess(
            command=command,
            cwd=cwd,
            env=env,
            input_data=input_data,
            timeout=timeout,
        )

    def _spawn_restricted_token_subprocess(
        self,
        command: List[str],
        cwd: Path,
        env: Dict[str, str],
        input_data: Optional[str] = None,
        timeout: float = 15.0,
        active_process_limit: Optional[int] = None,
    ) -> SandboxExecutionResult:
        """Runs the skill under a REAL Windows Restricted Token, or fails closed.

        Dependencies are resolved from this module's globals at call time so
        that monkeypatching ``windows_sandbox.create_restricted_token`` /
        ``windows_sandbox.run_process_with_restricted_token`` keeps working.
        """
        return spawn_restricted_token_subprocess(
            create_token=create_restricted_token,
            run_with_token=run_process_with_restricted_token,
            command=command,
            cwd=cwd,
            env=env,
            input_data=input_data,
            timeout=timeout,
            active_process_limit=active_process_limit,
        )

    async def run_skill(
        self,
        skill: SkillDefinition,
        args: Dict[str, Any],
        runner_mode: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        execution_context: Optional[ExecutionContext] = None,
    ) -> SandboxExecutionResult:
        """Asynchronously executes a skill in the sandboxed runner."""
        return await asyncio.to_thread(
            self.run_skill_sync,
            skill,
            args,
            runner_mode,
            timeout_seconds,
            execution_context,
        )

    def run_skill_sync(
        self,
        skill: SkillDefinition,
        args: Dict[str, Any],
        runner_mode: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        execution_context: Optional[ExecutionContext] = None,
    ) -> SandboxExecutionResult:
        """Executes a skill, never overstating the isolation actually applied.

        Policy:
        - ``restricted_token``: executes under a real Windows Restricted Token
          (``CreateRestrictedToken`` + ``CreateProcessAsUserW``). On success
          ``sandbox_enforced=True`` and a scope warning spells out what the
          restricted token does *not* cover. If the token cannot be created or
          used, this fails closed -- the skill is not run at all.
        - ``wsb``: fails closed. ``WindowsSandbox.exe`` is not wired up, so the
          skill is never executed outside the (non-existent) sandbox.
        - anything else: fails closed as an unknown mode.
        """
        requested_mode = runner_mode or skill.runner_mode or MODE_RESTRICTED_TOKEN
        timeout = timeout_seconds or self.default_timeout
        context = execution_context or execution_context_from_env()

        if requested_mode not in SUPPORTED_REQUESTED_MODES:
            return SandboxExecutionResult(
                success=False,
                error=UNKNOWN_MODE_ERROR.format(mode=requested_mode),
                returncode=-1,
                runner_mode=EFFECTIVE_MODE_SANITIZED_SUBPROCESS,
                requested_runner_mode=requested_mode,
                sandbox_enforced=False,
            )

        # Entrypoint containment is enforced at definition level. If it is
        # violated we fail closed here rather than propagating an exception out
        # of the runner: the skill must not execute, and the caller still gets a
        # structured result instead of a 500.
        try:
            entrypoint_file = skill.entrypoint_path
        except SkillDefinitionError as exc:
            return SandboxExecutionResult(
                success=False,
                error=f"Skill entrypoint rejected: {exc}",
                returncode=-1,
                runner_mode=EFFECTIVE_MODE_SANITIZED_SUBPROCESS,
                requested_runner_mode=requested_mode,
                sandbox_enforced=False,
                warnings=[ENTRYPOINT_CONTAINMENT_WARNING],
            )

        if not entrypoint_file.is_file():
            return SandboxExecutionResult(
                success=False,
                error=f"Skill entrypoint not found: {entrypoint_file}",
                returncode=-1,
                runner_mode=EFFECTIVE_MODE_SANITIZED_SUBPROCESS,
                requested_runner_mode=requested_mode,
                sandbox_enforced=False,
                warnings=[RESTRICTED_TOKEN_FALLBACK_WARNING],
            )

        # Fail closed: we cannot honour the request, so we must not run the
        # script in a plainly unsandboxed process and pretend otherwise.
        if requested_mode == MODE_WSB:
            return SandboxExecutionResult(
                success=False,
                error=WSB_UNSUPPORTED_ERROR,
                returncode=-1,
                runner_mode=EFFECTIVE_MODE_WSB_UNSUPPORTED,
                requested_runner_mode=MODE_WSB,
                sandbox_enforced=False,
                warnings=[WSB_UNSUPPORTED_ERROR],
            )

        # --- Permission gate -------------------------------------------------
        # The declared SKILL.md permissions are evaluated BEFORE any process is
        # created. A deny means no token, no temp workspace, no child process.
        #
        # A policy explicitly passed to the constructor always wins. Otherwise
        # the policy is rebuilt from the environment on EVERY run: the
        # SkillManager is a process-wide singleton, so caching the policy at
        # construction time would freeze whatever the environment happened to
        # say when the first skill ran. Re-reading per run keeps operator
        # revocations effective without a process restart.
        policy = self.permission_policy or SkillPermissionPolicy.from_env()
        decision = policy.evaluate(
            declared_permissions=getattr(skill, "permissions", None),
            context=context,
        )
        if decision.decision is Decision.DENY:
            return SandboxExecutionResult(
                success=False,
                error=(
                    "Skill execution denied by permission policy: "
                    + " ".join(decision.reasons)
                ),
                stderr="\n".join(decision.reasons),
                returncode=-1,
                runner_mode=requested_mode,
                requested_runner_mode=requested_mode,
                sandbox_enforced=False,
                warnings=list(decision.warnings),
                execution_context=context.value,
                policy_decision=Decision.DENY.value,
                policy_reasons=list(decision.reasons),
                normalized_permissions=list(decision.normalized_permissions),
                granted_capabilities=list(decision.granted_capabilities),
                denied_capabilities=list(decision.denied_capabilities),
                network_allowlist=list(decision.network_allowlist),
                network_egress_allowed=False,
            )

        # --- Hardening profile gate -----------------------------------------
        # Resolved BEFORE the temp workspace, token and child exist. A profile
        # that cannot be honoured (e.g. an ACL "enforce" run on a backend
        # without SetNamedSecurityInfoW) must fail closed rather than silently
        # degrade to an uncontained run.
        try:
            profile = load_profile().require()
        except SandboxProfileError as exc:
            return SandboxExecutionResult(
                success=False,
                error=str(exc),
                stderr=str(exc),
                returncode=-1,
                runner_mode=requested_mode,
                requested_runner_mode=requested_mode,
                sandbox_enforced=False,
                warnings=[
                    "Sandbox hardening profile could not be satisfied. The skill "
                    "was NOT executed: failing closed instead of running without "
                    "the requested containment.",
                ],
                execution_context=context.value,
                policy_decision=decision.decision.value,
                policy_reasons=list(decision.reasons),
                normalized_permissions=list(decision.normalized_permissions),
                granted_capabilities=list(decision.granted_capabilities),
                denied_capabilities=list(decision.denied_capabilities),
                network_allowlist=list(decision.network_allowlist),
                network_egress_allowed=False,
            )

        # Create isolated workspace directory for this execution
        temp_dir = Path(tempfile.mkdtemp(prefix="cog_sandbox_")).resolve()
        # Hoisted so the finally block can restore the original DACL even when
        # the run fails after the ACL layer was applied.
        acl_plan = None

        try:
            # --- Scoped NTFS ACL layer -------------------------------------
            # acl_mode="plan" (default) is dry-run: no DACL is written and
            # AclPlan.enforced stays False. acl_mode="enforce" really writes a
            # scoped allow ACE via SetNamedSecurityInfoW, reads it back, and
            # fails closed if verification fails. This is per-workspace NTFS
            # hardening only -- not a container, and not an OS network boundary.
            acl_plan_dict = None
            if profile.acl_mode != "disabled":
                try:
                    acl_plan = build_acl_plan(
                        temp_dir,
                        profile.sandbox_account_sid,
                        decision.granted_capabilities,
                        dry_run=(profile.acl_mode != "enforce"),
                    )
                    acl_plan_dict = acl_plan.describe()
                except AclPlanError as exc:
                    # Fail closed: a requested ACL layer that cannot even be
                    # planned must not degrade into an uncontained run.
                    return SandboxExecutionResult(
                        success=False,
                        error=f"NTFS ACL plan failed: {exc}",
                        stderr=str(exc),
                        returncode=-1,
                        runner_mode=requested_mode,
                        requested_runner_mode=requested_mode,
                        sandbox_enforced=False,
                        warnings=[
                            "The requested NTFS ACL layer could not be planned; "
                            "refusing to start the skill.",
                        ],
                        execution_context=context.value,
                        sandbox_profile=profile.describe(),
                    )

            # --- OS network boundary plan (PARTIAL: computed, never enforced) -
            try:
                net_plan = build_network_boundary_plan(
                    profile.network_boundary_mode,
                    decision.network_allowlist,
                    decision.granted_capabilities,
                    bool(decision.network_egress_allowed),
                )
            except NetworkBoundaryError as exc:
                net_plan = None
            net_plan_dict = net_plan.describe() if net_plan is not None else None

            if net_plan is not None and net_plan.blocking_errors:
                # Fail closed: a requested OS network boundary that cannot be
                # honoured must not degrade into a run that merely *looks*
                # bounded by an in-process Python guard.
                return SandboxExecutionResult(
                    success=False,
                    error='OS network boundary request failed: '
                          + ' '.join(net_plan.blocking_errors),
                    stderr=' '.join(net_plan.blocking_errors),
                    returncode=-1,
                    runner_mode=requested_mode,
                    requested_runner_mode=requested_mode,
                    sandbox_enforced=False,
                    warnings=[
                        'The requested OS network boundary could not be '
                        'honoured; refusing to start the skill.',
                    ],
                    execution_context=context.value,
                    sandbox_profile=profile.describe(),
                    os_network_boundary=net_plan_dict,
                    policy_decision=decision.decision.value,
                    policy_reasons=list(decision.reasons),
                    normalized_permissions=list(decision.normalized_permissions),
                    granted_capabilities=list(decision.granted_capabilities),
                    denied_capabilities=list(decision.denied_capabilities),
                    network_allowlist=list(decision.network_allowlist),
                    network_egress_allowed=False,
                )

            # Build sanitized environment and install the network egress guard.
            #
            # HONEST ENFORCEMENT BOUNDARY: this guard is injected at the Python
            # interpreter boundary (sitecustomize on PYTHONPATH). It is REAL for
            # Python processes that inherit this environment (children and
            # grandchildren). It is NOT an OS-level network control: a skill that
            # deletes the guard directory, restores socket.socket.connect, uses
            # ctypes/native code, or execs a non-Python binary bypasses it.
            # There is no Windows Firewall / AppContainer network isolation here.
            clean_env = self.build_sanitized_env()
            guard_dir = install_network_guard_dir(
                temp_dir, decision.network_allowlist
            )
            prepend_guard_to_pythonpath(clean_env, guard_dir)
            # Empty allowlist == deny all egress for this child.
            clean_env[ENV_ALLOW_HOSTS] = ",".join(decision.network_allowlist)

            # Prepare execution command
            # Use sys.executable to run inside the same virtual environment
            json_payload = json.dumps(args, ensure_ascii=True)
            input_file = temp_dir / "input.json"
            input_file.write_text(json_payload, encoding="utf-8")

            # Prevent command line overflow in Windows CreateProcess (>32k limit)
            if len(json_payload) > 2000:
                command = [
                    sys.executable,
                    "-X",
                    "utf8",
                    str(entrypoint_file),
                    "--file",
                    str(input_file),
                ]
            else:
                command = [
                    sys.executable,
                    "-X",
                    "utf8",
                    str(entrypoint_file),
                    "--json",
                    json_payload,
                    "--file",
                    str(input_file),
                ]

            result = self._spawn_restricted_token_subprocess(
                command=command,
                cwd=temp_dir,
                env=clean_env,
                input_data=json_payload,
                timeout=timeout,
                active_process_limit=profile.job_active_process_limit,
            )
            result.sandbox_profile = profile.describe()
            result.acl_plan = acl_plan_dict
            result.os_network_boundary = net_plan_dict
            for extra in profile.warnings:
                if extra not in result.warnings:
                    result.warnings.append(extra)
            if acl_plan_dict:
                for extra in acl_plan_dict.get("warnings", []):
                    if extra not in result.warnings:
                        result.warnings.append(extra)
            if net_plan_dict:
                for extra in net_plan_dict.get("warnings", []):
                    if extra not in result.warnings:
                        result.warnings.append(extra)
            result.execution_context = context.value
            result.policy_decision = decision.decision.value
            result.policy_reasons = list(decision.reasons)
            result.normalized_permissions = list(decision.normalized_permissions)
            result.granted_capabilities = list(decision.granted_capabilities)
            result.denied_capabilities = list(decision.denied_capabilities)
            result.network_allowlist = list(decision.network_allowlist)
            result.network_egress_allowed = bool(decision.network_egress_allowed)
            for warning in decision.warnings:
                if warning not in result.warnings:
                    result.warnings.append(warning)
            return result

        finally:
            # Best-effort rollback of the scoped ACL. This only runs when the
            # finally block is reached, so an ACL can still be left behind if
            # the runner is killed hard; a rollback failure is reported, never
            # swallowed.
            if acl_plan is not None:
                try:
                    acl_rollback_notes = acl_plan.restore()
                except Exception as exc:  # pragma: no cover - defensive
                    acl_rollback_notes = [f"NTFS ACL rollback raised: {exc}"]
                for note in acl_rollback_notes:
                    sys.stderr.write(note + "\n")
            # Clean up temp directory safely
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass


__all__ = [
    "SandboxExecutionResult",
    "WindowsSandboxRunner",
    "SAFE_ENV_WHITELIST",
    "SENSITIVE_PATTERNS",
    "MODE_RESTRICTED_TOKEN",
    "MODE_WSB",
    "EFFECTIVE_MODE_RESTRICTED_TOKEN",
    "EFFECTIVE_MODE_SANITIZED_SUBPROCESS",
    "EFFECTIVE_MODE_RESTRICTED_TOKEN_UNAVAILABLE",
    "EFFECTIVE_MODE_WSB_UNSUPPORTED",
    "RESTRICTED_TOKEN_FALLBACK_WARNING",
    "RESTRICTED_TOKEN_SCOPE_WARNING",
]
