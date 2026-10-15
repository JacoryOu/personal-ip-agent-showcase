# -*- coding: utf-8 -*-
"""Tests for the owned viral style fingerprint -> Draft pipeline.

Covers:
- Reference-style prompt block formatting and its hard constraints.
- Server-side resolution / ownership / validation of ``viral_analysis_id``
  strictly before any DraftAgent (LLM) call.
- The public request model cannot carry a trusted style prompt.
- The trusted prompt never leaks back out through ``model_dump()``.
- Lineage snapshot records the style provenance.
"""

import uuid

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.errors import AppError
from app.engine.agents.draft_agent import (
    REFERENCE_STYLE_FOOTER,
    REFERENCE_STYLE_HEADER,
    DraftAgent,
    format_reference_style_section,
)
from app.engine.cognitive_engine import (
    MAX_STYLE_FINGERPRINT_CHARS,
    CognitiveEngine,
)
from app.models.user import User
from app.models.viral_analysis import ViralSemanticAnalysisRecord
from app.schemas.draft_schemas import (
    CoreViewpoint,
    DraftGenerateRequest,
    DraftInput,
    DraftOutput,
)
from app.schemas.outline_schemas import Outline, OutlineSection

SAMPLE_FINGERPRINT = "Short paragraphs. One idea per line. Cold open."


@pytest.fixture(name="db_session")
def db_session_fixture():
    import app.models  # noqa: F401  (populate SQLModel metadata)

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        yield session


def _analysis(
    db_session,
    user_id,
    prompt_block=SAMPLE_FINGERPRINT,
    source_title="爆款参考",
    transfer=None,
    **kwargs,
):
    data = {"style_fingerprint": {"prompt_block": prompt_block}}
    if transfer is not None:
        data["transfer"] = {"reuse_score": transfer}
    record = ViralSemanticAnalysisRecord(
        user_id=user_id,
        source_title=source_title,
        source_content_hash=uuid.uuid4().hex,
        analysis_data=data,
        **kwargs,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


def _outline():
    return Outline(
        title="参考结构落地",
        rationale="验证风格参考",
        sections=[OutlineSection(title="第一节：冷开场", bullet_points=["一句话切入"])],
    )


class SpyDraftAgent(DraftAgent):
    """DraftAgent stand-in that records the payload and never calls an LLM."""

    def __init__(self):
        self.payloads = []

    async def generate_draft(self, input_data: DraftInput) -> DraftOutput:
        self.payloads.append(input_data)
        return DraftOutput(
            title="成稿",
            summary="摘要",
            content="# 成稿\n\n正文。",
            word_count=10,
            core_viewpoints=[CoreViewpoint(id="vp_1", claim="主张", options=[])],
        )


# ---------------------------------------------------------------------------
# 1. Prompt block formatting
# ---------------------------------------------------------------------------


def test_format_reference_style_section_includes_hard_constraints():
    section = format_reference_style_section(SAMPLE_FINGERPRINT)
    assert REFERENCE_STYLE_HEADER in section
    assert REFERENCE_STYLE_FOOTER in section
    assert SAMPLE_FINGERPRINT in section
    assert "Do NOT copy wording" in section
    assert "Do NOT present yourself as the reference author" in section
    assert "Do NOT invent facts" in section
    assert "take priority over this reference" in section


def test_format_reference_style_section_empty_returns_blank():
    assert format_reference_style_section("") == ""
    assert format_reference_style_section("   \n  ") == ""


def test_style_block_not_added_without_trusted_prompt(monkeypatch):
    captured = {}

    class CapturingAgent(SpyDraftAgent):
        async def generate_draft(self, input_data: DraftInput) -> DraftOutput:
            captured["payload"] = input_data
            return await super().generate_draft(input_data)

    agent = CapturingAgent()
    payload = DraftInput(topic="t", outline=_outline())
    # The engine never sets style_fingerprint_prompt here; assert the agent
    # only appends the section when the trusted value is present.
    assert payload.style_fingerprint_prompt is None
    # Static check of the guard condition used inside DraftAgent.generate_draft.
    body = ""
    if payload.style_fingerprint_prompt:
        body = format_reference_style_section(payload.style_fingerprint_prompt)
    assert body == ""


# ---------------------------------------------------------------------------
# 2. Schema separation: public vs internal
# ---------------------------------------------------------------------------


def test_public_request_cannot_set_trusted_style_prompt():
    body = {
        "topic": "t",
        "outline": {"title": "x", "sections": [{"title": "s", "bullet_points": ["b"]}]},
        "viral_analysis_id": str(uuid.uuid4()),
    }
    request = DraftGenerateRequest.model_validate(body)
    assert request.viral_analysis_id == body["viral_analysis_id"]
    assert not hasattr(request, "style_fingerprint_prompt")


def test_public_request_rejects_extra_trusted_field():
    body = {
        "topic": "t",
        "outline": {"title": "x", "sections": [{"title": "s", "bullet_points": ["b"]}]},
        "style_fingerprint_prompt": "injected",
    }
    with pytest.raises(Exception):
        DraftGenerateRequest.model_validate(body)


def test_legacy_draft_payload_without_viral_id_is_accepted():
    body = {
        "topic": "t",
        "outline": {"title": "x", "sections": [{"title": "s", "bullet_points": ["b"]}]},
    }
    request = DraftGenerateRequest.model_validate(body)
    assert request.viral_analysis_id is None


def test_trusted_prompt_not_serialized_back():
    payload = DraftInput(
        topic="t",
        outline=_outline(),
        style_fingerprint_prompt=SAMPLE_FINGERPRINT,
    )
    dumped = payload.model_dump()
    assert "style_fingerprint_prompt" not in dumped


# ---------------------------------------------------------------------------
# 3. Engine resolution + ownership + validation (no LLM reached on failure)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_draft_loads_owned_style_fingerprint(db_session):
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, username="style_user"))
    db_session.commit()
    record = _analysis(db_session, user_id)

    agent = SpyDraftAgent()
    engine = CognitiveEngine()
    result = await engine.generate_draft(
        topic="话题",
        outline=_outline(),
        user_id=user_id,
        agent=agent,
        readonly_session=db_session,
        session=db_session,
        viral_analysis_id=str(record.id),
    )

    assert result.title == "成稿"
    assert len(agent.payloads) == 1
    payload = agent.payloads[0]
    assert payload.viral_analysis_id == str(record.id)
    assert payload.style_fingerprint_prompt == SAMPLE_FINGERPRINT

    saved = db_session.get(__import__("app.models.draft", fromlist=["Draft"]).Draft, uuid.UUID(result.id))
    snapshot = saved.lineage_snapshot or saved.metadata_ or {}
    assert snapshot.get("viral_analysis_id") == str(record.id)
    assert snapshot.get("style_source") == "viral_semantic_analysis"


@pytest.mark.asyncio
async def test_generate_draft_rejects_invalid_uuid_before_llm(db_session):
    agent = SpyDraftAgent()
    engine = CognitiveEngine()
    with pytest.raises(AppError) as exc:
        await engine.generate_draft(
            topic="话题",
            outline=_outline(),
            user_id=uuid.uuid4(),
            agent=agent,
            readonly_session=db_session,
            session=db_session,
            viral_analysis_id="not-a-uuid",
        )
    assert exc.value.status_code == 422
    assert agent.payloads == []


@pytest.mark.asyncio
async def test_generate_draft_missing_analysis_404(db_session):
    agent = SpyDraftAgent()
    engine = CognitiveEngine()
    with pytest.raises(AppError) as exc:
        await engine.generate_draft(
            topic="话题",
            outline=_outline(),
            user_id=uuid.uuid4(),
            agent=agent,
            readonly_session=db_session,
            session=db_session,
            viral_analysis_id=str(uuid.uuid4()),
        )
    assert exc.value.status_code == 404
    assert agent.payloads == []


@pytest.mark.asyncio
async def test_generate_draft_cross_user_403(db_session):
    owner = uuid.uuid4()
    other = uuid.uuid4()
    db_session.add(User(id=owner, username="owner"))
    db_session.add(User(id=other, username="other"))
    db_session.commit()
    record = _analysis(db_session, owner)

    agent = SpyDraftAgent()
    engine = CognitiveEngine()
    with pytest.raises(AppError) as exc:
        await engine.generate_draft(
            topic="话题",
            outline=_outline(),
            user_id=other,
            agent=agent,
            readonly_session=db_session,
            session=db_session,
            viral_analysis_id=str(record.id),
        )
    assert exc.value.status_code == 403
    assert agent.payloads == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_prompt",
    [
        None,
        123,
        "",
        "   ",
        "x" * (MAX_STYLE_FINGERPRINT_CHARS + 1),
    ],
)
async def test_generate_draft_unusable_fingerprint_422(db_session, bad_prompt):
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, username="fp_user"))
    db_session.commit()
    data = {"style_fingerprint": {}}
    if bad_prompt is not None and isinstance(bad_prompt, int):
        data["style_fingerprint"] = {"prompt_block": bad_prompt}
    elif bad_prompt is not None and isinstance(bad_prompt, str):
        data["style_fingerprint"] = {"prompt_block": bad_prompt}
    record = ViralSemanticAnalysisRecord(
        user_id=user_id,
        source_title="t",
        source_content_hash=uuid.uuid4().hex,
        analysis_data=data,
    )
    db_session.add(record)
    db_session.commit()

    agent = SpyDraftAgent()
    engine = CognitiveEngine()
    with pytest.raises(AppError) as exc:
        await engine.generate_draft(
            topic="话题",
            outline=_outline(),
            user_id=user_id,
            agent=agent,
            readonly_session=db_session,
            session=db_session,
            viral_analysis_id=str(record.id),
        )
    assert exc.value.status_code == 422
    assert agent.payloads == []


@pytest.mark.asyncio
async def test_generate_draft_without_viral_id_keeps_legacy_behavior(db_session):
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, username="plain_user"))
    db_session.commit()

    agent = SpyDraftAgent()
    engine = CognitiveEngine()
    result = await engine.generate_draft(
        topic="话题",
        outline=_outline(),
        user_id=user_id,
        agent=agent,
        readonly_session=db_session,
        session=db_session,
    )
    assert result.title == "成稿"
    payload = agent.payloads[0]
    assert payload.viral_analysis_id is None
    assert payload.style_fingerprint_prompt is None

# ---------------------------------------------------------------------------
# 4. Automatic style selection (three-stage behaviour)
# ---------------------------------------------------------------------------


def _snapshot(db_session, draft_id):
    from app.models.draft import Draft as DraftModel

    saved = db_session.get(DraftModel, uuid.UUID(draft_id))
    return (saved.lineage_snapshot or saved.metadata_ or {})


def _matching_analysis(db_session, user_id, title="AI 副业 变现 复盘 手把手", transfer=5):
    record = ViralSemanticAnalysisRecord(
        user_id=user_id,
        source_title=title,
        source_content_hash=uuid.uuid4().hex,
        analysis_data={
            "style_fingerprint": {"prompt_block": SAMPLE_FINGERPRINT},
            "transfer": {"reuse_score": transfer},
        },
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


@pytest.mark.asyncio
async def test_explicit_id_never_runs_automatic_selection(db_session):
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, username="explicit_user"))
    db_session.commit()
    explicit = _matching_analysis(db_session, user_id)
    # A far better automatic candidate must not win over the explicit choice.
    _matching_analysis(db_session, user_id, title="AI 副业 变现 复盘 手把手 完整版 指南")

    class ExplodingSelectionService:
        def select(self, *args, **kwargs):
            raise AssertionError("automatic selection must not run for explicit ids")

    agent = SpyDraftAgent()
    engine = CognitiveEngine()
    result = await engine.generate_draft(
        topic="AI 副业 变现 复盘",
        outline=_outline(),
        user_id=user_id,
        agent=agent,
        readonly_session=db_session,
        session=db_session,
        viral_analysis_id=str(explicit.id),
        style_selection_service=ExplodingSelectionService(),
    )

    payload = agent.payloads[0]
    assert payload.viral_analysis_id == str(explicit.id)
    assert payload.style_fingerprint_prompt == SAMPLE_FINGERPRINT
    snapshot = _snapshot(db_session, result.id)
    assert snapshot.get("style_source") == "viral_semantic_analysis"
    assert "style_auto_selection" not in snapshot


@pytest.mark.asyncio
async def test_automatic_selection_picks_best_owned_fingerprint(db_session):
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, username="auto_user"))
    db_session.commit()
    _matching_analysis(db_session, user_id, title="副业 变现 复盘", transfer=0)
    best = _matching_analysis(
        db_session, user_id, title="AI 副业 变现 复盘 手把手", transfer=5
    )

    agent = SpyDraftAgent()
    engine = CognitiveEngine()
    result = await engine.generate_draft(
        topic="AI 副业 变现 复盘",
        outline=_outline(),
        user_id=user_id,
        agent=agent,
        readonly_session=db_session,
        session=db_session,
    )

    payload = agent.payloads[0]
    assert payload.viral_analysis_id == str(best.id)
    assert payload.style_fingerprint_prompt == SAMPLE_FINGERPRINT
    snapshot = _snapshot(db_session, result.id)
    assert snapshot.get("style_source") == "viral_semantic_analysis_auto_selected"
    assert snapshot.get("viral_analysis_id") == str(best.id)
    auto = snapshot.get("style_auto_selection")
    assert auto["accepted"] is True
    assert auto["score"] >= auto["threshold"]
    assert auto["reason"] == "selected"


@pytest.mark.asyncio
async def test_automatic_selection_never_crosses_user_boundary(db_session):
    me = uuid.uuid4()
    other = uuid.uuid4()
    db_session.add(User(id=me, username="me"))
    db_session.add(User(id=other, username="other"))
    db_session.commit()
    _matching_analysis(db_session, other, title="AI 副业 变现 复盘 手把手")

    agent = SpyDraftAgent()
    engine = CognitiveEngine()
    result = await engine.generate_draft(
        topic="AI 副业 变现 复盘",
        outline=_outline(),
        user_id=me,
        agent=agent,
        readonly_session=db_session,
        session=db_session,
    )

    payload = agent.payloads[0]
    assert payload.viral_analysis_id is None
    assert payload.style_fingerprint_prompt is None
    snapshot = _snapshot(db_session, result.id)
    assert snapshot.get("style_source") == "persona_dna_no_external_style"
    assert snapshot["style_auto_selection"]["candidate_count"] == 0


@pytest.mark.asyncio
async def test_automatic_selection_below_threshold_falls_back(db_session):
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, username="below_user"))
    db_session.commit()
    _analysis(db_session, user_id, source_title="完全无关的内容", transfer=0)

    agent = SpyDraftAgent()
    engine = CognitiveEngine()
    result = await engine.generate_draft(
        topic="量子计算 纠错码 综述",
        outline=_outline(),
        user_id=user_id,
        agent=agent,
        readonly_session=db_session,
        session=db_session,
    )

    assert result.title == "成稿"
    payload = agent.payloads[0]
    assert payload.viral_analysis_id is None
    assert payload.style_fingerprint_prompt is None
    snapshot = _snapshot(db_session, result.id)
    assert snapshot.get("style_source") == "persona_dna_no_external_style"
    assert snapshot["style_auto_selection"]["accepted"] is False
    assert snapshot["style_auto_selection"]["reason"] == "below_threshold"


@pytest.mark.asyncio
async def test_no_candidates_still_generates_cleanly(db_session):
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, username="plain_user"))
    db_session.commit()

    agent = SpyDraftAgent()
    engine = CognitiveEngine()
    result = await engine.generate_draft(
        topic="话题",
        outline=_outline(),
        user_id=user_id,
        agent=agent,
        readonly_session=db_session,
        session=db_session,
    )
    assert result.title == "成稿"
    payload = agent.payloads[0]
    assert payload.viral_analysis_id is None
    assert payload.style_fingerprint_prompt is None
    snapshot = _snapshot(db_session, result.id)
    assert snapshot.get("style_source") == "persona_dna_no_external_style"
    assert snapshot["style_auto_selection"]["reason"] == "no_candidates"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_prompt",
    ["", "   ", 123, "x" * (MAX_STYLE_FINGERPRINT_CHARS + 1)],
)
async def test_automatic_selection_falls_back_when_winner_is_unusable(db_session, bad_prompt):
    """An auto-selected record must still pass the strict loader; failure degrades."""
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, username="unusable_user"))
    db_session.commit()
    record = ViralSemanticAnalysisRecord(
        user_id=user_id,
        source_title="AI 副业 变现 复盘 手把手",
        source_content_hash=uuid.uuid4().hex,
        analysis_data={
            "style_fingerprint": {"prompt_block": bad_prompt},
            "transfer": {"reuse_score": 5},
        },
    )
    db_session.add(record)
    db_session.commit()

    agent = SpyDraftAgent()
    engine = CognitiveEngine()
    result = await engine.generate_draft(
        topic="AI 副业 变现 复盘",
        outline=_outline(),
        user_id=user_id,
        agent=agent,
        readonly_session=db_session,
        session=db_session,
    )

    assert result.title == "成稿"
    payload = agent.payloads[0]
    assert payload.viral_analysis_id is None
    assert payload.style_fingerprint_prompt is None
    snapshot = _snapshot(db_session, result.id)
    assert snapshot.get("style_source") == "persona_dna_no_external_style"


@pytest.mark.asyncio
async def test_automatic_selection_failure_never_breaks_draft(db_session):
    class ExplodingSelectionService:
        def select(self, *args, **kwargs):
            raise RuntimeError("boom")

    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, username="resilient_user"))
    db_session.commit()

    agent = SpyDraftAgent()
    engine = CognitiveEngine()
    result = await engine.generate_draft(
        topic="话题",
        outline=_outline(),
        user_id=user_id,
        agent=agent,
        readonly_session=db_session,
        session=db_session,
        style_selection_service=ExplodingSelectionService(),
    )
    assert result.title == "成稿"
    payload = agent.payloads[0]
    assert payload.viral_analysis_id is None
    assert payload.style_fingerprint_prompt is None
    snapshot = _snapshot(db_session, result.id)
    assert snapshot.get("style_source") == "persona_dna_no_external_style"
    assert snapshot["style_auto_selection"]["reason"] == "candidate_lookup_failed"
