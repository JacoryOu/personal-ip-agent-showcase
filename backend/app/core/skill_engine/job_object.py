"""Windows Job Object child-process containment for sandboxed skill runs.

WHAT THIS MODULE ACTUALLY DOES
------------------------------
A Job Object is a Win32 kernel container. When a process is assigned to a job,
Windows constrains that process *and every process it spawns*, and closing the
job handle with ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`` kills the whole tree.

This module wraps exactly the calls needed for skill containment, via
:mod:`ctypes` only:

1. ``CreateJobObjectW(NULL, NULL)`` -- an unnamed, non-inheritable job.
2. ``SetInformationJobObject(JobObjectExtendedLimitInformation, ...)`` with
   ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`` set, so the containment survives a
   crash of the parent: the OS reaps the tree when we drop the handle.
3. ``AssignProcessToJobObject(job, process)`` -- binds an *already created*
   process (from :func:`app.core.skill_engine.restricted_token.
   run_process_with_restricted_token`) to the job.
4. ``TerminateJobObject(job, exit_code)`` -- kills the whole tree on timeout,
   not only the root process.
5. ``CloseHandle`` -- releases the job.

WHY IT MATTERS
--------------
A restricted token limits *privileges* of the root process, but it does nothing
about child processes: a skill can spawn children that hold full user rights.
A job object closes that gap. This is the one Phase A containment guarantee
that needs **no administrator rights**.

WHAT IT DOES NOT DO
-------------------
* It is not a filesystem, registry, or network boundary.
* It does not change ``sandbox_enforced``: that flag still means exactly
  "a restricted token was created and used". Job containment is reported
  separately through :attr:`JobObjectInfo.assigned` and its own warnings.
* ``JOB_OBJECT_LIMIT_BREAKAWAY_OK`` is deliberately **not** set, so a child
  cannot ask to escape the job.
* Assigning a process that is already in a job (for example when this engine
  itself runs inside a CI job that forbids nesting) fails -- we fail closed and
  the caller terminates the freshly created process.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import List, Optional

IS_WINDOWS = sys.platform == "win32"


class JobObjectError(RuntimeError):
    """Raised when a job object cannot be created, configured, or used."""


class JobObjectUnsupportedPlatform(JobObjectError):
    """Raised when the platform has no usable Job Object support."""


# --- Win32 constants (documented values, stable across Windows versions) ----
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9

JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
# Not enabled. Listed so the intent is explicit and testable: enabling
# BREAKAWAY_OK would let a child process escape containment, which is exactly
# what this module exists to prevent.
JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00800000
# Not enabled by default. An active-process cap is available for operators who
# want one, but it is opt-in because it changes runtime behaviour.
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008

ERROR_NOT_SUPPORTED = 50


if IS_WINDOWS:  # pragma: no branch - platform guard
    import ctypes
    from ctypes import wintypes

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),  # ULONG_PTR
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _kernel32.CreateJobObjectW.argtypes = [
        ctypes.c_void_p, wintypes.LPCWSTR
    ]
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
    ]
    _kernel32.SetInformationJobObject.restype = wintypes.BOOL
    _kernel32.AssignProcessToJobObject.argtypes = [
        wintypes.HANDLE, wintypes.HANDLE
    ]
    _kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel32.TerminateJobObject.argtypes = [
        wintypes.HANDLE, wintypes.UINT
    ]
    _kernel32.TerminateJobObject.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL
else:  # pragma: no cover - non-Windows
    ctypes = None  # type: ignore
    wintypes = None  # type: ignore


def _last_error(action: str) -> JobObjectError:
    code = ctypes.get_last_error() if IS_WINDOWS else 0
    return JobObjectError(f"{action} failed (Win32 error {code}).")


def job_object_supported() -> bool:
    """True only when this process can really create and configure a job."""
    if not IS_WINDOWS:
        return False
    job = None
    try:
        job = create_job_object()
        return True
    except JobObjectError:
        return False
    finally:
        if job is not None:
            job.close()


@dataclass
class JobObjectInfo:
    """Truthful description of the job that was actually created."""

    handle: object = None
    created: bool = False
    kill_on_close: bool = False
    active_process_limit: Optional[int] = None
    assigned: bool = False
    assigned_pid: Optional[int] = None
    warnings: List[str] = field(default_factory=list)

    def close(self) -> None:
        # Closing the last handle to a job configured with KILL_ON_JOB_CLOSE
        # terminates every process still assigned to it.
        if IS_WINDOWS and self.handle:
            try:
                _kernel32.CloseHandle(self.handle)
            except Exception:
                pass
        self.handle = None

    def describe(self) -> dict:
        return {
            "created": self.created,
            "kill_on_close": self.kill_on_close,
            "active_process_limit": self.active_process_limit,
            "assigned": self.assigned,
            "assigned_pid": self.assigned_pid,
            "warnings": list(self.warnings),
        }


def create_job_object(
    active_process_limit: Optional[int] = None,
) -> JobObjectInfo:
    """Create and configure a job object with ``KILL_ON_JOB_CLOSE``.

    ``active_process_limit`` is opt-in; when given it must be >= 2 (the root
    process plus at least one child), otherwise it is rejected rather than
    silently clamped.
    """
    if not IS_WINDOWS:
        raise JobObjectUnsupportedPlatform(
            "Windows Job Objects require Windows; this platform is "
            f"'{sys.platform}'. No job was created."
        )

    if active_process_limit is not None:
        if not isinstance(active_process_limit, int) or active_process_limit < 2:
            raise JobObjectError(
                "active_process_limit must be an int >= 2 (the root process plus "
                f"at least one child); got {active_process_limit!r}."
            )

    handle = _kernel32.CreateJobObjectW(None, None)
    if not handle:
        raise _last_error("CreateJobObjectW")

    info = JobObjectInfo(handle=handle, created=True)
    try:
        limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags = (
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        # BREAKAWAY_OK is intentionally absent: children must not be able to
        # escape the job.
        if active_process_limit is not None:
            limits.BasicLimitInformation.LimitFlags |= (
                JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            )
            limits.BasicLimitInformation.ActiveProcessLimit = (
                active_process_limit
            )

        ok = _kernel32.SetInformationJobObject(
            handle,
            JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        )
        if not ok:
            raise _last_error("SetInformationJobObject(KILL_ON_JOB_CLOSE)")

        info.kill_on_close = True
        if active_process_limit is not None:
            info.active_process_limit = active_process_limit
        return info
    except Exception:
        info.close()
        raise


def assign_process(job: JobObjectInfo, process_handle) -> JobObjectInfo:
    """Assign an already-created process handle to ``job``.

    Fail closed: if Windows refuses the assignment (for example because the
    process already belongs to a job and nesting is not allowed), the caller
    receives a :class:`JobObjectError` and is expected to terminate the
    process it just created rather than run it uncontained.
    """
    if not IS_WINDOWS:  # pragma: no cover - guarded by callers
        raise JobObjectUnsupportedPlatform(
            "AssignProcessToJobObject is only available on Windows."
        )
    if job is None or not job.handle:
        raise JobObjectError("Cannot assign a process to a closed job object.")
    if not process_handle:
        raise JobObjectError(
            "Cannot assign a process: the process handle is empty."
        )

    if not _kernel32.AssignProcessToJobObject(job.handle, process_handle):
        code = ctypes.get_last_error()
        raise JobObjectError(
            "AssignProcessToJobObject failed (Win32 error "
            f"{code}). This process may already belong to a job object and "
            "nested jobs may be rejected on this system. Failing closed: the "
            "freshly created process must be terminated instead of running "
            "without job containment."
            + (
                " Windows reported 'not supported' for nested jobs."
                if code == ERROR_NOT_SUPPORTED
                else ""
            )
        )
    job.assigned = True
    return job


def terminate_job(job: JobObjectInfo, exit_code: int = 1) -> bool:
    """Terminate every process assigned to ``job``.

    Used on timeout so grandchildren die with the root process, which
    ``TerminateProcess`` alone does not guarantee. Returns False when the
    termination call itself failed, so the caller can add a warning rather
    than pretend the tree is gone.
    """
    if not IS_WINDOWS:  # pragma: no cover - guarded by callers
        return False
    if job is None or not job.handle:
        return False
    return bool(_kernel32.TerminateJobObject(job.handle, exit_code))


__all__ = [
    "IS_WINDOWS",
    "JobObjectError",
    "JobObjectUnsupportedPlatform",
    "JobObjectInfo",
    "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE",
    "JOB_OBJECT_LIMIT_BREAKAWAY_OK",
    "JOB_OBJECT_LIMIT_ACTIVE_PROCESS",
    "assign_process",
    "create_job_object",
    "job_object_supported",
    "terminate_job",
]
