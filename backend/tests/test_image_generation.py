import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.services.image_service import (
    ImageService,
    get_image_service,
    set_image_service,
    is_agnes_model,
    map_agnes_params,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_is_agnes_model():
    assert is_agnes_model("agnes-image-2.5-flash") is True
    assert is_agnes_model("AGNES-IMAGE-2.5-FLASH") is True
    assert is_agnes_model("dall-e-3") is False
    assert is_agnes_model("wanx-v1", base_url="https://apihub.agnes-ai.com/v1") is True
    assert is_agnes_model("dall-e-3", base_url="https://api.openai.com/v1") is False
    assert is_agnes_model(None, None) is False


def test_map_agnes_params():
    # Resolution tiers
    assert map_agnes_params(size="1K")[0] == "1K"
    assert map_agnes_params(size="2K")[0] == "2K"
    assert map_agnes_params(size="3K")[0] == "3K"
    assert map_agnes_params(size="4K")[0] == "4K"
    assert map_agnes_params(size="invalid")[0] == "2K"

    # Platform default mapping
    assert map_agnes_params(platform="xiaohongshu") == ("2K", "3:4")
    assert map_agnes_params(platform="wechat") == ("2K", "16:9")

    # Ratio mapping
    assert map_agnes_params(aspect_ratio="3:4")[1] == "3:4"
    assert map_agnes_params(aspect_ratio="16:9")[1] == "16:9"
    assert map_agnes_params(aspect_ratio="1:1")[1] == "1:1"
    assert map_agnes_params(aspect_ratio="4:3")[1] == "4:3"
    assert map_agnes_params(aspect_ratio="9:16")[1] == "9:16"
    assert map_agnes_params(aspect_ratio="21:9")[1] == "21:9"


def test_image_service_map_size():
    service = ImageService()
    assert service.map_size(aspect_ratio="3:4") == "1024x1792"
    assert service.map_size(aspect_ratio="16:9") == "1792x1024"
    assert service.map_size(aspect_ratio="1:1") == "1024x1024"
    assert service.map_size(platform="xiaohongshu") == "1024x1792"
    assert service.map_size(platform="wechat") == "1792x1024"
    assert service.map_size(size="1024x1024") == "1024x1024"


def test_image_service_prompt_optimization():
    service = ImageService()
    xhs_opt = service.optimize_prompt("AI超级个体", platform="xiaohongshu", style="dark_gold")
    assert "AI超级个体" in xhs_opt
    assert "3:4" in xhs_opt
    assert "typography overlay" in xhs_opt

    wechat_opt = service.optimize_prompt("AI超级个体", platform="wechat", style="indigo_purple")
    assert "AI超级个体" in wechat_opt
    assert "16:9" in wechat_opt


@pytest.mark.asyncio
async def test_agnes_generation_payload_and_url_response():
    """Verify Agnes Image API request structure and URL response parsing."""
    captured_payload = None

    class MockResponse:
        """Mirrors ``app.core.net_guard.SafeFetchResult``.

        ``image_service`` now goes through ``safe_fetch`` and reads the raw
        bytes off ``result.content`` instead of calling ``httpx``'s ``.json()``.
        """

        status_code = 200
        headers = {}
        final_url = "https://apihub.agnes-ai.com/v1"

        def __init__(self, payload):
            self.content = json.dumps(payload).encode("utf-8")

    async def mock_safe_fetch(url, policy=None, *, method="GET", headers=None, max_bytes=None, json=None):
        nonlocal captured_payload
        captured_payload = json
        # Assert Agnes critical spec: NO response_format at root!
        assert "response_format" not in json, "response_format must NOT be at top level of Agnes payload"
        assert json.get("extra_body", {}).get("response_format") == "url"
        assert json.get("size") == "2K"
        assert json.get("ratio") == "3:4"
        assert json.get("model") == "agnes-image-2.5-flash"
        assert headers.get("Authorization") == "Bearer sk-agnes-valid-key"
        return MockResponse(
            {
                "created": 1726750000,
                "data": [
                    {
                        "url": "https://apihub.agnes-ai.com/images/gen-98765.png",
                        "b64_json": None,
                        "revised_prompt": "Ultra realistic cinematic portrait 2K",
                    }
                ],
            }
        )

    service = ImageService(
        model="agnes-image-2.5-flash",
        api_key="sk-agnes-valid-key",
        base_url="https://apihub.agnes-ai.com/v1",
    )

    with patch("app.services.image_service.safe_fetch", side_effect=mock_safe_fetch):
        result = await service.generate(
            prompt="测试商业海报",
            platform="xiaohongshu",
            aspect_ratio="3:4",
        )

    assert result["is_fallback"] is False
    assert result["image_url"] == "https://apihub.agnes-ai.com/images/gen-98765.png"
    assert result["size"] == "2K (3:4)"
    assert result["model"] == "agnes-image-2.5-flash"
    assert captured_payload is not None


@pytest.mark.asyncio
async def test_agnes_generation_b64_json_response():
    """Verify Agnes Image API b64_json response decoding."""
    class MockResponse:
        """Mirrors ``app.core.net_guard.SafeFetchResult`` (raw ``content`` bytes)."""

        status_code = 200
        headers = {}
        final_url = "https://apihub.agnes-ai.com/v1"

        def __init__(self, payload):
            self.content = json.dumps(payload).encode("utf-8")

    async def mock_safe_fetch(url, policy=None, *, method="GET", headers=None, max_bytes=None, json=None):
        return MockResponse(
            {
                "created": 1726750000,
                "data": [
                    {
                        "url": None,
                        "b64_json": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                        "revised_prompt": None,
                    }
                ],
            }
        )

    service = ImageService(
        model="agnes-image-2.5-flash",
        api_key="sk-agnes-valid-key",
    )

    with patch("app.services.image_service.safe_fetch", side_effect=mock_safe_fetch):
        result = await service.generate(
            prompt="测试 Base64 生图",
            platform="wechat",
        )

    assert result["is_fallback"] is False
    assert result["image_url"].startswith("data:image/png;base64,iVBORw")
    assert result["size"] == "2K (16:9)"


def test_image_endpoint_fallback_when_no_api_key(client):
    """When no real API key is configured, Agnes / default model falls back smoothly to SVG data URL."""
    service = ImageService()
    app.dependency_overrides[get_image_service] = lambda: service

    try:
        response = client.post(
            "/api/images/generate",
            json={
                "prompt": "超级个体商业复利",
                "platform": "xiaohongshu",
                "aspect_ratio": "3:4",
                "style": "dark_gold",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "image_url" in data
        assert data["image_url"].startswith("data:image/svg+xml;base64,")
        assert data["prompt"] == "超级个体商业复利"
        assert data["is_fallback"] is True
        assert "3:4" in data["size"]
    finally:
        app.dependency_overrides.pop(get_image_service, None)


def test_image_endpoint_with_header_overrides(client):
    """Verify dynamic headers X-Image-Model, X-Image-Api-Key, X-Image-Base-Url are respected."""
    mock_resp = MagicMock()
    mock_item = MagicMock()
    mock_item.url = "https://images.openai.com/mock-dalle3.png"
    mock_item.revised_prompt = "DALL-E 3 revised prompt"
    mock_resp.data = [mock_item]

    mock_openai = MagicMock()
    mock_openai.images.generate = AsyncMock(return_value=mock_resp)

    # Test with custom headers overriding default Agnes model to DALL-E 3
    with patch("app.services.image_service.AsyncOpenAI", return_value=mock_openai):
        response = client.post(
            "/api/images/generate",
            json={
                "prompt": "商业思考",
                "platform": "xiaohongshu",
            },
            headers={
                "X-Image-Model": "dall-e-3",
                "X-Image-Api-Key": "sk-custom-dalle3-key",
                "X-Image-Base-Url": "https://api.openai.com/v1",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["image_url"] == "https://images.openai.com/mock-dalle3.png"
        assert data["is_fallback"] is False


def test_image_endpoint_empty_prompt_validation(client):
    """Empty or whitespace prompt returns 422 validation error."""
    response = client.post(
        "/api/images/generate",
        json={"prompt": "    "},
    )
    assert response.status_code == 422
