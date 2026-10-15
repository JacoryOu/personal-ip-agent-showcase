"""Configuration, constants and the result model for the Windows skill runner.

Split out of :mod:`app.core.skill_engine.windows_sandbox` to keep that module a
small facade. Nothing here executes a process.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

from pydantic import BaseModel, Field

from app.core.skill_engine.discovery import SkillDefinition

SENSITIVE_PATTERNS = (
    "KEY",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "CREDENTIAL",
    "AUTH",
    "DATABASE_URL",
    "POSTGRES",
    "REDIS",
    "AWS",
    "OPENAI",
    "ANTHROPIC",
    "DEEPSEEK",
    "GEMINI",
)

# Whitelist of essential system environment variables for Windows Python execution
SAFE_ENV_WHITELIST = {
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "PATH",
    "PATHEXT",
    "COMSPEC",
    "TEMP",
    "TMP",
    "LOCALAPPDATA",
    "APPDATA",
    "COMMONPROGRAMFILES",
    "PROGRAMDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
}


# Execution modes that are *declared* by skills / callers.
MODE_RESTRICTED_TOKEN = "restricted_token"
MODE_WSB = "wsb"

# Execution modes that this runner can actually deliver today. Neither of them
# provides real OS-level isolation; they are named so that logs and API
# responses never overstate the isolation level.
EFFECTIVE_MODE_RESTRICTED_TOKEN = "restricted_token"
EFFECTIVE_MODE_SANITIZED_SUBPROCESS = "sanitized_subprocess"
EFFECTIVE_MODE_WSB_UNSUPPORTED = "wsb_unsupported"
EFFECTIVE_MODE_RESTRICTED_TOKEN_UNAVAILABLE = "restricted_token_unavailable"

SUPPORTED_REQUESTED_MODES = {MODE_RESTRICTED_TOKEN, MODE_WSB}

ENTRYPOINT_CONTAINMENT_WARNING = (
    "Skill entrypoint was rejected by containment validation; the skill was not executed."
)
RESTRICTED_TOKEN_FALLBACK_WARNING = (
    "Requested runner_mode 'restricted_token' is NOT honoured: a real Windows "
    "Restricted Token could not be created, so no privilege-reduced token is "
    "attached to the skill. The skill was NOT executed -- this runner fails "
    "closed rather than starting a plain subprocess with a sanitized "
    "environment and calling it a sandbox."
)

# Appended to every successful restricted_token run so that nobody reading a
# log mistakes a restricted token for a full sandbox.
RESTRICTED_TOKEN_SCOPE_WARNING = (
    "A real Windows Restricted Token was created and attached to the skill "
    "process (CreateRestrictedToken with DISABLE_MAX_PRIVILEGE, launched via "
    "CreateProcessAsUserW). 'sandbox_enforced=True' therefore means: no token "
    "privileges, and no access through the SIDs Windows put on the restricted "
    "list (typically Administrators). The child is additionally bound to a "
    "Windows Job Object when containment succeeds (see job_object.py), which "
    "kills the whole process tree on timeout or parent crash. It does NOT "
    "mean: AppContainer, filesystem ACL isolation, a dedicated sandbox "
    "account, an OS-level network boundary, registry/clipboard/COM "
    "restrictions, or Windows Sandbox virtualization. "
    "SKILL.md permissions are now gated before launch (see policy.py), and "
    "network egress is gated by an injected Python interpreter-level guard "
    "(network_guard.py) -- but that guard is NOT a Windows Firewall / "
    "AppContainer network isolation, and filesystem permissions are still only "
    "a declared capability, not a physical ACL."
)
WSB_UNSUPPORTED_ERROR = (
    "Requested runner_mode 'wsb' is not implemented: this runner never launches "
    "WindowsSandbox.exe, so no Hyper-V isolation is applied. Refusing to execute "
    "the skill in an unsandboxed process. Use runner_mode 'restricted_token' for "
    "the restricted-token runner instead."
)
UNKNOWN_MODE_ERROR = (
    "Unknown runner_mode '{mode}'. Supported modes: restricted_token, wsb."
)


class SandboxExecutionResult(BaseModel):
    success: bool
    output: Any = None
    raw_stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    execution_time_ms: float = 0.0
    # The mode that was actually applied. Never used to advertise isolation we
    # do not provide.
    runner_mode: str = EFFECTIVE_MODE_SANITIZED_SUBPROCESS
    # The mode requested by the caller / skill definition, for traceability.
    requested_runner_mode: Optional[str] = None
    # False as long as no OS-level sandbox (Restricted Token / WSB) is applied.
    sandbox_enforced: bool = False
    warnings: List[str] = Field(default_factory=list)
    timed_out: bool = False
    error: Optional[str] = None
    wsb_config_path: Optional[str] = None
    # --- Permission policy trace (see policy.py) ---
    execution_context: Optional[str] = None
    policy_decision: Optional[str] = None
    policy_reasons: List[str] = Field(default_factory=list)
    normalized_permissions: List[str] = Field(default_factory=list)
    granted_capabilities: List[str] = Field(default_factory=list)
    denied_capabilities: List[str] = Field(default_factory=list)
    network_allowlist: List[str] = Field(default_factory=list)
    network_egress_allowed: bool = False
    # --- Hardening layers (see sandbox_profile.py) ---
    # sandbox_profile reports what the operator requested.
    # acl_plan reports the scoped NTFS layer: in acl_mode="enforce" the ACE is
    # really written and read back (acl_plan["enforced"] is then True);
    # in "plan" mode it stays a dry-run description.
    # os_network_boundary is still only a PLAN: no firewall rule is ever written.
    # Neither layer alone implies full container isolation.
    sandbox_profile: Optional[Dict[str, Any]] = None
    acl_plan: Optional[Dict[str, Any]] = None
    os_network_boundary: Optional[Dict[str, Any]] = None
    # True only when a real Job Object actually contained the process tree.
    job_object_enforced: bool = False


def build_sanitized_env(custom_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Constructs an isolated, minimal environment stripped of any API keys or secrets."""
    sanitized: Dict[str, str] = {}

    for k, v in os.environ.items():
        k_upper = k.upper()
        # Whitelist safe Windows OS variables
        if k_upper in SAFE_ENV_WHITELIST:
            sanitized[k] = v

    # Filter out anything that matches sensitive keywords
    for k in list(sanitized.keys()):
        k_upper = k.upper()
        if any(pat in k_upper for pat in SENSITIVE_PATTERNS):
            del sanitized[k]

    # Enforce UTF-8 for subprocess communication
    sanitized["PYTHONIOENCODING"] = "utf-8"
    sanitized["PYTHONUTF8"] = "1"
    sanitized["PYTHONUNBUFFERED"] = "1"

    if custom_env:
        for ck, cv in custom_env.items():
            if not any(pat in ck.upper() for pat in SENSITIVE_PATTERNS):
                sanitized[ck] = str(cv)

    return sanitized


def generate_wsb_config(
    skill: SkillDefinition,
    args_payload: Dict[str, Any],
    temp_work_dir: Path,
) -> str:
    """Generates a dynamic Windows Sandbox (.wsb) XML profile.

    DIAGNOSTIC ONLY: writing this file does NOT start a sandbox. This runner
    never invokes ``WindowsSandbox.exe``, so the produced profile is not
    executed anywhere. ``run_skill_sync`` fails closed for ``wsb`` mode.
    """
    host_skill_dir = str(Path(skill.skill_dir).resolve())
    host_work_dir = str(temp_work_dir.resolve())
    json_args = json.dumps(args_payload, ensure_ascii=False)

    return f"""<Configuration>
  <VGpu>Disable</VGpu>
  <Networking>Enable</Networking>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>{host_skill_dir}</HostFolder>
      <SandboxFolder>C:\\Skill</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>{host_work_dir}</HostFolder>
      <SandboxFolder>C:\\Work</SandboxFolder>
      <ReadOnly>false</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>cmd.exe /c python C:\\Skill\\{skill.entrypoint} --file C:\\Work\\input.json &gt; C:\\Work\\output.json 2&gt;&amp;1</Command>
  </LogonCommand>
</Configuration>"""


__all__ = [
    "SENSITIVE_PATTERNS",
    "SAFE_ENV_WHITELIST",
    "MODE_RESTRICTED_TOKEN",
    "MODE_WSB",
    "EFFECTIVE_MODE_RESTRICTED_TOKEN",
    "EFFECTIVE_MODE_SANITIZED_SUBPROCESS",
    "EFFECTIVE_MODE_WSB_UNSUPPORTED",
    "EFFECTIVE_MODE_RESTRICTED_TOKEN_UNAVAILABLE",
    "SUPPORTED_REQUESTED_MODES",
    "ENTRYPOINT_CONTAINMENT_WARNING",
    "RESTRICTED_TOKEN_FALLBACK_WARNING",
    "RESTRICTED_TOKEN_SCOPE_WARNING",
    "WSB_UNSUPPORTED_ERROR",
    "UNKNOWN_MODE_ERROR",
    "SandboxExecutionResult",
    "build_sanitized_env",
    "generate_wsb_config",
]
