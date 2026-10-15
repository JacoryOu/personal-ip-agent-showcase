"""Pydantic schemas for the Divergent Outline Agent."""

from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class OutlineSection(BaseModel):
    title: str = Field(description="The title of the section")
    bullet_points: List[str] = Field(
        default_factory=list,
        description="Key bullet points to cover in this section"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            title = (
                data.get("title")
                or data.get("heading")
                or data.get("part")
                or "Section"
            )
            points = (
                data.get("bullet_points")
                or data.get("points")
                or data.get("items")
                or []
            )
            if isinstance(points, str):
                points = [points]
            return {
                "title": str(title),
                "bullet_points": [str(p) for p in points]
            }
        return data


class Outline(BaseModel):
    title: str = Field(description="The overall title for this outline approach")
    rationale: str = Field(
        default="",
        description="Why this approach is interesting or effective"
    )
    sections: List[OutlineSection] = Field(
        default_factory=list,
        description="The sections of the outline"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            title = data.get("title") or "Untitled Outline"
            rationale = (
                data.get("rationale")
                or data.get("core_argument")
                or data.get("summary")
                or data.get("description")
                or ""
            )
            sections = (
                data.get("sections")
                or data.get("structure")
                or data.get("parts")
                or data.get("content")
                or []
            )
            return {
                "title": str(title),
                "rationale": str(rationale),
                "sections": sections,
            }
        return data


class OutlineOutput(BaseModel):
    outline_a: Outline = Field(description="A conventional, structured, or straightforward approach to the topic.")
    outline_b: Outline = Field(description="An unconventional, lateral, or completely different perspective on the topic.")
    persona_id: Optional[str] = Field(
        default=None,
        description="Optional referenced IP Persona ID."
    )
    product_id: Optional[str] = Field(
        default=None,
        description="Optional referenced product ID."
    )
    story_ids: Optional[List[str]] = Field(
        default_factory=list,
        description="Referenced episodic story IDs."
    )
    ip_context_prompt: Optional[str] = Field(
        default=None,
        description="The assembled full IP context prompt injected."
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_output(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "outlines" in data and isinstance(data["outlines"], dict):
                data = data["outlines"]
            if "outlineA" in data and "outline_a" not in data:
                data["outline_a"] = data["outlineA"]
            if "outlineB" in data and "outline_b" not in data:
                data["outline_b"] = data["outlineB"]
        return data


from app.schemas.diff_schemas import ThinkingDNA


class OutlineInput(BaseModel):
    topic: str = Field(min_length=1, max_length=500, description="The topic to generate outlines for")
    additional_context: Optional[str] = Field(default=None, description="Any additional context or instructions")
    user_id: Optional[str] = Field(default=None, description="Optional user id")
    thinking_dna: Optional[ThinkingDNA] = Field(
        default=None,
        description="Optional personal Thinking DNA to guide outline generation with author's cognitive style."
    )
    persona_id: Optional[str] = Field(
        default=None,
        description="Optional IP Persona ID to anchor creator persona."
    )
    product_id: Optional[str] = Field(
        default=None,
        description="Optional ProductVault item ID."
    )
    story_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional episodic story IDs."
    )
    ip_context_prompt: Optional[str] = Field(
        default=None,
        description="Pre-assembled full IP context prompt."
    )
    persona: Optional[Any] = Field(
        default=None,
        description="IPPersona object or dict."
    )
    product: Optional[Any] = Field(
        default=None,
        description="ProductVault object or dict."
    )
    stories: Optional[List[Any]] = Field(
        default=None,
        description="List of EpisodicStory objects or dicts."
    )

    @field_validator("topic")
    @classmethod
    def topic_must_not_be_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Topic cannot be empty or just whitespace.")
        return v.strip()

    @field_validator("additional_context")
    @classmethod
    def clean_additional_context(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_stripped = v.strip()
            return v_stripped if v_stripped else None
        return None
