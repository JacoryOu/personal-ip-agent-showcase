import difflib
import os
from typing import Optional
from openai import AsyncOpenAI

from app.core.model_gateway import ModelGateway, ModelRole, get_model_gateway
from app.engine.prompts.diff_prompts import DIFF_AGENT_SYSTEM_PROMPT
from app.schemas.diff_schemas import (
    DiffInput,
    DNAExtractionOutput,
    LLMDNAExtraction,
    ThinkingDNA,
)
from app.utils.lexical_filter import strip_ai_lexicon


class DiffAgent:
    def __init__(
        self,
        client: Optional[AsyncOpenAI] = None,
        model: Optional[str] = None,
        gateway: Optional[ModelGateway] = None,
    ):
        """
        Initializes the DiffAgent.
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
        self.client = client or self.gateway.get_client_for_role(ModelRole.DIFF)

    async def extract_dna(self, input_data: DiffInput) -> DNAExtractionOutput:
        """
        Analyzes the diff between the original AI draft and the user's final edited draft.
        Extracts Thinking DNA (vocabulary habits, logic preferences, core values).

        CRITICAL MECHANICAL CONSTRAINT (from AGENTS.md):
        Programmatically checks if the diff between original_ai_draft and user_final_draft
        is zero before calling the LLM, aborting early with a zero-diff result and skipping
        LLM invocation entirely!
        """
        orig = (
            (input_data.original_ai_draft or "")
            .replace("\r\n", "\n")
            .replace("\r", "\n")
            .strip()
        )
        final = (
            (input_data.user_final_draft or "")
            .replace("\r\n", "\n")
            .replace("\r", "\n")
            .strip()
        )

        # Check if user made custom viewpoint adjustments (e.g. counter, nuanced, custom note)
        active_judgments = [
            j for j in input_data.viewpoint_judgments
            if j.selected_key != "agree" or (j.custom_note and j.custom_note.strip())
        ]

        # 1. Deterministic Zero-Diff Baseline Gate
        # Only abort early if both text diff is zero AND no active viewpoint judgments were provided
        if orig == final and not active_judgments:
            return DNAExtractionOutput(
                has_diff=False,
                diff_summary="No modifications detected between drafts or core viewpoints.",
                thinking_dna=ThinkingDNA(
                    vocabulary_habits=[],
                    logic_preferences=[],
                    core_values=[],
                    summary="Drafts and viewpoints are identical; no cognitive delta to extract.",
                ),
                draft_id=input_data.draft_id,
            )

        # 2. Compute Unified Diff
        orig_lines = orig.splitlines()
        final_lines = final.splitlines()
        diff_text = "\n".join(
            difflib.unified_diff(
                orig_lines,
                final_lines,
                fromfile="Original_AI_Draft",
                tofile="User_Final_Draft",
                lineterm="",
            )
        )

        judgments_str = ""
        if input_data.viewpoint_judgments:
            judgments_lines = []
            for j in input_data.viewpoint_judgments:
                note_str = f" (User Note: {j.custom_note})" if j.custom_note else ""
                judgments_lines.append(
                    f"- Original Claim: {j.claim}\n  User Choice [{j.selected_key}]: {j.selected_text}{note_str}"
                )
            judgments_str = "=== USER VIEWPOINT JUDGMENTS & STANCES ===\n" + "\n".join(judgments_lines) + "\n\n"

        user_content = (
            f"Topic: {input_data.topic or 'Untitled'}\n\n"
            f"{judgments_str}"
            f"=== UNIFIED DIFF (Line by Line) ===\n{diff_text}\n\n"
            f"=== ORIGINAL AI DRAFT ===\n{orig}\n\n"
            f"=== USER FINAL DRAFT ===\n{final}\n"
        )

        # 3. Call ModelGateway for Structured DNA Extraction
        system_prompt = (
            DIFF_AGENT_SYSTEM_PROMPT
            + '\nYou MUST respond with valid raw JSON containing keys: "diff_summary", "vocabulary_habits", "logic_preferences", "core_values", and "summary".'
            + ' Do NOT wrap your response in markdown code blocks (e.g. ```json ... ```), return pure JSON only.'
        )

        parsed: LLMDNAExtraction = await self.gateway.generate_structured(
            role=ModelRole.DIFF,
            messages=[{"role": "user", "content": user_content}],
            response_model=LLMDNAExtraction,
            system_prompt=system_prompt,
            model_override=self.model,
        )

        # 4. Code-Based Lexical Stripping (Deterministic Harness Constraint from AGENTS.md)
        cleaned_vocab = [
            strip_ai_lexicon(v)
            for v in parsed.vocabulary_habits
            if strip_ai_lexicon(v).strip()
        ]
        cleaned_logic = [
            strip_ai_lexicon(l)
            for l in parsed.logic_preferences
            if strip_ai_lexicon(l).strip()
        ]
        cleaned_values = [
            strip_ai_lexicon(c)
            for c in parsed.core_values
            if strip_ai_lexicon(c).strip()
        ]
        # Explicitly incorporate user viewpoint decisions into core values
        for j in active_judgments:
            note_part = f" (补充: {j.custom_note})" if j.custom_note else ""
            claim_brief = j.claim[:24] + "..." if len(j.claim) > 24 else j.claim
            trait = f"关于「{claim_brief}」主张: {j.selected_text}{note_part}"
            if trait not in cleaned_values:
                cleaned_values.append(trait)

        cleaned_summary = (
            strip_ai_lexicon(parsed.summary) if parsed.summary else None
        )
        cleaned_diff_summary = (
            strip_ai_lexicon(parsed.diff_summary) if parsed.diff_summary else None
        )

        thinking_dna = ThinkingDNA(
            vocabulary_habits=cleaned_vocab,
            logic_preferences=cleaned_logic,
            core_values=cleaned_values,
            summary=cleaned_summary,
        )

        return DNAExtractionOutput(
            has_diff=True,
            diff_summary=cleaned_diff_summary,
            thinking_dna=thinking_dna,
            draft_id=input_data.draft_id,
        )


__all__ = [
    "DiffAgent",
    "DiffInput",
    "DNAExtractionOutput",
    "ThinkingDNA",
]
