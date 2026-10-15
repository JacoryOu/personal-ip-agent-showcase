"""ctypes structure definitions and advapi32/kernel32 bindings.

Split out of acl_guard_winapi so the enforcement logic and the raw Win32
binding surface can be reviewed independently. Nothing here is public:
acl_guard_winapi._WindowsAclApi stays the only entry point and keeps
every attribute name it has always exposed.
"""

from __future__ import annotations


def install_bindings(api) -> None:
    """Populate ``api`` with Win32 constants and bindings.

    The target must already expose ``api.ctypes`` and ``api.wintypes``.
    """
    ctypes = api.ctypes
    wintypes = api.wintypes
    # The extracted method body addressed every attribute through ``self``.
    # Alias the injected target locally so that spelling keeps working.
    self = api


    self._advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    self.SE_FILE_OBJECT = 1
    self.DACL_SECURITY_INFORMATION = 0x00000004
    self.OBJECT_INHERIT_ACE = 0x01
    self.CONTAINER_INHERIT_ACE = 0x02
    self.INHERITED_ACE = 0x10
    self.ACCESS_ALLOWED_ACE_TYPE = 0x00
    self.ACCESS_DENIED_ACE_TYPE = 0x01
    # Object-specific variants share the canonical allow/deny ordering.
    self.ACCESS_ALLOWED_OBJECT_ACE_TYPE = 0x05
    self.ACCESS_DENIED_OBJECT_ACE_TYPE = 0x06
    self.SUPPORTED_ACE_TYPES = frozenset({
        self.ACCESS_ALLOWED_ACE_TYPE,
        self.ACCESS_DENIED_ACE_TYPE,
        self.ACCESS_ALLOWED_OBJECT_ACE_TYPE,
        self.ACCESS_DENIED_OBJECT_ACE_TYPE,
    })
    self.ACL_SIZE_INFORMATION_CLASS = 0x02
    self.GENERIC_ALL = 0x10000000

    class ACL(ctypes.Structure):
        # struct _ACL { BYTE AclRevision; BYTE Sbz1; WORD AclSize;
        #               WORD AceCount; WORD Sbz2; }
        _fields_ = [
            ("AclRevision", ctypes.c_ubyte),
            ("Sbz1", ctypes.c_ubyte),
            ("AclSize", wintypes.WORD),
            ("AceCount", wintypes.WORD),
            ("Sbz2", wintypes.WORD),
        ]

    class ACL_SIZE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("AceCount", wintypes.DWORD),
            ("AclBytesInUse", wintypes.DWORD),
            ("AclBytesFree", wintypes.DWORD),
        ]

    class ACE_HEADER(ctypes.Structure):
        # Win32 layout is AceType(1) | AceFlags(1) | AceSize(2, LE).
        # Declaring AceSize before AceFlags silently transposes every
        # field and makes rebuilt DACLs fail IsValidAcl().
        _fields_ = [
            ("AceType", ctypes.c_ubyte),
            ("AceFlags", ctypes.c_ubyte),
            ("AceSize", wintypes.WORD),
        ]

    class ACCESS_ALLOWED_ACE(ctypes.Structure):
        _fields_ = [
            ("Header", ACE_HEADER),
            ("Mask", wintypes.DWORD),
            ("SidStart", ctypes.c_void_p),
        ]

    self.ACL = ACL
    self.ACL_SIZE_INFORMATION = ACL_SIZE_INFORMATION
    self.ACE_HEADER = ACE_HEADER
    self.ACCESS_ALLOWED_ACE = ACCESS_ALLOWED_ACE

    # ACL_REVISION is the only revision this code emits. We deliberately do
    # not use ACL_REVISION_DS or the object-specific ACE types.
    self.ACL_REVISION = 0x02
    # ACCESS_ALLOWED_ACE is 4 header bytes + 4 mask bytes + the SID.
    self.ACCESS_ALLOWED_ACE_HEADER_SIZE = 8

    # --- bindings -------------------------------------------------------
    self.LMEM_ZEROINIT = 0x0040

    self.LocalAlloc = self._kernel32.LocalAlloc
    self.LocalAlloc.argtypes = [wintypes.DWORD, ctypes.c_size_t]
    self.LocalAlloc.restype = ctypes.c_void_p

    self.LocalFree = self._kernel32.LocalFree
    self.LocalFree.argtypes = [ctypes.c_void_p]
    self.LocalFree.restype = ctypes.c_void_p

    self.ConvertStringSidToSidW = self._advapi32.ConvertStringSidToSidW
    self.ConvertStringSidToSidW.argtypes = [
        wintypes.LPWSTR, ctypes.POINTER(ctypes.c_void_p)
    ]
    self.ConvertStringSidToSidW.restype = wintypes.BOOL

    self.ConvertSidToStringSidW = self._advapi32.ConvertSidToStringSidW
    self.ConvertSidToStringSidW.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)
    ]
    self.ConvertSidToStringSidW.restype = wintypes.BOOL

    self.GetLengthSid = self._advapi32.GetLengthSid
    self.GetLengthSid.argtypes = [ctypes.c_void_p]
    self.GetLengthSid.restype = wintypes.DWORD

    self.IsValidSid = self._advapi32.IsValidSid
    self.IsValidSid.argtypes = [ctypes.c_void_p]
    self.IsValidSid.restype = wintypes.BOOL

    self.EqualSid = self._advapi32.EqualSid
    self.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    self.EqualSid.restype = wintypes.BOOL

    self.LookupAccountNameW = self._advapi32.LookupAccountNameW
    self.LookupAccountNameW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
    ]
    self.LookupAccountNameW.restype = wintypes.BOOL

    self.IsValidAcl = self._advapi32.IsValidAcl
    self.IsValidAcl.argtypes = [ctypes.c_void_p]
    self.IsValidAcl.restype = wintypes.BOOL

    self.GetAclInformation = self._advapi32.GetAclInformation
    self.GetAclInformation.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_int,
    ]
    self.GetAclInformation.restype = wintypes.BOOL

    self.GetAce = self._advapi32.GetAce
    self.GetAce.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)
    ]
    self.GetAce.restype = wintypes.BOOL

    self.GetNamedSecurityInfoW = self._advapi32.GetNamedSecurityInfoW
    self.GetNamedSecurityInfoW.argtypes = [
        wintypes.LPWSTR,
        ctypes.c_int,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),  # ppsidOwner
        ctypes.POINTER(ctypes.c_void_p),  # ppsidGroup
        ctypes.POINTER(ctypes.c_void_p),  # ppDacl
        ctypes.POINTER(ctypes.c_void_p),  # ppSacl
        ctypes.POINTER(ctypes.c_void_p),  # ppSecurityDescriptor
        ctypes.POINTER(wintypes.BOOL),   # pfDoesSelfRelative
    ]
    self.GetNamedSecurityInfoW.restype = wintypes.DWORD

    self.SetNamedSecurityInfoW = self._advapi32.SetNamedSecurityInfoW
    self.SetNamedSecurityInfoW.argtypes = [
        wintypes.LPWSTR,
        ctypes.c_int,
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    self.SetNamedSecurityInfoW.restype = wintypes.DWORD

    self.GetSecurityDescriptorDacl = self._advapi32.GetSecurityDescriptorDacl
    # BOOL GetSecurityDescriptorDacl(
    #   PSECURITY_DESCRIPTOR, LPBOOL pDaclPresent,
    #   PACL *pDacl, BOOL *lpdaclDefaulted);
    self.GetSecurityDescriptorDacl.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.BOOL),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.BOOL),
    ]
    self.GetSecurityDescriptorDacl.restype = wintypes.BOOL
