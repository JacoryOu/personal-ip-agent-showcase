import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.engine.agents.outline_agent import OutlineAgent
from app.engine.agents.draft_agent import DraftAgent
from app.schemas.outline_schemas import OutlineInput, Outline, OutlineSection
from app.schemas.draft_schemas import DraftInput


def test_outline_empty_topic():
    with pytest.raises(ValueError, match="Topic cannot be empty"):
        OutlineInput(topic="   ")

    with pytest.raises(ValueError):
        OutlineInput(topic="")


def test_outline_whitespace_additional_context():
    oi = OutlineInput(topic="Valid Topic", additional_context="   ")
    assert oi.additional_context is None


def test_draft_empty_sections_outline():
    empty_outline = Outline(
        title="Test",
        rationale="Test",
        sections=[],
    )
    with pytest.raises(ValueError, match="Outline must contain at least one section"):
        DraftInput(topic="Valid Topic", outline=empty_outline)


def test_draft_empty_title_outline():
    bad_title_outline = Outline(
        title="   ",
        rationale="Test",
        sections=[OutlineSection(title="S1", bullet_points=["p1"])],
    )
    with pytest.raises(ValueError, match="Outline title cannot be empty"):
        DraftInput(topic="Valid Topic", outline=bad_title_outline)


@pytest.mark.asyncio
async def test_outline_refusal():
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock()

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.refusal = "I cannot fulfill this request."
    mock_choice.message.parsed = None
    mock_response.choices = [mock_choice]

    mock_client.beta.chat.completions.parse.return_value = mock_response

    agent = OutlineAgent(client=mock_client)
    input_data = OutlineInput(topic="Harmful topic")

    with pytest.raises(ValueError, match="Model refused request"):
        await agent.generate_outlines(input_data)


@pytest.mark.asyncio
async def test_draft_refusal():
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock()

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.refusal = "Safety violation."
    mock_choice.message.parsed = None
    mock_response.choices = [mock_choice]

    mock_client.beta.chat.completions.parse.return_value = mock_response

    sample_outline = Outline(
        title="Test",
        rationale="Test",
        sections=[OutlineSection(title="S1", bullet_points=["P1"])],
    )
    agent = DraftAgent(client=mock_client)
    input_data = DraftInput(topic="Unsafe topic", outline=sample_outline)

    with pytest.raises(ValueError, match="Model refused request"):
        await agent.generate_draft(input_data)
