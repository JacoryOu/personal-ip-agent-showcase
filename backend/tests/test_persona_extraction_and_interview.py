"""
Comprehensive tests for:
1. POST /api/dna/v2/personas/extract-from-text (reverse extraction of persona + stories)
2. 4th mode 'interview' in chat lounge (soul interview mode)
3. POST /api/chat/lounge/sessions/{session_id}/crystallize-persona (crystallizing interview into IPPersona + stories)
"""

from __future__ import annotations

import json
import uuid
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.chat_lounge import _build_twin_system_prompt, _session_meta, _session_store
from app.core.config import settings
from app.core.db import get_session
from app.main import app
from app.models.persona import IPPersona
from app.models.story import EpisodicStory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(name="test_engine")
def engine_fixture():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import app.models  # noqa: F401
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture(name="session")
def session_fixture(test_engine) -> Generator[Session, None, None]:
    with Session(test_engine) as sess:
        yield sess


@pytest.fixture(name="client")
def client_fixture(session: Session, test_engine) -> Generator[TestClient, None, None]:
    _session_store.clear()
    _session_meta.clear()

    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    with patch("app.api.chat_lounge.engine", test_engine):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


USER_ID = "00000000-0000-0000-0000-000000000001"
USER_UUID = uuid.UUID(USER_ID)

MOCK_EXTRACTED_JSON = json.dumps({
    "name": "节气内养生活家",
    "target_audience": "25-45岁注重身心平衡与慢性调理的都市女性",
    "tone_style": "温润亲和、松弛但有力量、拒绝焦虑",
    "reader_salutation": "亲爱的调养伙伴",
    "origin_story": "因长期在快节奏大厂中身心俱疲，在一次严重的亚健康危机后接触中医节气调养，通过顺时而养重获生机，希望带更多女性找回内心的松弛感。",
    "extracted_stories": [
        {
            "title": "大厂加班夜的顿悟",
            "story_type": "failure_reflection",
            "story_content": "连续熬夜三个月后突然体温骤降、心慌失眠，那一刻我意识到身体在发出最严厉的抗议。",
            "occurred_at": "2023-11-15",
            "tags": ["职业转折", "至暗时刻", "健康觉醒"]
        },
        {
            "title": "第一剂四神汤的温暖",
            "story_type": "daily_life",
            "story_content": "在老中医指导下喝下第一周四神汤，脾胃的温热感第一次让我睡了一个整觉。",
            "occurred_at": "2023-12-01",
            "tags": ["食疗实践", "脾胃调理"]
        },
        {
            "title": "学员小芸的体质蜕变",
            "story_type": "client_case",
            "story_content": "小芸坚持两个节气温和饮食，困扰五年的面色发黄与经期腹痛明显好转。",
            "occurred_at": "2024-03-20",
            "tags": ["学员案例", "节气陪伴"]
        }
    ]
}, ensure_ascii=False)


def _make_mock_gateway(content: str = MOCK_EXTRACTED_JSON):
    gw = MagicMock()
    mock_client = MagicMock()
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]

    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=response)

    gw.get_client_for_role = MagicMock(return_value=mock_client)
    gw.get_model_for_role = MagicMock(return_value="gpt-4o")
    return gw


# ===========================================================================
# 1. Reverse-Extraction Tests (POST /api/dna/v2/personas/extract-from-text)
# ===========================================================================

class TestPersonaExtractFromText:
    def test_extract_without_auto_save(self, client: TestClient, session: Session):
        """Verify extraction parses raw text into structured persona & stories without saving."""
        gw = _make_mock_gateway()
        with patch("app.api.dna_v2.get_model_gateway", return_value=gw):
            resp = client.post("/api/dna/v2/personas/extract-from-text", json={
                "text": "我是一个从大厂裸辞的女生，以前天天熬夜喝冰美式...后来我靠中医节气食疗救了自己。",
                "user_id": USER_ID,
                "auto_save": False,
            })

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data["saved"] is False

        # Persona checks
        persona = data["persona"]
        assert persona["name"] == "节气内养生活家"
        assert "25-45岁" in persona["target_audience"]
        assert "温润亲和" in persona["tone_style"]
        assert persona["reader_salutation"] == "亲爱的调养伙伴"
        assert "顺时而养" in persona["origin_story"]

        # Stories checks
        stories = data["stories"]
        assert len(stories) == 3
        types = {s["story_type"] for s in stories}
        assert types == {"failure_reflection", "daily_life", "client_case"}

        # Verify NOT saved in DB
        db_personas = session.exec(select(IPPersona).where(IPPersona.user_id == USER_UUID)).all()
        assert len(db_personas) == 0
        db_stories = session.exec(select(EpisodicStory).where(EpisodicStory.user_id == USER_UUID)).all()
        assert len(db_stories) == 0

    def test_extract_with_auto_save(self, client: TestClient, session: Session):
        """Verify auto_save inserts persona & stories into DB and marks persona active."""
        # Pre-seed an existing active persona to verify it gets deactivated
        old_persona = IPPersona(
            user_id=USER_UUID,
            name="旧人设",
            is_active=True,
        )
        session.add(old_persona)
        session.commit()
        session.refresh(old_persona)
        assert old_persona.is_active is True

        gw = _make_mock_gateway()
        with patch("app.api.dna_v2.get_model_gateway", return_value=gw):
            resp = client.post("/api/dna/v2/personas/extract-from-text", json={
                "text": "分享一下我近三年的调养心得...",
                "user_id": USER_ID,
                "auto_save": True,
            })

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data["saved"] is True

        # Check DB personas
        session.refresh(old_persona)
        assert old_persona.is_active is False, "Old persona must be deactivated"

        active_personas = session.exec(
            select(IPPersona).where(IPPersona.user_id == USER_UUID, IPPersona.is_active == True)
        ).all()
        assert len(active_personas) == 1
        new_p = active_personas[0]
        assert new_p.name == "节气内养生活家"
        assert new_p.reader_salutation == "亲爱的调养伙伴"

        # Check DB stories
        saved_stories = session.exec(
            select(EpisodicStory).where(EpisodicStory.user_id == USER_UUID)
        ).all()
        assert len(saved_stories) == 3
        titles = [s.title for s in saved_stories]
        assert "大厂加班夜的顿悟" in titles
        assert "第一剂四神汤的温暖" in titles
        assert "学员小芸的体质蜕变" in titles

    def test_extract_with_markdown_fences_and_preamble(self, client: TestClient):
        """Resilience test: LLM returns ```json fences and thought preamble."""
        noisy_output = f"<think>这是思考过程</think>\n好的，为您提炼如下个人IP资产：\n```json\n{MOCK_EXTRACTED_JSON}\n```\n希望对您有帮助！"
        gw = _make_mock_gateway(noisy_output)

        with patch("app.api.dna_v2.get_model_gateway", return_value=gw):
            resp = client.post("/api/dna/v2/personas/extract-from-text", json={
                "text": "生活杂记随笔...",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["persona"]["name"] == "节气内养生活家"

    def test_extract_empty_text_rejected(self, client: TestClient):
        """Empty or whitespace-only text should return 422."""
        resp = client.post("/api/dna/v2/personas/extract-from-text", json={"text": ""})
        assert resp.status_code == 422

        resp2 = client.post("/api/dna/v2/personas/extract-from-text", json={"text": "   "})
        assert resp2.status_code == 422


# ===========================================================================
# 2. Soul Interview Mode Tests (Chat Lounge mode == 'interview')
# ===========================================================================

class TestSoulInterviewMode:
    def test_interview_prompt_generation(self):
        """Verify interview mode builds documentary interviewer persona prompt."""
        prompt = _build_twin_system_prompt("interview")
        assert "十三邀" in prompt or "许知远" in prompt
        assert "灵魂专访" in prompt
        assert "真实生活与转折节点" in prompt
        assert "痛恨与反感什么" in prompt
        assert "对读者的真正初心与交付心境" in prompt
        assert "随心表达" in prompt

    def test_interview_message_exchange(self, client: TestClient):
        """Verify chat message in interview mode generates interviewer responses and stores them."""
        interviewer_reply = "你刚才提到在大厂熬夜到崩溃，我想知道，当时最刺痛你、让你下决心彻底离开的那一刻，究竟发生了什么？"
        mock_gw = MagicMock()
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[
                MagicMock(choices=[MagicMock(message=MagicMock(content=interviewer_reply))]),
                MagicMock(choices=[MagicMock(message=MagicMock(content='{"capsules": []}'))]),
            ]
        )
        mock_gw.get_client_for_role = MagicMock(return_value=mock_client)
        mock_gw.get_model_for_role = MagicMock(return_value="test-model")

        with patch("app.api.chat_lounge.get_model_gateway", return_value=mock_gw):
            resp = client.post("/api/chat/lounge/message", json={
                "message": "我以前在互联网大厂做了六年运营，每天都靠咖啡续命，后来身体彻底垮了。",
                "mode": "interview",
                "session_id": "interview-sess-001",
                "user_id": USER_ID,
            })

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["reply"] == interviewer_reply
        assert data["session_id"] == "interview-sess-001"

        # Verify history endpoint contains both user message and assistant reply
        hist_resp = client.get("/api/chat/lounge/history?session_id=interview-sess-001")
        assert hist_resp.status_code == 200
        msgs = hist_resp.json()["messages"]
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert "互联网大厂" in msgs[0]["content"]
        assert msgs[1]["role"] == "assistant"
        assert "彻底离开" in msgs[1]["content"]


# ===========================================================================
# 3. Crystallize Persona Tests (POST .../crystallize-persona)
# ===========================================================================

class TestCrystallizePersona:
    def test_crystallize_persona_from_session(self, client: TestClient, session: Session):
        """Verify crystallizing interview history produces active IPPersona & EpisodicStories."""
        session_id = "interview-crystallize-101"

        # Step 1: Pre-populate session with interview dialogue
        dialogue = [
            ("user", "我叫林岚，以前是大厂高管，两年前因为身体透支差点进ICU。后来我花了一年跟老中医调养，彻底爱上了内养食疗。"),
            ("assistant", "那次差点进ICU的经历，是不是你整个人生最大的转弯？当时市面上那么多养生课，你为什么觉得它们不行？"),
            ("user", "市面上到处都在卖焦虑，动不动就吓唬人说你湿气重、肾虚。我特别反感这种割韭菜的套路。我想做的是让人松弛下来的陪伴式调理。"),
            ("assistant", "如果让你用一句话对你的读者说，你最希望她们因为你得到什么？"),
            ("user", "我希望每一个被生活逼得紧绷的姐妹，都能在早晨的一碗温热羹汤里，找回爱自己的从容节奏。同行者，不焦虑，慢慢变好。"),
        ]

        for role, text in dialogue:
            _session_store.setdefault(session_id, []).append({
                "role": role,
                "content": text,
                "ts": "2026-09-28T10:00:00Z"
            })
        _session_meta[session_id] = {
            "user_id": USER_ID,
            "mode": "interview",
            "created_at": "2026-09-28T10:00:00Z",
            "title": "大厂高管的健康转型"
        }

        # Step 2: Call crystallize endpoint
        # Identity now comes from the credential, not from the body's user_id.
        settings.API_KEYS = f"{USER_ID}=test-persona-key"
        headers = {"X-API-Key": "test-persona-key"}
        gw = _make_mock_gateway(MOCK_EXTRACTED_JSON)
        with patch("app.api.chat_lounge.get_model_gateway", return_value=gw):
            resp = client.post(f"/api/chat/lounge/sessions/{session_id}/crystallize-persona",
                               json={"user_id": "00000000-0000-0000-0000-0000000000ff"},
                               headers=headers)

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "persona" in data
        assert "stories" in data

        persona = data["persona"]
        assert persona["name"] == "节气内养生活家"
        assert persona["is_active"] is True

        stories = data["stories"]
        assert len(stories) == 3

        # Step 3: Check database persistence
        db_persona = session.exec(
            select(IPPersona).where(IPPersona.user_id == USER_UUID, IPPersona.is_active == True)
        ).first()
        assert db_persona is not None
        assert db_persona.name == "节气内养生活家"
        assert db_persona.reader_salutation == "亲爱的调养伙伴"

        db_stories = session.exec(
            select(EpisodicStory).where(EpisodicStory.user_id == USER_UUID)
        ).all()
        assert len(db_stories) == 3

    def test_crystallize_empty_session_not_found(self, client: TestClient):
        """Crystallizing a non-existent or empty session should return 404."""
        resp = client.post("/api/chat/lounge/sessions/nonexistent-session/crystallize-persona")
        assert resp.status_code == 404

    def test_crystallize_deactivates_previous_active_persona(self, client: TestClient, session: Session):
        """Verify newly crystallized persona deactivates previous active personas."""
        prev = IPPersona(
            user_id=USER_UUID,
            name="旧人设分身",
            is_active=True,
        )
        session.add(prev)
        session.commit()
        session.refresh(prev)

        session_id = "sess-deactivate-test"
        _session_store[session_id] = [
            {"role": "user", "content": "这是深度对谈内容", "ts": "2026-09-28T10:00:00Z"},
            {"role": "assistant", "content": "主持人深刻追问", "ts": "2026-09-28T10:01:00Z"}
        ]
        _session_meta[session_id] = {"user_id": USER_ID, "mode": "interview"}

        settings.API_KEYS = f"{USER_ID}=test-persona-key"
        headers = {"X-API-Key": "test-persona-key"}
        gw = _make_mock_gateway(MOCK_EXTRACTED_JSON)
        with patch("app.api.chat_lounge.get_model_gateway", return_value=gw):
            resp = client.post(f"/api/chat/lounge/sessions/{session_id}/crystallize-persona",
                               headers=headers)

        assert resp.status_code == 200
        session.refresh(prev)
        assert prev.is_active is False
