"""Regression coverage for the model provider base_url SSRF guard."""
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.settings import (
    BASE_URL_REJECTED_MESSAGE,
    validate_provider_base_url,
)
import app.api.settings as settings_mod


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def no_outbound_socket():
    """Any attempt to open a real connection during these tests is a failure."""
    with patch.object(settings_mod, "AsyncOpenAI") as mock_cls:
        instance = MagicMock()
        instance.chat.completions.create = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="ok"))])
        )
        mock_cls.return_value = instance
        yield mock_cls


#: URLs that must never be accepted as an LLM provider endpoint, whether or
#: not the caller looks like a "local" provider. ``100.100.100.200`` is the
#: Alibaba Cloud metadata address inside RFC 6598 CGNAT space, which
#: ``ipaddress`` does not report as private.
@pytest.fixture
def public_dns():
    """Neutralise TUN/fake-IP DNS so the guard sees a genuinely public address.

    Local dev machines resolve public hostnames into 198.18.0.0/15 (reserved,
    used as a proxy fake-IP range), which the guard correctly rejects. The
    network layer is stubbed rather than the guard being weakened.
    """
    import ipaddress

    real = socket.getaddrinfo

    def usable(infos):
        out = []
        for i in infos or []:
            try:
                ip = ipaddress.ip_address(i[4][0])
            except (ValueError, IndexError):
                continue
            if not (
                ip.is_private
                or ip.is_loopback
                or ip.is_reserved
                or ip.is_link_local
                or ip in ipaddress.ip_network("100.64.0.0/10")
            ):
                out.append(i)
        return out

    def fake(host, port, *args, **kwargs):
        try:
            infos = real(host, port, *args, **kwargs)
        except Exception:
            infos = []
        good = usable(infos)
        if good:
            return infos
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 443))]

    with patch("app.api.settings.socket.getaddrinfo", side_effect=fake):
        yield


BLOCKED_URLS = [
    "http://10.0.0.5/v1",
    "http://192.168.1.1:11434/v1",
    "http://172.16.0.1/v1",
    "http://169.254.169.254/latest/meta-data",
    "http://metadata.google.internal/computeMetadata/v1",
    "http://100.100.100.200/latest/meta-data",
    "http://100.64.1.1/v1",
    "http://198.18.0.1/v1",
    "http://user:password@api.example.com/v1",
    "ftp://api.example.com/v1",
    "file:///etc/passwd",
    "http://0.0.0.0:11434/v1",
    "http://localhost:8080/v1",
    "http://[fd00::1]/v1",
    "http://api.example.com:99999/v1",
    "not-a-url",
]

#: Loopback endpoints are legitimate for an explicitly local provider, but
#: must still be rejected as soon as the port is not the local-provider port.
BLOCKED_EVEN_IN_LOCAL_MODE = [
    "http://127.0.0.1:8080/v1",
    "http://[::1]:8080/v1",
    "http://0.0.0.0:11434/v1",
]


@pytest.mark.parametrize("url", BLOCKED_URLS)
def test_validate_provider_base_url_blocks(url):
    with pytest.raises(settings_mod._BaseUrlRejected):
        validate_provider_base_url(url)


@pytest.mark.parametrize("url", BLOCKED_EVEN_IN_LOCAL_MODE)
def test_validate_provider_base_url_blocks_even_in_local_mode(url):
    with pytest.raises(settings_mod._BaseUrlRejected):
        validate_provider_base_url(url, allow_loopback=True)


def test_public_provider_url_is_allowed(public_dns):
    assert validate_provider_base_url("https://api.openai.com/v1")


def test_loopback_only_allowed_in_local_mode():
    assert validate_provider_base_url("http://127.0.0.1:11434/v1", allow_loopback=True)
    assert validate_provider_base_url("http://localhost:11434/v1", allow_loopback=True)


def test_loopback_rejected_on_other_port_even_in_local_mode():
    with pytest.raises(settings_mod._BaseUrlRejected):
        validate_provider_base_url("http://127.0.0.1:8080/v1", allow_loopback=True)


def test_hostname_resolving_to_private_address_is_blocked():
    def fake(host, port, *a, **k):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", port or 443))]

    with patch("app.api.settings.socket.getaddrinfo", side_effect=fake):
        with pytest.raises(settings_mod._BaseUrlRejected):
            validate_provider_base_url("https://evil.example.com/v1")


def test_hostname_with_mixed_public_and_private_records_is_blocked():
    def fake(host, port, *a, **k):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.1.2.3", port or 443)),
        ]

    with patch("app.api.settings.socket.getaddrinfo", side_effect=fake):
        with pytest.raises(settings_mod._BaseUrlRejected):
            validate_provider_base_url("https://mixed.example.com/v1")


def test_loopback_provider_is_accepted_for_explicit_local_url(client):
    """An explicit local Ollama-style endpoint is a supported configuration."""
    resp = client.post(
        "/api/settings/test-connection",
        json={"base_url": "http://127.0.0.1:11434/v1", "model": "qwen2.5:7b"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.parametrize("url", BLOCKED_URLS)
def test_endpoint_returns_generic_message_without_host_detail(client, url):
    resp = client.post(
        "/api/settings/test-connection",
        json={"api_key": "sk-test", "base_url": url, "model": "gpt-test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["message"] == BASE_URL_REJECTED_MESSAGE
    # No host / port / IP / resolver detail may leak to the caller.
    blob = repr(data).lower()
    for secret in ("127.0.0.1", "localhost", "10.0.0.5", "192.168", "169.254",
                   "metadata.google.internal", "100.100.100.200", "fd00",
                   "getaddrinfo", "password"):
        assert secret not in blob


def test_rejected_url_never_opens_a_client(client):
    resp = client.post(
        "/api/settings/test-connection",
        json={"api_key": "sk-test", "base_url": "http://169.254.169.254/latest", "model": "gpt-test"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is False
    # AsyncOpenAI patched autouse fixture records construction; none should happen.
    assert not settings_mod.AsyncOpenAI.called
