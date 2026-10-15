# -*- coding: utf-8 -*-
"""Tests for the automatic viral style-fingerprint selection service.

Covers the ranking contract (weights, threshold, determinism) and, critically,
the ownership boundary: only the authenticated user's own analysed records may
ever become candidates. The service ranks only -- it never returns prompt text.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.models.draft import Draft
from app.models.user import User
from app.models.viral_analysis import ViralSemanticAnalysisRecord
from app.services.style_selection_service import (
    STYLE_SOURCE_AUTO,
    STYLE_SOURCE_NONE,
    StyleSelectionService,
    StyleSelectionWeights,
    overlap_score,
    tokenize,
)


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


def _make_user(db_session, username="selector_user"):
    user = User(id=uuid.uuid4(), username=username)
    db_session.add(user)
    db_session.commit()
    return user


def _analysis(db_session, user_id, source_title, *, prompt_block="p", transfer=None, created_at=None):
    data = {"style_fingerprint": {"prompt_block": prompt_block}}
    if transfer is not None:
        data["transfer"] = {"reuse_score": transfer}
    record = ViralSemanticAnalysisRecord(
        user_id=user_id,
        source_title=source_title,
        source_content_hash=uuid.uuid4().hex,
        analysis_data=data,
    )
    if created_at is not None:
        record.created_at = created_at
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


def test_tokenize_handles_cjk_bigrams_and_ascii_words():
    tokens = tokenize("AI Agent")
    assert "ai" in tokens
    assert "agent" in tokens
    assert "写" + "作" in tokenize("写作风格")


def test_overlap_score_is_bounded():
    assert overlap_score(set(), {"a"}) == 0.0
    assert overlap_score({"a"}, set()) == 0.0
    assert overlap_score({"a"}, {"a"}) == 1.0
    assert overlap_score({"a", "b"}, {"b", "c"}) == 0.5


def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        StyleSelectionWeights(topic_match=0.9, ip_match=0.9).validate()


def test_service_rejects_invalid_threshold():
    with pytest.raises(ValueError):
        StyleSelectionService(min_match_score=1.5)


def test_service_rejects_weights_that_do_not_sum_to_one():
    with pytest.raises(ValueError):
        StyleSelectionService(weights=StyleSelectionWeights(topic_match=0.5, ip_match=0.2))


# ---------------------------------------------------------------------------
# Candidate scoping (security-critical)
# ---------------------------------------------------------------------------


def test_other_users_records_never_become_candidates(db_session):
    me = _make_user(db_session, "me")
    other = _make_user(db_session, "other")
    _analysis(db_session, other.id, "完全 匹配 的 标题", transfer=5)

    result = StyleSelectionService().select(db_session, me.id, topic="完全 匹配 的 标题")

    assert result.candidate_count == 0
    assert result.accepted is False
    assert result.reason == "no_candidates"
    assert result.analysis_id is None


def test_candidate_scope_is_limited_to_current_user(db_session):
    me = _make_user(db_session, "me")
    other = _make_user(db_session, "other")
    mine = _analysis(db_session, me.id, "写作 方法论 拆解", transfer=5)
    _analysis(db_session, other.id, "写作 方法论 拆解", transfer=5)

    result = StyleSelectionService().select(db_session, me.id, topic="写作 方法论 拆解")

    assert result.candidate_count == 1
    assert result.analysis_id == mine.id


def test_missing_user_id_is_rejected_cleanly(db_session):
    result = StyleSelectionService().select(db_session, None, topic="任意话题")
    assert result.accepted is False
    assert result.reason == "no_authenticated_user"


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def test_highest_scoring_candidate_wins(db_session):
    user = _make_user(db_session)
    _analysis(db_session, user.id, "副业 变现 复盘", transfer=1)
    best = _analysis(db_session, user.id, "AI 副业 变现 复盘 手把手", transfer=5)

    result = StyleSelectionService().select(db_session, user.id, topic="AI 副业 变现 复盘")

    assert result.accepted is True
    assert result.reason == "selected"
    assert result.analysis_id == best.id
    assert result.style_source == STYLE_SOURCE_AUTO
    assert result.score >= result.threshold


def test_low_scoring_candidates_fall_below_threshold(db_session):
    user = _make_user(db_session)
    _analysis(db_session, user.id, "完全无关的内容", transfer=0)

    result = StyleSelectionService().select(db_session, user.id, topic="量子计算 纠错码")

    assert result.accepted is False
    assert result.reason == "below_threshold"
    assert result.candidate_count == 1
    assert result.style_source == STYLE_SOURCE_NONE


def test_no_candidates_returns_no_candidates(db_session):
    user = _make_user(db_session)
    result = StyleSelectionService().select(db_session, user.id, topic="任何话题")
    assert result.accepted is False
    assert result.reason == "no_candidates"
    assert result.candidate_count == 0


def test_threshold_is_injectable_and_enforced(db_session):
    user = _make_user(db_session)
    _analysis(db_session, user.id, "AI 副业 变现 复盘 手把手", transfer=5)

    strict = StyleSelectionService(min_match_score=0.99)
    strict_result = strict.select(db_session, user.id, topic="AI 副业 变现 复盘")
    assert strict_result.accepted is False
    assert strict_result.reason == "below_threshold"

    loose = StyleSelectionService(min_match_score=0.01)
    loose_result = loose.select(db_session, user.id, topic="AI 副业 变现 复盘")
    assert loose_result.accepted is True


def test_weights_are_injectable_and_change_the_score(db_session):
    user = _make_user(db_session)
    _analysis(db_session, user.id, "完全无关", transfer=5)

    transfer_only = StyleSelectionService(
        weights=StyleSelectionWeights(
            topic_match=0.0, ip_match=0.0, recent_work_affinity=0.0, transferability=1.0
        )
    )
    result = transfer_only.select(db_session, user.id, topic="AI 副业 变现")
    assert result.accepted is True


def test_recent_work_affinity_uses_only_own_drafts(db_session):
    user = _make_user(db_session)
    recent = _analysis(db_session, user.id, "复盘 迭代 方法论", transfer=5)

    db_session.add(
        Draft(
            user_id=user.id,
            topic="复盘 迭代 方法论",
            original_ai_draft="# 正文\n复盘 迭代 方法论 的经验总结。",
        )
    )
    db_session.commit()

    service = StyleSelectionService(
        weights=StyleSelectionWeights(
            topic_match=0.0, ip_match=0.0, recent_work_affinity=1.0, transferability=0.0
        )
    )
    result = service.select(db_session, user.id, topic="毫不相干的话题")
    assert result.accepted is True
    assert result.analysis_id == recent.id


def test_scores_are_explainable_per_candidate(db_session):
    user = _make_user(db_session)
    record = _analysis(db_session, user.id, "AI 副业 变现 复盘", transfer=4)

    result = StyleSelectionService().select(db_session, user.id, topic="AI 副业 变现 复盘")

    assert result.considered
    entry = next(c for c in result.considered if c["analysis_id"] == str(record.id))
    for key in ("score", "topic_match", "ip_match", "recent_work_affinity", "transferability"):
        assert key in entry
        assert 0.0 <= entry[key] <= 1.0


def test_ties_are_broken_deterministically(db_session):
    user = _make_user(db_session)
    now = datetime.now(timezone.utc)
    older = _analysis(
        db_session, user.id, "同样 匹配 的 标题", transfer=5, created_at=now - timedelta(days=3)
    )
    newer = _analysis(
        db_session, user.id, "同样 匹配 的 标题", transfer=5, created_at=now - timedelta(days=1)
    )

    first = StyleSelectionService().select(db_session, user.id, topic="同样 匹配 的 标题")
    second = StyleSelectionService().select(db_session, user.id, topic="同样 匹配 的 标题")

    assert first.analysis_id == second.analysis_id
    assert first.analysis_id == newer.id
    assert first.analysis_id != older.id


def test_candidate_pool_is_capped_by_max_candidates(db_session):
    user = _make_user(db_session)
    for i in range(5):
        _analysis(db_session, user.id, f"文章 副业 变现 {i}", transfer=3)

    result = StyleSelectionService(max_candidates=2).select(
        db_session, user.id, topic="副业 变现"
    )
    assert result.candidate_count == 2


def test_service_never_returns_prompt_text(db_session):
    user = _make_user(db_session)
    _analysis(
        db_session, user.id, "AI 副业 变现 复盘", prompt_block="SECRET_STYLE", transfer=5
    )

    result = StyleSelectionService().select(db_session, user.id, topic="AI 副业 变现 复盘")

    assert result.analysis_id is not None
    assert "SECRET_STYLE" not in str(result.__dict__)
    assert "SECRET_STYLE" not in str(result.considered)
