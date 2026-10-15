"""ACE read/copy helpers for the Windows DACL writer.

Split out of :mod:cl_guard_winapi so the ctypes bindings and the ACE
manipulation logic stay independently readable. This module is an internal
implementation detail: import `acl_guard` instead.
"""

from __future__ import annotations

from typing import Any

from .acl_types import AclPlanError


class _AceCopyMixin:
    """Reads existing ACEs and assembles a new DACL buffer.

    Mixed into :class:cl_guard_winapi._WindowsAclApi, which supplies the
    ctypes handles (`self.ctypes`, `self.ACL`, `self.GetAce`, ...).
    """

    def _read_ace_header(self, ace_address):
        """Read (AceType, AceSize, AceFlags) straight from ACE memory.

        The layout is fixed and little-endian: 1 byte type, 1 byte flags,
        2 bytes size. Reading the raw bytes avoids the extra pointer
        indirection that a ctypes structure cast introduces for the
        `c_void_p` container GetAce writes into.
        """
        ctypes = self.ctypes
        raw = ctypes.string_at(ace_address, 4)
        return (
            int(raw[0]),
            int.from_bytes(raw[2:4], "little"),
            int(raw[1]),
        )

    def _fail(self, api_name: str, context: str) -> AclPlanError:
        code = self.ctypes.get_last_error()
        raise AclPlanError(
            f"{api_name} failed for {context} (Win32 error {code}). "
            "If this is 5 (access denied) the current process does not hold "
            "WRITE_DAC on the workspace; this build never elevates, so the run "
            "is refused rather than attempted without the ACL."
        )

    # -- SID resolution ---------------------------------------------------
    def _copy_acl_with_extra_ace(self, path, sid, mask, inheritable):
        """Build a new DACL = every existing ACE + one allow ACE for ``sid``.

        ``SetEntriesInAclW`` is deliberately not used. Its ``TRUSTEE_W``
        ``ptstrName`` member is declared ``LPWSTR`` but must hold a *pointer to
        SID bytes* under ``TRUSTEE_IS_SID``; handing it SID memory through a
        ``ctypes.cast`` produces Win32 error 87/1008 depending on struct
        packing. Assembling the ACL buffer by hand keeps the trustee as raw SID
        bytes, which is exactly what ``ACCESS_ALLOWED_ACE`` stores.
        """
        ctypes = self.ctypes
        descriptor, old_dacl = self._get_descriptor(path)
        header_size = ctypes.sizeof(self.ACL)
        ace_header_size = ctypes.sizeof(self.ACE_HEADER)
        sid_len = self.GetLengthSid(sid.pointer)
        if not sid_len:
            self._best_effort_restore(path, descriptor)
            self.free_descriptor(descriptor)
            self._fail("GetLengthSid", "the sandbox principal")

        new_ace_size = self.ACCESS_ALLOWED_ACE_HEADER_SIZE + sid_len
        if new_ace_size > 0xFF:
            self._best_effort_restore(path, descriptor)
            self.free_descriptor(descriptor)
            raise AclPlanError(
                "The resolved SID is too large for a single ACCESS_ALLOWED_ACE "
                f"({sid_len} bytes); refusing to write {path!r}."
            )
        flags = (
            self.CONTAINER_INHERIT_ACE | self.OBJECT_INHERIT_ACE
            if inheritable else 0
        )

        # Collect the raw bytes of every ACE we must preserve. Replacing the
        # DACL wholesale would silently drop the owner/Administrators entries
        # the workspace already relies on.
        explicit_deny = []
        explicit_allow = []
        inherited_deny = []
        inherited_allow = []
        ace_count = 0
        if old_dacl:
            if not self.IsValidAcl(old_dacl):
                self._best_effort_restore(path, descriptor)
                self.free_descriptor(descriptor)
                raise AclPlanError(
                    f"The existing DACL on {path!r} is malformed; refusing to "
                    "rebuild it."
                )
            size_info = self.ACL_SIZE_INFORMATION()
            if not self.GetAclInformation(
                old_dacl, ctypes.byref(size_info), ctypes.sizeof(size_info),
                self.ACL_SIZE_INFORMATION_CLASS,
            ):
                self._best_effort_restore(path, descriptor)
                self.free_descriptor(descriptor)
                self._fail("GetAclInformation", repr(path))
            for index in range(size_info.AceCount):
                ace_ptr = ctypes.c_void_p()
                if not self.GetAce(old_dacl, index, ctypes.byref(ace_ptr)):
                    self._best_effort_restore(path, descriptor)
                    self.free_descriptor(descriptor)
                    self._fail("GetAce", f"ACE {index} of {path!r}")
                # GetAce hands back the *address of the ACE itself*, so the
                # header must be read from that address. Casting the
                # ctypes.c_void_p container instead reads one indirection too
                # many and yields AceType/AceSize/AceFlags shifted by a byte,
                # which silently truncates every preserved ACE and makes the
                # rebuilt DACL fail IsValidAcl().
                ace_address = ace_ptr.value
                if not ace_address:
                    self._best_effort_restore(path, descriptor)
                    self.free_descriptor(descriptor)
                    raise AclPlanError(
                        f"ACE {index} on {path!r} resolved to a null address; "
                        "refusing to copy it into a new DACL."
                    )
                ace_type, ace_size, ace_flags = self._read_ace_header(
                    ace_address
                )
                if ace_size < ace_header_size:
                    self._best_effort_restore(path, descriptor)
                    self.free_descriptor(descriptor)
                    raise AclPlanError(
                        f"ACE {index} on {path!r} reports AceSize {ace_size}, "
                        "which is smaller than an ACE header; refusing to copy "
                        "it into a new DACL."
                    )
                if ace_type not in self.SUPPORTED_ACE_TYPES:
                    self._best_effort_restore(path, descriptor)
                    self.free_descriptor(descriptor)
                    raise AclPlanError(
                        f"ACE {index} on {path!r} has unsupported AceType "
                        f"0x{ace_type:02x}; refusing to rebuild the DACL "
                        "rather than risk weakening it."
                    )
                # GetAce/AceSize describes the ACE *payload* only. The ACL
                # buffer itself is DWORD aligned, so every ACE except the
                # last one is followed by up to three padding bytes that are
                # not included in AceSize. Copying only AceSize bytes drops
                # that padding, the rebuilt DACL ends up with misaligned ACE
                # offsets, and IsValidAcl() rejects it. Copy the full aligned
                # storage span instead and keep the padded bytes verbatim.
                stored_len = (ace_size + 3) & ~3
                raw = ctypes.string_at(ace_address, stored_len)
                ace_count += 1
                # Windows requires the canonical ACE order: explicit deny,
                # explicit allow, inherited deny, inherited allow. Appending
                # the new explicit allow after inherited entries makes
                # IsValidAcl() reject the whole DACL, so bucket every
                # preserved ACE by its canonical slot and rejoin them around
                # our new explicit allow ACE.
                inherited_flag = bool(ace_flags & self.INHERITED_ACE)
                allow_flag = ace_type in (
                    self.ACCESS_ALLOWED_ACE_TYPE,
                    self.ACCESS_ALLOWED_OBJECT_ACE_TYPE,
                )
                if not inherited_flag and not allow_flag:
                    explicit_deny.append(raw)
                elif not inherited_flag and allow_flag:
                    explicit_allow.append(raw)
                elif inherited_flag and not allow_flag:
                    inherited_deny.append(raw)
                else:
                    inherited_allow.append(raw)

        preserved_explicit_deny = b"".join(explicit_deny)
        preserved_explicit_allow = b"".join(explicit_allow)
        preserved_inherited_deny = b"".join(inherited_deny)
        preserved_inherited_allow = b"".join(inherited_allow)
        preserved_explicit = preserved_explicit_deny + preserved_explicit_allow
        preserved_inherited = (
            preserved_inherited_deny + preserved_inherited_allow
        )

        # The new ACE is inserted into the explicit-allow bucket, so it needs
        # its own DWORD alignment padding after its payload as well.
        new_ace_stored = (new_ace_size + 3) & ~3
        total = header_size + len(preserved_explicit) + new_ace_stored + len(
            preserved_inherited
        )
        # ACL buffers are DWORD aligned; round up so IsValidAcl is satisfied.
        total = (total + 3) & ~3
        buffer = self.LocalAlloc(self.LMEM_ZEROINIT, total)
        if not buffer:
            self.free_descriptor(descriptor)
            raise AclPlanError(
                "LocalAlloc failed while building the sandbox DACL for "
                f"{path!r} (error {ctypes.get_last_error()})."
            )

        acl = self.ACL.from_address(buffer)
        acl.AclRevision = self.ACL_REVISION
        acl.Sbz1 = 0
        acl.AclSize = total
        acl.AceCount = ace_count + 1
        acl.Sbz2 = 0

        offset = header_size
        if preserved_explicit:
            ctypes.memmove(
                buffer + offset, preserved_explicit, len(preserved_explicit)
            )
            offset += len(preserved_explicit)

        # ACE layout: 4 bytes ACE_HEADER, 4 bytes ACCESS_MASK, then the SID.
        # ``sid.pointer`` is already the address of the SID bytes.
        mask_value = ctypes.c_uint32(int(mask))
        # Write the header as raw little-endian bytes; going through the
        # ctypes structure is what made the rebuilt DACL invalid.
        ctypes.memmove(
            buffer + offset,
            bytes([
                self.ACCESS_ALLOWED_ACE_TYPE,
                flags & 0xFF,
                new_ace_size & 0xFF,
                (new_ace_size >> 8) & 0xFF,
            ]),
            ace_header_size,
        )
        ctypes.memmove(
            buffer + offset + ace_header_size,
            ctypes.byref(mask_value),
            ctypes.sizeof(mask_value),
        )
        ctypes.memmove(
            buffer + offset + self.ACCESS_ALLOWED_ACE_HEADER_SIZE,
            sid.pointer,
            sid_len,
        )
        offset += new_ace_stored

        if preserved_inherited:
            ctypes.memmove(
                buffer + offset, preserved_inherited, len(preserved_inherited)
            )

        if not self.IsValidAcl(buffer):
            self.LocalFree(buffer)
            self._best_effort_restore(path, descriptor)
            self.free_descriptor(descriptor)
            raise AclPlanError(
                f"The DACL built for {path!r} failed IsValidAcl; it was never "
                "written."
            )
        return descriptor, buffer
