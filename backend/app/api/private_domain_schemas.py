from app.api.private_domain_common import *  # noqa: F401,F403
from app.api.private_domain_common import router, public_router  # noqa: F401

# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------

MomentCategory = Literal["专业沉淀", "生活切片", "好物自用", "互动截流", "岁月反思"]
TimeNarrativeMode = Literal["invisible", "fuzzy", "solar_term", "anniversary"]


TriggerType = Literal["study_insight", "reading_notes", "case_experience", "daily_thought"]
LengthTier = Literal["short", "standard", "deep"]


class GenerateMomentRequest(BaseModel):
    category: MomentCategory
    topic: Optional[str] = None
    product_id: Optional[str] = None
    persona_id: Optional[str] = None
    time_narrative_mode: Optional[TimeNarrativeMode] = "invisible"
    user_id: Optional[str] = None
    # Enhanced input: event trigger & personal takeaway
    trigger_type: Optional[TriggerType] = "daily_thought"
    raw_experience: Optional[str] = None
    my_takeaway: Optional[str] = None
    length_tier: Optional[LengthTier] = "standard"


class GenerateMomentResponse(BaseModel):
    text: str
    estimated_lines: int
    will_fold: bool
    fold_preview: str
    pinned_comment: str
    visual_card_prompt: str
    tags: List[str]
    character_count: int = 0


class GenerateCommunityRequest(BaseModel):
    script_type: Optional[Literal["discussion_starter", "sale_theater", "qa_spark"]] = "discussion_starter"
    topic: Optional[str] = None
    product_id: Optional[str] = None
    persona_id: Optional[str] = None
    user_id: Optional[str] = None


class GenerateCommunityResponse(BaseModel):
    content: str
    script_type: str
    roles: List[str]
    recommended_timing: str
    call_to_action: str


class TemplateItem(BaseModel):
    category: str
    name: str
    description: str
    example_topic: str
    sample_hook: str
    recommended_timing: str
    target_goal: str


