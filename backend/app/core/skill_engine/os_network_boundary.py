"""OS-level network boundary policy layer (planning only).

WHAT THIS MODULE ACTUALLY DOES
------------------------------
It describes the Windows Firewall policy a sandboxed skill run *would* need,
and refuses to describe enforcement that does not exist. It is a pure
planning layer: no firewall rule is created, removed, or modified.

WHY THIS IS SEPARATE FROM ``network_guard.py``
-----------------------------------------------
``network_guard.py`` injects a ``sitecustomize`` module into the skill's
``PYTHONPATH``. That is a real, effective control **for Python children that
inherit the environment**. It is not an OS boundary: a skill can delete the
guard directory, restore ``socket.socket.connect``, call into native code, or
exec a non-Python binary. Windows Firewall does not have those holes, which
is why an OS-level boundary is the goal and why this module exists as the
specification of that goal.

ENFORCEMENT STATUS: **Not implemented.** ``NetworkBoundaryPlan.enforced`` is
hard-coded ``False``. ``enforce`` is accepted as a *request* and rejected with
a blocking reason, so no caller can mistake a plan for a live rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from .policy import NETWORK_READ, NETWORK_WRITE, WILDCARD_HOST


class NetworkBoundaryError(ValueError):
    """Raised when a network boundary cannot be honoured as requested."""


@dataclass
class NetworkRuleSpec:
    """A single intended firewall rule. Never applied by this build."""

    name: str
    action: str
    direction: str
    protocol: str
    remote_addresses: List[str]
    remote_ports: List[str]
    reason: str

    def describe(self) -> dict:
        return {
            "name": self.name,
            "action": self.action,
            "direction": self.direction,
            "protocol": self.protocol,
            "remote_addresses": list(self.remote_addresses),
            "remote_ports": list(self.remote_ports),
            "reason": self.reason,
        }


@dataclass
class NetworkBoundaryPlan:
    mode: str
    rules: List[NetworkRuleSpec] = field(default_factory=list)
    # Always False in this build: no firewall rule exists.
    enforced: bool = False
    warnings: List[str] = field(default_factory=list)
    blocking_errors: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blocking_errors

    def describe(self) -> dict:
        return {
            "mode": self.mode,
            "rules": [r.describe() for r in self.rules],
            "enforced": self.enforced,
            "warnings": list(self.warnings),
            "blocking_errors": list(self.blocking_errors),
        }


_DEFAULT_OUT_PORTS = ["80", "443"]


def build_network_boundary_plan(
    mode: str,
    allowlist: Iterable[str],
    granted_capabilities: Iterable[str],
    egress_allowed: bool,
) -> NetworkBoundaryPlan:
    """Compute the intended OS network boundary for one run.

    ``mode`` is one of ``disabled`` / ``dry_run`` / ``enforce``. ``enforce``
    does not silently degrade: it produces a plan *and* a blocking error, so
    the runner refuses to start rather than running uncontained.
    """
    mode = (mode or "disabled").strip().lower()
    if mode not in ("disabled", "dry_run", "enforce"):
        return NetworkBoundaryPlan(
            mode=mode,
            blocking_errors=[
                f"Unknown OS network boundary mode {mode!r}; expected one of "
                "'disabled', 'dry_run', 'enforce'."
            ],
        )

    hosts = [h.strip().lower() for h in allowlist if h and h.strip()]
    caps = {c.strip().lower() for c in granted_capabilities if c}

    rules: List[NetworkRuleSpec] = []
    warnings: List[str] = []
    errors: List[str] = []

    if mode == "enforce":
        errors.append(
            "An OS-level network boundary was requested via 'enforce', but this "
            "build creates no Windows Firewall rules. Refusing to run the skill "
            "with an unenforced request rather than reporting a boundary that "
            "does not exist."
        )

    if mode == "disabled":
        warnings.append(
            "OS network boundary is DISABLED: egress is bounded only by the "
            "in-process Python guard, which native code, a non-Python binary, or "
            "a skill that deletes its guard directory can bypass."
        )
        return NetworkBoundaryPlan(
            mode=mode, rules=rules, enforced=False, warnings=warnings,
            blocking_errors=errors,
        )

    # --- dry_run: describe the rules an enforcing implementation would add ---
    wildcard = WILDCARD_HOST in hosts
    if not egress_allowed:
        rules.append(
            NetworkRuleSpec(
                name="cog-skill-block-all-egress",
                action="BLOCK",
                direction="Outbound",
                protocol="TCP",
                remote_addresses=["*"],
                remote_ports=["*"],
                reason=(
                    "The permission policy granted no network capability or an "
                    "empty host allowlist, so the intended boundary is a deny-"
                    "all egress rule."
                ),
            )
        )
    else:
        ports = _DEFAULT_OUT_PORTS if NETWORK_READ in caps else []
        if NETWORK_WRITE in caps:
            ports = sorted(set(ports) | {"*"})
        if wildcard:
            rules.append(
                NetworkRuleSpec(
                    name="cog-skill-allow-any-destination",
                    action="ALLOW",
                    direction="Outbound",
                    protocol="TCP",
                    remote_addresses=["*"],
                    remote_ports=ports or ["*"],
                    reason=(
                        "The policy allowlist contains the wildcard host, so the "
                        "intended rule permits any destination."
                    ),
                )
            )
            warnings.append(
                "The host allowlist contains '*'. Any OS-level boundary built "
                "from it would permit every destination."
            )
        elif hosts:
            rules.append(
                NetworkRuleSpec(
                    name="cog-skill-allowlisted-egress",
                    action="ALLOW",
                    direction="Outbound",
                    protocol="TCP",
                    remote_addresses=sorted(set(hosts)),
                    remote_ports=ports or ["*"],
                    reason="Destinations limited to the policy host allowlist.",
                )
            )
        else:
            warnings.append(
                "Egress was allowed by the policy but the host allowlist is "
                "empty; no meaningful OS rule could be described."
            )

    warnings.append(
        "NETWORK BOUNDARY PLAN ONLY: no firewall rule was created. Real "
        "enforcement requires a per-skill Windows Firewall policy applied by an "
        "administrator, which this build does not implement."
    )

    return NetworkBoundaryPlan(
        mode=mode,
        rules=rules,
        enforced=False,
        warnings=warnings,
        blocking_errors=errors,
    )


__all__ = [
    "NetworkBoundaryError",
    "NetworkBoundaryPlan",
    "NetworkRuleSpec",
    "build_network_boundary_plan",
]
