# -*- coding: utf-8 -*-
"""SSRF guard behaviour for :mod:`app.core.net_guard`."""
import asyncio
import socket
from pathlib import Path
import sys

import httpx
import pytest

backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core import net_guard
from app.core.net_guard import (
    OutboundPolicy,
    OutboundRequestBlocked,
    assert_url_allowed,
    load_policy,
    safe_fetch,
)


PUBLIC_IP = "93.184.216.34"


@pytest.fixture
def public_dns(monkeypatch):
    """Resolve every hostname to a public address unless a test says otherwise."""

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, port or 80))]

    monkeypatch.setattr(net_guard.socket, "getaddrinfo", fake_getaddrinfo)
    return fake_getaddrinfo


@pytest.fixture
def policy():
    return OutboundPolicy(
        allowed_hosts=(),
        allow_private_network=False,
        max_redirects=3,
        timeout_seconds=5.0,
        max_response_bytes=1024,
    )


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://example.com/",
        "ftp://example.com/",
        "data:text/plain;base64,QQ==",
    ],
)
def test_non_http_schemes_are_rejected(url):
    with pytest.raises(OutboundRequestBlocked):
        assert_url_allowed(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://127.0.0.1:8080/admin",
        "http://[::1]/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://172.16.9.9/",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://metadata.goog/",
        "http://100.100.100.200/latest/meta-data/",
        "http://foo.internal/",
        "http://printer.local/",
    ],
)
def test_private_and_metadata_targets_are_rejected(url):
    with pytest.raises(OutboundRequestBlocked):
        assert_url_allowed(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://2130706433/",       # 127.0.0.1
        "http://0x7f000001/",       # 127.0.0.1
        "http://0177.0.0.1/",       # 127.0.0.1
        "http://[::ffff:127.0.0.1]/",
        "http://[::1]/",
        "http://0.0.0.0/",
    ],
)
def test_numeric_ip_spellings_are_rejected(url):
    with pytest.raises(OutboundRequestBlocked):
        assert_url_allowed(url)


def test_url_with_credentials_is_rejected():
    with pytest.raises(OutboundRequestBlocked):
        assert_url_allowed("http://user:pass@example.com/")


def test_allowlist_blocks_unlisted_host(public_dns):
    restricted = OutboundPolicy(
        allowed_hosts=("cdn.example.com",),
        allow_private_network=False,
        max_redirects=1,
        timeout_seconds=5.0,
        max_response_bytes=1024,
    )
    assert_url_allowed("https://cdn.example.com/a.png", restricted)
    with pytest.raises(OutboundRequestBlocked):
        assert_url_allowed("https://evil.example.net/a.png", restricted)


def test_public_host_is_allowed(public_dns, policy):
    normalized, addresses = assert_url_allowed("https://example.com/a.png", policy)
    assert normalized.startswith("https://example.com/")
    assert [str(addr) for addr in addresses] == [PUBLIC_IP]


def test_oversized_content_length_is_rejected(public_dns, policy, monkeypatch):
    class FakeResponse:
        status_code = 200
        headers = httpx.Headers({"content-length": "999999", "content-type": "image/png"})
        is_redirect = False

        async def aiter_bytes(self):
            yield b"tiny"

        async def aclose(self):
            return None

    class FakeStreamCtx:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, *exc):
            return False

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def stream(self, *args, **kwargs):
            return FakeStreamCtx()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(net_guard.httpx, "AsyncClient", lambda **kw: FakeClient(**kw))

    import asyncio

    with pytest.raises(OutboundRequestBlocked):
        asyncio.run(
            safe_fetch("https://example.com/big.png", policy, max_bytes=1024)
        )


def test_streamed_body_over_limit_is_rejected(public_dns, policy, monkeypatch):
    class FakeResponse:
        status_code = 200
        headers = httpx.Headers({"content-type": "image/png"})
        is_redirect = False

        async def aiter_bytes(self):
            yield b"a" * 600
            yield b"b" * 600
            await asyncio.sleep(0)

        async def aclose(self):
            return None

    class FakeStreamCtx:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, *exc):
            return False

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def stream(self, *args, **kwargs):
            return FakeStreamCtx()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(net_guard.httpx, "AsyncClient", lambda **kw: FakeClient(**kw))

    import asyncio

    with pytest.raises(OutboundRequestBlocked):
        asyncio.run(
            safe_fetch("https://example.com/big.png", policy, max_bytes=1024)
        )


# ---------------------------------------------------------------------------
# Port allowlist
# ---------------------------------------------------------------------------


def test_default_policy_allows_only_443():
    from app.core.net_guard import DEFAULT_ALLOWED_PORTS

    assert DEFAULT_ALLOWED_PORTS == (443,)
    assert load_policy().port_allowed(443) is True
    assert load_policy().port_allowed(80) is False


def test_non_allowlisted_port_is_rejected(public_dns, policy):
    with pytest.raises(OutboundRequestBlocked) as excinfo:
        assert_url_allowed("https://example.com:8443/a.png", policy)
    assert "port allowlist" in str(excinfo.value)


def test_http_scheme_default_port_is_rejected_by_default(public_dns, policy):
    """http:// (implied port 80) is not allowlisted under the 443-only default."""
    with pytest.raises(OutboundRequestBlocked) as excinfo:
        assert_url_allowed("http://example.com/a.png", policy)
    assert "port allowlist" in str(excinfo.value)


def test_port_80_can_be_opened_explicitly(public_dns):
    opened = OutboundPolicy(
        allowed_hosts=(),
        allow_private_network=False,
        max_redirects=1,
        timeout_seconds=5.0,
        max_response_bytes=1024,
        allowed_ports=(443, 80),
    )
    normalized, _ = assert_url_allowed("http://example.com/a.png", opened)
    assert normalized.startswith("http://example.com/")
    # 22 stays shut even with 80 opened.
    with pytest.raises(OutboundRequestBlocked):
        assert_url_allowed("http://example.com:22/a.png", opened)


def test_redirect_to_non_allowlisted_port_is_rejected(public_dns, policy, monkeypatch):
    """A redirect must not be able to escape the port allowlist."""

    class FakeResponse:
        status_code = 302
        headers = httpx.Headers({"location": "https://example.com:8443/evil.png"})
        is_redirect = True

        async def aiter_bytes(self):
            yield b""

        async def aclose(self):
            return None

    class FakeStreamCtx:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, *exc):
            return False

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def stream(self, *args, **kwargs):
            return FakeStreamCtx()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(net_guard.httpx, "AsyncClient", lambda **kw: FakeClient(**kw))

    with pytest.raises(OutboundRequestBlocked) as excinfo:
        asyncio.run(safe_fetch("https://example.com/a.png", policy))
    assert "port allowlist" in str(excinfo.value)


# ---------------------------------------------------------------------------
# DNS-rebinding shaped gaps
# ---------------------------------------------------------------------------


def test_rebind_to_private_address_is_rejected(public_dns, policy, monkeypatch):
    """Host validates on the first hop, then 'rebinds' to a private address."""
    state = {"calls": 0}
    real = public_dns

    def rebinding(host, port, *args, **kwargs):
        state["calls"] += 1
        ip = "10.0.0.7" if state["calls"] > 1 else PUBLIC_IP
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port or 443))]

    monkeypatch.setattr(net_guard.socket, "getaddrinfo", rebinding)

    class FakeResponse:
        status_code = 302
        headers = httpx.Headers({"location": "https://example.com/rebound.png"})
        is_redirect = True

        async def aiter_bytes(self):
            yield b""

        async def aclose(self):
            return None

    class FakeStreamCtx:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, *exc):
            return False

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def stream(self, *args, **kwargs):
            return FakeStreamCtx()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(net_guard.httpx, "AsyncClient", lambda **kw: FakeClient(**kw))

    with pytest.raises(OutboundRequestBlocked) as excinfo:
        asyncio.run(safe_fetch("https://example.com/a.png", policy))
    assert "private address" in str(excinfo.value)


def test_redirect_to_metadata_ip_is_rejected(public_dns, policy, monkeypatch):
    """A 302 pointing straight at the cloud metadata endpoint must not follow."""

    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host in ("169.254.169.254", "metadata.google.internal"):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, port or 80))]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, port or 443))]

    monkeypatch.setattr(net_guard.socket, "getaddrinfo", fake_getaddrinfo)

    class FakeResponse:
        status_code = 302
        headers = httpx.Headers({"location": "http://169.254.169.254/latest/meta-data/"})
        is_redirect = True

        async def aiter_bytes(self):
            yield b""

        async def aclose(self):
            return None

    class FakeStreamCtx:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, *exc):
            return False

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def stream(self, *args, **kwargs):
            return FakeStreamCtx()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(net_guard.httpx, "AsyncClient", lambda **kw: FakeClient(**kw))

    with pytest.raises(OutboundRequestBlocked):
        asyncio.run(safe_fetch("https://example.com/a.png", policy))


def test_normal_public_url_is_allowed_end_to_end(public_dns, policy, monkeypatch):
    """A benign public URL passes validation and reaches the transport."""

    seen = {}

    class FakeResponse:
        status_code = 200
        headers = httpx.Headers({"content-type": "image/png"})
        is_redirect = False

        async def aiter_bytes(self):
            yield b"png-bytes"

        async def aclose(self):
            return None

    class FakeStreamCtx:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, *exc):
            return False

    class FakeClient:
        def __init__(self, **kwargs):
            seen["client_kwargs"] = kwargs

        def stream(self, method, url, **kwargs):
            seen["method"] = method
            seen["url"] = url
            seen["json"] = kwargs.get("json")
            return FakeStreamCtx()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(net_guard.httpx, "AsyncClient", lambda **kw: FakeClient(**kw))

    result = asyncio.run(
        safe_fetch(
            "https://example.com/ok.png",
            policy,
            method="POST",
            headers={"Authorization": "Bearer x"},
            json={"prompt": "hi"},
        )
    )
    assert result.status_code == 200
    assert result.content == b"png-bytes"
    assert seen["method"] == "POST"
    assert seen["json"] == {"prompt": "hi"}
