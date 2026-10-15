# -*- coding: utf-8 -*-
from pathlib import Path
import sys
import uuid
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Ensure backend root is on sys.path
backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app
from app.core.db import init_db
from app.services.cognitive_service import CognitiveService
from app.domain.cognitive.models import CognitiveDimension


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()


def _register_test_api_key(user_id) -> str:
    """Register a throwaway API key for ``user_id`` and return it.

    Draft routes derive identity from the presented credential only, so a test
    that needs a specific identity must authenticate as that identity rather
    than pass ``user_id`` in the body.
    """
    from app.core.config import settings

    key = f"test-key-{uuid.uuid4().hex}"
    settings.API_KEYS = ",".join(
        chunk for chunk in [settings.API_KEYS, f"{user_id}={key}"] if chunk
    )
    return key


@pytest.fixture
def client():
    return TestClient(app)


def test_record_feedback_for_draft(client):
    """Verify recording audience feedback comments and engagement metrics."""
    # 1. Create a draft
    draft_res = client.post("/api/drafts", json={
        "topic": "独立开发者商业闭环",
        "user_final_draft": "商业的本质是价值交换。独立开发者必须在第一天就考虑现金流，而不是沉迷于纯粹的技术自嗨。",
    })
    assert draft_res.status_code == 200
    draft_id = draft_res.json()["id"]

    # 2. Record feedback
    comments_payload = {
        "comments_text": "太对了！'第一天就考虑现金流'这句话太扎心了，深有同感！但是很多人还是不知道怎么做MVP。",
        "metrics": {"likes": 128, "reads": 3400, "comments": 24},
    }
    fb_res = client.post(f"/api/drafts/{draft_id}/feedback", json=comments_payload)
    assert fb_res.status_code == 200
    fb_data = fb_res.json()
    assert fb_data["draft_id"] == draft_id
    assert "第一天就考虑现金流" in fb_data["comments_text"]
    assert fb_data["metrics"]["likes"] == 128

    # 3. List feedback
    list_res = client.get(f"/api/drafts/{draft_id}/feedback")
    assert list_res.status_code == 200
    feedbacks = list_res.json()
    assert len(feedbacks) >= 1
    assert feedbacks[0]["id"] == fb_data["id"]


def test_extract_feedback_insights_and_dna_evolution(client):
    """Verify LLM/heuristic extraction saves notes to MaterialVault and boosts CognitiveProfile ThinkingDNA."""
    # 1. Create user and register a cognitive trait
    # A fresh identity per run: the suite shares one SQLite file, and a re-used
    # user would return an already-maxed-out trait (confidence cap 2.0).
    test_uid = uuid.uuid4()
    # Identity comes from the presented credential, so the trait owner, the
    # draft owner and the feedback evolution target are all this one user.
    auth_headers = {"X-API-Key": _register_test_api_key(test_uid)}

    from sqlmodel import Session
    from app.core.db import engine
    with Session(engine) as session:
        t = CognitiveService.add_custom_trait(
            session=session,
            dimension=CognitiveDimension.CORE_VALUE,
            statement="商业的本质是现金流与价值交换",
            user_id=test_uid,
        )
        initial_score = t.confidence_score

    # 2. Create a draft owned by the authenticated caller.
    # A body user_id is NOT an identity source: the credential decides ownership.
    draft_res = client.post("/api/drafts", json={
        "topic": "超级个体的认知杠杆",
        "user_final_draft": "商业的本质是现金流与价值交换。通过 AI 杠杆，一人也可以实现高坪效。",
    }, headers=auth_headers)
    draft_id = draft_res.json()["id"]

    # 3. Extract feedback insights
    comments_text = (
        "太对了！商业的本质是现金流与价值交换，这句话醍醐灌顶！\n"
        "但是很多人说一人企业容易遭遇天花板，你怎么看？\n"
        "如果能结合具体 SaaS 定价策略讲讲就更好了，比如按用量收费还是按月订阅。"
    )
    extract_payload = {
        "comments_text": comments_text,
        "metrics": {"shares": 50, "likes": 320},
    }

    res_extract = client.post(
        f"/api/drafts/{draft_id}/feedback/extract", json=extract_payload, headers=auth_headers
    )
    assert res_extract.status_code == 200
    data = res_extract.json()

    assert data["draft_id"] == draft_id
    assert len(data["resonant_ideas"]) > 0
    assert len(data["created_materials"]) > 0
    assert len(data["boosted_traits"]) > 0

    # Verify that MaterialVault received the inspiration personal note
    created_mat = data["created_materials"][0]
    mat_res = client.get(f"/api/materials/{created_mat['id']}", headers=auth_headers)
    assert mat_res.status_code == 200
    mat_data = mat_res.json()
    assert mat_data["material_type"] == "personal"
    assert "读者反馈" in mat_data["tags"]

    # Verify that ThinkingDNA confidence score was evolved/boosted in CognitiveProfile
    with Session(engine) as session:
        profile = CognitiveService.get_or_create_user_profile(session, test_uid)
        boosted_trait = profile.find_trait(t.id)
        assert boosted_trait is not None
        assert boosted_trait.confidence_score > initial_score
        assert boosted_trait.evolution_boost_count >= 1


def test_feedback_nonexistent_draft(client):
    """Verify 404 response for invalid draft ID."""
    dummy_id = str(uuid.uuid4())
    res = client.post(f"/api/drafts/{dummy_id}/feedback", json={"comments_text": "Great article"})
    assert res.status_code == 404


def test_delete_draft_with_feedbacks_succeeds_without_integrity_error(client):
    """Verify deleting a draft that has attached feedbacks succeeds cleanly without NOT NULL constraint failures."""
    # 1. Create a draft
    draft_res = client.post("/api/drafts", json={
        "topic": "待删除测试草稿",
        "user_final_draft": "这是一篇用来测试删除级联反馈的草稿内容。",
    })
    assert draft_res.status_code == 200
    draft_id = draft_res.json()["id"]

    # 2. Add feedback
    fb_res = client.post(f"/api/drafts/{draft_id}/feedback", json={
        "comments_text": "非常棒的草稿！",
        "metrics": {"likes": 10},
    })
    assert fb_res.status_code == 200

    # 3. Delete draft
    del_res = client.delete(f"/api/drafts/{draft_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # 4. Feedbacks were cleaned up together with the draft, so the parent
    #    draft no longer resolves and the route answers 404 (not 200 + empty).
    list_res = client.get(f"/api/drafts/{draft_id}/feedback")
    assert list_res.status_code == 404


def test_feedback_with_string_non_uuid_draft_id(client):
    """Verify feedback endpoints support string IDs like 'draft_demo_01' without 500 UUID parsing crash."""
    string_draft_id = "draft_demo_01"

    # 1. Ensure draft with string ID exists in DB
    save_res = client.post("/api/drafts", json={
        "id": string_draft_id,
        "topic": "独立开发者的超级个体跃迁模型",
        "user_final_draft": "坚持长期主义，拒绝低效内卷，在行动中穿透迷雾，直击商业本质。",
    })
    assert save_res.status_code == 200

    # 2. Record feedback with string draft ID
    fb_res = client.post(f"/api/drafts/{string_draft_id}/feedback", json={
        "comments_text": "太对了！商业的本质是价值交换，非常赞同！",
        "metrics": {"likes": 88},
    })
    assert fb_res.status_code == 200
    fb_data = fb_res.json()
    assert "太对了" in fb_data["comments_text"]

    # 3. List feedback with string draft ID
    list_res = client.get(f"/api/drafts/{string_draft_id}/feedback")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 4. Extract insights with string draft ID
    ext_res = client.post(f"/api/drafts/{string_draft_id}/feedback/extract", json={
        "comments_text": "很有启发！坚持长期主义！但是初创团队怎么破局？",
    })
    assert ext_res.status_code == 200
    ext_data = ext_res.json()
    assert len(ext_data["resonant_ideas"]) > 0


def test_dna_record_persistence_in_sqlite_on_evolution(client):
    """Verify that audience feedback extraction persists or updates an evolutionary DNARecord in SQLite."""
    from sqlmodel import Session, select
    from app.core.db import engine
    from app.models.dna_record import DNARecord

    # 1. Create a draft
    draft_res = client.post("/api/drafts", json={
        "topic": "SQLite DNARecord持久化演化测试",
        "user_final_draft": "真正的商业飞轮需要底层资产的可复用性。",
    })
    assert draft_res.status_code == 200
    draft_id = draft_res.json()["id"]

    # 2. Extract feedback insights
    ext_res = client.post(f"/api/drafts/{draft_id}/feedback/extract", json={
        "comments_text": "太对了！真正的商业飞轮需要底层资产的可复用性！\n另外可以探讨如何将资产自动化。",
        "metrics": {"likes": 99, "shares": 33},
    })
    assert ext_res.status_code == 200

    # 3. Query SQLite database directly for DNARecord associated with this draft
    with Session(engine) as session:
        dna_uuid = uuid.UUID(draft_id)
        records = session.exec(select(DNARecord).where(DNARecord.draft_id == dna_uuid)).all()
        assert len(records) >= 1
        record = records[0]
        assert record.dna_data is not None
        assert "boosted_traits" in record.dna_data
        assert record.dna_data["evolution_metrics"]["likes"] == 99

