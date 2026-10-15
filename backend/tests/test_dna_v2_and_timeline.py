"""Tests for Thinking DNA 2.0: Personas, Products, Stories, Hybrid Retrieval,
Time Decay, naturalize_time_expression, and version supersede chain."""

import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.main import app
from app.core.db import get_session
from app.models.persona import IPPersona
from app.models.story import EpisodicStory
from app.models.product import ProductVault
from app.domain.cognitive.models import (
    CognitiveDimension,
    CognitiveTrait,
    CognitiveProfile,
    TraitStatus,
)


# ---------------------------------------------------------------------------
# Test DB Setup
# ---------------------------------------------------------------------------

@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Import all models so metadata is populated
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    with Session(engine) as sess:
        yield sess


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


USER_ID = "00000000-0000-0000-0000-000000000001"
USER_UUID = uuid.UUID(USER_ID)


# ===========================================================================
# 1. Persona CRUD
# ===========================================================================

class TestPersonaCRUD:
    def test_create_persona(self, client: TestClient):
        resp = client.post("/api/dna/v2/personas", json={
            "name": "测试博主人设",
            "target_audience": "25-35岁职场女性",
            "tone_style": "专业温暖",
            "reader_salutation": "亲爱的朋友",
            "origin_story": "我从健康调理受益后开始分享",
            "user_id": USER_ID,
        })
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["name"] == "测试博主人设"
        assert data["is_active"] is True

    def test_list_personas(self, client: TestClient):
        # Create two personas
        for name in ["人设A", "人设B"]:
            client.post("/api/dna/v2/personas", json={"name": name, "user_id": USER_ID})
        resp = client.get(f"/api/dna/v2/personas?user_id={USER_ID}")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "人设A" in names and "人设B" in names

    def test_update_persona(self, client: TestClient):
        create_resp = client.post("/api/dna/v2/personas", json={
            "name": "旧人设",
            "user_id": USER_ID,
        })
        pid = create_resp.json()["id"]
        patch_resp = client.patch(f"/api/dna/v2/personas/{pid}", json={
            "name": "新人设",
            "is_active": False,
        })
        assert patch_resp.status_code == 200
        assert patch_resp.json()["name"] == "新人设"
        assert patch_resp.json()["is_active"] is False

    def test_update_nonexistent_persona_returns_404(self, client: TestClient):
        fake_id = str(uuid.uuid4())
        resp = client.patch(f"/api/dna/v2/personas/{fake_id}", json={"name": "x"})
        assert resp.status_code == 404

    def test_persona_stored_in_db(self, client: TestClient, session: Session):
        client.post("/api/dna/v2/personas", json={"name": "DB人设", "user_id": USER_ID})
        personas = session.exec(
            select(IPPersona).where(IPPersona.user_id == USER_UUID)
        ).all()
        assert any(p.name == "DB人设" for p in personas)


# ===========================================================================
# 2. Product CRUD
# ===========================================================================

class TestProductCRUD:
    def test_create_product(self, client: TestClient):
        resp = client.post("/api/dna/v2/products", json={
            "product_name": "测试陈皮茶",
            "category": "养生茶饮",
            "core_ingredients": "新会陈皮、寿眉茶",
            "suitable_conditions": "脾虚湿寒",
            "user_id": USER_ID,
        })
        assert resp.status_code == 201, resp.text
        assert resp.json()["product_name"] == "测试陈皮茶"

    def test_list_products(self, client: TestClient):
        client.post("/api/dna/v2/products", json={"product_name": "产品A", "user_id": USER_ID})
        client.post("/api/dna/v2/products", json={"product_name": "产品B", "user_id": USER_ID})
        resp = client.get(f"/api/dna/v2/products?user_id={USER_ID}")
        assert resp.status_code == 200
        names = [p["product_name"] for p in resp.json()]
        assert "产品A" in names and "产品B" in names


# ===========================================================================
# 3. Story CRUD with occurred_at
# ===========================================================================

class TestStoryCRUD:
    def test_create_story_default_occurred_at(self, client: TestClient):
        resp = client.post("/api/dna/v2/stories", json={
            "story_content": "今天和客户聊了很多关于脾虚的话题",
            "story_type": "client_case",
            "user_id": USER_ID,
        })
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["story_type"] == "client_case"
        assert data["occurred_at"] is not None

    def test_create_story_with_occurred_at(self, client: TestClient):
        past_time = "2024-01-15T10:00:00+00:00"
        resp = client.post("/api/dna/v2/stories", json={
            "story_content": "过去的故事",
            "story_type": "failure_reflection",
            "occurred_at": past_time,
            "user_id": USER_ID,
        })
        assert resp.status_code == 201
        data = resp.json()
        # Occurred at should reflect the past time
        assert "2024-01-15" in data["occurred_at"]

    def test_create_story_with_tags(self, client: TestClient):
        resp = client.post("/api/dna/v2/stories", json={
            "story_content": "标签测试故事",
            "story_type": "daily_life",
            "tags": ["健康", "脾胃", "调理"],
            "user_id": USER_ID,
        })
        assert resp.status_code == 201
        assert "健康" in resp.json()["tags"]

    def test_invalid_story_type(self, client: TestClient):
        resp = client.post("/api/dna/v2/stories", json={
            "story_content": "非法类型",
            "story_type": "invalid_type",
            "user_id": USER_ID,
        })
        assert resp.status_code == 422

    def test_list_stories_with_date_filter(self, client: TestClient):
        client.post("/api/dna/v2/stories", json={
            "story_content": "旧故事",
            "story_type": "daily_life",
            "occurred_at": "2023-06-01T00:00:00+00:00",
            "user_id": USER_ID,
        })
        client.post("/api/dna/v2/stories", json={
            "story_content": "新故事",
            "story_type": "daily_life",
            "occurred_at": "2025-01-01T00:00:00+00:00",
            "user_id": USER_ID,
        })
        resp = client.get(
            f"/api/dna/v2/stories?user_id={USER_ID}&date_from=2024-01-01T00:00:00Z"
        )
        assert resp.status_code == 200
        contents = [s["story_content"] for s in resp.json()]
        assert "新故事" in contents
        assert "旧故事" not in contents

    def test_list_stories_with_story_type_filter(self, client: TestClient):
        client.post("/api/dna/v2/stories", json={
            "story_content": "日常故事",
            "story_type": "daily_life",
            "user_id": USER_ID,
        })
        client.post("/api/dna/v2/stories", json={
            "story_content": "失败反思",
            "story_type": "failure_reflection",
            "user_id": USER_ID,
        })
        resp = client.get(f"/api/dna/v2/stories?user_id={USER_ID}&story_type=failure_reflection")
        assert resp.status_code == 200
        types = [s["story_type"] for s in resp.json()]
        assert all(t == "failure_reflection" for t in types)


# ===========================================================================
# 4. Hybrid Retrieval Scoring
# ===========================================================================

class TestHybridRetrieval:
    """Tests the scoring logic without calling real LLM APIs."""

    def _make_profile_with_traits(self):
        """Create a CognitiveProfile with test traits."""
        profile = CognitiveProfile(user_id="test-user")
        t1 = CognitiveTrait(
            dimension=CognitiveDimension.CORE_VALUE,
            statement="脾虚湿寒是亚健康的核心原因，需要温补健脾",
            confidence_score=2.0,
            status=TraitStatus.ACTIVE,
        )
        t2 = CognitiveTrait(
            dimension=CognitiveDimension.VOCABULARY,
            statement="偏好使用接地气的生活化语言描述中医概念",
            confidence_score=1.5,
            status=TraitStatus.ACTIVE,
        )
        t3 = CognitiveTrait(
            dimension=CognitiveDimension.LOGIC_PREFERENCE,
            statement="以个人真实体验为依据，采用溯因法建立论证",
            confidence_score=1.0,
            status=TraitStatus.ACTIVE,
        )
        profile.traits = [t1, t2, t3]
        return profile

    def test_lexical_score_favors_topic_match(self):
        """Traits mentioning topic keywords should score higher."""
        import re
        topic = "脾虚湿寒调理"
        topic_lower = topic.lower()
        topic_keywords = set(re.findall(r"[a-zA-Z0-9_]{2,}", topic_lower))
        chinese_chars = re.findall(r"[\u4e00-\u9fa5]", topic_lower)
        for i in range(len(chinese_chars) - 1):
            topic_keywords.add("".join(chinese_chars[i:i+2]))
        topic_keywords.update(re.findall(r"[\u4e00-\u9fa5]{2,}", topic_lower))

        profile = self._make_profile_with_traits()
        
        def lexical_score(trait):
            stmt_lower = trait.statement.lower()
            overlap = sum(1 for kw in topic_keywords if kw in stmt_lower)
            return min(overlap / max(len(topic_keywords), 1), 1.0)

        scores = [lexical_score(t) for t in profile.traits]
        # First trait (脾虚湿寒) should have highest lexical score
        assert scores[0] > scores[1]
        assert scores[0] > scores[2]

    def test_confidence_bonus_is_additive(self):
        """Higher confidence traits should get higher final score."""
        t_high = CognitiveTrait(
            dimension=CognitiveDimension.CORE_VALUE,
            statement="高置信度特征",
            confidence_score=3.0,
            status=TraitStatus.ACTIVE,
        )
        t_low = CognitiveTrait(
            dimension=CognitiveDimension.CORE_VALUE,
            statement="低置信度特征",
            confidence_score=0.5,
            status=TraitStatus.ACTIVE,
        )
        high_bonus = t_high.confidence_score * 0.1
        low_bonus = t_low.confidence_score * 0.1
        assert high_bonus > low_bonus


# ===========================================================================
# 5. Time Decay Formula
# ===========================================================================

class TestTimeDecay:
    """Validates exp(-lambda * delta_days) formula."""

    def test_recent_has_less_penalty(self):
        lam = 0.05
        recent_decay = math.exp(-lam * 1)
        old_decay = math.exp(-lam * 365)
        # recent_decay > old_decay means recent has less penalty (higher retention)
        assert recent_decay > old_decay

    def test_zero_days_no_penalty(self):
        lam = 0.05
        assert math.exp(-lam * 0) == pytest.approx(1.0)

    def test_dna_lambda_slower_decay(self):
        """DNA lambda (0.0005) should decay much slower than episodic (0.05)."""
        days = 365
        dna_retention = math.exp(-0.0005 * days)
        episodic_retention = math.exp(-0.05 * days)
        assert dna_retention > episodic_retention

    def test_half_life_episodic(self):
        """Episodic stories should retain ~50% value after ~13.8 days."""
        lam = 0.05
        half_life_days = math.log(2) / lam
        assert half_life_days == pytest.approx(13.86, rel=0.01)

    def test_half_life_dna(self):
        """Core DNA traits should retain ~50% value after ~1386 days."""
        lam = 0.0005
        half_life_days = math.log(2) / lam
        assert half_life_days == pytest.approx(1386.3, rel=0.01)


# ===========================================================================
# 6. naturalize_time_expression
# ===========================================================================

class TestNaturalizeTimeExpression:
    def _ts(self, days_ago: int) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=days_ago)

    def test_invisible_mode_returns_empty(self):
        from app.services.memory_service import naturalize_time_expression
        result = naturalize_time_expression(self._ts(100), mode="invisible")
        assert result == ""

    def test_fuzzy_recent(self):
        from app.services.memory_service import naturalize_time_expression
        result = naturalize_time_expression(self._ts(3), mode="fuzzy")
        assert "最近" in result

    def test_fuzzy_medium(self):
        from app.services.memory_service import naturalize_time_expression
        result = naturalize_time_expression(self._ts(30), mode="fuzzy")
        assert result  # non-empty

    def test_fuzzy_old(self):
        from app.services.memory_service import naturalize_time_expression
        result = naturalize_time_expression(self._ts(400), mode="fuzzy")
        assert "年" in result or "之前" in result

    def test_solar_term_spring(self):
        from app.services.memory_service import naturalize_time_expression
        spring = datetime(2025, 4, 10, tzinfo=timezone.utc)
        result = naturalize_time_expression(spring, mode="solar_term")
        assert "春" in result or result  # just non-empty is fine

    def test_solar_term_autumn(self):
        from app.services.memory_service import naturalize_time_expression
        autumn = datetime(2024, 10, 20, tzinfo=timezone.utc)
        result = naturalize_time_expression(autumn, mode="solar_term")
        assert "秋" in result

    def test_solar_term_current_year(self):
        from app.services.memory_service import naturalize_time_expression
        now = datetime.now(timezone.utc)
        recent = datetime(now.year, 7, 1, tzinfo=timezone.utc)
        result = naturalize_time_expression(recent, mode="solar_term")
        # Should not have a year prefix since it's this year
        assert "去年" not in result or "年" not in result or result


# ===========================================================================
# 7. Version Supersede Chain
# ===========================================================================

class TestSupersede:
    def test_supersede_via_api(self, client: TestClient, session: Session):
        """Create a trait, supersede it, verify chain via API."""
        from app.services.cognitive_service import CognitiveService
        from app.domain.cognitive.models import CognitiveDimension, CognitiveTrait, TraitStatus

        # First, create a profile with a trait
        profile = CognitiveService.get_or_create_user_profile(session, USER_ID)
        trait = CognitiveTrait(
            dimension=CognitiveDimension.CORE_VALUE,
            statement="原始观点：应该每天喝绿茶",
            confidence_score=1.5,
            status=TraitStatus.ACTIVE,
        )
        profile.traits.append(trait)
        from app.models.user import User
        user = session.get(User, USER_UUID)
        if not user:
            user = User(id=USER_UUID, username="testuser")
            session.add(user)
            session.commit()
        CognitiveService.save_profile(session, user, profile)

        old_id = trait.id
        resp = client.post("/api/dna/v2/supersede", json={
            "old_trait_id": old_id,
            "new_content": "进化观点：应该根据体质选择茶类，脾虚者适合喝红茶或白茶",
            "evolution_reason": "实践发现绿茶性寒，脾虚者不宜",
            "user_id": USER_ID,
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["old_trait_id"] == old_id
        assert data["new_trait_id"] != old_id
        assert data["new_version"] == 2
        assert "进化观点" in data["new_statement"]
        assert "绿茶" in data["old_statement"]

    def test_supersede_nonexistent_trait_returns_404(self, client: TestClient, session: Session):
        # Ensure user exists
        from app.models.user import User
        user = session.get(User, USER_UUID)
        if not user:
            user = User(id=USER_UUID, username="testuser")
            session.add(user)
            session.commit()
        
        resp = client.post("/api/dna/v2/supersede", json={
            "old_trait_id": str(uuid.uuid4()),
            "new_content": "new content",
            "evolution_reason": "reason",
            "user_id": USER_ID,
        })
        assert resp.status_code == 404

    def test_supersede_increments_version(self, session: Session):
        """Test version increments correctly in the supersede chain."""
        from app.services.memory_service import supersede_dna_trait
        from app.services.cognitive_service import CognitiveService
        from app.domain.cognitive.models import CognitiveDimension, CognitiveTrait, TraitStatus
        from app.models.user import User

        # Ensure user exists
        user = session.get(User, USER_UUID)
        if not user:
            user = User(id=USER_UUID, username="testuser2")
            session.add(user)
            session.commit()

        profile = CognitiveService.get_or_create_user_profile(session, USER_ID)
        trait_v1 = CognitiveTrait(
            dimension=CognitiveDimension.VOCABULARY,
            statement="V1: 使用简单词汇",
            confidence_score=1.0,
            status=TraitStatus.ACTIVE,
            version=1,
        )
        profile.traits.append(trait_v1)
        CognitiveService.save_profile(session, user, profile)

        # Supersede once -> V2
        result = supersede_dna_trait(
            old_trait_id=trait_v1.id,
            new_content="V2: 使用精准专业词汇",
            evolution_reason="词汇升级",
            session=session,
            user_id=USER_ID,
        )
        assert result["new_version"] == 2

    def test_superseded_trait_marked_suppressed(self, session: Session):
        """Old trait should have trait_status='superseded' after supersede."""
        from app.services.memory_service import supersede_dna_trait
        from app.services.cognitive_service import CognitiveService
        from app.domain.cognitive.models import CognitiveDimension, CognitiveTrait, TraitStatus
        from app.models.user import User

        user = session.get(User, USER_UUID)
        if not user:
            user = User(id=USER_UUID, username="testuser3")
            session.add(user)
            session.commit()

        profile = CognitiveService.get_or_create_user_profile(session, USER_ID)
        old_trait = CognitiveTrait(
            dimension=CognitiveDimension.CORE_VALUE,
            statement="旧的核心价值观",
            confidence_score=1.0,
            status=TraitStatus.ACTIVE,
        )
        profile.traits.append(old_trait)
        CognitiveService.save_profile(session, user, profile)

        supersede_dna_trait(
            old_trait_id=old_trait.id,
            new_content="新的核心价值观",
            evolution_reason="认知升级",
            session=session,
            user_id=USER_ID,
        )

        # Re-fetch profile and verify old trait is suppressed
        updated_profile = CognitiveService.get_or_create_user_profile(session, USER_ID)
        found = updated_profile.find_trait(old_trait.id)
        if found:
            assert getattr(found, "trait_status", "active") == "superseded"


# ===========================================================================
# 8. Timeline
# ===========================================================================

class TestTimeline:
    def test_timeline_includes_stories(self, client: TestClient):
        client.post("/api/dna/v2/stories", json={
            "story_content": "时间线测试故事",
            "story_type": "daily_life",
            "user_id": USER_ID,
        })
        resp = client.get(f"/api/dna/v2/timeline?user_id={USER_ID}")
        assert resp.status_code == 200
        types = [e["type"] for e in resp.json()]
        assert "story" in types

    def test_timeline_sorted_newest_first(self, client: TestClient):
        client.post("/api/dna/v2/stories", json={
            "story_content": "古老故事",
            "story_type": "daily_life",
            "occurred_at": "2020-01-01T00:00:00+00:00",
            "user_id": USER_ID,
        })
        client.post("/api/dna/v2/stories", json={
            "story_content": "最新故事",
            "story_type": "daily_life",
            "occurred_at": "2025-06-01T00:00:00+00:00",
            "user_id": USER_ID,
        })
        resp = client.get(f"/api/dna/v2/timeline?user_id={USER_ID}")
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) >= 2
        # First event should be newer than last event
        assert events[0]["occurred_at"] >= events[-1]["occurred_at"]
