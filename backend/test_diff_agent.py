import pytest
from unittest.mock import AsyncMock, MagicMock
from app.engine.agents.diff_agent import DiffAgent
from app.schemas.diff_schemas import (
    DiffInput,
    LLMDNAExtraction,
)


@pytest.mark.asyncio
async def test_diff_agent_zero_diff_skips_llm():
    """
    CRITICAL MECHANICAL CONSTRAINT:
    The Diff Agent MUST programmatically check if the diff between original_ai_draft
    and user_final_draft is zero before calling the LLM, aborting early and skipping
    LLM invocation entirely.
    """
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock()

    agent = DiffAgent(client=mock_client)
    input_data = DiffInput(
        original_ai_draft="This is the exact same text.\nNo changes here.",
        user_final_draft="This is the exact same text.\nNo changes here.",
        topic="Testing Zero Diff",
    )

    result = await agent.extract_dna(input_data)

    assert result.has_diff is False
    assert "No modifications detected" in result.diff_summary
    assert result.thinking_dna is not None
    assert len(result.thinking_dna.vocabulary_habits) == 0
    assert len(result.thinking_dna.logic_preferences) == 0
    assert len(result.thinking_dna.core_values) == 0

    # Ensure LLM was NEVER called
    mock_client.beta.chat.completions.parse.assert_not_called()


@pytest.mark.asyncio
async def test_diff_agent_zero_diff_with_whitespace_stripping():
    """
    Verify whitespace around otherwise identical text still triggers the zero-diff gate.
    """
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock()

    agent = DiffAgent(client=mock_client)
    input_data = DiffInput(
        original_ai_draft="Same content\n\n",
        user_final_draft="  Same content  ",
    )

    result = await agent.extract_dna(input_data)
    assert result.has_diff is False
    mock_client.beta.chat.completions.parse.assert_not_called()


@pytest.mark.asyncio
async def test_diff_agent_zero_diff_with_crlf_normalization():
    """
    Verify CRLF (Windows) vs LF (Unix/Web) line endings on identical text
    still triggers the zero-diff gate and never invokes the LLM.
    """
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock()

    agent = DiffAgent(client=mock_client)
    input_data = DiffInput(
        original_ai_draft="Line one\r\nLine two\r\nLine three",
        user_final_draft="Line one\nLine two\nLine three",
    )

    result = await agent.extract_dna(input_data)
    assert result.has_diff is False
    mock_client.beta.chat.completions.parse.assert_not_called()


@pytest.mark.asyncio
async def test_diff_agent_success_with_diff():
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock()

    mock_parsed = LLMDNAExtraction(
        diff_summary="Replaced academic tone with direct, practitioner-led examples.",
        vocabulary_habits=[
            "Prefers short, punchy verbs",
            "Introduced engineering jargon like 'zero-latency'",
        ],
        logic_preferences=[
            "Inverted structure: conclusion first",
            "Added concrete failure case study",
        ],
        core_values=[
            "Extreme pragmatism over theory",
            "Skin in the game",
        ],
        summary="A pragmatic, practitioner-oriented thinker who cuts fluff and demands real-world proof.",
    )

    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed
    mock_choice.message.refusal = None
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse.return_value = mock_response

    agent = DiffAgent(client=mock_client)
    input_data = DiffInput(
        original_ai_draft="Autonomous agents will revolutionize software creation in the future.",
        user_final_draft="Autonomous agents are rewriting software now. Here is zero-latency proof.",
        topic="Autonomous AI",
    )

    result = await agent.extract_dna(input_data)

    assert result.has_diff is True
    assert result.diff_summary == "Replaced academic tone with direct, practitioner-led examples."
    assert "Prefers short, punchy verbs" in result.thinking_dna.vocabulary_habits
    assert "Inverted structure: conclusion first" in result.thinking_dna.logic_preferences
    assert "Extreme pragmatism over theory" in result.thinking_dna.core_values
    assert "practitioner-oriented thinker" in result.thinking_dna.summary

    mock_client.beta.chat.completions.parse.assert_called_once()
    call_kwargs = mock_client.beta.chat.completions.parse.call_args[1]
    user_msg = next(m["content"] for m in call_kwargs["messages"] if m["role"] == "user")
    assert "UNIFIED DIFF" in user_msg
    assert "--- Original_AI_Draft\n+++ User_Final_Draft\n@@" in user_msg
    assert "Autonomous agents" in user_msg


@pytest.mark.asyncio
async def test_diff_agent_lexical_stripping_on_extracted_dna():
    """
    Harness Constraint:
    Extracted DNA tags and summaries must be stripped of AI clichés.
    """
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock()

    mock_parsed = LLMDNAExtraction(
        diff_summary="In today's fast-paced world, the user decided to delve into concise prose.",
        vocabulary_habits=[
            "In today's fast-paced world, prefers active verbs",
            "Avoids the rich tapestry of metaphors",
        ],
        logic_preferences=[
            "At the end of the day, prioritizes simplicity",
        ],
        core_values=[
            "Delve into core principles directly",
        ],
        summary="In today's fast-paced world, stands as a testament to authentic voice.",
    )

    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed
    mock_choice.message.refusal = None
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse.return_value = mock_response

    agent = DiffAgent(client=mock_client)
    input_data = DiffInput(
        original_ai_draft="Original text.",
        user_final_draft="Significantly altered user text.",
    )

    result = await agent.extract_dna(input_data)

    assert result.has_diff is True
    # Verify AI clichés are stripped or replaced
    assert "in today's fast-paced world" not in result.diff_summary.lower()
    assert "delve into" not in result.diff_summary.lower()
    assert "in today's fast-paced world" not in result.thinking_dna.vocabulary_habits[0].lower()
    assert "rich tapestry" not in result.thinking_dna.vocabulary_habits[1].lower()
    assert "at the end of the day" not in result.thinking_dna.logic_preferences[0].lower()
    assert "delve into" not in result.thinking_dna.core_values[0].lower()
    assert "stands as a testament to" not in result.thinking_dna.summary.lower()


@pytest.mark.asyncio
async def test_diff_agent_refusal():
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock()

    mock_choice = MagicMock()
    mock_choice.message.parsed = None
    mock_choice.message.refusal = "Content policy violation."
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse.return_value = mock_response

    agent = DiffAgent(client=mock_client)
    input_data = DiffInput(
        original_ai_draft="Old text",
        user_final_draft="Harmful text",
    )

    with pytest.raises(ValueError, match="Model refused request"):
        await agent.extract_dna(input_data)


@pytest.mark.asyncio
async def test_diff_agent_parsing_failure():
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock()

    mock_choice = MagicMock()
    mock_choice.message.parsed = None
    mock_choice.message.refusal = None
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse.return_value = mock_response

    agent = DiffAgent(client=mock_client)
    input_data = DiffInput(
        original_ai_draft="Old text",
        user_final_draft="New text",
    )

    with pytest.raises(ValueError, match="Failed to parse the response"):
        await agent.extract_dna(input_data)


def test_diff_input_validation():
    # Empty drafts without draft_id
    with pytest.raises(ValueError, match="original_ai_draft cannot be empty"):
        DiffInput(original_ai_draft="", user_final_draft="valid text")

    with pytest.raises(ValueError, match="user_final_draft cannot be empty"):
        DiffInput(original_ai_draft="valid text", user_final_draft="   ")


@pytest.mark.asyncio
async def test_diff_agent_viewpoint_judgments_with_zero_text_diff():
    """
    When the user does not edit the long-form text (orig == final),
    but selects a contrarian viewpoint judgment, the zero-diff gate
    should allow extraction, and the viewpoint must be retained in Thinking DNA.
    """
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock()

    mock_parsed = LLMDNAExtraction(
        diff_summary="User adopted contrarian stance on developer obsolescence.",
        vocabulary_habits=["Prefers direct, pragmatic tone"],
        logic_preferences=["Emphasizes counter-intuitive framing"],
        core_values=["Believes in individual craftsmanship"],
        summary="Pragmatic builder with strong conviction in developer sovereignty.",
    )

    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed
    mock_choice.message.refusal = None
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse.return_value = mock_response

    from app.schemas.diff_schemas import ViewpointJudgment
    judgment = ViewpointJudgment(
        viewpoint_id="vp_1",
        claim="AI will replace all developers.",
        selected_key="counter",
        selected_text="AI supercharges builders who master system thinking.",
        custom_note="Experience shows builders with taste thrive.",
    )

    agent = DiffAgent(client=mock_client)
    input_data = DiffInput(
        original_ai_draft="Identical text in draft.",
        user_final_draft="Identical text in draft.",
        viewpoint_judgments=[judgment],
    )

    result = await agent.extract_dna(input_data)
    assert result.has_diff is True
    assert any("AI supercharges builders" in v for v in result.thinking_dna.core_values)
    mock_client.beta.chat.completions.parse.assert_called_once()

