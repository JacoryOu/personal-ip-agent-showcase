import os
from typing import Optional
from openai import AsyncOpenAI

from app.core.model_gateway import ModelGateway, ModelRole, get_model_gateway
from app.engine.prompts.outline_prompts import OUTLINE_AGENT_SYSTEM_PROMPT
from app.engine.prompts.dna_context import format_dna_prompt_section, format_full_ip_context_prompt
from app.schemas.outline_schemas import OutlineInput, OutlineOutput, Outline, OutlineSection


class OutlineAgent:
    def __init__(
        self,
        client: Optional[AsyncOpenAI] = None,
        model: Optional[str] = None,
        gateway: Optional[ModelGateway] = None,
    ):
        """
        Initializes the OutlineAgent.
        If a ModelGateway is provided, it uses it.
        If an AsyncOpenAI client is provided, wraps it in a gateway for backwards compatibility.
        Otherwise, uses the global get_model_gateway().
        """
        if gateway is not None:
            self.gateway = gateway
        elif client is not None:
            self.gateway = ModelGateway(default_client=client)
        else:
            self.gateway = get_model_gateway()

        self.model = model
        # Keep client attribute for backward compatibility with existing tests
        self.client = client or self.gateway.get_client_for_role(ModelRole.OUTLINE)

    async def generate_outlines(self, input_data: OutlineInput) -> OutlineOutput:
        """
        Generates two divergent outlines (A and B) for a given topic using the ModelGateway.
        Incorporates user's Thinking DNA into the prompt context if available.
        """
        dna_section = input_data.ip_context_prompt or format_full_ip_context_prompt(
            thinking_dna=input_data.thinking_dna,
            persona=input_data.persona,
            stories=input_data.stories,
            product=input_data.product,
        )
        if not dna_section and input_data.thinking_dna:
            dna_section = format_dna_prompt_section(input_data.thinking_dna)

        user_content = f"Topic: {input_data.topic}"
        if input_data.additional_context:
            user_content += f"\nAdditional Context: {input_data.additional_context}"
        if dna_section:
            user_content += f"\n{dna_section}"

        system_prompt = (
            OUTLINE_AGENT_SYSTEM_PROMPT
            + '\nYou MUST respond with valid raw JSON containing keys "outline_a" and "outline_b".'
            + ' Do NOT wrap your response in markdown code blocks (e.g. ```json ... ```), return pure JSON only.'
            + ' Example: {"outline_a": {"title": "...", "rationale": "...", "sections": [{"title": "...", "bullet_points": ["..."]}]}, "outline_b": {"title": "...", "rationale": "...", "sections": [{"title": "...", "bullet_points": ["..."]}]}}'
        )

        out = await self.gateway.generate_structured(
            role=ModelRole.OUTLINE,
            messages=[{"role": "user", "content": user_content}],
            response_model=OutlineOutput,
            system_prompt=system_prompt,
            model_override=self.model,
        )
        out.persona_id = input_data.persona_id
        out.product_id = input_data.product_id
        out.story_ids = input_data.story_ids or []
        out.ip_context_prompt = dna_section
        return out


__all__ = ["OutlineAgent", "OutlineInput", "OutlineOutput", "Outline", "OutlineSection"]
