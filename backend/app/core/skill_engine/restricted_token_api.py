"""Win32 restricted-token creation and verification (stage 1).

This module owns everything about *making* the token: opening our own primary
token, calling ``CreateRestrictedToken(DISABLE_MAX_PRIVILEGE)``, and verifying
the result by reading ``TokenIsRestricted`` / ``TokenGroups`` back. It never
launches a process -- see :mod:`.restricted_token_process` for that.

No AppContainer, no filesystem ACL, no network isolation. See
``docs/architecture/10_Sandbox_and_Permission_Model.md``.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional




class RestrictedTokenError(RuntimeError):
    """Raised when a real restricted token cannot be created or used."""


class RestrictedTokenUnsupportedPlatform(RestrictedTokenError):
    """Raised when the platform cannot host a Windows restricted token."""


from .restricted_token_winapi import (  # noqa: F401  (public re-export surface)
    CREATE_NO_WINDOW,
    DISABLE_MAX_PRIVILEGE,
    SE_GROUP_USE_FOR_DENY_ONLY,
    SID_AND_ATTRIBUTES,
    TOKEN_GROUPS,
    TokenGroups,
    TokenUser,
    TokenElevation,
    TokenIsRestricted,
    CREATE_UNICODE_ENVIRONMENT,
    HANDLE_FLAG_INHERIT,
    IS_WINDOWS,
    PROCESS_INFORMATION,
    STARTF_USESTDHANDLES,
    STARTUPINFO,
    TOKEN_ADJUST_DEFAULT,
    TOKEN_ASSIGN_PRIMARY,
    TOKEN_DUPLICATE,
    TOKEN_QUERY,
    WAIT_TIMEOUT,
    Win32UnavailableError,
    _advapi32,
    _api,
    _kernel32,
    ctypes,
    wintypes,
)

@dataclass
class RestrictedTokenInfo:
    """Truthful description of the token that was actually created."""

    handle: object = None
    is_restricted: bool = False
    privileges_disabled: bool = False
    deny_only_group_count: int = 0
    user_sid: Optional[str] = None
    caller_was_elevated: Optional[bool] = None
    warnings: List[str] = field(default_factory=list)

    def close(self) -> None:
        _close_handle(self.handle)
        self.handle = None

    def describe(self) -> Dict[str, object]:
        return {
            "is_restricted": self.is_restricted,
            "privileges_disabled": self.privileges_disabled,
            "deny_only_group_count": self.deny_only_group_count,
            "user_sid": self.user_sid,
            "caller_was_elevated": self.caller_was_elevated,
            "warnings": list(self.warnings),
        }

def _close_handle(handle) -> None:
    if IS_WINDOWS and handle:
        try:
            _api("CloseHandle")(handle)
        except Exception:
            pass


def _last_error(action: str) -> RestrictedTokenError:
    code = ctypes.get_last_error() if IS_WINDOWS else 0
    return RestrictedTokenError(f"{action} failed (Win32 error {code}).")


# --- token introspection ---------------------------------------------------

def _token_information(token, info_class: int) -> bytes:
    """Return the raw ``TOKEN_*_INFORMATION`` blob for ``token``.

    Note: ``TokenUser`` / ``TokenGroups`` blobs embed *pointers* into this
    very buffer, so any code that dereferences those SID pointers must keep
    the originating buffer alive. Use :func:`_token_information_buffer` when
    the pointers are needed.
    """
    raw, _buffer = _token_information_buffer(token, info_class)
    return raw


def _token_information_buffer(token, info_class: int):
    """Return ``(raw_bytes, backing_buffer)`` for a token information class.

    The live ``ctypes`` buffer is returned alongside the bytes because
    ``TOKEN_USER`` / ``TOKEN_GROUPS`` contain in-buffer pointers; handing back
    only a copy would leave those pointers dangling and produce opaque
    ``ERROR_INVALID_PARAMETER`` failures downstream.
    """
    size = wintypes.DWORD(0)
    ok = _api("GetTokenInformation")(token, info_class, None, 0, ctypes.byref(size))
    if not ok and size.value == 0:
        raise _last_error(f"GetTokenInformation(size probe, class={info_class})")
    buffer = ctypes.create_string_buffer(size.value)
    ok = _api("GetTokenInformation")(token, info_class, buffer, size, ctypes.byref(size))
    if not ok:
        raise _last_error(f"GetTokenInformation(class={info_class})")
    return buffer.raw, buffer


def _read_int32(raw: bytes) -> int:
    return int.from_bytes(raw[:4], "little", signed=True)


def _token_is_restricted(token) -> bool:
    return _read_int32(_token_information(token, TokenIsRestricted)) != 0


def _token_is_elevated(token) -> Optional[bool]:
    try:
        return _read_int32(_token_information(token, TokenElevation)) != 0
    except RestrictedTokenError:
        return None


def _sid_to_string(sid_ptr) -> Optional[str]:
    if not sid_ptr:
        return None
    out = wintypes.LPWSTR()
    if _api("ConvertSidToStringSidW")(ctypes.c_void_p(sid_ptr), ctypes.byref(out)):
        try:
            return out.value
        finally:
            _api("LocalFree")(out)
    return None


def _extract_user_sid(token_user_data: bytes) -> Optional[str]:
    # TOKEN_USER { SID_AND_ATTRIBUTES User ; } -> first pointer-sized slot.
    if len(token_user_data) < 8:
        return None
    sid_ptr = ctypes.cast(
        ctypes.c_char_p(token_user_data), ctypes.POINTER(ctypes.c_void_p)
    ).contents.value
    return _sid_to_string(sid_ptr)


def _group_sid_pointers(groups_data: bytes) -> List[int]:
    groups = ctypes.cast(
        ctypes.c_char_p(groups_data), ctypes.POINTER(TOKEN_GROUPS)
    ).contents
    base = ctypes.addressof(groups.Groups)
    size = ctypes.sizeof(SID_AND_ATTRIBUTES)
    result: List[int] = []
    for index in range(groups.GroupCount):
        entry = ctypes.cast(
            ctypes.c_void_p(base + index * size), ctypes.POINTER(SID_AND_ATTRIBUTES)
        ).contents
        if entry.Sid:
            result.append(entry.Sid)
    return result


def _count_deny_only_groups(token) -> int:
    """Count group SIDs on ``token`` that carry ``SE_GROUP_USE_FOR_DENY_ONLY``."""
    raw, _buffer = _token_information_buffer(token, TokenGroups)
    groups = ctypes.cast(
        ctypes.c_char_p(raw), ctypes.POINTER(TOKEN_GROUPS)
    ).contents
    base_addr = ctypes.addressof(groups.Groups)
    size = ctypes.sizeof(SID_AND_ATTRIBUTES)
    count = 0
    for index in range(groups.GroupCount):
        entry = ctypes.cast(
            ctypes.c_void_p(base_addr + index * size),
            ctypes.POINTER(SID_AND_ATTRIBUTES),
        ).contents
        if entry.Attributes & SE_GROUP_USE_FOR_DENY_ONLY:
            count += 1
    return count


# --- public API ------------------------------------------------------------

def restricted_token_supported() -> bool:
    """True only when this process can really build a restricted token."""
    if not IS_WINDOWS:
        return False
    try:
        token = create_restricted_token()
    except RestrictedTokenError:
        return False
    token.close()
    return True


def create_restricted_token() -> RestrictedTokenInfo:
    """Create a real restricted token derived from the current process token.

    Mechanism (single ``CreateRestrictedToken`` call, no manual SID list):

    * ``Flags = DISABLE_MAX_PRIVILEGE`` -- **every** privilege held by the
      caller (SeDebugPrivilege, SeImpersonatePrivilege, SeTcbPrivilege, ...) is
      disabled on the new token.
    * No ``SidsToDisable`` and no ``SidsToRestrict`` are passed. With an empty
      restricting SID list Windows makes the new token restricted by adding the
      restricting SIDs itself, which in practice denies group membership that
      was only usable through elevation (Administrators / S-1-5-32-544, the
      elevating SID). The deny-only outcome is *measured*, not assumed.

    An earlier draft of this module disabled every group SID explicitly with
    ``SE_GROUP_USE_FOR_DENY_ONLY``. That produced a genuinely restricted token
    but one that could not even start a non-elevated Python child
    (``STATUS_ACCESS_DENIED``), because the interactive / ``Users`` /
    ``Everyone`` memberships were stripped too. Dropping privileges must not
    stop a skill from running at all, so the narrower Windows-computed form is
    used instead.

    Fail closed: any Win32 failure raises instead of returning an unrestricted
    token, a token whose ``TokenIsRestricted`` flag reads 0 is rejected, and a
    token with no deny-only restricting SID is rejected too -- that would mean
    Windows produced no restriction at all on this machine.
    """
    if not IS_WINDOWS:
        raise RestrictedTokenUnsupportedPlatform(
            "Windows restricted tokens require Windows; this platform is "
            f"'{sys.platform}'. No token was created."
        )

    base = wintypes.HANDLE()
    final = wintypes.HANDLE()

    proc = _api("GetCurrentProcess")()
    if not _api("OpenProcessToken")(
        proc,
        TOKEN_QUERY | TOKEN_DUPLICATE | TOKEN_ASSIGN_PRIMARY | TOKEN_ADJUST_DEFAULT,
        ctypes.byref(base),
    ):
        raise _last_error("OpenProcessToken")

    try:
        if not _api("CreateRestrictedToken")(
            base,                   # 1 ExistingTokenHandle
            DISABLE_MAX_PRIVILEGE,  # 2 Flags
            0,                      # 3 DisableSidCount
            None,                   # 4 SidsToDisable
            0,                      # 5 DeletePrivilegeCount
            None,                   # 6 PrivilegesToDelete
            0,                      # 7 RestrictedSidCount
            None,                   # 8 SidsToRestrict
            ctypes.byref(final),    # 9 NewToken
        ):
            raise _last_error("CreateRestrictedToken(DISABLE_MAX_PRIVILEGE)")

        # Verify what actually came out instead of trusting the return value.
        is_restricted = _token_is_restricted(final)
        deny_only_count = _count_deny_only_groups(final)
        if not is_restricted:
            _close_handle(final)
            raise RestrictedTokenError(
                "CreateRestrictedToken reported success but TokenIsRestricted is 0; "
                "refusing to hand out an unrestricted token."
            )
        if deny_only_count == 0:
            _close_handle(final)
            raise RestrictedTokenError(
                "CreateRestrictedToken produced TokenIsRestricted=1 but no group "
                "SID is deny-only, so no restricting SID could be confirmed; "
                "refusing to claim a restriction that does not exist."
            )

        info = RestrictedTokenInfo(
            handle=final,
            is_restricted=is_restricted,
            privileges_disabled=True,
            deny_only_group_count=deny_only_count,
            user_sid=_extract_user_sid(_token_information(final, TokenUser)),
            caller_was_elevated=_token_is_elevated(final),
            warnings=[],
        )
        return info
    finally:
        _close_handle(base)
