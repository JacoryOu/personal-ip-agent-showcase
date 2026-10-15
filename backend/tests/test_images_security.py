# -*- coding: utf-8 -*-
"""Hardening tests for /api/images: no client key/base-URL passthrough, SSRF-safe proxy."""
from pathlib import Path
import sys

import httpx
import pytest
from fastapi.testclient import TestClient

backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.api import images
from app.core.net_guard import OutboundRequestBlocked, SafeFetchResult
from app.main import app
from app.services.image_service import ImageService, get_image_service


@pytest.fixture
def client():
    return TestClient(app)


def test_generate_request_has_no_api_key_or_base_url_fields():
    fields = set(images.ImageGenerateRequest.model_fields)
    assert "api_key" not in fields
    assert "base_url" not in fields
    # The model must not silently accept the old fields either.
    req = images.ImageGenerateRequest(prompt="x")
    assert not hasattr(req, "api_key")
    assert not hasattr(req, "base_url")


def test_base_url_override_respects_allowlist():
    assert images._base_url_override_allowed("https://api.openai.com/v1") is True
    assert images._base_url_override_allowed("https://apihub.agnes-ai.com/v1") is True
    assert images._base_url_override_allowed("https://evil.example.net/v1") is False
    assert images._base_url_override_allowed("http://127.0.0.1:8000/v1") is False
    assert images._base_url_override_allowed("https://user:pw@api.openai.com/v1") is False
    assert images._base_url_override_allowed("ftp://api.openai.com/v1") is False
    assert images._base_url_override_allowed("") is False


def test_non_allowlisted_base_url_is_ignored(client, monkeypatch):
    captured = {}

    class SpyService(ImageService):
        def __init__(self):
            super().__init__()
            self._custom_base_url = None

        async def generate(self, **kwargs):
            captured["base_url"] = self.resolve_base_url()
            captured["api_key"] = self.resolve_api_key()
            return {"image_url": "data:image/svg+xml;base64,AAA", "prompt": kwargs["prompt"]}

    app.dependency_overrides[get_image_service] = SpyService
    try:
        resp = client.post(
            "/api/images/generate",
            json={"prompt": "hi"},
            headers={
                "X-Image-Base-Url": "https://evil.example.net/v1",
                "X-Image-Api-Key": "sk-attacker-key",
            },
        )
        assert resp.status_code == 200
        assert captured["api_key"] != "sk-attacker-key"
        assert "evil.example.net" not in str(captured["base_url"])
    finally:
        app.dependency_overrides.pop(get_image_service, None)


def test_allowlisted_base_url_override_still_applies(client, monkeypatch):
    captured = {}

    class SpyService(ImageService):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            captured["ctor"] = kwargs

        async def generate(self, **kwargs):
            captured["base_url"] = self.resolve_base_url()
            captured["api_key"] = self.resolve_api_key()
            return {"image_url": "data:image/svg+xml;base64,AAA", "prompt": kwargs["prompt"]}

    # The allowlist path builds a *new* service from the operator-approved
    # header values, so patch the module-level symbol the endpoint uses.
    monkeypatch.setattr(images, "ImageService", SpyService)

    resp = client.post(
        "/api/images/generate",
        json={"prompt": "hi"},
        headers={
            "X-Image-Base-Url": "https://api.openai.com/v1",
            "X-Image-Api-Key": "sk-openai-key",
        },
    )
    assert resp.status_code == 200
    assert captured["ctor"]["base_url"] == "https://api.openai.com/v1"
    assert captured["base_url"] == "https://api.openai.com/v1"
    assert captured["api_key"] == "sk-openai-key"


def _stub_fetch(monkeypatch, result=None, exc=None):
    calls = []

    async def fake_safe_fetch(url, **kwargs):
        calls.append(url)
        if exc is not None:
            raise exc
        return result

    monkeypatch.setattr(images, "safe_fetch", fake_safe_fetch)
    return calls


def test_proxy_blocks_metadata_and_loopback(client, monkeypatch):
    calls = _stub_fetch(
        monkeypatch,
        exc=OutboundRequestBlocked("Target '169.254.169.254' resolves to link-local"),
    )
    resp = client.get("/api/images/proxy", params={"url": "http://169.254.169.254/latest/meta-data/"})
    assert resp.status_code == 400
    assert "169.254.169.254" not in resp.text
    assert "link-local" not in resp.text
    assert calls == ["http://169.254.169.254/latest/meta-data/"]

    resp = client.get("/api/images/proxy", params={"url": "http://127.0.0.1:8080/x.png"})
    assert resp.status_code == 400


def test_proxy_requires_url(client):
    resp = client.get("/api/images/proxy", params={"url": "   "})
    assert resp.status_code == 400


def test_proxy_rejects_non_image_content_type(client, monkeypatch):
    _stub_fetch(
        monkeypatch,
        result=SafeFetchResult(
            status_code=200,
            headers=httpx.Headers({"content-type": "text/html; charset=utf-8"}),
            content=b"<html>leak</html>",
            final_url="https://example.com/a",
        ),
    )
    resp = client.get("/api/images/proxy", params={"url": "https://example.com/a"})
    assert resp.status_code == 415
    assert "leak" not in resp.text


def test_proxy_allows_svg(client, monkeypatch):
    _stub_fetch(
        monkeypatch,
        result=SafeFetchResult(
            status_code=200,
            headers=httpx.Headers({"content-type": "image/svg+xml"}),
            content=b"<svg/>",
            final_url="https://example.com/a.svg",
        ),
    )
    resp = client.get("/api/images/proxy", params={"url": "https://example.com/a.svg"})
    assert resp.status_code == 200
    assert resp.json()["data_uri"].startswith("data:image/svg+xml;base64,")


def test_proxy_enforces_size_cap(client, monkeypatch):
    calls = _stub_fetch(
        monkeypatch,
        exc=OutboundRequestBlocked("Response body exceeds the 8388608 byte limit."),
    )
    resp = client.get("/api/images/proxy", params={"url": "https://example.com/huge.png"})
    assert resp.status_code == 400
    assert "8388608" not in resp.text
    assert calls


def test_proxy_does_not_leak_upstream_body_on_error(client, monkeypatch):
    _stub_fetch(
        monkeypatch,
        exc=httpx.ConnectError("connection refused to internal-host.corp:8080"),
    )
    resp = client.get("/api/images/proxy", params={"url": "https://example.com/x.png"})
    assert resp.status_code == 400
    assert "internal-host.corp" not in resp.text
    assert "ConnectError" in resp.text


def test_proxy_upstream_error_status_is_reported(client, monkeypatch):
    _stub_fetch(
        monkeypatch,
        result=SafeFetchResult(
            status_code=404,
            headers=httpx.Headers({"content-type": "image/png"}),
            content=b"",
            final_url="https://example.com/missing.png",
        ),
    )
    resp = client.get("/api/images/proxy", params={"url": "https://example.com/missing.png"})
    assert resp.status_code == 400
    assert "404" in resp.text
