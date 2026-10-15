import uuid
from typing import Any, List, Optional
from pydantic import BaseModel, Field, model_validator


class ThinkingDNA(BaseModel):
    vocabulary_habits: List[str] = Field(
        default_factory=list,
        description="Extracted vocabulary habits, preferred phrasing, and tone indicators.",
    )
    logic_preferences: List[str] = Field(
        default_factory=list,
        description="Logical progression preferences, structural reorganizations, or argumentative flow.",
    )
    core_values: List[str] = Field(
        default_factory=list,
        description="Implicit or explicit values, stance, or philosophies reflected in changes.",
    )
    summary: Optional[str] = Field(
        default=None,
        description="A concise holistic summary of the author's cognitive voice and thinking style.",
    )


class ViewpointJudgment(BaseModel):
    viewpoint_id: str = Field(description="The id of the viewpoint, e.g. vp_1")
    claim: str = Field(description="The original claim in the draft")
    selected_key: str = Field(description="Selected option key: agree, counter, nuanced, or custom")
    selected_text: str = Field(description="The text of the chosen stance")
    custom_note: Optional[str] = Field(default=None, description="Optional custom user note or tweak")


class DiffInput(BaseModel):
    original_ai_draft: Optional[str] = Field(
        default=None,
        description="The original AI-generated draft content before user edits.",
    )
    user_final_draft: Optional[str] = Field(
        default=None,
        description="The user-edited final draft content.",
    )
    topic: Optional[str] = Field(
        default=None,
        description="The topic of the draft for context.",
    )
    draft_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional draft ID if associating with an existing draft record.",
    )
    user_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional user ID for persistence.",
    )
    viewpoint_judgments: List[ViewpointJudgment] = Field(
        default_factory=list,
        description="User selections and adjustments on the core viewpoints.",
    )

    @model_validator(mode="after")
    def validate_content_or_id(self) -> "DiffInput":
        if not self.draft_id:
            if not self.original_ai_draft or not self.original_ai_draft.strip():
                raise ValueError("original_ai_draft cannot be empty when draft_id is not provided.")
            if not self.user_final_draft or not self.user_final_draft.strip():
                raise ValueError("user_final_draft cannot be empty when draft_id is not provided.")
        return self


class LLMDNAExtraction(BaseModel):
    diff_summary: str = Field(
        default="",
        description="Concise description of the primary structural and stylistic changes the user made.",
    )
    vocabulary_habits: List[str] = Field(
        default_factory=list,
        description="Specific vocabulary patterns, phrasing habits, and tone adjustments the user made.",
    )
    logic_preferences: List[str] = Field(
        default_factory=list,
        description="Structural or logical flow preferences demonstrated by the edits.",
    )
    core_values: List[str] = Field(
        default_factory=list,
        description="Underlying values, opinions, or philosophy reflected in what the user prioritized or removed.",
    )
    summary: str = Field(
        default="",
        description="A concise synthesis of the user's cognitive identity and writing style.",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            diff_summary = data.get("diff_summary") or data.get("summary_of_changes") or ""
            vocab = data.get("vocabulary_habits") or data.get("vocabulary") or data.get("words") or []
            logic = data.get("logic_preferences") or data.get("logic") or data.get("structure") or []
            values = data.get("core_values") or data.get("values") or data.get("beliefs") or []
            summary = data.get("summary") or data.get("authorial_synthesis") or diff_summary or "DNA summary"

            def to_list(val: Any) -> List[str]:
                if isinstance(val, str):
                    return [val]
                if isinstance(val, list):
                    return [str(v) for v in val]
                return []

            return {
                "diff_summary": str(diff_summary),
                "vocabulary_habits": to_list(vocab),
                "logic_preferences": to_list(logic),
                "core_values": to_list(values),
                "summary": str(summary),
            }
        return data


class DNAExtractionOutput(BaseModel):
    has_diff: bool = Field(
        description="Whether differences exist between original AI draft and user edited draft.",
    )
    diff_summary: Optional[str] = Field(
        default=None,
        description="Brief summary of what changed between drafts.",
    )
    thinking_dna: Optional[ThinkingDNA] = Field(
        default=None,
        description="The extracted Thinking DNA dimensions.",
    )
    draft_id: Optional[uuid.UUID] = Field(
        default=None,
        description="ID of associated draft, if any.",
    )
    dna_record_id: Optional[uuid.UUID] = Field(
        default=None,
        description="ID of created DNARecord, if persisted.",
    )
