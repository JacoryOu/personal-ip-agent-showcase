"""Launching a child process under an already-created restricted token.

Stage 2 of the restricted-token flow. Takes a
:class:`~.restricted_token_api.RestrictedTokenInfo` produced by
:func:`~.restricted_token_api.create_restricted_token` and starts a child
through ``CreateProcessAsUserW`` with three anonymous pipes and mandatory Job
Object containment.

The restricted token itself is *not* isolation: no AppContainer, no ACLs, no
network boundary. Job Object containment limits the process tree; it does not
restrict what the root process may touch.
"""
from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .job_object import (
    JobObjectError,
    JobObjectInfo,
    assign_process,
    create_job_object,
    terminate_job,
)
from .restricted_token_api import (
    CREATE_NO_WINDOW,
    CREATE_UNICODE_ENVIRONMENT,
    HANDLE_FLAG_INHERIT,
    IS_WINDOWS,
    PROCESS_INFORMATION,
    STARTF_USESTDHANDLES,
    STARTUPINFO,
    WAIT_TIMEOUT,
    RestrictedTokenError,
    RestrictedTokenInfo,
    RestrictedTokenUnsupportedPlatform,
    _api,
    _close_handle,
    _last_error,
    ctypes,
    wintypes,
)

def _build_environment_block(env: Dict[str, str]) -> str:
    return "\x00".join(f"{key}={value}" for key, value in env.items()) + "\x00\x00"


def _quote_command(command: Sequence[str]) -> str:
    """Quote ``command`` for the Win32 ``CreateProcessAsUserW`` command line.

    We delegate to the CRT's own ``list2cmdline`` instead of hand-rolling the
    escaping. A hand-rolled version that doubles backslashes corrupts any
    argument containing them -- notably our JSON skill payload, whose ``\\uXXXX``
    escapes would reach the child as literal backslash-u sequences and silently
    change the skill's behaviour. ``list2cmdline`` implements the exact
    ``CommandLineToArgvW`` rules the child's C runtime uses, so what the parent
    builds is exactly what the child parses.
    """
    return subprocess.list2cmdline([str(item) for item in command])


@dataclass
class TokenProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    timed_out: bool
    token_info: RestrictedTokenInfo
    # Job Object containment status. ``job_object_assigned`` is True only when
    # a real job object was created and the child was bound to it. It is
    # reported separately and never changes ``SandboxExecutionResult.
    # sandbox_enforced``, which continues to mean "restricted token used".
    job_object_assigned: bool = False
    job_object_active_process_limit: Optional[int] = None
    warnings: List[str] = field(default_factory=list)


def run_process_with_restricted_token(
    token_info: RestrictedTokenInfo,
    command: Sequence[str],
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    input_data: Optional[bytes] = None,
    timeout: float = 15.0,
    job_object: Optional["JobObjectInfo"] = None,
    job_object_active_process_limit: Optional[int] = None,
) -> TokenProcessResult:
    """Launch ``command`` via ``CreateProcessAsUserW`` under ``token_info``.

    Only the three child-side pipe ends are inheritable; the parent closes them
    immediately after creation, so the child cannot write into our console or
    reopen parent-owned handles.
    """
    if not IS_WINDOWS:  # pragma: no cover - guarded by callers
        raise RestrictedTokenUnsupportedPlatform(
            "CreateProcessAsUserW is only available on Windows."
        )

    env = env if env is not None else dict(os.environ)

    stdin_r, stdin_w = wintypes.HANDLE(), wintypes.HANDLE()
    stdout_r, stdout_w = wintypes.HANDLE(), wintypes.HANDLE()
    stderr_r, stderr_w = wintypes.HANDLE(), wintypes.HANDLE()
    pi = PROCESS_INFORMATION()
    open_handles: List[object] = []
    # Hoisted above the ``try`` so the ``finally`` below can always reference
    # them, including on paths where the child was never created.
    job_object: Optional["JobObjectInfo"] = job_object
    owned_job = False

    try:
        for read_h, write_h in (
            (stdin_r, stdin_w), (stdout_r, stdout_w), (stderr_r, stderr_w)
        ):
            if not _api("CreatePipe")(ctypes.byref(read_h), ctypes.byref(write_h), None, 0):
                raise _last_error("CreatePipe")

        # Child-side ends: stdin_r (child reads), stdout_w, stderr_w.
        # Parent-side ends: stdin_w, stdout_r, stderr_r.
        for handle in (stdin_w, stdout_r, stderr_r):
            _api("SetHandleInformation")(handle, HANDLE_FLAG_INHERIT, 0)
        for handle in (stdin_r, stdout_w, stderr_w):
            if not _api("SetHandleInformation")(
                handle, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT
            ):
                raise _last_error("SetHandleInformation(mark inheritable)")
        open_handles = [stdin_r, stdin_w, stdout_r, stdout_w, stderr_r, stderr_w]

        si = STARTUPINFO()
        si.cb = ctypes.sizeof(STARTUPINFO)
        si.dwFlags = STARTF_USESTDHANDLES
        # Only the *child* ends are inheritable (see SetHandleInformation above),
        # so STARTUPINFO must reference those ends, not the parent-side ones.
        si.hStdInput = stdin_r
        si.hStdOutput = stdout_w
        si.hStdError = stderr_w

        cmdline = ctypes.create_unicode_buffer(_quote_command(command))
        env_block = ctypes.create_unicode_buffer(_build_environment_block(env))

        ok = _api("CreateProcessAsUserW")(
            token_info.handle,
            None,
            ctypes.cast(cmdline, ctypes.c_void_p),
            None,
            None,
            True,  # bInheritHandles: only the three marked pipe ends are inheritable
            CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW,
            ctypes.cast(env_block, ctypes.c_void_p),
            str(cwd) if cwd else None,
            ctypes.byref(si),
            ctypes.byref(pi),
        )
        if not ok:
            raise _last_error("CreateProcessAsUserW")

        # Drop the child's copies now that it owns them.
        for handle in (stdin_r, stdout_w, stderr_w):
            _close_handle(handle)
            if handle in open_handles:
                open_handles.remove(handle)
        if pi.hThread:
            _close_handle(pi.hThread)
            pi.hThread = None

        # --- Job Object containment -------------------------------------
        # A restricted token does not constrain children. When containment is
        # requested we create the job *before* reading output and bind the
        # freshly created process. A failed binding is fatal: we terminate the
        # process we just created rather than run it uncontained.
        # Job Object containment is ALWAYS applied on this path, not only when
        # the caller happened to pass a limit: ``active_process_limit=None``
        # means "do not cap the number of processes", NOT "skip the job". A
        # restricted token does not constrain grandchildren, so running without
        # a job is exactly the uncontained case we refuse.
        job_warnings: List[str] = []
        job_assigned = False
        if job_object is None:
            job_object = create_job_object(job_object_active_process_limit)
            owned_job = True
        try:
            assign_process(job_object, pi.hProcess)
        except JobObjectError as exc:
            _api("TerminateProcess")(pi.hProcess, 1)
            _api("WaitForSingleObject")(pi.hProcess, 5000)
            raise RestrictedTokenError(
                "Job Object containment could not be established: "
                f"{exc} The freshly created process was terminated and "
                "no uncontained fallback is permitted."
            ) from exc
        job_assigned = True
        job_warnings.append(
            "Job Object containment is ACTIVE for this run (KILL_ON_JOB_CLOSE, "
            "no BREAKAWAY_OK): the whole process tree is terminated on timeout "
            "or parent crash."
        )
        if job_object.active_process_limit is not None:
            job_warnings.append(
                "Job Object active process limit is "
                f"{job_object.active_process_limit}."
            )

        out_chunks: List[bytes] = []
        err_chunks: List[bytes] = []

        def _reader(handle, sink: List[bytes]) -> None:
            while True:
                buf = ctypes.create_string_buffer(4096)
                read = wintypes.DWORD(0)
                if not _api("ReadFile")(handle, buf, 4096, ctypes.byref(read), None):
                    break  # ERROR_BROKEN_PIPE simply ends the stream
                if read.value == 0:
                    break
                sink.append(buf.raw[: read.value])

        threads = [
            threading.Thread(target=_reader, args=(stdout_r, out_chunks), daemon=True),
            threading.Thread(target=_reader, args=(stderr_r, err_chunks), daemon=True),
        ]
        for thread in threads:
            thread.start()

        if input_data:
            def _writer() -> None:
                try:
                    offset = 0
                    while offset < len(input_data):
                        written = wintypes.DWORD(0)
                        chunk = input_data[offset: offset + 65536]
                        if not _api("WriteFile")(
                            stdin_w, chunk, len(chunk), ctypes.byref(written), None
                        ):
                            break
                        if written.value == 0:
                            break
                        offset += written.value
                finally:
                    _api("CloseHandle")(stdin_w)

            threading.Thread(target=_writer, daemon=True).start()
        else:
            _close_handle(stdin_w)
            if stdin_w in open_handles:
                open_handles.remove(stdin_w)

        timeout_ms = max(1, int(timeout * 1000))
        wait = _api("WaitForSingleObject")(pi.hProcess, timeout_ms)
        timed_out = wait == WAIT_TIMEOUT
        if timed_out:
            if job_assigned and not terminate_job(job_object, 1):
                job_warnings.append(
                    "Timed out and TerminateJobObject failed; only the root "
                    "process was terminated, so surviving descendants cannot "
                    "be ruled out."
                )
                _api("TerminateProcess")(pi.hProcess, 1)
            else:
                _api("TerminateProcess")(pi.hProcess, 1)
            _api("WaitForSingleObject")(pi.hProcess, 5000)

        for thread in threads:
            thread.join(timeout=5)

        code = wintypes.DWORD(0)
        _api("GetExitCodeProcess")(pi.hProcess, ctypes.byref(code))
        returncode = -1 if timed_out else code.value

        return TokenProcessResult(
            returncode=returncode,
            stdout=b"".join(out_chunks),
            stderr=b"".join(err_chunks),
            timed_out=timed_out,
            token_info=token_info,
            job_object_assigned=job_assigned,
            job_object_active_process_limit=(
                job_object.active_process_limit if job_object else None
            ),
            warnings=job_warnings,
        )
    finally:
        if pi.hProcess:
            _close_handle(pi.hProcess)
        for handle in open_handles:
            _close_handle(handle)
        # Release a job object we created ourselves. KILL_ON_JOB_CLOSE only
        # affects processes still assigned to the job, so closing it after
        # the child has exited does not alter the reported exit code.
        if owned_job and job_object is not None:
            job_object.close()

