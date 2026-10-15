import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import BaseModel

from app.core.config import settings
from app.core.model_gateway import (
    ModelGateway,
    ModelRole,
    get_model_gateway,
    set_model_gateway,
)


class DummyResponseSchema(BaseModel):
    title: str
    score: int


@pytest.fixture(autouse=True)
def reset_gateway():
    set_model_gateway(None)
    yield
    set_model_gateway(None)


def test_role_to_model_resolution_default():
    gateway = ModelGateway()
    # When no overrides are set, all roles resolve to OPENAI_MODEL
    assert gateway.get_model_for_role(ModelRole.OUTLINE) == (settings.OPENAI_MODEL or "gpt-4o")
    assert gateway.get_model_for_role(ModelRole.DRAFT) == (settings.OPENAI_MODEL or "gpt-4o")
    assert gateway.get_model_for_role(ModelRole.DIFF) == (settings.OPENAI_MODEL or "gpt-4o")


def test_role_to_model_resolution_custom_override(monkeypatch):
    gateway = ModelGateway()

    # Test OUTLINE override
    monkeypatch.setenv("OUTLINE_MODEL", "qwen-max")
    assert gateway.get_model_for_role(ModelRole.OUTLINE) == "qwen-max"
    # Other roles still default
    assert gateway.get_model_for_role(ModelRole.DRAFT) == (settings.OPENAI_MODEL or "gpt-4o")

    # Test DRAFT override
    monkeypatch.setenv("DRAFT_MODEL", "claude-3-5-sonnet")
    assert gateway.get_model_for_role(ModelRole.DRAFT) == "claude-3-5-sonnet"

    # Test DIFF override
    monkeypatch.setenv("DIFF_MODEL", "deepseek-r1")
    assert gateway.get_model_for_role(ModelRole.DIFF) == "deepseek-r1"


def test_base_url_resolution(monkeypatch):
    gateway = ModelGateway()

    # Default without overrides
    assert gateway.get_base_url_for_role(ModelRole.OUTLINE) == settings.OPENAI_BASE_URL

    # Role-specific base_url override
    monkeypatch.setenv("OUTLINE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    assert gateway.get_base_url_for_role(ModelRole.OUTLINE) == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert gateway.get_base_url_for_role(ModelRole.DRAFT) == settings.OPENAI_BASE_URL


def test_client_caching():
    gateway = ModelGateway()
    client_outline = gateway.get_client_for_role(ModelRole.OUTLINE)
    client_draft = gateway.get_client_for_role(ModelRole.DRAFT)

    # Since both have default API key and base_url, the client should be cached and reused
    assert client_outline is client_draft


@pytest.mark.asyncio
async def test_structured_generation_success():
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock()

    mock_parsed = DummyResponseSchema(title="Structured Test", score=100)
    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed
    mock_choice.message.refusal = None
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client.beta.chat.completions.parse.return_value = mock_response

    gateway = ModelGateway()
    gateway.register_client_for_role(ModelRole.OUTLINE, mock_client)

    result = await gateway.generate_structured(
        role=ModelRole.OUTLINE,
        messages=[{"role": "user", "content": "Hello"}],
        response_model=DummyResponseSchema,
        system_prompt="You are a creative outline assistant.",
    )

    assert result == mock_parsed
    assert result.title == "Structured Test"
    assert result.score == 100

    mock_client.beta.chat.completions.parse.assert_called_once()
    called_kwargs = mock_client.beta.chat.completions.parse.call_args.kwargs
    assert called_kwargs["messages"][0] == {"role": "system", "content": "You are a creative outline assistant."}
    assert called_kwargs["messages"][1] == {"role": "user", "content": "Hello"}


@pytest.mark.asyncio
async def test_resilient_fallback_to_json_completion_when_parse_fails():
    mock_client = MagicMock()
    # 1. Parse fails with exception (e.g. 400 Bad Request on third-party proxy)
    mock_client.beta.chat.completions.parse = AsyncMock(side_effect=RuntimeError("Unsupported endpoint for beta parse"))

    # 2. Fallback create succeeds with markdown wrapped JSON
    mock_create_choice = MagicMock()
    mock_create_choice.message.content = '```json\n{"title": "Fallback Success", "score": 88}\n```'
    mock_create_choice.message.refusal = None
    mock_create_response = MagicMock()
    mock_create_response.choices = [mock_create_choice]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_create_response)

    gateway = ModelGateway()
    gateway.register_client_for_role(ModelRole.DRAFT, mock_client)

    result = await gateway.generate_structured(
        role=ModelRole.DRAFT,
        messages=[{"role": "user", "content": "Generate draft"}],
        response_model=DummyResponseSchema,
    )

    assert isinstance(result, DummyResponseSchema)
    assert result.title == "Fallback Success"
    assert result.score == 88

    mock_client.beta.chat.completions.parse.assert_called_once()
    mock_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_resilient_fallback_when_parse_returns_none():
    mock_client = MagicMock()
    # Parse returns choice with parsed=None and refusal=None
    mock_choice = MagicMock()
    mock_choice.message.parsed = None
    mock_choice.message.refusal = None
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse = AsyncMock(return_value=mock_response)

    # Fallback create returns clean JSON
    mock_create_choice = MagicMock()
    mock_create_choice.message.content = '{"title": "Clean JSON Fallback", "score": 99}'
    mock_create_choice.message.refusal = None
    mock_create_response = MagicMock()
    mock_create_response.choices = [mock_create_choice]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_create_response)

    gateway = ModelGateway()
    gateway.register_client_for_role(ModelRole.DIFF, mock_client)

    result = await gateway.generate_structured(
        role=ModelRole.DIFF,
        messages=[{"role": "user", "content": "Extract diff"}],
        response_model=DummyResponseSchema,
    )

    assert result.title == "Clean JSON Fallback"
    assert result.score == 99
    mock_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_refusal_error_handling_in_parse():
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.parsed = None
    mock_choice.message.refusal = "Content violates policy"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse = AsyncMock(return_value=mock_response)
    mock_client.chat.completions.create = AsyncMock()

    gateway = ModelGateway()
    gateway.register_client_for_role(ModelRole.OUTLINE, mock_client)

    with pytest.raises(ValueError, match="Model refused request: Content violates policy"):
        await gateway.generate_structured(
            role=ModelRole.OUTLINE,
            messages=[{"role": "user", "content": "Something disallowed"}],
            response_model=DummyResponseSchema,
        )

    # Crucial: fallback create must NOT be called when model refused
    mock_client.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_refusal_error_handling_in_fallback():
    mock_client = MagicMock()
    # Parse fails
    mock_client.beta.chat.completions.parse = AsyncMock(side_effect=RuntimeError("Parse error"))

    # Fallback has refusal
    mock_choice = MagicMock()
    mock_choice.message.refusal = "Fallback refusal reason"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    gateway = ModelGateway()
    gateway.register_client_for_role(ModelRole.DRAFT, mock_client)

    with pytest.raises(ValueError, match="Model refused request: Fallback refusal reason"):
        await gateway.generate_structured(
            role=ModelRole.DRAFT,
            messages=[{"role": "user", "content": "Draft prompt"}],
            response_model=DummyResponseSchema,
        )


@pytest.mark.asyncio
async def test_both_fail_raises_value_error():
    mock_client = MagicMock()
    # Parse fails
    mock_client.beta.chat.completions.parse = AsyncMock(side_effect=Exception("API failure"))

    # Fallback returns invalid non-JSON string
    mock_choice = MagicMock()
    mock_choice.message.content = "Not a JSON at all"
    mock_choice.message.refusal = None
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    gateway = ModelGateway()
    gateway.register_client_for_role(ModelRole.DIFF, mock_client)

    with pytest.raises(ValueError, match="Failed to parse the response from the model."):
        await gateway.generate_structured(
            role=ModelRole.DIFF,
            messages=[{"role": "user", "content": "Prompt"}],
            response_model=DummyResponseSchema,
        )


def test_singleton_get_model_gateway():
    gw1 = get_model_gateway()
    gw2 = get_model_gateway()
    assert gw1 is gw2

    custom_gw = ModelGateway()
    set_model_gateway(custom_gw)
    assert get_model_gateway() is custom_gw


def test_extract_json_from_text_formats():
    from app.core.model_gateway import extract_json_from_text

    # 1. Pure JSON
    assert extract_json_from_text('{"title": "Pure", "score": 1}') == {"title": "Pure", "score": 1}

    # 2. Markdown fenced with ```json
    markdown_json = '```json\n{\n  "title": "Fenced",\n  "score": 2\n}\n```'
    assert extract_json_from_text(markdown_json) == {"title": "Fenced", "score": 2}

    # 3. Markdown fenced without json label
    fenced_raw = '```\n{\n  "title": "RawFence",\n  "score": 3\n}\n```'
    assert extract_json_from_text(fenced_raw) == {"title": "RawFence", "score": 3}

    # 4. DeepSeek-R1 style with <think>...</think> reasoning tags
    think_json = '<think>I should formulate the response as JSON.</think>\n```json\n{"title": "Thought", "score": 4}\n```'
    assert extract_json_from_text(think_json) == {"title": "Thought", "score": 4}

    # 5. Conversational prefix and suffix text
    chatty_json = 'Here is the requested outline in JSON:\n{"title": "Chatty", "score": 5}\nHope this helps!'
    assert extract_json_from_text(chatty_json) == {"title": "Chatty", "score": 5}


@pytest.mark.asyncio
async def test_rescue_markdown_wrapped_validation_error_in_parse():
    """
    Directly tests the issue where beta.chat.completions.parse fails with a ValidationError
    because third-party model (like DeepSeek) returns ```json\n{...}\n```.
    The gateway must rescue and parse it without throwing an error to the caller.
    """
    from pydantic import ValidationError

    mock_client = MagicMock()

    # Simulate ValidationError with input string containing markdown fences
    try:
        DummyResponseSchema.model_validate_json('```json\n{"title": "Rescued", "score": 42}\n```')
    except ValidationError as val_err:
        mock_client.beta.chat.completions.parse = AsyncMock(side_effect=val_err)

    mock_client.chat.completions.create = AsyncMock()

    gateway = ModelGateway()
    gateway.register_client_for_role(ModelRole.OUTLINE, mock_client)

    result = await gateway.generate_structured(
        role=ModelRole.OUTLINE,
        messages=[{"role": "user", "content": "Generate topic"}],
        response_model=DummyResponseSchema,
    )

    assert result.title == "Rescued"
    assert result.score == 42
    # Layer 1 rescued it immediately without calling Layer 2!
    mock_client.chat.completions.create.assert_not_called()

