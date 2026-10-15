"""Win32 constants, ctypes structures and API bindings for restricted tokens.

Split out of :mod:`.restricted_token_api` so token *semantics* can be reviewed
without the ~180 lines of raw ``ctypes`` declarations. ``restricted_token_api``
re-exports every name defined here, so all existing import paths keep working.
"""
from __future__ import annotations

import sys

IS_WINDOWS = sys.platform == "win32"


class Win32UnavailableError(RuntimeError):
    """Raised when a required Win32 export is missing on this host."""


# --- Win32 constants (documented values, stable across Windows versions) ----
TOKEN_QUERY = 0x0008
TOKEN_DUPLICATE = 0x0002
TOKEN_ASSIGN_PRIMARY = 0x0001
TOKEN_ADJUST_DEFAULT = 0x0004

DISABLE_MAX_PRIVILEGE = 0x00000001
SE_GROUP_USE_FOR_DENY_ONLY = 0x00000010

TokenUser = 1
TokenGroups = 2
TokenElevation = 20
TokenIsRestricted = 21

CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_NO_WINDOW = 0x08000000
STARTF_USESTDHANDLES = 0x00000100
HANDLE_FLAG_INHERIT = 0x00000001
WAIT_TIMEOUT = 0x00000102


if IS_WINDOWS:  # pragma: no branch - platform guard
    import ctypes
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

    class SID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]

    class TOKEN_GROUPS(ctypes.Structure):
        _fields_ = [("GroupCount", wintypes.DWORD), ("Groups", SID_AND_ATTRIBUTES * 1)]

    class STARTUPINFO(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD),
            ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD),
            ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD),
            ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("hProcess", wintypes.HANDLE),
            ("hThread", wintypes.HANDLE),
            ("dwProcessId", wintypes.DWORD),
            ("dwThreadId", wintypes.DWORD),
        ]

    def _api(name: str):
        """Resolve a Win32 export: token APIs live in advapi32, the rest in kernel32."""
        try:
            return getattr(_advapi32, name)
        except AttributeError:
            return getattr(_kernel32, name)

    _api("GetCurrentProcess").restype = wintypes.HANDLE
    _api("OpenProcessToken").argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)
    ]
    _api("OpenProcessToken").restype = wintypes.BOOL
    # BOOL CreateRestrictedToken(
    #     HANDLE ExistingTokenHandle, DWORD Flags,
    #     DWORD DisableSidCount, SID_AND_ATTRIBUTES *SidsToDisable,
    #     DWORD DeletePrivilegeCount, LUID_AND_ATTRIBUTES *PrivilegesToDelete,
    #     DWORD RestrictedSidCount, SID_AND_ATTRIBUTES *SidsToRestrict,
    #     HANDLE *NewToken);
    _api("CreateRestrictedToken").argtypes = [
        wintypes.HANDLE,                  # 1 ExistingTokenHandle
        wintypes.DWORD,                   # 2 Flags
        wintypes.DWORD,                   # 3 DisableSidCount
        ctypes.c_void_p,                  # 4 SidsToDisable
        wintypes.DWORD,                   # 5 DeletePrivilegeCount
        ctypes.c_void_p,                  # 6 PrivilegesToDelete
        wintypes.DWORD,                   # 7 RestrictedSidCount
        ctypes.c_void_p,                  # 8 SidsToRestrict
        ctypes.POINTER(wintypes.HANDLE),  # 9 NewToken
    ]
    _api("CreateRestrictedToken").restype = wintypes.BOOL
    _api("GetTokenInformation").argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    _api("GetTokenInformation").restype = wintypes.BOOL
    _api("ConvertSidToStringSidW").argtypes = [
        ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)
    ]
    _api("ConvertSidToStringSidW").restype = wintypes.BOOL
    _api("CreateProcessAsUserW").argtypes = [
        wintypes.HANDLE, wintypes.LPCWSTR, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD,
        ctypes.c_void_p, wintypes.LPCWSTR,
        ctypes.POINTER(STARTUPINFO), ctypes.POINTER(PROCESS_INFORMATION),
    ]
    _api("CreateProcessAsUserW").restype = wintypes.BOOL
    _api("CreatePipe").argtypes = [
        ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(wintypes.HANDLE),
        ctypes.c_void_p, wintypes.DWORD,
    ]
    _api("CreatePipe").restype = wintypes.BOOL
    _api("SetHandleInformation").argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD
    ]
    _api("SetHandleInformation").restype = wintypes.BOOL
    _api("ReadFile").argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
    ]
    _api("ReadFile").restype = wintypes.BOOL
    _api("WriteFile").argtypes = [
        wintypes.HANDLE, ctypes.c_char_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
    ]
    _api("WriteFile").restype = wintypes.BOOL
    _api("WaitForSingleObject").argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _api("WaitForSingleObject").restype = wintypes.DWORD
    _api("TerminateProcess").argtypes = [wintypes.HANDLE, wintypes.UINT]
    _api("CloseHandle").argtypes = [wintypes.HANDLE]
    _api("CloseHandle").restype = wintypes.BOOL
    _api("GetExitCodeProcess").argtypes = [
        wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)
    ]
    _api("GetExitCodeProcess").restype = wintypes.BOOL
    _api("LocalFree").argtypes = [wintypes.HANDLE]
else:  # pragma: no cover - non-Windows
    ctypes = None  # type: ignore
    wintypes = None  # type: ignore

    def _api(name: str):
        raise Win32UnavailableError(
            f"Win32 API '{name}' is unavailable on platform '{sys.platform}'."
        )
