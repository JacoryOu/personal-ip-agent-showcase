import ipaddress
import logging
import os
import socket
import time
from typing import Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Header, Request
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.config import settings

logger = logging.getLogger(__name__)


def _facade():
    """Late-bound access to the facade module (keeps monkeypatching working)."""
    from app.api import settings as _settings_facade
    return _settings_facade

router = APIRouter(tags=["settings"])

# Public, fixed failure text. Upstream SDK / network errors may contain
# provider hostnames, internal URLs or credential fragments, so they are only
# ever written to the server log.
CONNECTION_TEST_FAILED_MESSAGE = (
    "Connection test failed. Verify the configured endpoint and credentials."
)

#: Public, fixed rejection text for a base_url that fails the SSRF guard.
#: It deliberately carries no host, port, resolved IP or DNS detail.
BASE_URL_REJECTED_MESSAGE = "The provided endpoint address is not allowed."

#: The only hostnames a local (Ollama-style) provider may use.
LOCAL_PROVIDER_HOSTS = {"localhost", "127.0.0.1", "::1"}
#: The only port a local provider may use.
LOCAL_PROVIDER_PORTS = {11434}

_ALLOWED_SCHEMES = ("http", "https")

#: Extra network ranges that ``ipaddress`` does not flag as private/reserved
#: but that are never a legitimate LLM provider endpoint. ``100.64.0.0/10``
#: (RFC 6598 CGNAT) notably contains ``100.100.100.200``, the Alibaba Cloud
#: instance-metadata address, so SSRF against cloud metadata is possible
#: unless this range is blocked explicitly.
_BLOCKED_EXTRA_NETWORKS = (
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("198.18.0.0/15"),
)


class _BaseUrlRejected(Exception):
    """Raised when a caller-supplied base_url fails the SSRF guard."""


def _check_ip(ip: ipaddress._BaseAddress, *, allow_loopback: bool) -> None:
    if allow_loopback and (ip.is_loopback or ip == ipaddress.ip_address("0.0.0.0")):
        # 0.0.0.0 is not a legal destination; reject it even for local mode.
        if ip == ipaddress.ip_address("0.0.0.0"):
            raise _BaseUrlRejected()
        return
    for network in _BLOCKED_EXTRA_NETWORKS:
        if ip.version == network.version and ip in network:
            raise _BaseUrlRejected()
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise _BaseUrlRejected()


def validate_provider_base_url(base_url: str, *, allow_loopback: bool = False) -> str:
    """Validate a caller-supplied LLM ``base_url`` against the SSRF guard.

    Rejects: non-HTTP(S) schemes, URL userinfo, literal private/loopback/
    link-local/reserved/metadata IPs, any hostname that resolves to one of
    those (checked for *every* resolved address, not just the first), and any
    port other than the local-provider port when loopback is allowed.

    Raises ``_BaseUrlRejected`` on any violation. The caller must translate
    that into a generic message without echoing resolver output.
    """
    try:
        parts = urlsplit(base_url)
    except ValueError as exc:
        raise _BaseUrlRejected() from exc

    if parts.scheme.lower() not in _ALLOWED_SCHEMES:
        raise _BaseUrlRejected()
    if parts.username or parts.password or "@" in parts.netloc:
        raise _BaseUrlRejected()

    try:
        hostname = parts.hostname
        port = parts.port
    except ValueError as exc:
        # Malformed / out-of-range port.
        raise _BaseUrlRejected() from exc
    if not hostname:
        raise _BaseUrlRejected()

    host = hostname.strip().strip(".").lower()

    # Literal IP address?
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None

    if ip is not None:
        _check_ip(ip, allow_loopback=allow_loopback)
        if allow_loopback and (port or 80) not in LOCAL_PROVIDER_PORTS:
            raise _BaseUrlRejected()
        return base_url

    # Hostname: loopback names are only acceptable in local mode.
    if host in LOCAL_PROVIDER_HOSTS:
        if not allow_loopback:
            raise _BaseUrlRejected()
        if (port or 80) not in LOCAL_PROVIDER_PORTS:
            raise _BaseUrlRejected()
        return base_url

    if allow_loopback and (port or 80) not in {443, 80}:
        # Local mode still reaches out to cloud providers; keep the same
        # restrictive port surface as the default guard.
        raise _BaseUrlRejected()

    # Resolve and validate *all* addresses (mitigates a single-record trick).
    try:
        infos = _facade().socket.getaddrinfo(
        host, port or (443 if parts.scheme.lower() == "https" else 80)
    )
    except _facade().socket.gaierror as exc:
        raise _BaseUrlRejected() from exc
    if not infos:
        raise _BaseUrlRejected()
    for info in infos:
        addr = info[4][0]
        try:
            _check_ip(ipaddress.ip_address(addr), allow_loopback=False)
        except ValueError as exc:
            raise _BaseUrlRejected() from exc

    return base_url


def is_local_provider_url(base_url: Optional[str]) -> bool:
    """True only when ``base_url`` points at an explicitly allowed loopback host."""
    if not base_url:
        return False
    try:
        host = (urlsplit(base_url).hostname or "").strip().strip(".").lower()
    except ValueError:
        return False
    if host not in LOCAL_PROVIDER_HOSTS:
        return False
    try:
        port = urlsplit(base_url).port
    except ValueError:
        return False
    return (port or 80) in LOCAL_PROVIDER_PORTS


class ConnectionTestRequest(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    is_system_default: Optional[bool] = False


class ConnectionTestResponse(BaseModel):
    success: bool
    latency_ms: int
    model: str
    message: str


def _safe_host(base_url: Optional[str]) -> str:
    """Extract only the host portion of a base URL for logging."""
    if not base_url:
        return "<unset>"
    try:
        from urllib.parse import urlparse

        return urlparse(base_url).hostname or "<unparsable>"
    except Exception:
        return "<unparsable>"


def normalize_model_for_provider(model: str, base_url: Optional[str]) -> str:
    """Normalizes model names for well-known providers to avoid 404/400 errors."""
    url = (base_url or "").lower()
    m = (model or "").strip()

    if "api.deepseek.com" in url:
        if m in ("deepseek-v3", "deepseek-chat"):
            return "deepseek-chat"
        if m in ("deepseek-r1", "deepseek-reasoner"):
            return "deepseek-reasoner"
    elif "dashscope.aliyuncs.com" in url:
        if m == "deepseek-chat":
            return "deepseek-v3"
        if m == "deepseek-reasoner":
            return "deepseek-r1"
    elif "api.siliconflow.cn" in url:
        if m in ("deepseek-v3", "deepseek-chat"):
            return "deepseek-ai/DeepSeek-V3"
        if m in ("deepseek-r1", "deepseek-reasoner"):
            return "deepseek-ai/DeepSeek-R1"

    return m or "deepseek-v3"

