"""Runtime network egress guard for skill child processes.

WHY THIS EXISTS
---------------
A Windows Restricted Token cannot filter network traffic. It removes
privileges; it does not stop a socket. So the network half of "skill
permissions" has to be enforced somewhere the child cannot simply ignore --
at the interpreter boundary.

HOW IT IS ENFORCED (and what that really means)
-----------------------------------------------
:func:`install_network_guard_dir` writes a throwaway directory containing

* ``sitecustomize.py`` -- executed by CPython automatically at interpreter
  startup, *before* the skill's own module code runs, and
* a copy of this module as ``cog_network_guard.py``.

The runner puts that directory at the FRONT of ``PYTHONPATH`` for the child.
CPython imports ``sitecustomize`` from there, which installs the socket hooks
below. The enforcement is therefore:

* REAL for any Python process started by the skill that inherits this
  environment -- including grandchildren, because ``PYTHONPATH`` is inherited.
  ``socket.socket.connect``, ``socket.create_connection``,
  ``socket.getaddrinfo`` and ``socket.gethostbyname`` all go through a
  host allowlist, and DNS resolution for a non-allowed host fails too, so a
  raw-IP fallback after a name lookup is also closed.
* NOT REAL against a child that deliberately mutates ``sys.path`` to drop the
  guard directory, or that speaks raw sockets/native code by another route,
  because a Python-level patch cannot make itself tamper-proof. Genuine kernel
  or firewall-level egress control would need Windows Firewall rules,
  AppContainer capabilities or a container -- none of which are implemented
  here. This file must never be described as OS-level network isolation.

The guard is only installed when the policy decision actually granted a network
capability. If it was denied, the runner refuses to start the process at all,
so no "guard" is needed to keep the promise.
"""

from __future__ import annotations

import os
import shutil
import socket
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

WILDCARD = "*"
ENV_ALLOW_HOSTS = "COG_SKILL_NETWORK_ALLOW_HOSTS"
ENV_GUARD_ACTIVE = "COG_SKILL_NETWORK_GUARD_ACTIVE"
ENV_POLICY_LABEL = "COG_SKILL_NETWORK_POLICY"

SITECUSTOMIZE_TEMPLATE = '''"""Auto-generated: installs the skill network guard at interpreter start."""
import os
import sys

_guard_dir = os.path.dirname(os.path.abspath(__file__))
if _guard_dir not in sys.path:
    sys.path.insert(0, _guard_dir)

# FAIL CLOSED. This is subtle and load-bearing:
#
# CPython does NOT abort startup when sitecustomize raises -- it prints
# "Error in sitecustomize" to stderr and keeps going, which would leave the
# skill running with UNRESTICTED network access while the caller believed
# egress was being filtered. So a bare ``raise`` is not sufficient here.
#
# Instead we hard-kill the interpreter with os._exit() before any of the
# skill's own module code is imported. os._exit() skips atexit handlers and
# cannot be swallowed by the skill, so the child dies non-zero and the skill
# body never executes.
_GUARD_EXIT_CODE = 78  # EX_CONFIG, distinct from a genuine skill failure

try:
    import cog_network_guard as _guard

    _guard.install()
except BaseException as _exc:  # noqa: BLE001 - deliberate catch-all
    try:
        sys.stderr.write(
            "[cog-network-guard] failed to install network egress guard: "
            + repr(_exc) + chr(10)
        )
        sys.stderr.flush()
    except BaseException:
        pass
    os._exit(_GUARD_EXIT_CODE)
'''


def parse_hosts(raw: str) -> List[str]:
    if not raw:
        return []
    hosts = []
    for item in raw.replace(";", ",").split(","):
        entry = item.strip().lower()
        if not entry:
            continue
        if entry == WILDCARD:
            hosts.append(WILDCARD)
        else:
            hosts.append(entry.lstrip("*.").rstrip("."))
    return hosts


def host_is_allowed(host: str, allowed: Iterable[str]) -> bool:
    candidate = (host or "").strip().lower().rstrip(".")
    if not candidate:
        return False
    for entry in allowed:
        entry = (entry or "").strip().lower().rstrip(".")
        if entry == WILDCARD:
            return True
        if not entry:
            continue
        if candidate == entry or candidate.endswith("." + entry):
            return True
    return False


class NetworkEgressDenied(PermissionError):
    """Raised inside the child when a skill reaches for a non-allowed host."""


def _current_allowed_hosts() -> List[str]:
    return parse_hosts(os.environ.get(ENV_ALLOW_HOSTS, ""))


def install() -> None:
    """Patches the socket layer in the *current* interpreter."""
    if os.environ.get(ENV_GUARD_ACTIVE) == "1":
        return
    os.environ[ENV_GUARD_ACTIVE] = "1"

    allowed = _current_allowed_hosts()
    if not allowed:
        # Defence in depth: guard installed with an empty allowlist means no
        # egress at all. This should not happen because the runner denies the
        # run before spawning, but failing shut here is correct.
        os.environ[ENV_POLICY_LABEL] = "deny-all (empty allowlist)"

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = socket.create_connection
    original_getaddrinfo = socket.getaddrinfo
    original_gethostbyname = socket.gethostbyname

    def _check(host: object) -> None:
        current = _current_allowed_hosts()
        text = str(host)
        if not host_is_allowed(text, current):
            raise NetworkEgressDenied(
                f"Network egress denied by skill policy: host '{text}' is not in "
                f"the allowlist ({ENV_ALLOW_HOSTS})."
            )

    def connect(self, address):  # type: ignore[no-untyped-def]
        try:
            _check(address[0] if isinstance(address, tuple) else address)
        except IndexError:
            pass
        return original_connect(self, address)

    def connect_ex(self, address):  # type: ignore[no-untyped-def]
        try:
            _check(address[0] if isinstance(address, tuple) else address)
        except IndexError:
            pass
        return original_connect_ex(self, address)

    def create_connection(address, *args, **kwargs):  # type: ignore[no-untyped-def]
        try:
            _check(address[0] if isinstance(address, tuple) else address)
        except IndexError:
            pass
        return original_create_connection(address, *args, **kwargs)

    def getaddrinfo(host, *args, **kwargs):  # type: ignore[no-untyped-def]
        if host is not None and str(host) not in {"", None}:
            _check(host)
        return original_getaddrinfo(host, *args, **kwargs)

    def gethostbyname(hostname):  # type: ignore[no-untyped-def]
        _check(hostname)
        return original_gethostbyname(hostname)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.create_connection = create_connection
    socket.getaddrinfo = getaddrinfo
    socket.gethostbyname = gethostbyname


def install_network_guard_dir(temp_dir: Path, allow_hosts: Iterable[str]) -> Path:
    """Materialises the guard directory inside the per-run temp workspace.

    Returns the directory to prepend to ``PYTHONPATH``.
    """
    guard_dir = Path(temp_dir) / "_cog_netguard"
    guard_dir.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve()
    shutil.copyfile(source, guard_dir / "cog_network_guard.py")
    (guard_dir / "sitecustomize.py").write_text(SITECUSTOMIZE_TEMPLATE, encoding="utf-8")
    hosts = ",".join(sorted({h.strip().lower() for h in allow_hosts if h.strip()}))
    return guard_dir


def prepend_guard_to_pythonpath(env: dict, guard_dir: Path) -> dict:
    existing = env.get("PYTHONPATH", "")
    parts = [str(guard_dir)] + ([existing] if existing else [])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


__all__ = [
    "ENV_ALLOW_HOSTS",
    "WILDCARD",
    "ENV_GUARD_ACTIVE",
    "ENV_POLICY_LABEL",
    "NetworkEgressDenied",
    "host_is_allowed",
    "install",
    "install_network_guard_dir",
    "parse_hosts",
    "prepend_guard_to_pythonpath",
]
