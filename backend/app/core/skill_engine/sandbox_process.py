"""Child-process execution strategies for the Skill sandbox runner.

Split out of ``windows_sandbox.py`` so the runner facade stays small and
readable. Behaviour is intentionally identical to the original inline
methods: sanitized subprocess execution never claims isolation, and
restricted-token execution fails closed when the token cannot be created or
used. The restricted-token helpers are injected as parameters so that
``windows_sandbox`` module-level monkeypatching keeps working.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .restricted_token import RestrictedTokenError
from .sandbox_config import (
    EFFECTIVE_MODE_RESTRICTED_TOKEN,
    EFFECTIVE_MODE_RESTRICTED_TOKEN_UNAVAILABLE,
    EFFECTIVE_MODE_SANITIZED_SUBPROCESS,
    MODE_RESTRICTED_TOKEN,
    RESTRICTED_TOKEN_FALLBACK_WARNING,
    RESTRICTED_TOKEN_SCOPE_WARNING,
    SandboxExecutionResult,
)

__all__ = [
    "spawn_restricted_token_subprocess",
    "spawn_sanitized_subprocess",
]


def _safe_decode(data: bytes) -> str:
    """Decodes process output, tolerating common Chinese encodings."""
    if not data:
        return ""
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")


def spawn_sanitized_subprocess(
    command: List[str],
    cwd: Path,
    env: Dict[str, str],
    input_data: Optional[str] = None,
    timeout: float = 15.0,
) -> SandboxExecutionResult:
    """Runs a plain subprocess with a sanitized env and watchdog timeout.

    This is NOT process-level isolation: the child inherits the current
    user's token and privileges. The returned result always reports
    ``runner_mode='sanitized_subprocess'`` and ``sandbox_enforced=False``.
    """
    start_time = time.perf_counter()
    timed_out = False
    stdout_text = ""
    stderr_text = ""
    returncode = 0

    # Windows-specific process creation flags: hide window if on Windows
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    try:
        stdin_bytes = input_data.encode("utf-8") if input_data is not None else None
        proc = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags,
        )

        try:
            raw_out, raw_err = proc.communicate(
                input=stdin_bytes,
                timeout=timeout,
            )
            returncode = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            raw_out, raw_err = proc.communicate()
            returncode = -1

        stdout_text = _safe_decode(raw_out)
        stderr_text = _safe_decode(raw_err)

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return SandboxExecutionResult(
            success=False,
            error=f"Process launch failed: {str(e)}",
            stderr=str(e),
            execution_time_ms=elapsed_ms,
            returncode=-1,
        )

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    if timed_out:
        return SandboxExecutionResult(
            success=False,
            runner_mode=EFFECTIVE_MODE_SANITIZED_SUBPROCESS,
            requested_runner_mode=MODE_RESTRICTED_TOKEN,
            sandbox_enforced=False,
            warnings=[RESTRICTED_TOKEN_FALLBACK_WARNING],
            timed_out=True,
            error=f"Execution timed out after {timeout} seconds.",
            raw_stdout=stdout_text,
            stderr=stderr_text,
            returncode=returncode,
            execution_time_ms=elapsed_ms,
        )

    # Attempt to parse stdout as JSON if possible
    parsed_output: Any = stdout_text.strip()
    if parsed_output:
        try:
            parsed_output = json.loads(parsed_output)
        except Exception:
            pass

    success = returncode == 0
    if isinstance(parsed_output, dict) and "error" in parsed_output and parsed_output.get("error"):
        # If application returned an explicit error object
        if not parsed_output.get("success", True):
            success = False

    return SandboxExecutionResult(
        success=success,
        output=parsed_output,
        raw_stdout=stdout_text,
        stderr=stderr_text,
        returncode=returncode,
        execution_time_ms=elapsed_ms,
        runner_mode=EFFECTIVE_MODE_SANITIZED_SUBPROCESS,
        requested_runner_mode=MODE_RESTRICTED_TOKEN,
        sandbox_enforced=False,
        warnings=[RESTRICTED_TOKEN_FALLBACK_WARNING],
    )


def spawn_restricted_token_subprocess(
    create_token: Callable[[], Any],
    run_with_token: Callable[..., Any],
    command: List[str],
    cwd: Path,
    env: Dict[str, str],
    input_data: Optional[str] = None,
    timeout: float = 15.0,
    active_process_limit: Optional[int] = None,
) -> SandboxExecutionResult:
    """Runs the skill under a REAL Windows Restricted Token.

    Path: ``create_restricted_token()`` -> ``CreateProcessAsUserW``. If the
    token cannot be created or the process cannot be started under it, this
    method FAILS CLOSED: it never falls back to an unrestricted subprocess.

    The returned result reports ``runner_mode='restricted_token'`` and
    ``sandbox_enforced=True`` only when all of the following held:

    1. a restricted token handle was created by ``CreateRestrictedToken``;
    2. ``TokenIsRestricted`` read back as 1;
    3. at least one group SID read back as ``SE_GROUP_USE_FOR_DENY_ONLY``;
    4. ``CreateProcessAsUserW`` accepted that exact token handle.

    ``sandbox_enforced=True`` covers exactly those four guarantees. See
    ``RESTRICTED_TOKEN_SCOPE_WARNING`` for what is still NOT enforced.
    """
    start_time = time.perf_counter()

    def _elapsed_ms() -> float:
        return (time.perf_counter() - start_time) * 1000

    try:
        token_info = create_token()
    except RestrictedTokenError as exc:
        return SandboxExecutionResult(
            success=False,
            error=f"Restricted token creation failed: {exc}",
            stderr=str(exc),
            execution_time_ms=_elapsed_ms(),
            returncode=-1,
            runner_mode=EFFECTIVE_MODE_RESTRICTED_TOKEN_UNAVAILABLE,
            requested_runner_mode=MODE_RESTRICTED_TOKEN,
            sandbox_enforced=False,
            warnings=[
                RESTRICTED_TOKEN_FALLBACK_WARNING,
                "The skill was NOT executed: failing closed instead of "
                "running it without a restricted token.",
            ],
        )

    try:
        stdin_bytes = input_data.encode("utf-8") if input_data is not None else b""
        token_result = run_with_token(
            token_info,
            command,
            cwd=str(cwd),
            env=env,
            input_data=stdin_bytes,
            timeout=timeout,
            job_object_active_process_limit=active_process_limit,
        )
    except RestrictedTokenError as exc:
        return SandboxExecutionResult(
            success=False,
            error=f"Process launch under restricted token failed: {exc}",
            stderr=str(exc),
            execution_time_ms=_elapsed_ms(),
            returncode=-1,
            runner_mode=EFFECTIVE_MODE_RESTRICTED_TOKEN_UNAVAILABLE,
            requested_runner_mode=MODE_RESTRICTED_TOKEN,
            sandbox_enforced=False,
            warnings=[
                RESTRICTED_TOKEN_FALLBACK_WARNING,
                "The skill was NOT executed: failing closed instead of "
                "running it without a restricted token.",
            ],
        )
    finally:
        token_info.close()

    stdout_text = _safe_decode(token_result.stdout)
    stderr_text = _safe_decode(token_result.stderr)
    elapsed_ms = _elapsed_ms()
    warnings = [RESTRICTED_TOKEN_SCOPE_WARNING]
    warnings.extend(token_result.warnings)

    if token_result.timed_out:
        return SandboxExecutionResult(
            success=False,
            runner_mode=EFFECTIVE_MODE_RESTRICTED_TOKEN,
            requested_runner_mode=MODE_RESTRICTED_TOKEN,
            sandbox_enforced=True,
            job_object_enforced=token_result.job_object_assigned,
            warnings=warnings,
            timed_out=True,
            error=f"Execution timed out after {timeout} seconds.",
            raw_stdout=stdout_text,
            stderr=stderr_text,
            returncode=token_result.returncode,
            execution_time_ms=elapsed_ms,
        )

    parsed_output: Any = stdout_text.strip()
    if parsed_output:
        try:
            parsed_output = json.loads(parsed_output)
        except Exception:
            pass

    success = token_result.returncode == 0
    if (
        isinstance(parsed_output, dict)
        and "error" in parsed_output
        and parsed_output.get("error")
    ):
        if not parsed_output.get("success", True):
            success = False

    return SandboxExecutionResult(
        success=success,
        output=parsed_output,
        raw_stdout=stdout_text,
        stderr=stderr_text,
        returncode=token_result.returncode,
        execution_time_ms=elapsed_ms,
        runner_mode=EFFECTIVE_MODE_RESTRICTED_TOKEN,
        requested_runner_mode=MODE_RESTRICTED_TOKEN,
        sandbox_enforced=True,
        job_object_enforced=token_result.job_object_assigned,
        warnings=warnings,
    )
