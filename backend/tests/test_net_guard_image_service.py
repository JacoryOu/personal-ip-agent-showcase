# -*- coding: utf-8 -*-
"""Egress-guard coverage for the image generation service.

``ImageService._generate_with_agnes`` used to call ``httpx.AsyncClient``
directly, which meant the only constraint on the target was a hostname
allowlist. These tests pin the unified behaviour: the call must go through
:mod:`app.core.net_guard` and inherit its DNS / port / scheme / credential /
redirect policy.
"""
import asyncio
import json
import socket
from pathlib import Path
import sys

import httpx
import pytest

backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core import net_guard
from app.core.net_guard import OutboundRequestBlocked
from app.services import image_service
from app.services.image_service import ImageService, build_image_outbound_policy


PUBLIC_IP = "93.184.216.34"
AGNES = "https://apihub.agnes-ai.com/v1/images/generations"


@pytest.fixture
def public_dns(monkeypatch):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, port or 443))]

    monkeypatch.setattr(net_guard.socket, "getaddrinfo", fake_getaddrinfo)
    return fake_getaddrinfo


class _Recorder:
    """Captures every request that reaches the transport layer."""

    def __init__(self, responder):
        self.requests = []
        self._responder = responder

    def client(self, **kwargs):
        outer = self

        class FakeClient:
            def __init__(self, **kw):
                self.kw = kw

            def stream(self, method, url, **kw):
                outer.requests.append({"method": method, "url": url, **kw})
                return outer._responder(url, method)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

        return FakeClient(**kwargs)


def _json_responder(payload=None, status_code=200):
    def responder(url, method):
        body = payload if payload is not None else {
            "data": [{"url": "https://cdn.example.com/result.png"}]
        }
        encoded = json.dumps(body).encode("utf-8")

        class FakeResponse:
            def __init__(self):
                self.status_code = status_code
                self.headers = httpx.Headers({"content-type": "application/json"})
                self.is_redirect = False

            async def aiter_bytes(self):
                yield encoded

            async def aclose(self):
                return None

        class Ctx:
            async def __aenter__(self):
                return FakeResponse()

            async def __aexit__(self, *exc):
                return False

        return Ctx()

    return responder


def _service():
    return ImageService(api_key="sk-test", base_url="https://apihub.agnes-ai.com/v1",
                        model="agnes-image-2.5-flash")


# -- policy shape -----------------------------------------------------------


def test_policy_only_allows_tls_port_443():
    policy = build_image_outbound_policy()
    assert policy.allowed_ports == (443,)
    assert policy.port_allowed(443) is True
    assert policy.port_allowed(80) is False
    assert policy.allow_private_network is False


def test_policy_host_allowlist_tracks_settings():
    policy = build_image_outbound_policy()
    for host in policy.allowed_hosts:
        assert net_guard._host_matches(host, "apihub.agnes-ai.com") or host == "api.openai.com"


# -- blocked destinations ----------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:443/x",
        "http://10.0.0.5/x",
        "https://user:pass@apihub.agnes-ai.com/v1/images/generations",
        "file:///etc/passwd",
        "gopher://apihub.agnes-ai.com:443/x",
    ],
)
def test_outbound_destinations_are_rejected(url, public_dns):
    """Direct policy check: the destinations SSRF hardening must reject."""
    with pytest.raises(OutboundRequestBlocked):
        net_guard.assert_url_allowed(url, build_image_outbound_policy())


def test_image_service_rejects_private_base_url(public_dns, monkeypatch):
    """A caller-supplied base URL pointing at the LAN must never be dialed."""
    recorder = _Recorder(_json_responder())
    monkeypatch.setattr(net_guard.httpx, "AsyncClient", recorder.client)

    service = ImageService(api_key="sk-test", model="agnes-image-2.5-flash",
                           base_url="http://192.168.1.10/v1")
    # Port 80 is not allowlisted; the private address would be rejected too.
    with pytest.raises(RuntimeError, match="Blocked outbound image request"):
        asyncio.run(service._generate_with_agnes(prompt="a cat", api_key="sk-test",
                                                base_url="http://192.168.1.10/v1",
                                                model="agnes-image-2.5-flash"))
    assert recorder.requests == []


def test_image_service_rejects_metadata_host(public_dns, monkeypatch):
    recorder = _Recorder(_json_responder())
    monkeypatch.setattr(net_guard.httpx, "AsyncClient", recorder.client)

    service = _service()
    with pytest.raises(RuntimeError, match="Blocked outbound image request"):
        asyncio.run(service._generate_with_agnes(
            prompt="a cat", api_key="sk-test",
            base_url="https://169.254.169.254/v1",
            model="agnes-image-2.5-flash",
        ))
    assert recorder.requests == []


def test_image_service_redirect_to_private_is_rejected(public_dns, monkeypatch):
    """A provider 302 to an internal host must be refused, not followed."""

    def responder(url, method):
        class FakeResponse:
            status_code = 302
            headers = httpx.Headers({"location": "http://169.254.169.254/latest/meta-data/"})
            is_redirect = True

            async def aiter_bytes(self):
                yield b""

            async def aclose(self):
                return None

        class Ctx:
            async def __aenter__(self):
                return FakeResponse()

            async def __aexit__(self, *exc):
                return False

        return Ctx()

    recorder = _Recorder(responder)
    monkeypatch.setattr(net_guard.httpx, "AsyncClient", recorder.client)

    with pytest.raises(RuntimeError, match="Blocked outbound image request"):
        asyncio.run(_service()._generate_with_agnes(prompt="a cat", api_key="sk-test"))
    # Only the first, public hop was ever contacted.
    assert len(recorder.requests) == 1


def test_image_service_redirect_to_bad_port_is_rejected(public_dns, monkeypatch):
    def responder(url, method):
        class FakeResponse:
            status_code = 302
            headers = httpx.Headers({"location": "https://apihub.agnes-ai.com:8443/v1/x"})
            is_redirect = True

            async def aiter_bytes(self):
                yield b""

            async def aclose(self):
                return None

        class Ctx:
            async def __aenter__(self):
                return FakeResponse()

            async def __aexit__(self, *exc):
                return False

        return Ctx()

    recorder = _Recorder(responder)
    monkeypatch.setattr(net_guard.httpx, "AsyncClient", recorder.client)

    with pytest.raises(RuntimeError, match="Blocked outbound image request"):
        asyncio.run(_service()._generate_with_agnes(prompt="a cat", api_key="sk-test"))
    assert len(recorder.requests) == 1


# -- happy path --------------------------------------------------------------


def test_public_provider_request_succeeds_through_the_guard(public_dns, monkeypatch):
    recorder = _Recorder(_json_responder())
    monkeypatch.setattr(net_guard.httpx, "AsyncClient", recorder.client)

    result = asyncio.run(_service()._generate_with_agnes(prompt="a cat", api_key="sk-test"))

    assert result["image_url"] == "https://cdn.example.com/result.png"
    assert result["is_fallback"] is False
    assert len(recorder.requests) == 1
    request = recorder.requests[0]
    assert request["method"] == "POST"
    assert request["url"].startswith("https://apihub.agnes-ai.com/v1/images/generations")
    assert request["headers"]["Authorization"] == "Bearer sk-test"
    assert request["json"]["prompt"]


def test_provider_http_error_surfaces(public_dns, monkeypatch):
    recorder = _Recorder(_json_responder({"error": "nope"}, status_code=500))
    monkeypatch.setattr(net_guard.httpx, "AsyncClient", recorder.client)

    with pytest.raises(RuntimeError, match="HTTP 500"):
        asyncio.run(_service()._generate_with_agnes(prompt="a cat", api_key="sk-test"))


def test_non_json_provider_response_surfaces(public_dns, monkeypatch):
    def responder(url, method):
        class FakeResponse:
            status_code = 200
            headers = httpx.Headers({"content-type": "text/html"})
            is_redirect = False

            async def aiter_bytes(self):
                yield b"<html>not json</html>"

            async def aclose(self):
                return None

        class Ctx:
            async def __aenter__(self):
                return FakeResponse()

            async def __aexit__(self, *exc):
                return False

        return Ctx()

    recorder = _Recorder(responder)
    monkeypatch.setattr(net_guard.httpx, "AsyncClient", recorder.client)

    with pytest.raises(RuntimeError, match="non-JSON"):
        asyncio.run(_service()._generate_with_agnes(prompt="a cat", api_key="sk-test"))


def test_image_service_module_no_longer_imports_httpx_directly():
    """Regression guard against a parallel HTTP implementation creeping back."""
    source = Path(image_service.__file__).read_text(encoding="utf-8")
    assert "httpx.AsyncClient" not in source
    assert "import httpx" not in source
