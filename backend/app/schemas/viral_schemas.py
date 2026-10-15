"""Typed semantic schemas for viral / benchmark article breakdown.

These models describe *actionable writing signals* (hook mechanics, structural
beats, formulas, rhythm, value promise, transferability and a reusable style
fingerprint) rather than a summary of the article.

Design notes:
- Every nested model has a lenient ``model_validator(mode="before")`` that
  accepts missing keys, common alternate key names, and bare strings where a
  list is expected. The goal is predictable degradation: a partially valid LLM
  response still produces a usable object instead of raising.
- Numeric rhythm statistics and ``StyleFingerprint.prompt_block`` are
  *deterministically recomputed* by the service from the raw article text, so
  they never depend on the model's arithmetic.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
import uuid


def _to_str_list(value: Any) -> List[str]:
    """Best-effort coercion of an arbitrary LLM value into a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, dict):
        return [str(v) for v in value.values() if v not in (None, "")]
    if isinstance(value, (list, tuple, set)):
        return [_flatten(v) for v in value if v not in (None, "")]
    return [str(value)]


def _flatten(value: Any) -> str:
    """Render a single LLM list element as a readable string."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("name", "summary", "pattern_name", "text", "description", "stage"):
            if value.get(key):
                return str(value[key])
        return ", ".join(f"{k}={v}" for k, v in value.items())
    return str(value)


def _as_dict(value: Any) -> Dict[str, Any]:
    """Treat a non-mapping payload as an empty mapping (lossy but safe)."""
    return value if isinstance(value, dict) else {}


def _clamp(value: Any, low: int = 0, high: int = 5, default: int = 0) -> int:
    try:
        num = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, num))


class HookAnalysis(BaseModel):
    """How the opening line captures attention."""

    pattern_name: str = Field(default="", description="Name of the opening pattern, e.g. 'counter-intuitive claim'.")
    opening_excerpt: str = Field(default="", description="Verbatim excerpt of the opening used as evidence.")
    attention_mechanism: str = Field(default="", description="Why the reader does not leave: curiosity gap, pain, stakes, identity.")
    hook_strength: int = Field(default=0, ge=0, le=5, description="0-5 rubric-anchored rating of opening strength. Must be justified by concrete evidence in the article; when the evidence for a level is missing, report the lower level.")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        data = _as_dict(data)
        strength = data.get("hook_strength", data.get("strength", data.get("score", data.get("rating", 0))))
        return {
            "pattern_name": str(data.get("pattern_name") or data.get("name") or data.get("pattern") or ""),
            "opening_excerpt": str(data.get("opening_excerpt") or data.get("excerpt") or data.get("opening") or ""),
            "attention_mechanism": str(
                data.get("attention_mechanism") or data.get("mechanism") or data.get("why_it_works") or ""
            ),
            "hook_strength": _clamp(strength),
        }


class StructuralBeat(BaseModel):
    """One structural segment of the article with its tension level."""

    order: int = Field(default=0, ge=0, description="Position of this beat in the article, starting at 1.")
    stage: str = Field(default="", description="Role of the beat, e.g. 'setup', 'complication', 'payoff'.")
    summary: str = Field(default="", description="What happens in this beat.")
    tension_level: int = Field(default=0, ge=0, le=5, description="0-5 rubric-anchored narrative tension in this beat. Must be justified by concrete evidence in the article; when the evidence for a level is missing, report the lower level.")
    is_payoff: bool = Field(default=False, description="True for the beat that delivers the promised payoff.")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, str):
            data = {"summary": data}
        data = _as_dict(data)
        order = data.get("order", data.get("index", data.get("position", 0)))
        is_payoff = data.get("is_payoff", data.get("payoff", data.get("is_climax", False)))
        if isinstance(is_payoff, str):
            is_payoff = is_payoff.strip().lower() in ("true", "yes", "1", "是")
        return {
            "order": max(0, _clamp(order, low=0, high=999, default=0)),
            "stage": str(data.get("stage") or data.get("role") or data.get("label") or ""),
            "summary": str(data.get("summary") or data.get("description") or data.get("content") or ""),
            "tension_level": _clamp(data.get("tension_level", data.get("tension", data.get("intensity", 0)))),
            "is_payoff": bool(is_payoff),
        }


class StructureAnalysis(BaseModel):
    """The overall shape of the article and where tension/payoff sit."""

    beats: List[StructuralBeat] = Field(default_factory=list, description="Ordered structural beats.")
    tension_shape: str = Field(default="", description="Description of how tension rises and releases.")
    payoff_position: str = Field(default="", description="Where the payoff lands, e.g. 'final 20%', 'before the CTA'.")
    climax_excerpt: str = Field(default="", description="Verbatim excerpt at the high-tension point.")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        data = _as_dict(data)
        raw_beats = data.get("beats") or data.get("structure") or data.get("outline") or []
        if isinstance(raw_beats, dict):
            raw_beats = [raw_beats]
        beats: List[StructuralBeat] = []
        for index, item in enumerate(raw_beats if isinstance(raw_beats, (list, tuple)) else [], start=1):
            try:
                beat = StructuralBeat.model_validate(item)
            except Exception:
                continue
            if not beat.order:
                beat.order = index
            beats.append(beat)
        return {
            "beats": beats,
            "tension_shape": str(data.get("tension_shape") or data.get("shape") or data.get("tension_arc") or ""),
            "payoff_position": str(data.get("payoff_position") or data.get("payoff") or ""),
            "climax_excerpt": str(data.get("climax_excerpt") or data.get("climax") or data.get("highlight") or ""),
        }


class FormulaPattern(BaseModel):
    """A reusable title or hook formula."""

    name: str = Field(default="", description="Short name of the formula.")
    template: str = Field(default="", description="Fill-in-the-blank template with placeholders.")
    example: str = Field(default="", description="Example drawn from the article.")
    why_it_works: str = Field(default="", description="Why the formula produces curiosity or urgency.")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, str):
            data = {"template": data}
        data = _as_dict(data)
        return {
            "name": str(data.get("name") or data.get("formula_name") or ""),
            "template": str(data.get("template") or data.get("pattern") or ""),
            "example": str(data.get("example") or data.get("sample") or ""),
            "why_it_works": str(data.get("why_it_works") or data.get("reason") or data.get("rationale") or ""),
        }


class FormulaAnalysis(BaseModel):
    """Title and hook formulas extracted from the article."""

    title_formulas: List[FormulaPattern] = Field(default_factory=list)
    hook_formulas: List[FormulaPattern] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        data = _as_dict(data)
        return {
            "title_formulas": [FormulaPattern.model_validate(i) for i in _coerce_formula_list(data.get("title_formulas") or data.get("titles") or data.get("title"))],
            "hook_formulas": [FormulaPattern.model_validate(i) for i in _coerce_formula_list(data.get("hook_formulas") or data.get("hooks") or data.get("hook"))],
        }


def _coerce_formula_list(value: Any) -> List[Any]:
    """Allow a single formula (string/dict) where a list is expected."""
    if value is None:
        return []
    if isinstance(value, (str, dict)):
        return [value]
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


class RhythmProfile(BaseModel):
    """Emotional and rhythmic fingerprint.

    The three numeric fields are recomputed from the raw text by the service.
    """

    mean_sentence_length: float = Field(default=0.0, description="Mean characters per sentence, computed in code.")
    sentence_length_std: float = Field(default=0.0, description="Sentence-length standard deviation, computed in code.")
    short_sentence_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="Share of sentences <= 15 chars, computed in code.")
    pacing: str = Field(default="", description="Qualitative pacing description, e.g. 'fast and punchy'.")
    dominant_emotions: List[str] = Field(default_factory=list, description="Emotions that dominate the piece.")
    emotion_arc: str = Field(default="", description="How the emotional intensity changes over the article.")
    device_usage: List[str] = Field(default_factory=list, description="Rhetorical devices observed, e.g. 'contrast', 'second person'.")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        data = _as_dict(data)
        return {
            "mean_sentence_length": float(data.get("mean_sentence_length") or 0.0),
            "sentence_length_std": float(data.get("sentence_length_std") or 0.0),
            "short_sentence_ratio": float(data.get("short_sentence_ratio") or 0.0),
            "pacing": str(data.get("pacing") or data.get("pace") or ""),
            "dominant_emotions": _to_str_list(data.get("dominant_emotions") or data.get("emotions")),
            "emotion_arc": str(data.get("emotion_arc") or data.get("emotional_arc") or ""),
            "device_usage": _to_str_list(data.get("device_usage") or data.get("devices") or data.get("rhetorical_devices")),
        }


class ValuePromise(BaseModel):
    """The core promise made to the reader and whether it is delivered."""

    promise: str = Field(default="", description="What the article promises the reader.")
    payoff: str = Field(default="", description="What the reader actually gets.")
    promise_kept: bool = Field(default=False, description="Whether the payoff matches the promise.")
    target_reader: str = Field(default="", description="The reader the article is written for.")
    shareability_hook: str = Field(default="", description="Why a reader would forward or share it.")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        data = _as_dict(data)
        kept = data.get("promise_kept", data.get("kept", data.get("fulfilled", data.get("delivers", False))))
        if isinstance(kept, str):
            kept = kept.strip().lower() in ("true", "yes", "1", "是")
        return {
            "promise": str(data.get("promise") or data.get("core_promise") or data.get("value_promise") or ""),
            "payoff": str(data.get("payoff") or data.get("delivered") or ""),
            "promise_kept": bool(kept),
            "target_reader": str(data.get("target_reader") or data.get("audience") or data.get("reader") or ""),
            "shareability_hook": str(data.get("shareability_hook") or data.get("shareability") or data.get("share_hook") or ""),
        }


class TransferAnalysis(BaseModel):
    """Separates what generalizes from what is article-specific."""

    reusable_patterns: List[str] = Field(default_factory=list, description="Mechanisms that can be reused on other topics.")
    one_off_specifics: List[str] = Field(default_factory=list, description="Details that only work for this exact article.")
    reuse_score: int = Field(default=0, ge=0, le=5, description="0-5 rubric-anchored rating of how transferable this article is. Must be justified by concrete evidence in the article; when the evidence for a level is missing, report the lower level.")
    adaptation_notes: str = Field(default="", description="How to adapt the pattern to a different topic or voice.")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        data = _as_dict(data)
        return {
            "reusable_patterns": _to_str_list(data.get("reusable_patterns") or data.get("reusable") or data.get("transferable")),
            "one_off_specifics": _to_str_list(data.get("one_off_specifics") or data.get("one_off") or data.get("specifics")),
            "reuse_score": _clamp(data.get("reuse_score", data.get("transferability", data.get("score", 0)))),
            "adaptation_notes": str(data.get("adaptation_notes") or data.get("adaptation") or data.get("notes") or ""),
        }


class StyleFingerprint(BaseModel):
    """Reusable voice/style descriptor for downstream draft generation."""

    model_config = ConfigDict(protected_namespaces=())
    voice: str = Field(default="", description="Narrator voice, e.g. 'practitioner sharing hard-won lessons'.")
    stance: str = Field(default="", description="Stance toward the reader, e.g. 'peer, not expert'.")
    register: str = Field(default="", description="Language register, e.g. 'colloquial', 'white-paper'.")
    sentence_style: str = Field(default="", description="Sentence construction habit.")
    signature_devices: List[str] = Field(default_factory=list, description="Signature moves that recur in this voice.")
    prompt_block: str = Field(default="", description="Ready-to-inject instruction block for draft generation. Built in code.")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        data = _as_dict(data)
        return {
            "voice": str(data.get("voice") or data.get("persona") or ""),
            "stance": str(data.get("stance") or data.get("position") or ""),
            "register": str(data.get("register") or data.get("tone") or ""),
            "sentence_style": str(data.get("sentence_style") or data.get("sentence_pattern") or ""),
            "signature_devices": _to_str_list(data.get("signature_devices") or data.get("devices") or data.get("signatures")),
            "prompt_block": str(data.get("prompt_block") or ""),
        }


class ViralSemanticAnalysis(BaseModel):
    """The complete semantic breakdown of one viral / benchmark article."""

    one_line_verdict: str = Field(default="", description="Single sentence explaining why this article worked.")
    hook: HookAnalysis = Field(default_factory=HookAnalysis)
    structure: StructureAnalysis = Field(default_factory=StructureAnalysis)
    formulas: FormulaAnalysis = Field(default_factory=FormulaAnalysis)
    rhythm: RhythmProfile = Field(default_factory=RhythmProfile)
    value_promise: ValuePromise = Field(default_factory=ValuePromise)
    transfer: TransferAnalysis = Field(default_factory=TransferAnalysis)
    style_fingerprint: StyleFingerprint = Field(default_factory=StyleFingerprint)
    extraction_mode: str = Field(default="llm", description="'llm' when the model produced the analysis, 'fallback' for deterministic-only output.")
    warnings: List[str] = Field(default_factory=list, description="Human-readable notes about degraded or unmet guarantees.")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        data = _as_dict(data)
        nested = {
            "hook": data.get("hook") or data.get("opening") or data.get("hook_analysis"),
            "structure": data.get("structure") or data.get("structure_analysis") or ({"beats": data["beats"]} if data.get("beats") else None),
            "formulas": data.get("formulas") or data.get("formula_analysis") or ({"title_formulas": data["titles"]} if data.get("titles") else None) or ({"hook_formulas": data["hooks"]} if data.get("hooks") else None),
            "rhythm": data.get("rhythm") or data.get("rhythm_profile"),
            "value_promise": data.get("value_promise") or data.get("promise"),
            "transfer": data.get("transfer") or data.get("transfer_analysis"),
            "style_fingerprint": data.get("style_fingerprint") or data.get("fingerprint") or data.get("style"),
        }
        mode = str(data.get("extraction_mode") or "llm").strip().lower() or "llm"
        return {
            "one_line_verdict": str(data.get("one_line_verdict") or data.get("verdict") or data.get("summary") or ""),
            "hook": HookAnalysis.model_validate(nested["hook"]),
            "structure": StructureAnalysis.model_validate(nested["structure"]),
            "formulas": FormulaAnalysis.model_validate(nested["formulas"]),
            "rhythm": RhythmProfile.model_validate(nested["rhythm"]),
            "value_promise": ValuePromise.model_validate(nested["value_promise"]),
            "transfer": TransferAnalysis.model_validate(nested["transfer"]),
            "style_fingerprint": StyleFingerprint.model_validate(nested["style_fingerprint"]),
            "extraction_mode": mode,
            "warnings": _to_str_list(data.get("warnings")),
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


# ==============================================================================
# API request / response schemas
# ==============================================================================

class ViralAnalysisRequest(BaseModel):
    """Payload for analysing a single article."""

    title: str = Field(default="", description="Article title. May be empty for body-only analysis.")
    content: str = Field(..., min_length=1, description="Full article body to analyse.")
    source_platform: Optional[str] = Field(default=None, description="Platform the article came from, e.g. 'wechat'.")
    source_url: Optional[str] = Field(default=None)
    user_id: Optional[uuid.UUID] = Field(default=None, description="Optional owner; validated on persistence.")
    material_id: Optional[uuid.UUID] = Field(default=None, description="Optional source Material to link.")


class ViralAnalysisResponse(BaseModel):
    """Analysis payload returned by the API."""

    id: uuid.UUID
    status: str
    extraction_mode: str
    source_title: str
    source_platform: Optional[str] = None
    source_url: Optional[str] = None
    analysis: Dict[str, Any]
    warnings: List[str] = Field(default_factory=list)
    model_name: Optional[str] = None
    created_at: Any = None
