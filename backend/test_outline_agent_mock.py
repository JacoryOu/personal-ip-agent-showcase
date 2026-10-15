import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.engine.agents.outline_agent import OutlineAgent, OutlineInput, OutlineOutput, Outline, OutlineSection

async def main():
    print("Testing OutlineAgent...")
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock()
    
    mock_response = MagicMock()
    mock_parsed = OutlineOutput(
        outline_a=Outline(title="Title A", rationale="Rat A", sections=[OutlineSection(title="Sec A1", bullet_points=["A1.1"])]),
        outline_b=Outline(title="Title B", rationale="Rat B", sections=[OutlineSection(title="Sec B1", bullet_points=["B1.1"])])
    )
    
    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed
    mock_response.choices = [mock_choice]
    
    mock_client.beta.chat.completions.parse.return_value = mock_response

    agent = OutlineAgent(client=mock_client)
    input_data = OutlineInput(topic="Artificial Intelligence")
    
    output = await agent.generate_outlines(input_data)
    print("Generated outlines successfully!")
    print("Outline A:", output.outline_a.title)
    print("Outline B:", output.outline_b.title)

    mock_client.beta.chat.completions.parse.assert_called_once()
    print("API called correctly.")

if __name__ == "__main__":
    asyncio.run(main())
