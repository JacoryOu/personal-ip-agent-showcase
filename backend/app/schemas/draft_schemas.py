from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.schemas.outline_schemas import Outline
from app.schemas.diff_schemas import ThinkingDNA


class DraftGenerateRequest(BaseModel):
    """Public request payload for ``POST /drafts/generate``.

    Only references a stored viral semantic analysis by id. The style
    fingerprint text itself is *never* accepted from the client; the backend
    loads it from the authenticated user's own analysis record through the
    read-only session.

    Extra fields are rejected so that a client can never smuggle a trusted
    server-derived field (for example ``style_fingerprint_prompt``) into the
    public payload.
    """

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(
        min_length=1,
        max_length=500,
        description="The topic or core subject of the article draft."
    )
    outline: Outline = Field(
        description="The selected structural outline to expand into a full draft."
    )
    additional_context: Optional[str] = Field(
        default=None,
        description="Optional additional tone, audience, or stylistic guidance."
    )
    user_id: Optional[str] = Field(default=None, description="Optional user id")
    thinking_dna: Optional[ThinkingDNA] = Field(
        default=None,
        description="Optional personal Thinking DNA to guide draft generation."
    )
    source_material_id: Optional[str] = Field(
        default=None,
        description="Optional source material ID from Material Vault."
    )
    benchmark_blueprint_id: Optional[str] = Field(
        default=None,
        description="Optional benchmark blueprint ID."
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
    viral_analysis_id: Optional[str] = Field(
        default=None,
        description=(
            "Optional id of a viral semantic analysis record owned by the current "
            "user. When provided, the server loads its style fingerprint through "
            "the read-only session and uses it as a structural/rhythm reference; "
            "an explicit id always wins and automatic style selection is skipped. "
            "When omitted, the server auto-selects the best matching fingerprint "
            "among the current user's own analysed records and falls back to "
            "Persona/DNA when no candidate clears the match threshold. Clients "
            "cannot submit a style fingerprint or style prompt directly."
        ),
    )

    @field_validator("topic")
    @classmethod
    def _topic_not_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Topic cannot be empty or just whitespace.")
        return v.strip()

    @field_validator("additional_context")
    @classmethod
    def _clean_additional_context(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            return stripped if stripped else None
        return None


class DraftInput(BaseModel):
    topic: str = Field(
        min_length=1,
        max_length=500,
        description="The topic or core subject of the article draft."
    )
    outline: Outline = Field(
        description="The selected structural outline to expand into a full draft."
    )
    additional_context: Optional[str] = Field(
        default=None,
        description="Optional additional tone, audience, or stylistic guidance."
    )
    user_id: Optional[str] = Field(default=None, description="Optional user id")
    thinking_dna: Optional[ThinkingDNA] = Field(
        default=None,
        description="Optional personal Thinking DNA to guide draft generation with author's unique voice and logic."
    )
    source_material_id: Optional[str] = Field(
        default=None,
        description="Optional source material ID from Material Vault."
    )
    benchmark_blueprint_id: Optional[str] = Field(
        default=None,
        description="Optional benchmark blueprint ID."
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
    viral_analysis_id: Optional[str] = Field(
        default=None,
        description="Id of the viral semantic analysis record used for this draft."
    )
    style_fingerprint_prompt: Optional[str] = Field(
        default=None,
        exclude=True,
        description=(
            "Trusted style-fingerprint prompt text derived server-side from the "
            "current user's own viral analysis record. Never supplied by the "
            "client and never serialized back out."
        ),
    )

    @field_validator("topic")
    @classmethod
    def topic_must_not_be_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Topic cannot be empty or just whitespace.")
        return v.strip()

    @field_validator("outline")
    @classmethod
    def outline_must_have_sections(cls, v: Outline) -> Outline:
        if not v.title.strip():
            raise ValueError("Outline title cannot be empty.")
        if not v.sections:
            raise ValueError("Outline must contain at least one section.")
        return v

    @field_validator("additional_context")
    @classmethod
    def clean_additional_context(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_stripped = v.strip()
            return v_stripped if v_stripped else None
        return None


class ViewpointOption(BaseModel):
    key: str = Field(description="Identifier of the stance: agree, counter, nuanced, or custom")
    label: str = Field(description="Short human-friendly badge label: e.g. 认同并保留, 逆向反驳, 深入洞察")
    text: str = Field(description="Detailed statement of this viewpoint option")


class CoreViewpoint(BaseModel):
    id: str = Field(description="Unique id of the viewpoint, e.g. vp_1")
    claim: str = Field(description="The core claim/argument extracted from the draft")
    section_title: Optional[str] = Field(default=None, description="The article section or theme this claim belongs to")
    options: list[ViewpointOption] = Field(default_factory=list, description="Available stance choices for the user")


class DraftOutput(BaseModel):
    id: Optional[str] = Field(
        default=None,
        description="The unique ID of the draft archived in the database."
    )
    draft_id: Optional[str] = Field(
        default=None,
        description="Alias for id."
    )
    title: str = Field(
        description="The final headline or title of the generated draft."
    )
    summary: Optional[str] = Field(
        default=None,
        description="A concise executive summary or thesis statement of the article."
    )
    content: str = Field(
        description="The complete article text written in well-formatted Markdown."
    )
    word_count: Optional[int] = Field(
        default=None,
        description="The estimated total word or character count of the draft."
    )
    core_viewpoints: list[CoreViewpoint] = Field(
        default_factory=list,
        description="Extracted key viewpoints from the draft for quick user review and judgment."
    )
    injected_dna: Optional[ThinkingDNA] = Field(
        default=None,
        description="Thinking DNA injected into this draft generation."
    )
    source_material_id: Optional[str] = Field(
        default=None,
        description="Optional referenced source material UUID."
    )
    benchmark_blueprint_id: Optional[str] = Field(
        default=None,
        description="Optional referenced benchmark blueprint ID."
    )
    lineage_snapshot: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Immutable snapshot of referenced material, origin author, URL, and inspiration hooks at generation time."
    )
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
    def normalize_draft(cls, data: Any) -> Any:
        if isinstance(data, dict):
            draft_id = data.get("id") or data.get("draft_id")
            title = data.get("title") or data.get("headline") or "Untitled Draft"
            content = data.get("content") or data.get("article") or data.get("body") or data.get("text") or ""
            summary = data.get("summary") or data.get("thesis") or data.get("description") or None
            word_count = data.get("word_count")
            injected_dna = data.get("injected_dna")
            source_material_id = data.get("source_material_id")
            benchmark_blueprint_id = data.get("benchmark_blueprint_id")
            lineage_snapshot = data.get("lineage_snapshot")
            persona_id = data.get("persona_id")
            product_id = data.get("product_id")
            story_ids = data.get("story_ids") or []
            ip_context_prompt = data.get("ip_context_prompt")
            
            # Normalize core_viewpoints
            raw_vps = data.get("core_viewpoints") or data.get("viewpoints") or data.get("key_claims") or []
            normalized_vps = []
            if isinstance(raw_vps, list):
                for i, vp in enumerate(raw_vps):
                    if isinstance(vp, CoreViewpoint):
                        normalized_vps.append(vp)
                    elif isinstance(vp, dict):
                        vp_id = str(vp.get("id") or f"vp_{i+1}")
                        claim = str(vp.get("claim") or vp.get("point") or vp.get("statement") or "")
                        sec = vp.get("section_title") or vp.get("section") or None
                        raw_opts = vp.get("options") or []
                        norm_opts = []
                        if isinstance(raw_opts, list):
                            for opt in raw_opts:
                                if isinstance(opt, ViewpointOption):
                                    norm_opts.append(opt)
                                elif isinstance(opt, dict):
                                    norm_opts.append({
                                        "key": str(opt.get("key") or "agree"),
                                        "label": str(opt.get("label") or "认同并保留"),
                                        "text": str(opt.get("text") or opt.get("statement") or claim)
                                    })
                        if not norm_opts and claim:
                            norm_opts.append({"key": "agree", "label": "认同并保留", "text": claim})
                        if claim:
                            normalized_vps.append({
                                "id": vp_id,
                                "claim": claim,
                                "section_title": sec,
                                "options": norm_opts
                            })

            return {
                "id": str(draft_id) if draft_id else None,
                "draft_id": str(draft_id) if draft_id else None,
                "title": str(title),
                "content": str(content),
                "summary": str(summary) if summary else None,
                "word_count": word_count,
                "core_viewpoints": normalized_vps,
                "injected_dna": injected_dna,
                "source_material_id": str(source_material_id) if source_material_id else None,
                "benchmark_blueprint_id": str(benchmark_blueprint_id) if benchmark_blueprint_id else None,
                "lineage_snapshot": lineage_snapshot,
                "persona_id": str(persona_id) if persona_id else None,
                "product_id": str(product_id) if product_id else None,
                "story_ids": [str(s) for s in story_ids] if story_ids else [],
                "ip_context_prompt": ip_context_prompt,
            }
        return data


class UpdateDraftRequest(BaseModel):
    topic: Optional[str] = Field(default=None, description="Updated topic of the draft.")
    title: Optional[str] = Field(default=None, description="Updated title in draft metadata.")
    user_final_draft: Optional[str] = Field(default=None, description="User revised or final draft content.")
    original_ai_draft: Optional[str] = Field(default=None, description="AI original draft content if editing directly.")
    source_material_id: Optional[str] = Field(default=None, description="Updated source material ID.")
    benchmark_blueprint_id: Optional[str] = Field(default=None, description="Updated benchmark blueprint ID.")
    lineage_snapshot: Optional[Dict[str, Any]] = Field(default=None, description="Updated lineage snapshot.")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional custom metadata.")


class DraftArchiveItem(BaseModel):
    id: str
    user_id: str
    topic: str
    title: Optional[str] = None
    summary: Optional[str] = None
    content: str
    original_ai_draft: str
    user_final_draft: Optional[str] = None
    word_count: Optional[int] = None
    source_material_id: Optional[str] = None
    benchmark_blueprint_id: Optional[str] = None
    lineage_snapshot: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class BlueprintDraftInput(BaseModel):
    topic: str = Field(
        min_length=1,
        max_length=500,
        description="The topic or angle for the new article."
    )
    blueprint_id: Optional[str] = Field(
        default=None,
        description="Optional ID of existing benchmark blueprint in user profile."
    )
    blueprint: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional explicit benchmark blueprint dictionary if not using blueprint_id."
    )
    source_material_id: Optional[str] = Field(
        default=None,
        description="Optional referenced source material UUID."
    )
    additional_context: Optional[str] = Field(
        default=None,
        description="Optional extra instructions, tone, or constraints."
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Optional user ID."
    )
    thinking_dna: Optional[ThinkingDNA] = Field(
        default=None,
        description="Optional explicit Thinking DNA."
    )
    persona_id: Optional[str] = Field(
        default=None,
        description="Optional IP Persona ID to anchor voice and reader salutation."
    )
    product_id: Optional[str] = Field(
        default=None,
        description="Optional ProductVault item ID."
    )
    story_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional episodic story IDs."
    )

    @field_validator("topic")
    @classmethod
    def topic_must_not_be_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Topic cannot be empty or just whitespace.")
        return v.strip()

    @model_validator(mode="after")
    def validate_blueprint_presence(self) -> "BlueprintDraftInput":
        if not self.blueprint_id and not self.blueprint:
            raise ValueError("Either blueprint_id or blueprint must be provided.")
        return self


class DistributeContentInput(BaseModel):
    content: str = Field(min_length=1, description="Full article or draft content to format across platforms.")
    title: Optional[str] = Field(default=None, description="Optional article title or subject.")
    platforms: Optional[List[str]] = Field(default=None, description="Target platforms (e.g. xiaohongshu, wechat, twitter, video).")

    @field_validator("content")
    @classmethod
    def content_must_not_be_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Content cannot be empty.")
        return v.strip()


class DistributeDraftRequest(BaseModel):
    platforms: Optional[List[str]] = Field(default=None, description="Target platforms.")


class FeedbackCreateRequest(BaseModel):
    comments_text: str = Field(min_length=1, description="Raw reader comments, review text, or feedback")
    metrics: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Engagement metrics (likes, shares, views, etc.)")
    user_id: Optional[str] = Field(default=None, description="Optional user id")


class FeedbackExtractRequest(BaseModel):
    feedback_id: Optional[str] = Field(default=None, description="Existing feedback ID to extract insights from")
    comments_text: Optional[str] = Field(default=None, description="Optional raw feedback text to analyze directly")
    metrics: Optional[Dict[str, Any]] = Field(default=None, description="Optional metrics")
    user_id: Optional[str] = Field(default=None, description="Optional user id")


class BoostedTraitInfo(BaseModel):
    id: str = Field(description="Trait ID")
    statement: str = Field(description="Cognitive statement")
    dimension: str = Field(description="Dimension name")
    old_confidence: float = Field(description="Confidence score before feedback")
    new_confidence: float = Field(description="Confidence score after feedback boost")
    boost_amount: float = Field(default=0.5, description="Boost delta applied")
    reason: Optional[str] = Field(default=None, description="Reason for resonance boost")


class FeedbackExtractResponse(BaseModel):
    feedback_id: str
    draft_id: str
    resonant_ideas: List[str] = Field(default_factory=list, description="Ideas resonated by audience")
    controversy_points: List[str] = Field(default_factory=list, description="Debate and controversy points")
    inspiration_notes: List[str] = Field(default_factory=list, description="New inspiration fragments for future topics")
    created_materials: List[Dict[str, Any]] = Field(default_factory=list, description="Inspiration notes saved to MaterialVault")
    boosted_traits: List[BoostedTraitInfo] = Field(default_factory=list, description="Cognitive traits boosted by audience resonance")
    evolution_summary: str = Field(default="", description="Summary of cognitive DNA evolution")


class FeedbackItemResponse(BaseModel):
    id: str
    draft_id: str
    user_id: str
    comments_text: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    extracted_insights: Optional[Dict[str, Any]] = None
    boosted_dna_traits: Optional[List[Dict[str, Any]]] = None
    saved_material_ids: Optional[List[str]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

