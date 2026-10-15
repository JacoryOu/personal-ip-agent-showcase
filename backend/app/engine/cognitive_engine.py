"""Headless Core Cognitive Engine Facade.

Decouples all business capabilities (outlines, drafts, diff evolution,
own work DNA ingestion, benchmark deconstruction, and dialogue clash)
from FastAPI HTTP controllers into a pure Python headless engine.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from contextlib import nullcontext

from sqlmodel import Session, select

from app.core.db import engine as default_engine, get_session, readonly_engine
from app.core.errors import FORBIDDEN, NOT_FOUND, VALIDATION_ERROR, AppError
from app.core.skill_engine import get_skill_manager
from app.domain.cognitive.models import CognitiveProfile, CognitiveDimension, TraitStatus, CognitiveTrait
from app.engine.agents.diff_agent import DiffAgent
from app.engine.agents.draft_agent import DraftAgent
from app.engine.agents.outline_agent import OutlineAgent
from app.models.dna_record import DNARecord
from app.models.persona import IPPersona, PERSONA_PRESETS, DEFAULT_USER_ID
from app.models.product import ProductVault, PRODUCT_PRESETS
from app.models.story import EpisodicStory
from app.engine.prompts.dna_context import format_full_ip_context_prompt, format_dna_prompt_section
from app.services.memory_service import hybrid_retrieve_dna, hybrid_retrieve_dna_readonly, naturalize_time_expression
from app.models.draft import Draft
from app.models.material import Material
from app.models.viral_analysis import ViralSemanticAnalysisRecord
from app.models.user import User
from app.schemas.diff_schemas import DiffInput, DNAExtractionOutput, ThinkingDNA
from app.schemas.draft_schemas import DraftInput, DraftOutput
from app.schemas.outline_schemas import Outline, OutlineInput, OutlineOutput, OutlineSection
from app.services.cognitive_service import CognitiveService
from app.services.memory_service import MemoryService
from app.services.style_selection_service import (
    STYLE_SOURCE_AUTO,
    STYLE_SOURCE_EXPLICIT,
    STYLE_SOURCE_NONE,
    StyleSelectionResult,
    StyleSelectionService,
)

logger = logging.getLogger(__name__)



def _parse_user_id(user_id: Optional[str | uuid.UUID]) -> Optional[uuid.UUID]:
    if not user_id:
        return None
    if isinstance(user_id, uuid.UUID):
        return user_id
    try:
        return uuid.UUID(str(user_id))
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(user_id))


MAX_STYLE_FINGERPRINT_CHARS = 8000


def _load_owned_style_fingerprint(
    sess: Session,
    viral_analysis_id: str | uuid.UUID,
    user_id: Optional[str | uuid.UUID],
) -> tuple[uuid.UUID, str]:
    """Load the style fingerprint prompt block for a user-owned viral analysis.

    Runs against the read-only session before any prompt is assembled, so an
    invalid or foreign analysis can never influence an LLM call. Raises
    :class:`AppError` with the correct public status (404 / 403 / 422) instead
    of a bare ``ValueError``, which the API layer would collapse to 422.
    """
    try:
        analysis_id = (
            viral_analysis_id
            if isinstance(viral_analysis_id, uuid.UUID)
            else uuid.UUID(str(viral_analysis_id))
        )
    except (ValueError, AttributeError, TypeError):
        raise AppError(
            code=VALIDATION_ERROR,
            message="viral_analysis_id must be a valid UUID.",
            status_code=422,
        )

    record = sess.get(ViralSemanticAnalysisRecord, analysis_id)
    if record is None:
        raise AppError(
            code=NOT_FOUND,
            message="The referenced viral analysis record could not be found.",
            status_code=404,
        )

    target_user_id = _parse_user_id(user_id)
    if record.user_id is None or target_user_id is None or record.user_id != target_user_id:
        raise AppError(
            code=FORBIDDEN,
            message="The referenced viral analysis record does not belong to the authenticated user.",
            status_code=403,
        )

    fingerprint = (record.analysis_data or {}).get("style_fingerprint")
    prompt_block = fingerprint.get("prompt_block") if isinstance(fingerprint, dict) else None
    if not isinstance(prompt_block, str) or not prompt_block.strip():
        raise AppError(
            code=VALIDATION_ERROR,
            message="The selected viral analysis record has no usable style fingerprint.",
            status_code=422,
        )
    if len(prompt_block) > MAX_STYLE_FINGERPRINT_CHARS:
        raise AppError(
            code=VALIDATION_ERROR,
            message="The selected viral analysis record has an oversized style fingerprint.",
            status_code=422,
        )

    return analysis_id, prompt_block.strip()


def _readonly_ctx(session: Optional[Session]):
    """Return a read-only session context manager for agent input assembly.

    If ``session`` is provided it is used as-is (callers inject
    ``get_readonly_session``); otherwise a session on ``readonly_engine`` is
    opened. The agent layer NEVER falls back to the writable engine here.
    """
    if session is not None:
        return nullcontext(session)
    return Session(readonly_engine)


def _writable_ctx(session: Optional[Session]):
    """Return a writable session context manager (draft archive only)."""
    if session is not None:
        return nullcontext(session)
    return Session(default_engine)

class CognitiveEngine:
    def __init__(self):
        self.skill_manager = get_skill_manager()

    def _assemble_ip_bundle(
        self,
        topic: str,
        sess: Session,
        user_id: Optional[str | uuid.UUID] = None,
        thinking_dna: Optional[ThinkingDNA] = None,
        persona_id: Optional[str | uuid.UUID] = None,
        product_id: Optional[str | uuid.UUID] = None,
        story_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Assembles IPPersona, Thinking DNA 2.0, EpisodicStory, and ProductVault into a unified context."""
        # NOTE: this method is the agent layer's *input context* assembly. It is
        # only ever called with a physically read-only session (readonly_engine),
        # so it must not use any get_or_create_* helper - those commit.
        parsed_uid = _parse_user_id(user_id)
        if not parsed_uid:
            user = CognitiveService.get_default_user_readonly(sess)
            uid = user.id if user is not None else DEFAULT_USER_ID
        else:
            uid = parsed_uid

        # 1. IP Persona
        persona: Optional[IPPersona] = None
        if persona_id:
            try:
                p_uuid = uuid.UUID(str(persona_id))
                persona = sess.get(IPPersona, p_uuid)
                if persona and persona.user_id != uid and persona.user_id != DEFAULT_USER_ID:
                    persona = None
            except ValueError:
                pass
        if not persona:
            persona = sess.exec(
                select(IPPersona).where(IPPersona.user_id == uid, IPPersona.is_active == True)
            ).first()
        if not persona and uid != DEFAULT_USER_ID:
            persona = sess.exec(
                select(IPPersona).where(IPPersona.user_id == DEFAULT_USER_ID, IPPersona.is_active == True)
            ).first()
        if not persona and PERSONA_PRESETS:
            persona = PERSONA_PRESETS[0]

        # 2. Thinking DNA 2.0 & Evolution notes
        evolution_notes: List[str] = []
        if thinking_dna is None:
            traits_data = hybrid_retrieve_dna_readonly(topic, user_id=uid, session=sess, limit=8)
            if traits_data:
                vocab = []
                logic = []
                values = []
                for item in traits_data:
                    t = item["trait"]
                    if t.dimension == CognitiveDimension.VOCABULARY:
                        vocab.append(t.statement)
                    elif t.dimension == CognitiveDimension.LOGIC_PREFERENCE:
                        logic.append(t.statement)
                    elif t.dimension in (CognitiveDimension.CORE_VALUE, CognitiveDimension.VIEWPOINT_STANCE):
                        values.append(t.statement)

                    if getattr(t, "evolution_reason", None) or getattr(t, "version", 1) > 1:
                        ver = getattr(t, "version", 1)
                        reason = getattr(t, "evolution_reason", "") or "深化演进"
                        evolution_notes.append(f"V{ver}: {t.statement}（演进背景：{reason}）")

                thinking_dna = ThinkingDNA(
                    vocabulary_habits=vocab,
                    logic_preferences=logic,
                    core_values=values,
                    summary=f"Contextual Thinking DNA 2.0 retrieved for topic '{topic}'",
                )
            else:
                # Fall back to the read-only profile export. The writable
                # retrieve_contextual_dna / get_exportable_dna_for_user helpers
                # both route through get_or_create_user_profile and would fail
                # on a read-only session.
                profile_ro = CognitiveService.get_user_profile_readonly(sess, uid)
                if profile_ro is not None and profile_ro.traits:
                    thinking_dna = profile_ro.export_thinking_dna(
                        summary=f"Thinking DNA 2.0 read from profile for topic '{topic}'"
                    )
                else:
                    thinking_dna = ThinkingDNA(
                        summary=f"No accumulated Thinking DNA yet for topic '{topic}'"
                    )

        if not evolution_notes:
            profile = CognitiveService.get_user_profile_readonly(sess, uid)
            for t in (profile.traits if profile is not None else []):
                if getattr(t, "status", None) == TraitStatus.SUPPRESSED:
                    continue
                if getattr(t, "trait_status", "active") == "deprecated":
                    continue
                if getattr(t, "evolution_reason", None) or getattr(t, "version", 1) > 1:
                    ver = getattr(t, "version", 1)
                    reason = getattr(t, "evolution_reason", "") or "深化演进"
                    evolution_notes.append(f"V{ver}: {t.statement}（演进背景：{reason}）")

        # 3. Episodic Stories
        stories = MemoryService.retrieve_relevant_stories_readonly(
            topic=topic,
            user_id=uid,
            limit=2,
            session=sess,
            story_ids=story_ids,
        )

        # 4. Product Vault
        product: Optional[ProductVault] = None
        if product_id and str(product_id).strip().lower() not in ("none", "null", "false", ""):
            try:
                pr_uuid = uuid.UUID(str(product_id))
                product = sess.get(ProductVault, pr_uuid)
                if product and product.user_id != uid and product.user_id != DEFAULT_USER_ID:
                    product = None
            except ValueError:
                pass
        elif str(product_id).strip().lower() in ("none", "null", "false"):
            product = None

        if not product and product_id is None:
            active_prods = sess.exec(
                select(ProductVault).where(ProductVault.user_id == uid, ProductVault.is_active == True)
            ).all()
            if not active_prods and uid != DEFAULT_USER_ID:
                active_prods = sess.exec(
                    select(ProductVault).where(ProductVault.user_id == DEFAULT_USER_ID, ProductVault.is_active == True)
                ).all()
            if not active_prods:
                active_prods = [p for p in PRODUCT_PRESETS if p.is_active]

            topic_lower = topic.lower()
            topic_keywords = set(re.findall(r"[a-zA-Z0-9_]{2,}", topic_lower))
            chinese_chars = re.findall(r"[\u4e00-\u9fa5]", topic_lower)
            for i in range(len(chinese_chars) - 1):
                topic_keywords.add("".join(chinese_chars[i:i+2]))
            for i in range(len(chinese_chars) - 2):
                topic_keywords.add("".join(chinese_chars[i:i+3]))
            topic_keywords.update(re.findall(r"[\u4e00-\u9fa5]{2,}", topic_lower))

            scored_prods = []
            for p in active_prods:
                p_text = f"{p.product_name} {p.category} {p.suitable_conditions} {p.core_ingredients} {p.personal_usage_experience}".lower()
                match_count = sum(1 for kw in topic_keywords if kw in p_text)
                scored_prods.append((match_count, p))

            scored_prods.sort(key=lambda x: x[0], reverse=True)
            if scored_prods and scored_prods[0][0] > 0:
                product = scored_prods[0][1]

        # 5. Full IP Context prompt
        ip_context_prompt = format_full_ip_context_prompt(
            thinking_dna=thinking_dna,
            persona=persona,
            stories=stories,
            product=product,
            dna_evolution_notes=evolution_notes,
        )

        return {
            "persona": persona,
            "product": product,
            "stories": stories,
            "thinking_dna": thinking_dna,
            "evolution_notes": evolution_notes,
            "ip_context_prompt": ip_context_prompt,
        }


    async def explore_outlines(
        self,
        topic: str,
        additional_context: Optional[str] = None,
        user_id: Optional[str | uuid.UUID] = None,
        thinking_dna: Optional[ThinkingDNA] = None,
        agent: Optional[OutlineAgent] = None,
        readonly_session: Optional[Session] = None,
        persona_id: Optional[str | uuid.UUID] = None,
        product_id: Optional[str | uuid.UUID] = None,
        story_ids: Optional[List[str]] = None,
    ) -> OutlineOutput:
        """Generates two divergent outlines enriched with user thinking DNA, Persona, Stories, and Product.

        The Outline agent is read-only: its context assembly always runs on
        ``readonly_engine`` (or the injected read-only session).
        """
        if not topic or not topic.strip():
            raise ValueError("Topic cannot be empty.")

        outline_agent = agent or OutlineAgent()

        with _readonly_ctx(readonly_session) as sess:
            ip_bundle = self._assemble_ip_bundle(
                topic=topic,
                sess=sess,
                user_id=user_id,
                thinking_dna=thinking_dna,
                persona_id=persona_id,
                product_id=product_id,
                story_ids=story_ids,
            )

        payload = OutlineInput(
            topic=topic.strip(),
            additional_context=additional_context.strip() if additional_context else None,
            thinking_dna=ip_bundle["thinking_dna"],
            user_id=str(user_id) if user_id else None,
            persona_id=str(persona_id) if persona_id else (str(ip_bundle["persona"].id) if ip_bundle.get("persona") and hasattr(ip_bundle["persona"], "id") else None),
            product_id=str(product_id) if product_id else (str(ip_bundle["product"].id) if ip_bundle.get("product") and hasattr(ip_bundle["product"], "id") else None),
            story_ids=story_ids or [str(s.id) for s in ip_bundle.get("stories", []) if hasattr(s, "id")],
            ip_context_prompt=ip_bundle["ip_context_prompt"],
            persona=ip_bundle["persona"],
            product=ip_bundle["product"],
            stories=ip_bundle["stories"],
        )

        return await outline_agent.generate_outlines(payload)

    async def generate_draft(
        self,
        topic: str,
        outline: Outline | Dict[str, Any],
        additional_context: Optional[str] = None,
        user_id: Optional[str | uuid.UUID] = None,
        thinking_dna: Optional[ThinkingDNA] = None,
        agent: Optional[DraftAgent] = None,
        readonly_session: Optional[Session] = None,
        session: Optional[Session] = None,
        source_material_id: Optional[str | uuid.UUID] = None,
        benchmark_blueprint_id: Optional[str] = None,
        lineage_snapshot: Optional[Dict[str, Any]] = None,
        persona_id: Optional[str | uuid.UUID] = None,
        product_id: Optional[str | uuid.UUID] = None,
        story_ids: Optional[List[str]] = None,
        viral_analysis_id: Optional[str | uuid.UUID] = None,
        style_selection_service: Optional[StyleSelectionService] = None,
    ) -> DraftOutput:
        """Generates a complete draft article guided by Thinking DNA.

        Two distinct sessions are used:

        * ``readonly_session`` - agent *input context* assembly only
          (``readonly_engine``). The Draft agent itself never writes.
        * ``session`` - the writable archive harness that persists the generated
          draft after generation. The Draft workflow as a whole is therefore NOT
          read-only; only the agent-facing read path is isolated.
        """
        if not topic or not topic.strip():
            raise ValueError("Topic cannot be empty.")

        draft_agent = agent or DraftAgent()

        parsed_outline = outline if isinstance(outline, Outline) else Outline.model_validate(outline)

        with _readonly_ctx(readonly_session) as sess:
            ip_bundle = self._assemble_ip_bundle(
                topic=topic,
                sess=sess,
                user_id=user_id,
                thinking_dna=thinking_dna,
                persona_id=persona_id,
                product_id=product_id,
                story_ids=story_ids,
            )

            # Ownership + integrity of the referenced style fingerprint are proven
            # here, on the read-only session, strictly before any prompt or LLM
            # work. A missing / foreign / malformed record is a hard error and
            # never a silent degradation to "no style".
            style_analysis_id: Optional[uuid.UUID] = None
            style_prompt: Optional[str] = None
            style_source = STYLE_SOURCE_NONE
            selection: Optional[StyleSelectionResult] = None
            if viral_analysis_id is not None:
                # Stage 1 - an explicit request wins outright. Automatic selection
                # is never consulted and never overrides this choice.
                style_analysis_id, style_prompt = _load_owned_style_fingerprint(
                    sess, viral_analysis_id, user_id
                )
                style_source = STYLE_SOURCE_EXPLICIT
            else:
                # Stage 2 - rank the caller's own analyses. The service only ranks;
                # the strict loader below still re-validates the winner.
                selector = style_selection_service or StyleSelectionService()
                try:
                    selection = selector.select(
                        sess,
                        _parse_user_id(user_id),
                        topic=topic,
                        ip_text=ip_bundle.get("ip_context_prompt") or "",
                        additional_context=additional_context,
                    )
                except Exception:
                    # Selection is an optimisation, never a hard requirement: a
                    # misbehaving or unavailable selector must degrade to
                    # Persona/DNA instead of failing an otherwise valid request.
                    logger.exception("Viral style auto-selection failed; degrading")
                    selection = StyleSelectionResult(reason="candidate_lookup_failed")
                if selection.accepted and selection.analysis_id is not None:
                    try:
                        style_analysis_id, style_prompt = _load_owned_style_fingerprint(
                            sess, selection.analysis_id, user_id
                        )
                    except AppError:
                        # Stage 3 - an automatic choice is best effort: degrade to
                        # Persona/DNA instead of failing the request.
                        style_analysis_id, style_prompt = None, None
                    else:
                        style_source = STYLE_SOURCE_AUTO

        payload = DraftInput(
            topic=topic.strip(),
            outline=parsed_outline,
            additional_context=additional_context.strip() if additional_context else None,
            thinking_dna=ip_bundle["thinking_dna"],
            user_id=str(user_id) if user_id else None,
            source_material_id=str(source_material_id) if source_material_id else None,
            benchmark_blueprint_id=str(benchmark_blueprint_id) if benchmark_blueprint_id else None,
            persona_id=str(persona_id) if persona_id else (str(ip_bundle["persona"].id) if ip_bundle.get("persona") and hasattr(ip_bundle["persona"], "id") else None),
            product_id=str(product_id) if product_id else (str(ip_bundle["product"].id) if ip_bundle.get("product") and hasattr(ip_bundle["product"], "id") else None),
            story_ids=story_ids or [str(s.id) for s in ip_bundle.get("stories", []) if hasattr(s, "id")],
            ip_context_prompt=ip_bundle["ip_context_prompt"],
            persona=ip_bundle["persona"],
            product=ip_bundle["product"],
            stories=ip_bundle["stories"],
            viral_analysis_id=str(style_analysis_id) if style_analysis_id else None,
            style_fingerprint_prompt=style_prompt,
        )

        draft_output = await draft_agent.generate_draft(payload)

        # Auto-save generated draft to DB archive
        def _persist_draft(sess: Session) -> uuid.UUID:
            target_user_id = user_id
            if target_user_id:
                parsed_uid = _parse_user_id(target_user_id)
                user = sess.get(User, parsed_uid) if parsed_uid else None
                if not user:
                    user = User(id=parsed_uid, username=f"user_{str(parsed_uid)[:8]}")
                    sess.add(user)
                    sess.commit()
                    sess.refresh(user)
                uid = user.id
            else:
                user = CognitiveService.get_or_create_default_user(sess)
                uid = user.id

            mat_id = _parse_user_id(source_material_id)
            mat = sess.get(Material, mat_id) if mat_id else None
            snapshot = dict(lineage_snapshot or {})
            if mat:
                snapshot.setdefault("source_material_id", str(mat.id))
                snapshot.setdefault("source_title", mat.title)
                snapshot.setdefault("source_author", mat.source_author)
                snapshot.setdefault("source_platform", mat.source_platform)
                snapshot.setdefault("source_url", mat.source_url)
                snapshot.setdefault("material_type", mat.material_type)
                if mat.blueprint_data:
                    snapshot.setdefault("blueprint_title", mat.blueprint_data.get("title"))
                    snapshot.setdefault("inspiration_hook", mat.blueprint_data.get("hook_style"))
                    snapshot.setdefault("emotional_arc", mat.blueprint_data.get("emotional_arc"))
                snapshot.setdefault("captured_at", datetime.now(timezone.utc).isoformat())
                mat.status = "used"
                sess.add(mat)
            if style_analysis_id is not None:
                snapshot.setdefault("viral_analysis_id", str(style_analysis_id))
            snapshot.setdefault("style_source", style_source)
            if selection is not None:
                snapshot.setdefault("style_auto_selection", {
                    "accepted": selection.accepted,
                    "score": selection.score,
                    "threshold": selection.threshold,
                    "reason": selection.reason,
                    "candidate_count": selection.candidate_count,
                })
            if benchmark_blueprint_id and "benchmark_blueprint_id" not in snapshot:
                snapshot["benchmark_blueprint_id"] = str(benchmark_blueprint_id)
            effective_dna = ip_bundle.get("thinking_dna") or thinking_dna
            if effective_dna and "dna_snapshot" not in snapshot:
                snapshot["dna_snapshot"] = {
                    "style_tone": getattr(effective_dna, "style_tone", ""),
                    "vocabulary_signature": getattr(effective_dna, "vocabulary_signature", []),
                    "thinking_archetype": getattr(effective_dna, "thinking_archetype", ""),
                }

            new_draft = Draft(
                user_id=uid,
                topic=topic.strip(),
                original_ai_draft=draft_output.content,
                user_final_draft=None,
                source_material_id=mat.id if mat else mat_id,
                benchmark_blueprint_id=str(benchmark_blueprint_id) if benchmark_blueprint_id else None,
                lineage_snapshot=snapshot if snapshot else None,
                metadata_={
                    "title": draft_output.title,
                    "summary": draft_output.summary,
                    "word_count": draft_output.word_count,
                    "outline": parsed_outline.model_dump() if hasattr(parsed_outline, "model_dump") else parsed_outline,
                    "core_viewpoints": [
                        vp.model_dump() if hasattr(vp, "model_dump") else vp
                        for vp in (draft_output.core_viewpoints or [])
                    ],
                    "injected_dna": ip_bundle["thinking_dna"].model_dump() if ip_bundle.get("thinking_dna") and hasattr(ip_bundle["thinking_dna"], "model_dump") else (ip_bundle.get("thinking_dna") or {}),
                    "persona_id": str(ip_bundle["persona"].id) if ip_bundle.get("persona") and hasattr(ip_bundle["persona"], "id") else None,
                    "product_id": str(ip_bundle["product"].id) if ip_bundle.get("product") and hasattr(ip_bundle["product"], "id") else None,
                    "story_ids": [str(s.id) for s in ip_bundle.get("stories", []) if hasattr(s, "id")],
                    "additional_context": additional_context,
                },
            )
            sess.add(new_draft)
            sess.commit()
            sess.refresh(new_draft)
            return new_draft.id, (snapshot if snapshot else None)

        try:
            with _writable_ctx(session) as w_sess:
                saved_id, final_snapshot = _persist_draft(w_sess)
            draft_output.id = str(saved_id)
            draft_output.draft_id = str(saved_id)
            draft_output.source_material_id = str(source_material_id) if source_material_id else None
            draft_output.benchmark_blueprint_id = str(benchmark_blueprint_id) if benchmark_blueprint_id else None
            draft_output.lineage_snapshot = final_snapshot
        except Exception:
            pass

        draft_output.injected_dna = ip_bundle["thinking_dna"]
        draft_output.persona_id = str(persona_id) if persona_id else (str(ip_bundle["persona"].id) if ip_bundle.get("persona") and hasattr(ip_bundle["persona"], "id") else None)
        draft_output.product_id = str(product_id) if product_id else (str(ip_bundle["product"].id) if ip_bundle.get("product") and hasattr(ip_bundle["product"], "id") else None)
        draft_output.story_ids = story_ids or [str(s.id) for s in ip_bundle.get("stories", []) if hasattr(s, "id")]
        draft_output.ip_context_prompt = ip_bundle.get("ip_context_prompt")
        return draft_output

    async def generate_from_blueprint(
        self,
        topic: str,
        blueprint: Optional[Dict[str, Any]] = None,
        blueprint_id: Optional[str] = None,
        additional_context: Optional[str] = None,
        user_id: Optional[str | uuid.UUID] = None,
        thinking_dna: Optional[ThinkingDNA] = None,
        agent: Optional[DraftAgent] = None,
        readonly_session: Optional[Session] = None,
        session: Optional[Session] = None,
        source_material_id: Optional[str | uuid.UUID] = None,
        persona_id: Optional[str | uuid.UUID] = None,
        product_id: Optional[str | uuid.UUID] = None,
        story_ids: Optional[List[str]] = None,
    ) -> DraftOutput:
        """Generates a complete draft article structured by BenchmarkBlueprint ('Bone')
        and styled with user's authentic ThinkingDNA ('Skin').
        """
        if not topic or not topic.strip():
            raise ValueError("Topic cannot be empty.")

        if blueprint:
            if hasattr(blueprint, "model_dump"):
                effective_blueprint = blueprint.model_dump()
            elif isinstance(blueprint, dict):
                effective_blueprint = dict(blueprint)
            else:
                effective_blueprint = dict(blueprint)
        else:
            effective_blueprint = None
        if not effective_blueprint and blueprint_id:
            def _find_blueprint(sess: Session) -> Optional[Dict[str, Any]]:
                parsed_uid = _parse_user_id(user_id)
                user = (
                    sess.get(User, parsed_uid)
                    if parsed_uid
                    else CognitiveService.get_default_user_readonly(sess)
                )
                if user and user.profile_data:
                    blueprints = user.profile_data.get("benchmark_blueprints", [])
                    for bp in blueprints:
                        if str(bp.get("id")) == str(blueprint_id):
                            return dict(bp)
                return None

            with _readonly_ctx(readonly_session) as sess:
                effective_blueprint = _find_blueprint(sess)

        if not effective_blueprint:
            raise ValueError(
                f"Benchmark blueprint not found (id: {blueprint_id}). "
                "Provide a valid blueprint_id or explicit blueprint object."
            )

        blueprint_title = effective_blueprint.get("title", "Benchmark Article")
        hook_style = effective_blueprint.get("hook_style", "开门见山提出问题或悬念")
        raw_stages = effective_blueprint.get("structural_stages") or [
            "提出核心痛点与悬念",
            "深入剖析根因与逻辑",
            "给出具体解法与策略",
            "升华总结与行动号召",
        ]
        structural_stages: List[str] = []
        for s in raw_stages:
            if isinstance(s, dict):
                structural_stages.append(str(s.get("title") or s.get("name") or s.get("stage") or "结构阶段"))
            elif s is not None:
                structural_stages.append(str(s).strip())
        if not structural_stages:
            structural_stages = [
                "提出核心痛点与悬念",
                "深入剖析根因与逻辑",
                "给出具体解法与策略",
                "升华总结与行动号召",
            ]
        emotional_arc = effective_blueprint.get("emotional_arc", "困惑/痛点 ➔ 认知重构 ➔ 笃定/赋能行动")
        pacing = effective_blueprint.get("pacing", "前 20% 快速切入，中段 60% 展开论证，后 20% 总结升华")

        sections = [
            OutlineSection(
                title=f"阶段 {i}: {stage}",
                bullet_points=[
                    f"节奏把控：{pacing}",
                    f"情绪推进：{emotional_arc}",
                    f"围绕选题「{topic.strip()}」展开论述",
                ],
            )
            for i, stage in enumerate(structural_stages, 1)
        ]
        bone_outline = Outline(
            title=f"基于【{blueprint_title}】骨架：{topic.strip()}",
            rationale=f"结构源自爆款骨架【{blueprint_title}】。Hook风格：{hook_style}；情绪弧线：{emotional_arc}；节奏：{pacing}。",
            sections=sections,
        )

        stages_str = " ➔ ".join(structural_stages)
        bone_instructions = chr(10).join([
            "【对标爆款骨架约束 (Bone Architecture)】",
            f"- 来源对标：{blueprint_title}",
            f"- 开篇Hook策略：{hook_style}",
            f"- 情绪弧线推进：{emotional_arc}",
            f"- 叙事节奏律动：{pacing}",
            f"- 骨架阶段演进：{stages_str}",
            "必须严格遵循该爆款骨架的结构阶段、叙事节奏和情绪起伏，同时注入作者个人独创皮肉 (Thinking DNA)，创作出版级原创长文。",
        ])
        combined_context = (
            f"{bone_instructions}\n\n{additional_context.strip()}"
            if additional_context and additional_context.strip()
            else bone_instructions
        )

        bp_val = blueprint_id or (effective_blueprint.get("id") if isinstance(effective_blueprint, dict) else None)
        effective_bp_id = str(bp_val) if bp_val else None
        return await self.generate_draft(
            topic=topic.strip(),
            outline=bone_outline,
            additional_context=combined_context,
            user_id=user_id,
            thinking_dna=thinking_dna,
            agent=agent,
            readonly_session=readonly_session,
            session=session,
            source_material_id=source_material_id,
            benchmark_blueprint_id=effective_bp_id,
            persona_id=persona_id,
            product_id=product_id,
            story_ids=story_ids,
        )

    def distribute_content(
        self,
        content: str,
        title: Optional[str] = None,
        platforms: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Distributes article content into multiple platform formats using content_multi_distributor skill."""
        if not content or not content.strip():
            raise ValueError("Content cannot be empty for multi-platform distribution.")

        args: Dict[str, Any] = {"content": content.strip()}
        if title:
            args["title"] = title.strip()
        if platforms:
            args["platforms"] = platforms

        result = self.skill_manager.execute_skill_sync("content_multi_distributor", args)
        if not result.success or not isinstance(result.output, dict):
            raise RuntimeError(f"Skill execution failed: {result.error or result.stderr or 'Unknown error'}")

        return result.output

    async def evolve_with_diff(
        self,
        original_ai_draft: str,
        user_final_draft: str,
        topic: Optional[str] = None,
        draft_id: Optional[str | uuid.UUID] = None,
        user_id: Optional[str | uuid.UUID] = None,
        viewpoint_judgments: Optional[List[Any]] = None,
        agent: Optional[DiffAgent] = None,
        session: Optional[Session] = None,
    ) -> DNAExtractionOutput:
        """Extracts Thinking DNA from draft modifications and reinforces user profile."""
        if not original_ai_draft or not original_ai_draft.strip():
            raise ValueError("Original AI draft content cannot be empty.")
        if not user_final_draft or not user_final_draft.strip():
            raise ValueError("User final draft content cannot be empty.")

        diff_agent = agent or DiffAgent()

        diff_input = DiffInput(
            original_ai_draft=original_ai_draft.strip(),
            user_final_draft=user_final_draft.strip(),
            topic=topic,
            draft_id=str(draft_id) if draft_id else None,
            user_id=str(user_id) if user_id else None,
            viewpoint_judgments=viewpoint_judgments or [],
        )

        result = await diff_agent.extract_dna(diff_input)

        if result.has_diff and result.thinking_dna:
            def _persist(sess: Session):
                target_user_id = user_id
                target_draft = None
                if draft_id:
                    parsed_draft_id = _parse_user_id(draft_id)
                    target_draft = sess.get(Draft, parsed_draft_id) if parsed_draft_id else None
                    if target_draft and not target_user_id:
                        target_user_id = target_draft.user_id

                if target_user_id:
                    parsed_uid = _parse_user_id(target_user_id)
                    user = sess.get(User, parsed_uid) if parsed_uid else None
                    if not user:
                        user = User(id=parsed_uid, username="default_user")
                        sess.add(user)
                        sess.commit()
                        sess.refresh(user)
                else:
                    user = CognitiveService.get_or_create_default_user(sess)
                    target_user_id = user.id

                effective_draft_id = draft_id
                if target_draft:
                    target_draft.user_final_draft = user_final_draft
                    target_draft.updated_at = datetime.now(timezone.utc)
                    sess.add(target_draft)
                    sess.commit()
                    sess.refresh(target_draft)
                    effective_draft_id = target_draft.id
                else:
                    new_draft = Draft(
                        user_id=target_user_id,
                        topic=topic or "Untitled Draft",
                        original_ai_draft=original_ai_draft,
                        user_final_draft=user_final_draft,
                    )
                    sess.add(new_draft)
                    sess.commit()
                    sess.refresh(new_draft)
                    effective_draft_id = new_draft.id

                dna_record = DNARecord(
                    user_id=target_user_id,
                    draft_id=effective_draft_id,
                    dna_data=result.thinking_dna.model_dump(),
                )
                sess.add(dna_record)
                sess.commit()
                sess.refresh(dna_record)

                CognitiveService.sync_extracted_dna(
                    session=sess,
                    user_id=target_user_id,
                    thinking_dna=result.thinking_dna,
                    source_draft_id=str(effective_draft_id) if effective_draft_id else None,
                )

                result.dna_record_id = dna_record.id
                result.draft_id = effective_draft_id

            if session:
                _persist(session)
            else:
                with Session(default_engine) as sess:
                    _persist(sess)

        return result

    def ingest_own_works_for_dna(
        self,
        content_or_url: str,
        user_id: Optional[str | uuid.UUID] = None,
        title: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Ingests user's own original works (via raw text or web URL) to cold-start Thinking DNA."""
        target_text = content_or_url.strip()
        effective_title = title

        # Check if input is a URL
        if target_text.startswith("http://") or target_text.startswith("https://"):
            extraction = self.skill_manager.execute_skill_sync(
                "media_article_extractor",
                {"url": target_text},
            )
            if extraction.success and isinstance(extraction.output, dict):
                target_text = extraction.output.get("text", "")
                if not effective_title:
                    effective_title = extraction.output.get("title")
            else:
                raise ValueError(f"Failed to fetch and extract content from URL: {extraction.error or extraction.stderr}")

        return MemoryService.add_own_work_dna(
            content=target_text,
            user_id=user_id,
            session=session,
            title=effective_title,
        )

    def deconstruct_benchmark_article(
        self,
        content_or_url: str,
        user_id: Optional[str | uuid.UUID] = None,
        title: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Deconstructs an external benchmark article into Blueprint Skeletons & Clash Points.
        Does NOT alter CognitiveProfile.
        """
        target_text = content_or_url.strip()
        effective_title = title
        source_url = None

        if target_text.startswith("http://") or target_text.startswith("https://"):
            source_url = target_text
            extraction = self.skill_manager.execute_skill_sync(
                "media_article_extractor",
                {"url": target_text},
            )
            if extraction.success and isinstance(extraction.output, dict):
                target_text = extraction.output.get("text", "")
                if not effective_title:
                    effective_title = extraction.output.get("title")
            else:
                raise ValueError(f"Failed to fetch and extract benchmark from URL: {extraction.error or extraction.stderr}")

        return MemoryService.deconstruct_benchmark(
            content=target_text,
            user_id=user_id,
            session=session,
            title=effective_title,
            source_url=source_url,
        )

    async def extract_blueprint_from_text(
        self,
        content_or_url: str,
        title: Optional[str] = None,
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Extracts structural blueprint ('bone') from a benchmark article (URL or raw text)
        and persists it to the user's benchmark library.
        """
        result = self.deconstruct_benchmark_article(
            content_or_url=content_or_url,
            user_id=user_id,
            title=title,
            session=session,
        )
        bp = result.get("blueprint", {})
        output = dict(bp)
        output["success"] = True
        output["blueprint"] = bp
        output["clash_points"] = result.get("clash_points", [])
        return output

    def ingest_dialogue_and_evolve(
        self,
        messages: List[Dict[str, str]],
        user_id: Optional[str | uuid.UUID] = None,
        debate_topic: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Alias for record_dialogue_clash conforming to implementation_plan.md specification."""
        return self.record_dialogue_clash(
            messages=messages,
            user_id=user_id,
            debate_topic=debate_topic,
            session=session,
        )

    def record_dialogue_clash(
        self,
        messages: List[Dict[str, str]],
        user_id: Optional[str | uuid.UUID] = None,
        debate_topic: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Records user's viewpoints and refutations from a clash dialogue."""
        return MemoryService.record_dialogue_clash(
            messages=messages,
            user_id=user_id,
            debate_topic=debate_topic,
            session=session,
        )


_engine_instance: Optional[CognitiveEngine] = None


def get_cognitive_engine() -> CognitiveEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = CognitiveEngine()
    return _engine_instance


__all__ = ["CognitiveEngine", "get_cognitive_engine"]
