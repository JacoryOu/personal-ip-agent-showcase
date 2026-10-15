import pytest
from unittest.mock import AsyncMock, MagicMock
from app.engine.agents.draft_agent import DraftAgent
from app.schemas.draft_schemas import DraftInput, DraftOutput
from app.schemas.outline_schemas import Outline, OutlineSection


@pytest.fixture
def sample_outline():
    return Outline(
        title="The Future of Autonomous Coding",
        rationale="Explores shift towards autonomous multi-agent software engineering.",
        sections=[
            OutlineSection(
                title="Introduction to AI Agents",
                bullet_points=["Evolution from autocomplete to agents", "Shift in developer roles"],
            ),
            OutlineSection(
                title="Cognitive IP & Memory",
                bullet_points=["Extracting personal thinking style", "Preventing homogenization"],
            ),
            OutlineSection(
                title="Conclusion",
                bullet_points=["The era of individual 10x creators", "Final thoughts"],
            ),
        ],
    )


@pytest.mark.asyncio
async def test_draft_agent_success(sample_outline):
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock()

    mock_parsed = DraftOutput(
        title="The Future of Autonomous Coding",
        summary="A deep dive into how AI agents transform software craftsmanship.",
        content="## Introduction\n\nSoftware engineering is undergoing a tectonic shift...",
        word_count=500,
    )
    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed
    mock_choice.message.refusal = None
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse.return_value = mock_response

    agent = DraftAgent(client=mock_client)
    input_data = DraftInput(
        topic="AI Autonomous Coding",
        outline=sample_outline,
        additional_context="Focus on cognitive uniqueness and solopreneurs.",
    )

    result = await agent.generate_draft(input_data)

    assert result.title == "The Future of Autonomous Coding"
    assert "Software engineering" in result.content
    assert result.word_count > 0
    assert len(result.core_viewpoints) > 0
    assert result.core_viewpoints[0].claim != ""

    # Verify mock was called with correct parameters
    mock_client.beta.chat.completions.parse.assert_called_once()
    call_kwargs = mock_client.beta.chat.completions.parse.call_args[1]
    messages = call_kwargs["messages"]
    assert any("AI Autonomous Coding" in m["content"] for m in messages if m["role"] == "user")
    assert any("solopreneurs" in m["content"] for m in messages if m["role"] == "user")


@pytest.mark.asyncio
async def test_draft_agent_computes_accurate_word_count_with_smart_punctuation(sample_outline):
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock()

    # English text with curly apostrophe and em-dash (non-ASCII)
    content = "Don’t worry about autonomous agents — they are here to stay."
    mock_parsed = DraftOutput(
        title="Draft Title",
        summary="Draft Summary",
        content=content,
        word_count=None,
    )
    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed
    mock_choice.message.refusal = None
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse.return_value = mock_response

    agent = DraftAgent(client=mock_client)
    input_data = DraftInput(topic="Test Topic", outline=sample_outline)

    result = await agent.generate_draft(input_data)
    # Should be 10 words, NOT 50+ characters
    assert result.word_count == 10


@pytest.mark.asyncio
async def test_draft_agent_lexical_stripping(sample_outline):
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock()

    mock_parsed = DraftOutput(
        title="Navigating the Landscape of Autonomous AI",
        summary="In today's fast-paced world, it is crucial to remember that AI is growing.",
        content="In today's fast-paced world, we must delve into the rich tapestry of modern software.",
        word_count=100,
    )
    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed
    mock_choice.message.refusal = None
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse.return_value = mock_response

    agent = DraftAgent(client=mock_client)
    input_data = DraftInput(topic="Test Topic", outline=sample_outline)

    result = await agent.generate_draft(input_data)

    assert "delve into" not in result.content.lower()
    assert "explore" in result.content.lower()
    assert "rich tapestry" not in result.content.lower()
    assert "in today's fast-paced world" not in result.content.lower()
    assert "in today's fast-paced world" not in (result.summary or "").lower()
    assert "navigating" in result.title.lower()


@pytest.mark.asyncio
async def test_draft_agent_refusal(sample_outline):
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock()

    mock_choice = MagicMock()
    mock_choice.message.parsed = None
    mock_choice.message.refusal = "Content violates safety policy."
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse.return_value = mock_response

    agent = DraftAgent(client=mock_client)
    input_data = DraftInput(topic="Unsafe topic", outline=sample_outline)

    with pytest.raises(ValueError, match="Model refused request"):
        await agent.generate_draft(input_data)


@pytest.mark.asyncio
async def test_draft_agent_parsing_failure(sample_outline):
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock()

    mock_choice = MagicMock()
    mock_choice.message.parsed = None
    mock_choice.message.refusal = None
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse.return_value = mock_response

    agent = DraftAgent(client=mock_client)
    input_data = DraftInput(topic="Normal topic", outline=sample_outline)

    with pytest.raises(ValueError, match="Failed to parse the response"):
        await agent.generate_draft(input_data)


def test_draft_input_validation(sample_outline):
    with pytest.raises(ValueError, match="Topic cannot be empty"):
        DraftInput(topic="   ", outline=sample_outline)

    with pytest.raises(ValueError):
        DraftInput(topic="", outline=sample_outline)

    # Empty sections in outline
    empty_outline = Outline(title="Empty Outline", rationale="No sections", sections=[])
    with pytest.raises(ValueError, match="Outline must contain at least one section"):
        DraftInput(topic="Valid Topic", outline=empty_outline)

    # Whitespace-only additional context is converted to None
    di = DraftInput(topic="Valid Topic", outline=sample_outline, additional_context="   ")
    assert di.additional_context is None


def test_draft_output_core_viewpoints_normalization():
    raw_data = {
        "title": "Test Title",
        "content": "# Test Content",
        "summary": "Test Summary",
        "core_viewpoints": [
            {
                "id": "vp_1",
                "claim": "AI will replace junior developers.",
                "section_title": "Industry Trends",
                "options": [
                    {"key": "agree", "label": "认同并保留", "text": "AI will replace junior developers."},
                    {"key": "counter", "label": "逆向反驳", "text": "AI empowers junior developers to build faster."}
                ]
            }
        ]
    }
    output = DraftOutput.model_validate(raw_data)
    assert len(output.core_viewpoints) == 1
    assert output.core_viewpoints[0].id == "vp_1"
    assert output.core_viewpoints[0].claim == "AI will replace junior developers."
    assert len(output.core_viewpoints[0].options) == 2
    assert output.core_viewpoints[0].options[1].key == "counter"

