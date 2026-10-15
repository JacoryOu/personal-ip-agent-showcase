"""Real Windows Restricted Token creation and restricted child-process launch.

WHAT THIS MODULE ACTUALLY DOES (and nothing more)
--------------------------------------------------
Win32 APIs used, through :mod:`ctypes` only (no third-party dependency):

1. ``OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY | TOKEN_DUPLICATE |
   TOKEN_ASSIGN_PRIMARY | TOKEN_ADJUST_DEFAULT, &base)`` -- opens *our own*
   primary token, so everything below is a strictly weaker derivative of the
   caller's identity and never requires admin rights or a service.
2. ``GetTokenInformation(base, TokenUser | TokenGroups)`` -- reads the user SID
   and every group SID of that token.
3. ``CreateRestrictedToken(base, DISABLE_MAX_PRIVILEGE, 0, NULL, 0, NULL, 0,
   NULL, &final)`` -- stage 1. ``DISABLE_MAX_PRIVILEGE`` disables **every**
   privilege the caller held (SeDebugPrivilege, SeImpersonatePrivilege,
   SeTcbPrivilege, ...) and, because no restricting SID list is supplied,
   Windows itself puts restricting SIDs on the new token (on a typical desktop
   token that denies Administrators / S-1-5-32-544 and the elevating SID).
   Ordinary per-user access is untouched, so a skill can still read and write
   files the user owns.
4. ``GetTokenInformation(final, TokenIsRestricted | TokenGroups)`` -- verify,
   never assume: the module refuses to return a token whose
   ``TokenIsRestricted`` flag reads 0, and reports the real deny-only count.
5. ``CreateProcessAsUserW(final, NULL, cmdline, ..., CREATE_UNICODE_ENVIRONMENT |
   CREATE_NO_WINDOW, envBlock, cwd, &si, &pi)`` with ``STARTF_USESTDHANDLES``
   over three anonymous pipes -- stage 2. Because the new token is a restricted
   *subset of our own primary token*, Windows accepts this without
   ``SeAssignPrimaryTokenPrivilege``.

Result: the skill script runs under a genuinely restricted token -- it
holds **no** privileges and cannot use the group memberships Windows put on
the restricted SID list (typically Administrators). It still keeps the
per-user access the account already had.

WHAT THIS MODULE DOES **NOT** DO -- read before trusting it
------------------------------------------------------------
* **No AppContainer.** ``CreateAppContainerProfile`` /
  ``PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES`` are not used.
* **No filesystem isolation.** No ACLs, no per-run capability directory. The
  child can still read and write everything the *user account itself* can,
  because restricted tokens do not deny ``FILE_WRITE_DATA`` on user-owned
  files.
* **No network restriction.** Sockets, DNS and outbound traffic still work.
* **No registry / clipboard / COM / child-process restriction.**
* **No machine virtualisation** -- that remains Windows Sandbox (WSB), which
  this runner still refuses rather than faking.
* **SKILL.md ``permissions`` metadata is still not enforced.**
* Windows only. Off Windows, :func:`create_restricted_token` raises instead of
  silently degrading.
"""
from __future__ import annotations

from .restricted_token_api import (
    DISABLE_MAX_PRIVILEGE,
    IS_WINDOWS,
    RestrictedTokenError,
    RestrictedTokenInfo,
    RestrictedTokenUnsupportedPlatform,
    create_restricted_token,
    restricted_token_supported,
)
from .restricted_token_process import (
    TokenProcessResult,
    run_process_with_restricted_token,
)

__all__ = [
    "IS_WINDOWS",
    "RestrictedTokenError",
    "RestrictedTokenUnsupportedPlatform",
    "RestrictedTokenInfo",
    "TokenProcessResult",
    "create_restricted_token",
    "restricted_token_supported",
    "run_process_with_restricted_token",
]
