# -*- coding: utf-8 -*-
"""Contract tests for the viral article semantic breakdown layer.

Covers:
- Schema validation / lenient normalization.
- Deterministic code-owned fields (rhythm numerics, prompt_block).
- Persistence round-trip through the SQLModel record and the API.
- Predictable degradation (never crash) when the model layer fails.
- Fresh-database schema creation.
"""

import uuid
from pathlib import Path
import sys

import pytest
from sqlmodel import SQLModel, Session, select

backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.db import engine, init_db
from app.models.viral_analysis import ViralSemanticAnalysisRecord
from app.schemas.viral_schemas import (
    FormulaAnalysis,
    RhythmProfile,
    StyleFingerprint,
    ViralSemanticAnalysis,
)
from app.services import viral_semantic_service as svc
from app.services.viral_semantic_service import ViralSemanticService

SAMPLE_TITLE = "为什么你的副业总在第三个月死掉"

SAMPLE_CONTENT = (
    "我做过七个副业，只有两个活过了三个月。\n"
    "不是因为不努力，而是因为你在用打工的逻辑做创业。\n"
    "第一份副业，我在第三个月的时候还在每天更新。\n"
    "没有人在看，没有人买，我也没有停下来。\n"
    "直到我把目标从「做起来」换成了「能收到第一笔钱」，一切就变了。\n"
    "这不是一个新方法论，这是一个选择问题。\n"
    "你到底在优化内容，还是在优化成交？\n"
    "如果你只做前者，你会在第三个月安静地放弃。"
)


class FakeGateway:
    """Minimal ModelGateway stand-in that returns a canned payload."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def generate_structured(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.payload, Exception):
            raise self.payload
        # Round-trip through the schema, mirroring the real gateway's behaviour.
        return ViralSemanticAnalysis.model_validate(self.payload)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()


@pytest.fixture
def session():
    with Session(engine) as db:
        yield db


# ==============================================================================
# Schema validation
# ==============================================================================

def test_viral_schema_validates_full_payload():
    payload = {
        "one_line_verdict": "It reframes failure as a choice problem.",
        "hook": {
            "pattern_name": "failure statistic opener",
            "opening_excerpt": "我做过七个副业，只有两个活过了三个月。",
            "attention_mechanism": "credible loss before advice",
            "hook_strength": 4,
        },
        "structure": {
            "beats": [
                {"order": 1, "stage": "setup", "summary": "seven attempts", "tension_level": 2, "is_payoff": False},
                {"order": 2, "stage": "payoff", "summary": "first payment reframed the goal", "tension_level": 5, "is_payoff": True},
            ],
            "tension_shape": "rises after the third failure",
            "payoff_position": "final 30%",
            "climax_excerpt": "你到底在优化内容，还是在优化成交？",
        },
        "formulas": {
            "title_formulas": [
                {"name": "failure-loop", "template": "为什么你的{X}总在{时间}死掉", "example": SAMPLE_TITLE, "why_it_works": "names the reader's loop"}
            ],
            "hook_formulas": [],
        },
        "rhythm": {"pacing": "fast and punchy", "dominant_emotions": ["焦虑", "释然"], "emotion_arc": "deflation then resolve", "device_usage": ["second person", "question"]},
        "value_promise": {"promise": "diagnose why side hustles die", "payoff": "a goal-selection switch", "promise_kept": True, "target_reader": "有副业焦虑的打工人", "shareability_hook": "names a private failure"},
        "transfer": {"reusable_patterns": ["open with your own loss count"], "one_off_specifics": ["the specific seven projects"], "reuse_score": 4, "adaptation_notes": "swap the domain, keep the loop"},
        "style_fingerprint": {"voice": "practitioner", "stance": "peer", "register": "colloquial", "sentence_style": "short declaratives", "signature_devices": ["rhetorical question"]},
    }
    analysis = ViralSemanticAnalysis.model_validate(payload)
    assert analysis.hook.hook_strength == 4
    assert len(analysis.structure.beats) == 2
    assert analysis.structure.beats[1].is_payoff is True
    assert analysis.formulas.title_formulas[0].template.startswith("为什么")
    assert analysis.value_promise.promise_kept is True
    assert analysis.transfer.reuse_score == 4


def test_viral_schema_normalizes_alternate_keys_and_missing_fields():
    """Alternate key names and bare strings must normalize, not raise."""
    payload = {
        "summary": "generic verdict",
        "opening": {"name": "pain-first", "excerpt": "line", "score": "5"},
        "beats": ["plain string beat", {"description": "another beat"}],
        "titles": ["为什么{X}会失败"],
        "rhythm": {"emotions": "焦虑", "devices": ["对比"]},
        "promise": {"audience": "打工人", "kept": "yes"},
        "transfer": {"reusable": "count your losses first", "score": 3},
        "style": {"persona": "peer", "devices": ["提问"]},
    }
    analysis = ViralSemanticAnalysis.model_validate(payload)
    assert analysis.hook.pattern_name == "pain-first"
    assert analysis.hook.hook_strength == 5  # string coerced to int
    assert len(analysis.structure.beats) == 2
    assert analysis.structure.beats[0].order == 1  # auto-numbered
    assert analysis.structure.beats[1].summary == "another beat"
    assert analysis.formulas.title_formulas[0].template == "为什么{X}会失败"
    assert analysis.rhythm.dominant_emotions == ["焦虑"]
    assert analysis.rhythm.device_usage == ["对比"]
    assert analysis.value_promise.promise_kept is True
    assert analysis.transfer.reusable_patterns == ["count your losses first"]
    assert analysis.style_fingerprint.voice == "peer"


def test_viral_schema_survives_garbage_payload():
    """A non-dict payload degrades to an empty-but-valid analysis."""
    analysis = ViralSemanticAnalysis.model_validate("not a dict")
    assert analysis.hook.hook_strength == 0
    assert analysis.structure.beats == []
    assert analysis.rhythm.mean_sentence_length == 0.0


def test_deterministic_overrides_own_rhythm_and_prompt_block():
    payload = {
        "rhythm": {"mean_sentence_length": 999.0, "sentence_length_std": 999.0, "short_sentence_ratio": 1.0},
        "style_fingerprint": {"voice": "practitioner", "signature_devices": ["rhetorical question"]},
        "formulas": {"title_formulas": [{"template": "为什么你的{X}会失败"}]},
    }
    analysis = ViralSemanticAnalysis.model_validate(payload)
    stats = svc.compute_rhythm_stats(SAMPLE_CONTENT)
    svc.apply_deterministic_overrides(analysis, SAMPLE_CONTENT, SAMPLE_TITLE)

    # Code recomputes numerics, ignoring whatever the model claimed.
    assert analysis.rhythm.mean_sentence_length == stats["mean_sentence_length"]
    assert analysis.rhythm.sentence_length_std == stats["sentence_length_std"]
    assert analysis.rhythm.short_sentence_ratio == stats["short_sentence_ratio"]

    # prompt_block is generated in code and contains the model's descriptors.
    block = analysis.style_fingerprint.prompt_block
    assert block.startswith("[STYLE FINGERPRINT]")
    assert "practitioner" in block
    assert "为什么你的{X}会失败" in block
    assert block.endswith("[END STYLE FINGERPRINT]")


def test_rhythm_stats_handle_chinese_punctuation():
    stats = svc.compute_rhythm_stats("短句。非常短。稍微长一点的句子用来测试标准差的计算！")
    assert stats["mean_sentence_length"] > 0
    assert 0.0 <= stats["short_sentence_ratio"] <= 1.0


def test_rhythm_stats_empty_text_is_zero():
    assert svc.compute_rhythm_stats("") == {"mean_sentence_length": 0.0, "sentence_length_std": 0.0, "short_sentence_ratio": 0.0}


# ==============================================================================
# Persistence round-trip
# ==============================================================================

@pytest.mark.asyncio
async def test_persistence_round_trip_with_fake_gateway(session):
    payload = {
        "one_line_verdict": "Reframes failure as a choice problem.",
        "hook": {"pattern_name": "failure statistic opener", "opening_excerpt": "我做过七个副业", "attention_mechanism": "credible loss", "hook_strength": 4},
        "structure": {"beats": [{"order": 1, "stage": "setup", "summary": "seven attempts", "tension_level": 2}], "payoff_position": "final 30%"},
        "rhythm": {"pacing": "fast and punchy", "dominant_emotions": ["焦虑"]},
        "value_promise": {"promise": "diagnose", "payoff": "switch", "promise_kept": True},
        "style_fingerprint": {"voice": "practitioner"},
    }
    gateway = FakeGateway(payload)
    service = ViralSemanticService(gateway=gateway)

    response = await service.analyze_article(
        title=SAMPLE_TITLE,
        content=SAMPLE_CONTENT,
        session=session,
        source_platform="wechat",
        source_url="https://example.com/a",
    )

    assert response.status == "completed"
    assert response.extraction_mode == "llm"
    assert response.analysis["hook"]["pattern_name"] == "failure statistic opener"
    assert response.analysis["style_fingerprint"]["prompt_block"].startswith("[STYLE FINGERPRINT]")
    assert response.model_name  # resolved
    assert gateway.calls, "gateway should have been called"

    # Round-trip: the record can be reloaded and re-serialized identically.
    record = session.get(ViralSemanticAnalysisRecord, response.id)
    assert record is not None
    assert record.source_title == SAMPLE_TITLE
    assert record.source_content_hash == svc.content_hash(SAMPLE_CONTENT)
    reloaded = service.get_analysis(response.id, session)
    assert reloaded is not None
    assert reloaded.analysis == response.analysis
    # The JSON payload is a plain dict, not a Pydantic object.
    assert isinstance(reloaded.analysis, dict)


@pytest.mark.asyncio
async def test_get_analysis_returns_none_for_unknown_id(session):
    assert ViralSemanticService(gateway=FakeGateway({})).get_analysis(uuid.uuid4(), session) is None


@pytest.mark.asyncio
async def test_provenance_validation_rejects_unknown_user(session):
    service = ViralSemanticService(gateway=FakeGateway({}))
    with pytest.raises(ValueError, match="not found"):
        await service.analyze_article(
            title=SAMPLE_TITLE,
            content=SAMPLE_CONTENT,
            session=session,
            user_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_empty_content_rejected(session):
    service = ViralSemanticService(gateway=FakeGateway({}))
    with pytest.raises(ValueError):
        await service.analyze_article(title="t", content="   ", session=session)


# ==============================================================================
# Malformed / failing LLM output -> predictable degradation
# ==============================================================================

@pytest.mark.asyncio
async def test_llm_raises_value_error_degrades_to_fallback(session):
    gateway = FakeGateway(ValueError("Failed to parse the response from the model."))
    service = ViralSemanticService(gateway=gateway)
    response = await service.analyze_article(
        title=SAMPLE_TITLE,
        content=SAMPLE_CONTENT,
        session=session,
    )
    assert response.extraction_mode == "fallback"
    assert response.warnings, "fallback must carry explicit warnings"
    # Real mechanical stats still present.
    assert response.analysis["rhythm"]["mean_sentence_length"] > 0
    # Hook excerpt falls back to the first sentence of the article.
    assert response.analysis["hook"]["opening_excerpt"]
    # Judgement fields are honestly empty.
    assert response.analysis["transfer"]["reusable_patterns"] == []
    assert response.analysis["style_fingerprint"]["voice"] == ""


@pytest.mark.asyncio
async def test_llm_returns_unexpected_shape_degrades_to_fallback(session):
    """Even a 'successful' gateway call with unusable content must not crash."""
    class ShapeBreakerGateway:
        async def generate_structured(self, **kwargs):
            # A payload that is a dict but whose nested values are junk.
            return ViralSemanticAnalysis.model_validate({"hook": 12345, "beats": object()})

    service = ViralSemanticService(gateway=ShapeBreakerGateway())
    response = await service.analyze_article(title=SAMPLE_TITLE, content=SAMPLE_CONTENT, session=session)
    # Lenient schema normalizes junk to empty objects without raising.
    assert response.extraction_mode == "llm"
    assert response.analysis["hook"]["hook_strength"] == 0


@pytest.mark.asyncio
async def test_fallback_is_persisted_and_reloadable(session):
    gateway = FakeGateway(RuntimeError("network down"))
    service = ViralSemanticService(gateway=gateway)
    response = await service.analyze_article(title=SAMPLE_TITLE, content=SAMPLE_CONTENT, session=session)
    assert response.extraction_mode == "fallback"

    record = session.get(ViralSemanticAnalysisRecord, response.id)
    assert record is not None
    assert record.extraction_mode == "fallback"
    assert record.analysis_data  # non-empty JSON persisted
    assert record.warnings  # warnings persisted alongside
    reloaded = service.get_analysis(response.id, session)
    assert reloaded.extraction_mode == "fallback"


# ==============================================================================
# Schema / fresh-DB creation
# ==============================================================================

def test_viral_table_is_registered_in_metadata():
    assert "viral_semantic_analyses" in SQLModel.metadata.tables


def test_fresh_database_schema_creation(tmp_path):
    """A brand-new SQLite file gets the viral table via init_db-style create_all."""
    from sqlalchemy import create_engine as sa_create_engine
    fresh_path = tmp_path / "fresh_viral.db"
    fresh_engine = sa_create_engine(f"sqlite:///{fresh_path}")
    SQLModel.metadata.create_all(fresh_engine)
    from sqlalchemy import inspect as sa_inspect
    tables = sa_inspect(fresh_engine).get_table_names()
    assert "viral_semantic_analyses" in tables
    fresh_engine.dispose()


def test_viral_analysis_record_defaults():
    record = ViralSemanticAnalysisRecord(source_title="t", source_content_hash="h")
    assert record.status == "completed"
    assert record.extraction_mode == "llm"
    assert record.user_id is None and record.material_id is None
    assert record.analysis_data == {}
    assert record.warnings == []
