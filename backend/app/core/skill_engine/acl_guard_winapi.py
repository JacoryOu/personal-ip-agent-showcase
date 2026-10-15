"""Windows Security API bindings (ctypes only, no third-party deps).

The ``_AclApi`` interface lets the planner/enforcer in ``acl_guard`` be
unit-tested against a fake on any platform, and lets a non-Windows host fail
closed instead of pretending. Only this module talks to advapi32.
"""

from __future__ import annotations

import os
from typing import Any, Sequence

from .acl_guard_winapi_ace import _AceCopyMixin
from .acl_guard_winapi_bindings import install_bindings
from .acl_types import AclPlanError, SidHandle


# ---------------------------------------------------------------------------
# Windows Security API bindings
# ---------------------------------------------------------------------------
#
# Only ctypes is used; there is no third-party dependency. Everything lives
# behind a small interface (``_AclApi``) so the enforcement logic above can be
# unit-tested against a fake on any platform, and so a non-Windows host fails
# closed instead of pretending.

_RIGHTS_MASK = {
    # Generic bits are intentional: the object manager maps them per object
    # type, so the same entry means "read" on a file and "list directory" on a
    # container.
    "read": 0x80000000,   # GENERIC_READ
    "write": 0x40000000,  # GENERIC_WRITE
    "execute": 0x20000000,  # GENERIC_EXECUTE
    "delete": 0x00010000,  # DELETE
}


def rights_to_mask(rights: Sequence[str]) -> int:
    """Translate plan rights into an access mask. Unknown rights are refused."""
    mask = 0
    for right in rights:
        key = right.strip().lower()
        if key not in _RIGHTS_MASK:
            raise AclPlanError(
                f"Unknown ACL right {right!r}. Refusing to guess an access mask."
            )
        mask |= _RIGHTS_MASK[key]
    if not mask:
        raise AclPlanError("An empty access mask was requested; refusing to write it.")
    return mask


class _AclApi:
    """Interface the planner/enforcer depends on."""

    name = "base"

    def resolve_sid(self, principal: str) -> SidHandle:
        raise NotImplementedError

    def apply_allow_rules(
        self, path: str, sid: SidHandle, mask: int, inheritable: bool
    ):
        """Write ``mask`` for ``sid`` into the path's DACL.

        Returns the *original* security descriptor, owned by the caller and
        required for rollback.
        """
        raise NotImplementedError

    def verify_allow_rules(self, path: str, sid: SidHandle, mask: int) -> bool:
        """Read the DACL back and confirm the ACE really landed."""
        raise NotImplementedError

    def _best_effort_restore(self, path: str, descriptor: Any) -> None:
        """Last-ditch attempt to restore ``descriptor``; never raises."""
        try:
            self.set_dacl(path, descriptor)
        except Exception:
            pass

    def set_dacl(self, path: str, descriptor: Any) -> None:
        raise NotImplementedError

    def free_descriptor(self, descriptor: Any) -> None:
        raise NotImplementedError


class _UnsupportedApi(_AclApi):
    """Non-Windows (or missing advapi32) stand-in that always fails closed."""

    name = "unsupported"

    def _refuse(self, what: str) -> "AclPlanError":
        return AclPlanError(
            f"NTFS ACL enforcement requested but {what} is unavailable on this "
            "host (os.name != 'nt'). No ACL was written and the run is refused "
            "rather than silently degraded."
        )

    def resolve_sid(self, principal: str) -> SidHandle:
        raise self._refuse("the Windows security API")

    def _best_effort_restore(self, path: str, descriptor: Any) -> None:
        return None

    def verify_allow_rules(self, path, sid, mask) -> bool:
        raise self._refuse("the Windows security API")

    def set_dacl(self, path, descriptor) -> None:
        raise self._refuse("the Windows security API")

    def free_descriptor(self, descriptor) -> None:
        return None


class _WindowsAclApi(_AceCopyMixin, _AclApi):
    """Real ctypes bindings. Instantiated only on Windows."""

    name = "windows"

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self.ctypes = ctypes
        self.wintypes = wintypes

        self._advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        install_bindings(self)

    # -- helpers ----------------------------------------------------------
    def resolve_sid(self, principal: str) -> SidHandle:
        text = (principal or "").strip()
        if not text:
            raise AclPlanError("An empty principal cannot be resolved to a SID.")
        if text.upper().startswith("S-"):
            sid_ptr = self.ctypes.c_void_p()
            if not self.ConvertStringSidToSidW(text, self.ctypes.byref(sid_ptr)):
                raise AclPlanError(
                    f"{text!r} is not a valid SID string (ConvertStringSidToSidW "
                    f"failed, error {self.ctypes.get_last_error()}). No ACL was "
                    "written."
                )
            if not self.IsValidSid(sid_ptr):
                self.LocalFree(sid_ptr)
                raise AclPlanError(f"ConvertStringSidToSidW produced an invalid SID for {text!r}.")
            canonical = self._sid_to_string(sid_ptr)
            return SidHandle(sid_ptr, canonical, self.LocalFree)

        # An account name: resolve an account that ALREADY exists. This build
        # never creates one, so an unknown account is a hard failure.
        needed = self.wintypes.DWORD(0)
        ref_type = self.wintypes.DWORD(1)  # SID_TYPE_USER
        # Probe for the required size instead of assuming a fixed 68-byte SID:
        # domain SIDs and well-known SIDs do not share one length.
        self.LookupAccountNameW(
            None, text, None, self.ctypes.byref(needed), None, None,
            self.ctypes.byref(ref_type),
        )
        if needed.value == 0:
            needed = self.wintypes.DWORD(68)
        buffer = self.ctypes.create_string_buffer(needed.value)
        size = self.wintypes.DWORD(needed.value)
        if not self.LookupAccountNameW(
            None, text, buffer, self.ctypes.byref(size), None, None,
            self.ctypes.byref(ref_type),
        ):
            raise AclPlanError(
                f"Sandbox account {text!r} could not be resolved by "
                f"LookupAccountNameW (error {self.ctypes.get_last_error()}). "
                "This build never creates accounts and never elevates, so an "
                "unknown or unresolvable principal is refused."
            )
        if not self.IsValidSid(self.ctypes.cast(buffer, self.ctypes.c_void_p)):
            raise AclPlanError(
                f"LookupAccountNameW returned an invalid SID for {text!r}."
            )
        # The lookup wrote into a Python buffer that dies with this frame. Copy
        # the SID into LocalAlloc'd memory so the handle owns real, LocalFree-able
        # storage for the whole apply/verify/rollback window.
        sid_len = self.GetLengthSid(self.ctypes.cast(buffer, self.ctypes.c_void_p))
        if not sid_len:
            self._fail("GetLengthSid", repr(text))
        owned = self.LocalAlloc(self.LMEM_ZEROINIT, sid_len)
        if not owned:
            raise AclPlanError(
                f"LocalAlloc failed while copying the SID for {text!r} "
                f"(error {self.ctypes.get_last_error()})."
            )
        self.ctypes.memmove(owned, buffer, sid_len)
        handle = self.ctypes.cast(owned, self.ctypes.c_void_p)
        return SidHandle(handle, self._sid_to_string(handle), self.LocalFree)

    def _sid_to_string(self, sid_ptr) -> str:
        out = self.wintypes.LPWSTR()
        if not self.ConvertSidToStringSidW(sid_ptr, self.ctypes.byref(out)):
            self._fail("ConvertSidToStringSidW", "the resolved SID")
        try:
            return out.value
        finally:
            self.LocalFree(out)

    # -- descriptor IO ----------------------------------------------------
    def _get_descriptor(self, path: str):
        descriptor = self.ctypes.c_void_p()
        dacl = self.ctypes.c_void_p()
        # The real signature has nine parameters; omitting the trailing
        # pfDoesSelfRelative shifts every later argument left by one slot and
        # leaves the security descriptor NULL on return.
        self_relative = self.wintypes.BOOL()
        code = self.GetNamedSecurityInfoW(
            path, self.SE_FILE_OBJECT, self.DACL_SECURITY_INFORMATION,
            None, None, self.ctypes.byref(dacl), None,
            self.ctypes.byref(descriptor), self.ctypes.byref(self_relative),
        )
        if code != 0 or not descriptor.value:
            if descriptor.value:
                self.LocalFree(self._address_of(descriptor))
            self._fail(
                "GetNamedSecurityInfoW",
                f"{path!r} (cannot read the current DACL, so nothing could be "
                "rolled back)",
            )
        return descriptor, dacl


    def apply_allow_rules(self, path, sid, mask, inheritable):
        descriptor, new_dacl = self._copy_acl_with_extra_ace(
            path, sid, mask, inheritable
        )
        try:
            written = self.SetNamedSecurityInfoW(
                path, self.SE_FILE_OBJECT, self.DACL_SECURITY_INFORMATION,
                None, None, new_dacl, None,
            )
            if written != 0:
                self._fail("SetNamedSecurityInfoW", repr(path))
            # The original descriptor stays alive for the caller's rollback
            # handle; the DACL buffer we built is always ours to release.
            return descriptor
        except BaseException:
            # The write may or may not have partially landed; put the original
            # descriptor back before giving up so we never leave a
            # half-applied DACL behind.
            self._best_effort_restore(path, descriptor)
            self.free_descriptor(descriptor)
            raise
        finally:
            if new_dacl:
                self.LocalFree(new_dacl)

    def _best_effort_restore(self, path: str, descriptor: Any) -> None:
        try:
            self.set_dacl(path, descriptor)
        except Exception:
            # Best effort only. The caller is already failing closed and the
            # rollback handle path reports restore failures explicitly.
            pass

    def verify_allow_rules(self, path, sid, mask) -> bool:
        descriptor = self.ctypes.c_void_p()
        dacl = self.ctypes.c_void_p()
        self_relative = self.wintypes.BOOL()
        try:
            code = self.GetNamedSecurityInfoW(
                path, self.SE_FILE_OBJECT, self.DACL_SECURITY_INFORMATION,
                None, None, self.ctypes.byref(dacl), None,
                self.ctypes.byref(descriptor), self.ctypes.byref(self_relative),
            )
            if code != 0 or not descriptor.value:
                raise self._fail("GetNamedSecurityInfoW (verify)", repr(path))
            if not dacl:
                raise AclPlanError(
                    f"The DACL on {path} reads back as absent (NULL); the write "
                    "did not take effect."
                )
            if not self.IsValidAcl(dacl):
                raise AclPlanError(f"The DACL on {path} reads back malformed.")

            size_info = self.ACL_SIZE_INFORMATION()
            if not self.GetAclInformation(
                dacl, self.ctypes.byref(size_info), self.ctypes.sizeof(size_info),
                self.ACL_SIZE_INFORMATION_CLASS,
            ):
                raise self._fail("GetAclInformation", repr(path))

            for index in range(size_info.AceCount):
                ace_ptr = self.ctypes.c_void_p()
                if not self.GetAce(dacl, index, self.ctypes.byref(ace_ptr)):
                    raise self._fail("GetAce", f"ACE {index} of {path!r}")
                # GetAce fills a c_void_p container; the ACE lives at
                # ``ace_ptr.value``. Casting the container itself adds one
                # indirection too many and reads garbage (observed as an
                # access violation at 0xFFFFFFFFFFFFFFFF).
                if not ace_ptr.value:
                    raise AclPlanError(
                        f"ACE {index} on {path!r} resolved to a null address "
                        "during verification."
                    )
                ace_address = ace_ptr.value
                header = self._read_ace_header(ace_address)
                if header[0] != self.ACCESS_ALLOWED_ACE_TYPE:
                    continue
                if header[1] < self.ACCESS_ALLOWED_ACE_HEADER_SIZE:
                    raise AclPlanError(
                        f"ACE {index} on {path!r} is an ACCESS_ALLOWED_ACE of "
                        f"only {header[1]} bytes during verification."
                    )
                # The SID is *inline* variable-length data starting right
                # after the fixed header+mask. ACCESS_ALLOWED_ACE declares
                # SidStart as a c_void_p, so casting the struct and reading
                # that field dereferences the SID bytes as an address and
                # faults. Compute the real address instead.
                sid_address = ace_address + self.ACCESS_ALLOWED_ACE_HEADER_SIZE
                if not self.EqualSid(sid_address, sid.pointer):
                    continue
                # AccessMask is the DWORD sitting between the header and the
                # inline SID.
                ace_mask = int.from_bytes(
                    self.ctypes.string_at(
                        ace_address + self.ACCESS_ALLOWED_ACE_HEADER_SIZE - 4, 4
                    ),
                    "little",
                )
                if (ace_mask & mask) == mask:
                    return True
            return False
        finally:
            if descriptor:
                self.free_descriptor(descriptor)

    @staticmethod
    def _address_of(value: Any) -> Any:
        # GetNamedSecurityInfoW fills a c_void_p *container*; passing that
        # container straight to a Win32 call hands over the address of the
        # Python object instead of the security descriptor, which faults.
        # Always dereference before crossing the boundary.
        address = getattr(value, "value", value)
        if address is None:
            raise AclPlanError("null security descriptor passed to a Win32 call")
        return address

    def set_dacl(self, path: str, descriptor: Any) -> None:
        dacl = self.ctypes.c_void_p()
        present = self.wintypes.BOOL()
        defaulted = self.wintypes.BOOL()
        # Signature is (descriptor, pDaclPresent, pDacl, lpdaclDefaulted) --
        # the two out parameters must not be swapped, and every out parameter
        # must be a real pointer: passing None makes the API write to NULL.
        if not self.GetSecurityDescriptorDacl(
            self._address_of(descriptor),
            self.ctypes.byref(present),
            self.ctypes.byref(dacl),
            self.ctypes.byref(defaulted),
        ):
            self._fail("GetSecurityDescriptorDacl", repr(path))
        code = self.SetNamedSecurityInfoW(
            path, self.SE_FILE_OBJECT, self.DACL_SECURITY_INFORMATION,
            None, None, dacl, None,
        )
        if code != 0:
            self._fail("SetNamedSecurityInfoW (rollback)", repr(path))

    def free_descriptor(self, descriptor: Any) -> None:
        if descriptor is not None and getattr(descriptor, "value", descriptor):
            self.LocalFree(descriptor)
