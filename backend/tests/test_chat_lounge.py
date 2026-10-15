"""
Tests for the Cognitive Chat Lounge API.
Tests:
- All three modes (free_talk, coach_inquiry, timeline_review)
- Natural date parsing: 今天, 去年冬天, 上个月15号, 2023年冬, 三年前, etc.
- Capsule extraction returns expected types
- Session management (history, sessions)
- Edge cases: empty message, invalid session_id
"""

from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---- Import the natural date parser directly for unit testing ----
from app.api.chat_lounge import _parse_natural_date, _session_store, _session_meta


# ===========================================================================
# Unit tests for _parse_natural_date
# ===========================================================================

class TestParsNaturalDate:
    """Unit-test the natural date parser without any LLM calls."""

    REF = datetime(2026, 9, 28, tzinfo=timezone.utc)

    def test_today(self):
        result = _parse_natural_date("我今天遇到一件事", self.REF)
        assert result == "2026-09-28"

    def test_today_日(self):
        result = _parse_natural_date("今日完成了一次复盘", self.REF)
        assert result == "2026-09-28"

    def test_yesterday(self):
        result = _parse_natural_date("昨天下午发生了", self.REF)
        assert result == "2026-09-27"

    def test_last_week(self):
        result = _parse_natural_date("上周我去参加了一个会议", self.REF)
        expected = (self.REF - timedelta(weeks=1)).strftime("%Y-%m-%d")
        assert result == expected

    def test_last_month(self):
        result = _parse_natural_date("上个月和朋友聊了很多", self.REF)
        assert result == "2026-08-01"

    def test_last_month_day(self):
        result = _parse_natural_date("上个月15号去医院", self.REF)
        assert result == "2026-08-15"

    def test_specific_year_winter(self):
        result = _parse_natural_date("2023年冬天我开始学习中医", self.REF)
        assert result == "2023-12-01"

    def test_specific_year_winter_short(self):
        result = _parse_natural_date("2023年冬那会儿", self.REF)
        assert result == "2023-12-01"

    def test_specific_year_spring(self):
        result = _parse_natural_date("2022年春天开始创业", self.REF)
        assert result == "2022-03-01"

    def test_specific_year_summer(self):
        result = _parse_natural_date("2021年夏天遇到了瓶颈", self.REF)
        assert result == "2021-06-01"

    def test_specific_year_autumn(self):
        result = _parse_natural_date("2020年秋季入行", self.REF)
        assert result == "2020-09-01"

    def test_bare_year(self):
        result = _parse_natural_date("2019年我刚毕业", self.REF)
        assert result == "2019-01-01"

    def test_year_month(self):
        result = _parse_natural_date("2023年11月开始写作", self.REF)
        assert result == "2023-11-01"

    def test_year_month_day(self):
        result = _parse_natural_date("2024年3月15日签的合同", self.REF)
        assert result == "2024-03-15"

    def test_last_year(self):
        result = _parse_natural_date("去年我换了工作", self.REF)
        assert result == "2025-01-01"

    def test_last_year_winter(self):
        """去年冬天 should parse to Dec 1 of last year."""
        result = _parse_natural_date("去年冬天我开始反思自己", self.REF)
        assert result == "2025-12-01"

    def test_year_before_last(self):
        result = _parse_natural_date("前年那段时间我很迷茫", self.REF)
        assert result == "2024-01-01"

    def test_n_years_ago(self):
        result = _parse_natural_date("三年前我开始做自媒体", self.REF)
        assert result == "2023-01-01"

    def test_n_months_ago(self):
        result = _parse_natural_date("两个月前我开始运动", self.REF)
        # 2 months ago from 2026-09 = 2026-07
        assert result == "2026-07-01"

    def test_no_date(self):
        result = _parse_natural_date("我觉得这件事很有意义", self.REF)
        assert result is None

    def test_last_last_week(self):
        result = _parse_natural_date("上上周的事情", self.REF)
        expected = (self.REF - timedelta(weeks=2)).strftime("%Y-%m-%d")
        assert result == expected


# ===========================================================================
# Integration-style tests using TestClient with mocked LLM
# ===========================================================================

def _make_mock_gateway(reply: str = "这是一个测试回复。", capsules_json: str = '{"capsules": []}'):
    """Build a mock ModelGateway that returns predictable replies."""
    gateway = MagicMock()

    async def _fake_create(**kwargs):
        messages = kwargs.get("messages", [])
        # Determine if this is an extraction call by looking at system prompt
        system_content = ""
        for m in messages:
            if m.get("role") == "system":
                system_content = m.get("content", "")
                break

        content = capsules_json if "capsules" in system_content else reply

        choice = MagicMock()
        choice.message.content = content
        response = MagicMock()
        response.choices = [choice]
        return response

    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=_fake_create)

    gateway.get_client_for_role = MagicMock(return_value=mock_client)
    gateway.get_model_for_role = MagicMock(return_value="test-model")
    return gateway


@pytest.fixture()
def client():
    """TestClient with the full FastAPI app."""
    # Clear session state before each test
    _session_store.clear()
    _session_meta.clear()

    from app.main import app
    return TestClient(app)


@pytest.fixture()
def mock_gateway():
    return _make_mock_gateway()


# ---------------------------------------------------------------------------
# Mode tests
# ---------------------------------------------------------------------------

class TestChatModes:

    def test_free_talk_mode(self, client, mock_gateway):
        with patch("app.api.chat_lounge.get_model_gateway", return_value=mock_gateway):
            resp = client.post("/api/chat/lounge/message", json={
                "message": "今天心情不太好，工作压力很大",
                "mode": "free_talk",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert "session_id" in data
        assert isinstance(data["capsules"], list)
        assert len(data["session_id"]) > 0

    def test_coach_inquiry_mode(self, client, mock_gateway):
        with patch("app.api.chat_lounge.get_model_gateway", return_value=mock_gateway):
            resp = client.post("/api/chat/lounge/message", json={
                "message": "我觉得做自媒体需要真实，但又怕暴露隐私",
                "mode": "coach_inquiry",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert data["reply"] != ""

    def test_timeline_review_mode(self, client, mock_gateway):
        with patch("app.api.chat_lounge.get_model_gateway", return_value=mock_gateway):
            resp = client.post("/api/chat/lounge/message", json={
                "message": "我现在觉得创业比打工更有意义",
                "mode": "timeline_review",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data


# ---------------------------------------------------------------------------
# Date extraction in capsules
# ---------------------------------------------------------------------------

class TestCapsuleExtraction:

    def _gateway_with_capsules(self, capsule_type: str = "story", occurred_at: Optional[str] = None):
        occ_val = f'"{occurred_at}"' if occurred_at else "null"
        capsules_json = f'{{"capsules": [{{"type": "{capsule_type}", "title": "测试切片", "summary": "用户的一段经历", "occurred_at": {occ_val}}}]}}'
        return _make_mock_gateway(capsules_json=capsules_json)

    def test_capsule_story_type(self, client):
        gw = self._gateway_with_capsules("story", "2023-12-01")
        with patch("app.api.chat_lounge.get_model_gateway", return_value=gw):
            resp = client.post("/api/chat/lounge/message", json={
                "message": "2023年冬天我开始学习中医调理",
                "mode": "free_talk",
            })
        assert resp.status_code == 200
        data = resp.json()
        capsules = data["capsules"]
        assert len(capsules) == 1
        assert capsules[0]["type"] == "story"
        assert capsules[0]["occurred_at"] == "2023-12-01"

    def test_capsule_dna_type(self, client):
        gw = self._gateway_with_capsules("dna", None)
        with patch("app.api.chat_lounge.get_model_gateway", return_value=gw):
            resp = client.post("/api/chat/lounge/message", json={
                "message": "我认为创业必须在某个领域有积累才行",
                "mode": "coach_inquiry",
            })
        assert resp.status_code == 200
        capsules = resp.json()["capsules"]
        assert len(capsules) == 1
        assert capsules[0]["type"] == "dna"

    def test_capsule_occurred_at_fallback(self, client):
        """When LLM returns null for occurred_at, our parser should fill it in from text."""
        gw = _make_mock_gateway(
            reply="很有意思的经历",
            capsules_json='{"capsules": [{"type": "story", "title": "冬天学习", "summary": "学中医", "occurred_at": null}]}'
        )
        with patch("app.api.chat_lounge.get_model_gateway", return_value=gw):
            resp = client.post("/api/chat/lounge/message", json={
                "message": "2023年冬天我开始系统学中医",
                "mode": "free_talk",
            })
        assert resp.status_code == 200
        capsules = resp.json()["capsules"]
        # Fallback parser should have set occurred_at to 2023-12-01
        assert capsules[0]["occurred_at"] == "2023-12-01"

    def test_no_capsules_for_casual_message(self, client):
        gw = _make_mock_gateway(capsules_json='{"capsules": []}')
        with patch("app.api.chat_lounge.get_model_gateway", return_value=gw):
            resp = client.post("/api/chat/lounge/message", json={
                "message": "好的，谢谢你",
                "mode": "free_talk",
            })
        assert resp.status_code == 200
        assert resp.json()["capsules"] == []

    def test_multiple_capsule_types(self, client):
        capsules_json = '{"capsules": [{"type": "story", "title": "创业经历", "summary": "刚开始创业那段", "occurred_at": "2023-01-01"}, {"type": "dna", "title": "创业观", "summary": "需要积累", "occurred_at": null}]}'
        gw = _make_mock_gateway(capsules_json=capsules_json)
        with patch("app.api.chat_lounge.get_model_gateway", return_value=gw):
            resp = client.post("/api/chat/lounge/message", json={
                "message": "三年前开始创业，我觉得需要积累",
                "mode": "coach_inquiry",
            })
        assert resp.status_code == 200
        capsules = resp.json()["capsules"]
        assert len(capsules) == 2
        types = {c["type"] for c in capsules}
        assert "story" in types
        assert "dna" in types


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

class TestSessionManagement:

    def test_session_id_preserved(self, client, mock_gateway):
        session_id = "test-session-abc123"
        with patch("app.api.chat_lounge.get_model_gateway", return_value=mock_gateway):
            resp = client.post("/api/chat/lounge/message", json={
                "message": "第一条消息",
                "mode": "free_talk",
                "session_id": session_id,
            })
        assert resp.status_code == 200
        assert resp.json()["session_id"] == session_id

    def test_history_endpoint(self, client, mock_gateway):
        session_id = "hist-test-456"
        with patch("app.api.chat_lounge.get_model_gateway", return_value=mock_gateway):
            client.post("/api/chat/lounge/message", json={
                "message": "历史记录测试消息",
                "mode": "free_talk",
                "session_id": session_id,
            })

        resp = client.get(f"/api/chat/lounge/history?session_id={session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id
        messages = data["messages"]
        assert len(messages) == 2  # user + assistant
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "历史记录测试消息"
        assert messages[1]["role"] == "assistant"

    def test_history_not_found(self, client):
        resp = client.get("/api/chat/lounge/history?session_id=nonexistent-999")
        assert resp.status_code == 404

    def test_list_sessions(self, client, mock_gateway):
        with patch("app.api.chat_lounge.get_model_gateway", return_value=mock_gateway):
            client.post("/api/chat/lounge/message", json={
                "message": "消息1",
                "mode": "free_talk",
                "session_id": "sess-aaa",
            })
            client.post("/api/chat/lounge/message", json={
                "message": "消息2",
                "mode": "coach_inquiry",
                "session_id": "sess-bbb",
            })

        resp = client.get("/api/chat/lounge/sessions")
        assert resp.status_code == 200
        sessions = resp.json()
        session_ids = [s["session_id"] for s in sessions]
        assert "sess-aaa" in session_ids
        assert "sess-bbb" in session_ids

    def test_auto_generate_session_id(self, client, mock_gateway):
        """When no session_id provided, a new one should be generated."""
        with patch("app.api.chat_lounge.get_model_gateway", return_value=mock_gateway):
            resp1 = client.post("/api/chat/lounge/message", json={
                "message": "消息1",
                "mode": "free_talk",
            })
            resp2 = client.post("/api/chat/lounge/message", json={
                "message": "消息2",
                "mode": "free_talk",
            })
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        # Each call without session_id creates a new session
        assert resp1.json()["session_id"] != resp2.json()["session_id"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_message_rejected(self, client):
        resp = client.post("/api/chat/lounge/message", json={
            "message": "",
            "mode": "free_talk",
        })
        assert resp.status_code == 422

    def test_whitespace_only_message_rejected(self, client):
        resp = client.post("/api/chat/lounge/message", json={
            "message": "   ",
            "mode": "free_talk",
        })
        assert resp.status_code == 422

    def test_invalid_mode_rejected(self, client):
        resp = client.post("/api/chat/lounge/message", json={
            "message": "测试",
            "mode": "invalid_mode",
        })
        assert resp.status_code == 422

    def test_extraction_error_does_not_fail_request(self, client):
        """Even if extraction LLM call fails, the main reply should still return."""
        gateway = MagicMock()

        call_count = {"n": 0}

        async def _fake_create(**kwargs):
            call_count["n"] += 1
            messages = kwargs.get("messages", [])
            system_content = ""
            for m in messages:
                if m.get("role") == "system":
                    system_content = m.get("content", "")
                    break

            if "capsules" in system_content:
                raise RuntimeError("Extraction LLM failed")

            choice = MagicMock()
            choice.message.content = "正常回复"
            response = MagicMock()
            response.choices = [choice]
            return response

        from unittest.mock import AsyncMock
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=_fake_create)
        gateway.get_client_for_role = MagicMock(return_value=mock_client)
        gateway.get_model_for_role = MagicMock(return_value="test-model")

        with patch("app.api.chat_lounge.get_model_gateway", return_value=gateway):
            resp = client.post("/api/chat/lounge/message", json={
                "message": "测试消息",
                "mode": "free_talk",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["reply"] == "正常回复"
        assert data["capsules"] == []  # gracefully empty


# ---------------------------------------------------------------------------
# Natural date extraction integration tests
# ---------------------------------------------------------------------------

class TestNaturalDateInMessages:
    """Verify that date extraction pipeline works end-to-end for various expressions."""

    @pytest.mark.parametrize("message,expected_occurred_at", [
        ("去年冬天我开始学习节气食疗", "2025-12-01"),
        ("2023年冬天开始转型", "2023-12-01"),
        ("三年前开始做自媒体", "2023-01-01"),
        ("上个月15号我去体检了", "2026-08-15"),
        ("今天突然想明白了一件事", "2026-09-28"),
    ])
    def test_date_parsing_from_message(self, message: str, expected_occurred_at: str):
        """Unit test: directly call _parse_natural_date with fixed reference date."""
        ref = datetime(2026, 9, 28, tzinfo=timezone.utc)
        result = _parse_natural_date(message, ref)
        assert result == expected_occurred_at, f"For message '{message}': expected {expected_occurred_at}, got {result}"

# ---------------------------------------------------------------------------
# New Session & Persona Tests
# ---------------------------------------------------------------------------

class TestNewSessionEndpoints:
    def test_list_sessions_returns_list(self, client, mock_gateway):
        with patch("app.api.chat_lounge.get_model_gateway", return_value=mock_gateway):
            client.post("/api/chat/lounge/message", json={
                "message": "hello",
                "mode": "free_talk",
                "session_id": "sess-new-1"
            })
        resp = client.get("/api/chat/lounge/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        sess = next((s for s in data if s["session_id"] == "sess-new-1"), None)
        assert sess is not None
        assert "title" in sess
        assert "updated_at" in sess
        assert "mode" in sess
        assert "message_count" in sess

    def test_delete_session(self, client, mock_gateway):
        with patch("app.api.chat_lounge.get_model_gateway", return_value=mock_gateway):
            client.post("/api/chat/lounge/message", json={
                "message": "hello",
                "mode": "free_talk",
                "session_id": "sess-del"
            })
        resp = client.delete("/api/chat/lounge/sessions/sess-del")
        assert resp.status_code == 200
        # verify history is empty or 404
        resp = client.get("/api/chat/lounge/history?session_id=sess-del")
        assert resp.status_code == 404

    def test_rename_session(self, client, mock_gateway):
        with patch("app.api.chat_lounge.get_model_gateway", return_value=mock_gateway):
            client.post("/api/chat/lounge/message", json={
                "message": "hello",
                "mode": "free_talk",
                "session_id": "sess-ren"
            })
        resp = client.post("/api/chat/lounge/sessions/sess-ren/title", json={"title": "新标题"})
        assert resp.status_code == 200
        
        resp = client.get("/api/chat/lounge/sessions")
        sess = next((s for s in resp.json() if s["session_id"] == "sess-ren"), None)
        assert sess is not None
        assert sess["title"] == "新标题"

    def test_twin_prompt_built(self):
        from app.api.chat_lounge import _build_twin_system_prompt
        prompt = _build_twin_system_prompt("free_talk")
        assert "数字孪生" in prompt
