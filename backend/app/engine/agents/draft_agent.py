import os
from typing import Optional
from openai import AsyncOpenAI

from app.core.model_gateway import ModelGateway, ModelRole, get_model_gateway
from app.engine.prompts.draft_prompts import DRAFT_AGENT_SYSTEM_PROMPT
from app.engine.prompts.dna_context import format_dna_prompt_section, format_full_ip_context_prompt
from app.schemas.draft_schemas import DraftInput, DraftOutput, CoreViewpoint, ViewpointOption
from app.utils.lexical_filter import strip_ai_lexicon, compute_accurate_word_count



REFERENCE_STYLE_HEADER = "[REFERENCE STYLE FINGERPRINT - SELECTED VIRAL ANALYSIS]"
REFERENCE_STYLE_FOOTER = "[END REFERENCE STYLE FINGERPRINT]"


def format_reference_style_section(style_prompt: str) -> str:
    """Render the trusted, server-derived style fingerprint as its own prompt block.

    The block is intentionally separated from the persona / Thinking DNA context so
    the model can treat it as a *structural and rhythmic reference only*. The rules
    below are hard constraints, not suggestions: the draft must never copy wording,
    cases, facts or distinctive phrasing from the analysed article, must not adopt
    the reference author's identity, must not invent facts to imitate the style, and
    the user's Persona, Thinking DNA and real material always take priority.
    """
    body = (style_prompt or "").strip()
    if not body:
        return ""
    return (
        f"\n{REFERENCE_STYLE_HEADER}\n"
        "The following is a style fingerprint of a viral article selected by the user.\n"
        "Use it ONLY as a reference for structure, pacing, paragraph organisation and narrative mechanics.\n"
        "Hard constraints:\n"
        "- Do NOT copy wording, phrasing, cases, facts or any distinctive expression from the reference.\n"
        "- Do NOT present yourself as the reference author or blur the identity between the reference author and the current user.\n"
        "- Do NOT invent facts, data or experiences in order to imitate the style.\n"
        "- The user's Persona, Thinking DNA and real source material always take priority over this reference.\n"
        f"{body}\n"
        f"{REFERENCE_STYLE_FOOTER}\n"
    )

class DraftAgent:
    def __init__(
        self,
        client: Optional[AsyncOpenAI] = None,
        model: Optional[str] = None,
        gateway: Optional[ModelGateway] = None,
    ):
        """
        Initializes the DraftAgent.
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
        self.client = client or self.gateway.get_client_for_role(ModelRole.DRAFT)

    async def generate_draft(self, input_data: DraftInput) -> DraftOutput:
        """
        Expands the chosen outline and topic into a comprehensive article draft.
        Deeply embodies user's Thinking DNA when available.
        Enforces code-based lexical filtering and accurate word count.
        """
        sections_str = []
        for i, sec in enumerate(input_data.outline.sections, 1):
            bullets = "\n".join([f"    - {b}" for b in sec.bullet_points])
            sections_str.append(f"  {i}. {sec.title}\n{bullets}")
        sections_formatted = "\n".join(sections_str)

        dna_section = input_data.ip_context_prompt or format_full_ip_context_prompt(
            thinking_dna=input_data.thinking_dna,
            persona=input_data.persona,
            stories=input_data.stories,
            product=input_data.product,
        )
        if not dna_section and input_data.thinking_dna:
            dna_section = format_dna_prompt_section(input_data.thinking_dna)

        user_content = (
            f"Topic: {input_data.topic}\n"
            f"Outline Title: {input_data.outline.title}\n"
            f"Outline Rationale: {input_data.outline.rationale}\n\n"
            f"Outline Structure:\n{sections_formatted}\n"
        )
        if input_data.additional_context:
            user_content += f"\nAdditional Context / Instructions:\n{input_data.additional_context}\n"
        if dna_section:
            user_content += f"\n{dna_section}\n"
        if input_data.style_fingerprint_prompt:
            user_content += format_reference_style_section(input_data.style_fingerprint_prompt)

        system_prompt = (
            DRAFT_AGENT_SYSTEM_PROMPT
            + '\nYou MUST respond with valid raw JSON with keys "title", "summary", "content" (in Markdown), and "core_viewpoints".'
            + ' Do NOT wrap your response in markdown code blocks (e.g. ```json ... ```), return pure JSON only.'
            + ' Example: {"title": "...", "summary": "...", "content": "# ...\\n\\n...", "core_viewpoints": [{"id": "vp_1", "claim": "...", "section_title": "...", "options": [{"key": "agree", "label": "认同并保留", "text": "..."}, {"key": "counter", "label": "逆向反驳", "text": "..."}]}]}'
        )

        draft = await self.gateway.generate_structured(
            role=ModelRole.DRAFT,
            messages=[{"role": "user", "content": user_content}],
            response_model=DraftOutput,
            system_prompt=system_prompt,
            model_override=self.model,
        )

        # Code-Based Lexical Stripping (Deterministic Harness Constraint from AGENTS.md)
        cleaned_content = strip_ai_lexicon(draft.content)
        cleaned_title = strip_ai_lexicon(draft.title)
        cleaned_summary = strip_ai_lexicon(draft.summary) if draft.summary else None

        # Process core viewpoints
        cleaned_viewpoints: list[CoreViewpoint] = []
        for vp in (draft.core_viewpoints or []):
            claim_clean = strip_ai_lexicon(vp.claim).strip()
            if not claim_clean:
                continue
            sec_clean = strip_ai_lexicon(vp.section_title).strip() if vp.section_title else None
            opts: list[ViewpointOption] = []
            for opt in vp.options:
                opts.append(
                    ViewpointOption(
                        key=opt.key,
                        label=strip_ai_lexicon(opt.label).strip(),
                        text=strip_ai_lexicon(opt.text).strip(),
                    )
                )
            if not opts:
                opts = [
                    ViewpointOption(key="agree", label="认同并保留", text=claim_clean),
                    ViewpointOption(key="counter", label="逆向反驳", text="反对该论点：在实际中存在反向作用力"),
                ]
            cleaned_viewpoints.append(
                CoreViewpoint(
                    id=vp.id,
                    claim=claim_clean,
                    section_title=sec_clean,
                    options=opts,
                )
            )

        # Resilient fallback: if the model did not output core_viewpoints, extract from outline sections
        if not cleaned_viewpoints and input_data.outline.sections:
            for idx, sec in enumerate(input_data.outline.sections[:3], 1):
                bullet = sec.bullet_points[0] if sec.bullet_points else sec.title
                cleaned_viewpoints.append(
                    CoreViewpoint(
                        id=f"vp_{idx}",
                        claim=bullet,
                        section_title=sec.title,
                        options=[
                            ViewpointOption(key="agree", label="认同并保留", text=bullet),
                            ViewpointOption(key="counter", label="逆向反驳", text=f"反对「{bullet[:20]}」：存在显著的反向实践模式"),
                            ViewpointOption(key="nuanced", label="深入洞察", text=f"深层重构「{bullet[:20]}」：需区分不同业务阶段与边界"),
                        ],
                    )
                )

        # Compute accurate word / character count
        accurate_count = compute_accurate_word_count(cleaned_content)

        return DraftOutput(
            title=cleaned_title,
            summary=cleaned_summary,
            content=cleaned_content,
            word_count=accurate_count,
            core_viewpoints=cleaned_viewpoints,
            persona_id=input_data.persona_id,
            product_id=input_data.product_id,
            story_ids=input_data.story_ids or [],
            ip_context_prompt=input_data.ip_context_prompt,
        )


__all__ = [
    "DraftAgent",
    "DraftInput",
    "DraftOutput",
    "CoreViewpoint",
    "ViewpointOption",
    "format_reference_style_section",
    "REFERENCE_STYLE_HEADER",
    "REFERENCE_STYLE_FOOTER",
]
