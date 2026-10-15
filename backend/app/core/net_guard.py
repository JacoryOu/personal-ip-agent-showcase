"""Reusable SSRF guard for server-side outbound HTTP fetches.

Why this exists
---------------
Any endpoint that accepts a caller-supplied URL and fetches it from the server
is a Server-Side Request Forgery primitive unless the target is constrained.
``GET /api/images/proxy`` was one such endpoint. This module centralises the
checks so future outbound-fetch features do not each reinvent (or forget) them.

What is enforced
----------------
1. Scheme allowlist: only ``http`` / ``https``.
2. No credentials embedded in the URL (``user:pass@host``).
3. Host allowlist is optional; when non-empty the host must match (exact or
   dotted-suffix match on a registrable label boundary).
4. DNS resolution, then **every** resolved address is checked. Literal IPs are
   checked directly, which blocks the classic DNS-rebinding-free cases such as
   ``http://127.0.0.1/`` and ``http://2130706433/``.
5. Blocked ranges by default: loopback, private, link-local (incl. cloud
   metadata ``169.254.169.254``), multicast, reserved, unspecified, and the
   IPv4/IPv6 IPv4-mapped equivalents. IPv6 unique-local (``fc00::/7``) and
   IPv4-compatible forms are covered too.
6. Redirects are followed manually, one hop at a time, re-validating every
   hop, with a hard hop cap. Redirect handling is therefore **strict
   re-validation**, not "follow anywhere": a ``Location`` that resolves to a
   blocked range, a non-allowlisted port, or a disallowed scheme is rejected
   exactly like a caller-supplied URL would be.
7. **Port allowlist**: only ports listed in ``OutboundPolicy.allowed_ports``
   are reachable. An explicit port must be allowlisted; an omitted port falls
   back to the scheme default (443 for https, 80 for http) and must be
   allowlisted too. The default allowlist is 443 only.
8. Connect/read timeouts and a response body size cap are always applied.

Escaping hatch
--------------
Set ``OUTBOUND_ALLOW_PRIVATE_NETWORK=true`` **and** set
``OUTBOUND_ALLOWED_HOSTS`` to explicit hosts. This is intended for local
development against a loopback service, not for production.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence, Tuple, Union
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.core.config import settings

_IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]

ALLOWED_SCHEMES: Tuple[str, ...] = ("http", "https")

#: Ports an outbound fetch may target when a policy does not narrow it further.
#: 443 is the only default; plain http / port 80 must be opted into explicitly
#: by passing ``allowed_ports`` on the policy.
DEFAULT_ALLOWED_PORTS: Tuple[int, ...] = (443,)

#: Ports implied by the scheme when the URL omits one.
SCHEME_DEFAULT_PORTS: dict = {"https": 443, "http": 80}

#: Well-known cloud instance-metadata endpoints, blocked explicitly so that a
#: future change to range checks cannot silently re-open them.
BLOCKED_HOSTS: Tuple[str, ...] = (
    "169.254.169.254",          # AWS / Azure / GCP / OpenStack metadata
    "metadata.google.internal", # GCP metadata hostname
    "metadata.goog",
    "100.100.100.200",          # Alibaba Cloud metadata
    "metadata.azure.com",
)

#: Hostname suffixes that must never be resolved for outbound fetches.
BLOCKED_HOST_SUFFIXES: Tuple[str, ...] = (
    ".localhost",
    ".local",
    ".internal",
)


_NUMERIC_HOST_RE = re.compile(r"^(0[xX][0-9a-fA-F]+|\d+)$")


def _looks_like_numeric_ip(host: str) -> bool:
    """True for bare integer / hex host spellings that denote an IPv4 address."""
    if _NUMERIC_HOST_RE.match(host):
        return True
    # Dotted forms where every label is numeric but the host is not a valid
    # dotted quad (e.g. 0x7f.0.0.1 or 0177.1.1.1).
    if all(re.fullmatch(r"(0[xX][0-9a-fA-F]+|\d+)", label) for label in host.split(".")):
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return True
    return False


class OutboundRequestBlocked(Exception):
    """Raised when an outbound URL fails SSRF policy validation."""


@dataclass(frozen=True)
class OutboundPolicy:
    allowed_hosts: Sequence[str]
    allow_private_network: bool
    max_redirects: int
    timeout_seconds: float
    max_response_bytes: int
    #: Ports this policy may connect to. Defaults to 443 only; callers that
    #: legitimately need plain http/80 must say so explicitly.
    allowed_ports: Sequence[int] = DEFAULT_ALLOWED_PORTS

    def port_allowed(self, port: int) -> bool:
        return port in set(self.allowed_ports or ())


@dataclass(frozen=True)
class SafeFetchResult:
    """A fully-read, size-bounded response.

    Returned instead of an ``httpx.Response`` so callers never need to reach into
    private attributes, and so the body is guaranteed to be materialised *while
    streaming* rather than after the fact.
    """

    status_code: int
    headers: "httpx.Headers"
    content: bytes
    final_url: str

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "")


def _split_hosts(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [part.strip().lower() for part in value.split(",") if part.strip()]
    return [str(part).strip().lower() for part in value if str(part).strip()]


def load_policy(overrides: Optional[OutboundPolicy] = None) -> OutboundPolicy:
    """Build the effective policy from settings, optionally overridden."""
    if overrides is not None:
        return overrides
    return OutboundPolicy(
        allowed_hosts=tuple(_split_hosts(settings.OUTBOUND_ALLOWED_HOSTS)),
        allow_private_network=bool(settings.OUTBOUND_ALLOW_PRIVATE_NETWORK),
        max_redirects=int(settings.OUTBOUND_MAX_REDIRECTS),
        timeout_seconds=float(settings.OUTBOUND_TIMEOUT_SECONDS),
        max_response_bytes=int(settings.OUTBOUND_MAX_RESPONSE_BYTES),
        allowed_ports=DEFAULT_ALLOWED_PORTS,
    )


def _host_matches(host: str, allowed: str) -> bool:
    """Exact host match, or a dotted-suffix match on a label boundary."""
    if host == allowed:
        return True
    if allowed.startswith("."):
        return host.endswith(allowed) or host == allowed[1:]
    return host.endswith("." + allowed)


def _is_address_blocked(ip: ipaddress._BaseAddress) -> Tuple[bool, str]:
    """Return ``(blocked, reason)`` for a resolved address."""
    # IPv4-mapped / 6to4 / Teredo wrappers hide real v4 targets.
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        return _is_address_blocked(mapped)
    sixtofour = getattr(ip, "sixtofour", None)
    if sixtofour is not None:
        return _is_address_blocked(sixtofour)
    if getattr(ip, "is_site_local", False):  # IPv6 fec0::/10 (deprecated)
        return True, "site-local address"

    if ip.is_loopback:
        return True, "loopback address"
    if ip.is_private:
        return True, "private address"
    if ip.is_link_local:
        return True, "link-local address"
    if ip.is_multicast:
        return True, "multicast address"
    if ip.is_reserved:
        return True, "reserved address"
    if ip.is_unspecified:
        return True, "unspecified address"
    return False, ""


def _resolve(host: str, port: int) -> List[ipaddress._BaseAddress]:
    """Resolve ``host`` to every address it maps to (literal or via DNS)."""
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass

    infos = socket.getaddrinfo(host, port or None, proto=socket.IPPROTO_TCP)
    addresses: List[ipaddress._BaseAddress] = []
    for info in infos:
        sockaddr = info[4]
        literal = sockaddr[0]
        try:
            addresses.append(ipaddress.ip_address(literal))
        except ValueError:
            # Scope-id suffixed IPv6 such as 'fe80::1%eth0'.
            cleaned = literal.split("%", 1)[0]
            try:
                addresses.append(ipaddress.ip_address(cleaned))
            except ValueError:
                continue
    if not addresses:
        raise OutboundRequestBlocked(f"Host {host!r} could not be resolved.")
    return addresses


def assert_url_allowed(
    url: str,
    policy: Optional[OutboundPolicy] = None,
    *,
    allow_missing_dns: bool = False,
) -> Tuple[str, List[ipaddress._BaseAddress]]:
    """Validate ``url`` against the SSRF policy.

    Returns:
        ``(normalized_url, resolved_addresses)``.

    Raises:
        OutboundRequestBlocked: on any policy violation.
    """
    effective = load_policy(policy)
    if not url or not isinstance(url, str):
        raise OutboundRequestBlocked("A URL is required.")

    candidate = url.strip()
    if len(candidate) > 2048:
        raise OutboundRequestBlocked("URL is too long.")
    if any(ch in candidate for ch in ("\n", "\r", "\t", " ")):
        raise OutboundRequestBlocked("URL contains illegal whitespace characters.")

    parts = urlsplit(candidate)
    scheme = (parts.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise OutboundRequestBlocked(
            f"URL scheme {scheme or '(missing)'!r} is not allowed; use http or https."
        )

    if parts.username or parts.password:
        raise OutboundRequestBlocked("URLs with embedded credentials are not allowed.")

    try:
        port = parts.port
    except ValueError as exc:
        raise OutboundRequestBlocked(f"URL has an invalid port: {exc}") from exc

    # Port allowlist. Checked before any DNS work so a disallowed port costs
    # nothing, and checked for redirect hops too because every hop goes back
    # through this function.
    effective_port = port if port is not None else SCHEME_DEFAULT_PORTS.get(scheme)
    if effective_port is not None and not effective.port_allowed(effective_port):
        raise OutboundRequestBlocked(
            f"Port {effective_port} is not in the outbound port allowlist."
        )

    host = (parts.hostname or "").lower()
    if not host:
        raise OutboundRequestBlocked("URL is missing a host.")

    # Reject alternate integer/octal/hex IP spellings (e.g. http://2130706433/,
    # http://0x7f.1/). These are ambiguous across resolvers, so they are never
    # allowed as outbound targets.
    if _looks_like_numeric_ip(host):
        raise OutboundRequestBlocked(
            f"Host {host!r} uses a numeric IP literal form, which is not allowed."
        )

    if host in BLOCKED_HOSTS:
        raise OutboundRequestBlocked(f"Host {host!r} is a blocked metadata endpoint.")

    # Blocked suffixes are only meaningful when a host allowlist is absent.
    if not effective.allowed_hosts and any(
        host == suffix.lstrip(".") or host.endswith(suffix)
        for suffix in BLOCKED_HOST_SUFFIXES
    ):
        raise OutboundRequestBlocked(f"Host {host!r} is not resolvable for outbound fetches.")

    if effective.allowed_hosts:
        if not any(_host_matches(host, allowed) for allowed in effective.allowed_hosts):
            raise OutboundRequestBlocked(f"Host {host!r} is not in the outbound allowlist.")
    elif effective.allow_private_network:
        # Explicit opt-in still requires an allowlist; see module docstring.
        raise OutboundRequestBlocked(
            "Private-network access requires OUTBOUND_ALLOWED_HOSTS to list the target host."
        )

    try:
        addresses = _resolve(host, effective_port or (443 if scheme == "https" else 80))
    except OutboundRequestBlocked:
        raise
    except Exception as exc:
        if allow_missing_dns:
            return candidate, []
        raise OutboundRequestBlocked(f"Host {host!r} could not be resolved: {exc}") from exc

    # ``allow_missing_dns`` only tolerates a resolver *error*; it must never
    # turn "resolved to nothing" into a pass, otherwise integer-literal hosts
    # such as http://2130706433/ would slip through unvalidated.
    if not addresses:
        if allow_missing_dns:
            raise OutboundRequestBlocked(
                f"Host {host!r} did not resolve to any usable address."
            )
        raise OutboundRequestBlocked(f"Host {host!r} could not be resolved.")

    if not effective.allow_private_network:
        for address in addresses:
            blocked, reason = _is_address_blocked(address)
            if blocked:
                raise OutboundRequestBlocked(
                    f"Target {host!r} resolves to a {reason} ({address}); refusing to fetch."
                )

    normalized = urlunsplit((scheme, parts.netloc, parts.path or "/", parts.query, ""))
    return normalized, addresses


async def _stream_capped(response: httpx.Response, limit: int) -> bytes:
    """Read at most ``limit`` bytes from a *streaming* response.

    Enforces the cap incrementally so an oversized body is abandoned after
    ``limit`` bytes instead of being fully buffered in memory first.
    """
    declared = response.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        await response.aclose()
        raise OutboundRequestBlocked(
            f"Response body exceeds the {limit} byte limit (content-length={declared})."
        )

    chunks: List[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > limit:
            await response.aclose()
            raise OutboundRequestBlocked(f"Response body exceeds the {limit} byte limit.")
        chunks.append(chunk)
    return b"".join(chunks)


async def safe_fetch(
    url: str,
    policy: Optional[OutboundPolicy] = None,
    *,
    method: str = "GET",
    headers: Optional[dict] = None,
    max_bytes: Optional[int] = None,
    json: Optional[Any] = None,
) -> SafeFetchResult:
    """Fetch ``url`` with full SSRF protection, re-validating every redirect.

    The body is streamed and capped, so peak memory stays bounded by
    ``max_bytes`` regardless of what the remote server actually sends.

    ``json`` sends a JSON request body (for POST-style callers such as the
    image-generation service) while keeping the same SSRF guarantees.

    Raises:
        OutboundRequestBlocked: when any hop violates the policy or the body is
            too large. Transport failures propagate as ``httpx.HTTPError``.
    """
    effective = load_policy(policy)
    limit = max_bytes if max_bytes is not None else effective.max_response_bytes

    timeout = httpx.Timeout(effective.timeout_seconds)
    limits = httpx.Limits(max_connections=8, max_keepalive_connections=0)
    current = url
    async with httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        follow_redirects=False,
    ) as client:
        for hop in range(effective.max_redirects + 1):
            normalized, _addresses = assert_url_allowed(current, effective)

            request_kwargs: dict = {"headers": headers or {}}
            if json is not None:
                request_kwargs["json"] = json

            async with client.stream(method.upper(), normalized, **request_kwargs) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise OutboundRequestBlocked(
                            "Redirect response is missing a Location header."
                        )
                    if hop >= effective.max_redirects:
                        raise OutboundRequestBlocked(
                            f"Exceeded the {effective.max_redirects} redirect limit."
                        )
                    current = str(httpx.URL(normalized).join(location))
                    continue

                content = await _stream_capped(response, limit)
                return SafeFetchResult(
                    status_code=response.status_code,
                    headers=response.headers,
                    content=content,
                    final_url=normalized,
                )

    raise OutboundRequestBlocked("Too many redirects.")

