"""Semantic breakdown service for viral / benchmark articles.

Layering: API -> this Service -> SQLModel. LLM access goes through the existing
``ModelGateway`` with ``ModelRole.VIRAL_ANALYSIS``.

Two deliberate reliability choices:

1. **Deterministic numerics.** Sentence-length statistics and the style
   fingerprint's ``prompt_block`` are computed in code from the raw text, never
   delegated to the model's arithmetic.

2. **Predictable degradation.** If the model call fails or returns something we
   cannot turn into a ``ViralSemanticAnalysis``, we do NOT raise. We return a
   clearly-labelled ``extraction_mode="fallback"`` result containing only the
   mechanical statistics and a paragraph-level skeleton, plus an explicit
   warning stating the semantic layer did not run. An honest gap is more useful
   than a 500.
"""

import hashlib
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError
from sqlmodel import Session

from app.core.model_gateway import ModelGateway, ModelRole, get_model_gateway
from app.engine.prompts.viral_prompts import VIRAL_ANALYSIS_SYSTEM_PROMPT
from app.models.material import Material
from app.models.user import User
from app.models.viral_analysis import ViralSemanticAnalysisRecord
from app.schemas.viral_schemas import (
    FormulaAnalysis,
    FormulaPattern,
    HookAnalysis,
    RhythmProfile,
    StructuralBeat,
    StructureAnalysis,
    StyleFingerprint,
    TransferAnalysis,
    ValuePromise,
    ViralAnalysisResponse,
    ViralSemanticAnalysis,
)

# Sentence terminators for both Chinese and English punctuation.
_SENTENCE_SPLIT = re.compile(r"[。！？!?；;\n]+|(?<=[.!?])\s+")
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")
SHORT_SENTENCE_THRESHOLD = 15


def normalize_article_text(text: str) -> str:
    """Normalize line endings and collapse trailing whitespace."""
    if not text:
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def content_hash(text: str) -> str:
    """Stable sha256 of the normalized article body, for de-duplication."""
    return hashlib.sha256(normalize_article_text(text).encode("utf-8")).hexdigest()


def split_sentences(text: str) -> List[str]:
    """Split into sentences using Chinese and English terminators."""
    if not text:
        return []
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text)]
    return [p for p in parts if p]


def compute_rhythm_stats(text: str) -> Dict[str, float]:
    """Deterministic sentence-length statistics (mean, std, short-sentence ratio)."""
    sentences = split_sentences(text)
    if not sentences:
        return {"mean_sentence_length": 0.0, "sentence_length_std": 0.0, "short_sentence_ratio": 0.0}

    lengths = [float(len(s)) for s in sentences]
    count = len(lengths)
    mean = sum(lengths) / count
    variance = sum((length - mean) ** 2 for length in lengths) / count
    std = variance ** 0.5
    short_ratio = sum(1 for length in lengths if length <= SHORT_SENTENCE_THRESHOLD) / count
    return {
        "mean_sentence_length": round(mean, 2),
        "sentence_length_std": round(std, 2),
        "short_sentence_ratio": round(short_ratio, 4),
    }


def build_prompt_block(
    fingerprint: StyleFingerprint,
    formulas: FormulaAnalysis,
    value_promise: ValuePromise,
) -> str:
    """Deterministically assemble a ready-to-inject draft-generation instruction block.

    Built in code so downstream generation never depends on the model having
    formatted this string correctly.
    """
    lines: List[str] = ["[STYLE FINGERPRINT]"]
    if fingerprint.voice:
        lines.append(f"- Voice: {fingerprint.voice}")
    if fingerprint.stance:
        lines.append(f"- Stance toward reader: {fingerprint.stance}")
    if fingerprint.register:
        lines.append(f"- Register: {fingerprint.register}")
    if fingerprint.sentence_style:
        lines.append(f"- Sentence style: {fingerprint.sentence_style}")
    if fingerprint.signature_devices:
        lines.append(f"- Signature devices: {', '.join(fingerprint.signature_devices)}")
    if formulas.title_formulas:
        templates = "; ".join(f.template for f in formulas.title_formulas if f.template)
        if templates:
            lines.append(f"- Title formulas to draw from: {templates}")
    if formulas.hook_formulas:
        templates = "; ".join(f.template for f in formulas.hook_formulas if f.template)
        if templates:
            lines.append(f"- Hook formulas to draw from: {templates}")
    if value_promise.promise:
        lines.append(f"- Value promise to honour: {value_promise.promise}")
    lines.append("[END STYLE FINGERPRINT]")
    return "\n".join(lines)


def apply_deterministic_overrides(
    analysis: ViralSemanticAnalysis, text: str, title: str = ""
) -> ViralSemanticAnalysis:
    """Recompute code-owned fields on a validated analysis, in place.

    Code owns: rhythm numerics, hook opening excerpt (when the model gave none),
    and the style fingerprint prompt block.
    """
    stats = compute_rhythm_stats(text)
    analysis.rhythm.mean_sentence_length = stats["mean_sentence_length"]
    analysis.rhythm.sentence_length_std = stats["sentence_length_std"]
    analysis.rhythm.short_sentence_ratio = stats["short_sentence_ratio"]

    if not analysis.hook.opening_excerpt:
        sentences = split_sentences(text)
        if sentences:
            analysis.hook.opening_excerpt = sentences[0]
    if not title and not analysis.hook.pattern_name:
        analysis.hook.pattern_name = ""

    analysis.style_fingerprint.prompt_block = build_prompt_block(
        analysis.style_fingerprint, analysis.formulas, analysis.value_promise
    )
    return analysis


def build_fallback_analysis(text: str, title: str, reason: str) -> ViralSemanticAnalysis:
    """Deterministic-only analysis used when the semantic model call fails.

    Provides the title, the opening sentence, real rhythm statistics and a
    paragraph-level structural skeleton. All judgement fields stay empty and the
    warnings make the degradation explicit.
    """
    stats = compute_rhythm_stats(text)
    sentences = split_sentences(text)
    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(text) if p.strip()]

    beats: List[StructuralBeat] = []
    for index, paragraph in enumerate(paragraphs, start=1):
        beats.append(
            StructuralBeat(
                order=index,
                stage="paragraph",
                summary=f"Paragraph {index} ({len(paragraph)} chars).",
                tension_level=0,
                is_payoff=False,
            )
        )

    hook = HookAnalysis(
        pattern_name="",
        opening_excerpt=sentences[0] if sentences else "",
        attention_mechanism="",
        hook_strength=0,
    )
    structure = StructureAnalysis(
        beats=beats,
        tension_shape="",
        payoff_position="",
        climax_excerpt="",
    )
    rhythm = RhythmProfile(
        mean_sentence_length=stats["mean_sentence_length"],
        sentence_length_std=stats["sentence_length_std"],
        short_sentence_ratio=stats["short_sentence_ratio"],
        pacing="",
        dominant_emotions=[],
        emotion_arc="",
        device_usage=[],
    )
    value_promise = ValuePromise()
    transfer = TransferAnalysis()
    fingerprint = StyleFingerprint()

    analysis = ViralSemanticAnalysis(
        one_line_verdict="",
        hook=hook,
        structure=structure,
        formulas=FormulaAnalysis(),
        rhythm=rhythm,
        value_promise=value_promise,
        transfer=transfer,
        style_fingerprint=fingerprint,
        extraction_mode="fallback",
        warnings=[
            "Model analysis failed; returning deterministic statistics only.",
            f"Fallback reason: {reason}",
            "Semantic fields (hook pattern, structure tension, formulas, value promise, "
            "transferability, style fingerprint) are EMPTY and were not inferred.",
        ],
    )
    # prompt_block for the empty fingerprint is still deterministic (end markers only),
    # so downstream can detect an unpopulated fingerprint reliably.
    analysis.style_fingerprint.prompt_block = build_prompt_block(fingerprint, analysis.formulas, value_promise)
    return analysis


class ViralSemanticService:
    """Orchestrates LLM semantic extraction, persistence and retrieval."""

    def __init__(self, gateway: Optional[ModelGateway] = None):
        self.gateway = gateway or get_model_gateway()

    async def analyze_article(
        self,
        title: str,
        content: str,
        session: Session,
        source_platform: Optional[str] = None,
        source_url: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        material_id: Optional[uuid.UUID] = None,
    ) -> ViralAnalysisResponse:
        """Analyze one article and persist the result.

        Validates optional provenance (user_id / material_id) before persisting so
        we never violate a foreign key. Never raises on model failure.
        """
        normalized_title = normalize_article_text(title or "")
        normalized_content = normalize_article_text(content or "")
        if not normalized_content:
            raise ValueError("Article content must not be empty.")

        self._validate_provenance(user_id=user_id, material_id=material_id, session=session)

        analysis = await self._run_model_analysis(normalized_title, normalized_content)

        record = ViralSemanticAnalysisRecord(
            user_id=user_id,
            material_id=material_id,
            source_title=normalized_title,
            source_content_hash=content_hash(normalized_content),
            source_platform=source_platform,
            source_url=source_url,
            status="completed",
            extraction_mode=analysis.extraction_mode,
            analysis_data=analysis.to_dict(),
            warnings=list(analysis.warnings),
            model_name=self._resolve_model_name(),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return self._to_response(record)

    async def _run_model_analysis(self, title: str, content: str) -> ViralSemanticAnalysis:
        """Call the model, falling back deterministically on any failure."""
        user_content = f"Title: {title or '(untitled)'}\n\n=== ARTICLE ===\n{content}"
        try:
            parsed: ViralSemanticAnalysis = await self.gateway.generate_structured(
                role=ModelRole.VIRAL_ANALYSIS,
                messages=[{"role": "user", "content": user_content}],
                response_model=ViralSemanticAnalysis,
                system_prompt=VIRAL_ANALYSIS_SYSTEM_PROMPT,
            )
            parsed = ViralSemanticAnalysis.model_validate(parsed)
        except (ValueError, ValidationError) as exc:
            return build_fallback_analysis(content, title, reason=f"{type(exc).__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001 - never let a model error surface as a 500
            return build_fallback_analysis(content, title, reason=f"{type(exc).__name__}: {exc}")

        parsed.extraction_mode = "llm"
        return apply_deterministic_overrides(parsed, content, title=title)

    def get_analysis(self, analysis_id: uuid.UUID, session: Session) -> Optional[ViralAnalysisResponse]:
        """Load a persisted analysis by id, or None when not found."""
        record = session.get(ViralSemanticAnalysisRecord, analysis_id)
        if record is None:
            return None
        return self._to_response(record)

    @staticmethod
    def _validate_provenance(
        user_id: Optional[uuid.UUID],
        material_id: Optional[uuid.UUID],
        session: Session,
    ) -> None:
        if user_id is not None and session.get(User, user_id) is None:
            raise ValueError(f"User '{user_id}' not found.")
        if material_id is not None and session.get(Material, material_id) is None:
            raise ValueError(f"Material '{material_id}' not found.")

    @staticmethod
    def _resolve_model_name() -> str:
        try:
            return get_model_gateway().get_model_for_role(ModelRole.VIRAL_ANALYSIS)
        except Exception:  # noqa: BLE001 - never fail persistence over a name lookup
            return "unknown"

    @staticmethod
    def _to_response(record: ViralSemanticAnalysisRecord) -> ViralAnalysisResponse:
        return ViralAnalysisResponse(
            id=record.id,
            status=record.status,
            extraction_mode=record.extraction_mode,
            source_title=record.source_title,
            source_platform=record.source_platform,
            source_url=record.source_url,
            analysis=record.analysis_data or {},
            warnings=list(record.warnings or []),
            model_name=record.model_name,
            created_at=record.created_at,
        )
