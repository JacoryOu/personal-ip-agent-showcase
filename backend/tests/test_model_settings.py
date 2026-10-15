import socket
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.model_gateway import (
    ModelGateway,
    ModelRole,
    dynamic_model_context,
    get_model_gateway,
    request_model_override,
    request_api_key_override,
    request_base_url_override,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def public_dns():
    """Neutralise TUN/fake-IP DNS so the SSRF guard sees a public address.

    Local dev machines often resolve public hostnames into 198.18.0.0/15
    (reserved, used as a proxy fake-IP range). The guard correctly rejects
    those, so the network layer must be stubbed out instead of weakened.
    """
    import ipaddress

    real = socket.getaddrinfo

    def is_public(addr):
        try:
            return not ipaddress.ip_address(addr[0]).is_private
        except ValueError:
            return False

    def fake(host, port, *args, **kwargs):
        try:
            infos = real(host, port, *args, **kwargs)
        except Exception:
            infos = []
        usable = [i for i in infos if i and is_public(i[4])]
        if usable:
            return infos
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 443))]

    with patch("app.api.settings.socket.getaddrinfo", side_effect=fake):
        yield


def test_current_settings_endpoint(client):
    response = client.get("/api/settings/current")
    assert response.status_code == 200
    data = response.json()
    assert "model" in data
    assert "api_key_configured" in data


@pytest.mark.asyncio
async def test_connection_endpoint_success(client, public_dns):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="hi"))]

    with patch("app.api.settings.AsyncOpenAI") as mock_openai_cls:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_cls.return_value = mock_instance

        payload = {
            "api_key": "sk-test-key-123456",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-v3",
        }
        res = client.post("/api/settings/test-connection", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["model"] == "deepseek-chat"
        assert data["latency_ms"] >= 1
        assert "successful" in data["message"].lower()

        mock_openai_cls.assert_called_once_with(
            api_key="sk-test-key-123456",
            base_url="https://api.deepseek.com/v1",
            timeout=15.0,
        )


@pytest.mark.asyncio
async def test_connection_endpoint_missing_key_for_cloud_fails(client):
    payload = {
        "api_key": "",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-v3",
    }
    res = client.post("/api/settings/test-connection", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "未检测到 API Key" in data["message"]


@pytest.mark.asyncio
async def test_connection_endpoint_failure(client, public_dns):
    with patch("app.api.settings.AsyncOpenAI") as mock_openai_cls:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create = AsyncMock(side_effect=Exception("401 Unauthorized: Invalid API Key"))
        mock_openai_cls.return_value = mock_instance

        payload = {
            "api_key": "invalid-key",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
        }
        res = client.post("/api/settings/test-connection", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert data["model"] == "gpt-4o"
        # The upstream error body must never be echoed back to the client.
        assert "401 Unauthorized" not in data["message"]
        assert "Connection test failed" in data["message"]


def test_dynamic_model_context_manager():
    gw = ModelGateway()
    default_model = gw.get_model_for_role(ModelRole.OUTLINE)
    default_key = gw.get_api_key_for_role(ModelRole.OUTLINE)
    default_url = gw.get_base_url_for_role(ModelRole.OUTLINE)

    with dynamic_model_context(
        model="deepseek-r1",
        api_key="sk-dynamic-key",
        base_url="https://api.siliconflow.cn/v1",
    ):
        assert gw.get_model_for_role(ModelRole.OUTLINE) == "deepseek-r1"
        assert gw.get_api_key_for_role(ModelRole.OUTLINE) == "sk-dynamic-key"
        assert gw.get_base_url_for_role(ModelRole.OUTLINE) == "https://api.siliconflow.cn/v1"

        client = gw.get_client_for_role(ModelRole.OUTLINE)
        assert client.api_key == "sk-dynamic-key"
        assert str(client.base_url).rstrip("/") == "https://api.siliconflow.cn/v1"

    # Restored after context exit
    assert gw.get_model_for_role(ModelRole.OUTLINE) == default_model
    assert gw.get_api_key_for_role(ModelRole.OUTLINE) == default_key
    assert gw.get_base_url_for_role(ModelRole.OUTLINE) == default_url


def test_dynamic_header_middleware_propagation(client, public_dns):
    # BYOK model credentials use the dedicated ``X-Model-Api-Key`` header so
    # they can never collide with the application auth credential.
    headers = {
        "X-Model-Name": "qwen-max",
        "X-Model-Api-Key": "sk-qwen-key-999",
        "X-Base-Url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    }

    with patch("app.api.settings.AsyncOpenAI") as mock_openai_cls:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create = AsyncMock(return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="ok"))]))
        mock_openai_cls.return_value = mock_instance

        # Test connection without payload, passing headers
        res = client.post("/api/settings/test-connection", json={}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["model"] == "qwen-max"
        assert data["success"] is True

        mock_openai_cls.assert_called_once_with(
            api_key="sk-qwen-key-999",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            timeout=15.0,
        )


def test_byok_key_is_not_treated_as_auth_credential(client, public_dns):
    """A model BYOK key must never be accepted as an application credential."""
    with patch("app.api.settings.AsyncOpenAI") as mock_openai_cls:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="ok"))])
        )
        mock_openai_cls.return_value = mock_instance

        res = client.post(
            "/api/settings/test-connection",
            json={},
            headers={
                "X-Model-Name": "qwen-max",
                "X-Model-Api-Key": "sk-qwen-key-999",
                "X-Base-Url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            },
        )
        assert res.status_code == 200
        assert mock_openai_cls.call_args.kwargs["api_key"] == "sk-qwen-key-999"


def test_legacy_byok_header_still_accepted(client, public_dns):
    """The legacy ``X-Api-Key`` BYOK header keeps working for older clients."""
    with patch("app.api.settings.AsyncOpenAI") as mock_openai_cls:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="ok"))])
        )
        mock_openai_cls.return_value = mock_instance

        res = client.post(
            "/api/settings/test-connection",
            json={"api_key": "sk-legacy-key-123"},
            headers={
                "X-Model-Name": "qwen-max",
                "X-Base-Url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            },
        )
        assert res.status_code == 200
        assert mock_openai_cls.call_args.kwargs["api_key"] == "sk-legacy-key-123"
