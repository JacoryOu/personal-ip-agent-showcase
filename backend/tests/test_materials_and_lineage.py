import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

import uuid
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.skill_engine import SkillManager, get_skill_manager
from app.core.skill_engine.windows_sandbox import SandboxExecutionResult


@pytest.fixture
def client():
    return TestClient(app)


def test_material_crud_api(client):
    # 1. Manual Creation
    create_payload = {
        "title": "从零构建超级个体的认知复利模型",
        "cleaned_content": "超级个体最核心的护城河不是工时投入，而是将非共识认知沉淀为确定性执行流与杠杆工具。",
        "raw_content": "<p>超级个体最核心的护城河不是工时投入...</p>",
        "material_type": "personal",
        "source_platform": "manual",
        "source_author": "Jacory",
        "tags": ["个人思考", "认知杠杆", "商业模型"],
        "status": "inbox",
        "meta_info": {"importance": "high"},
    }
    res = client.post("/api/materials", json=create_payload)
    assert res.status_code == 200, res.text
    data = res.json()
    mat_id = data["id"]
    assert data["title"] == create_payload["title"]
    assert data["material_type"] == "personal"
    assert data["status"] == "inbox"
    assert "认知杠杆" in data["tags"]

    # 2. Get Single Material
    res_get = client.get(f"/api/materials/{mat_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == mat_id
    assert res_get.json()["source_author"] == "Jacory"

    # 3. List with Filters
    res_list_type = client.get("/api/materials?material_type=personal")
    assert res_list_type.status_code == 200
    assert any(m["id"] == mat_id for m in res_list_type.json())

    res_list_tag = client.get("/api/materials?tag=认知杠杆")
    assert res_list_tag.status_code == 200
    assert any(m["id"] == mat_id for m in res_list_tag.json())

    res_list_search = client.get("/api/materials?search=超级个体")
    assert res_list_search.status_code == 200
    assert any(m["id"] == mat_id for m in res_list_search.json())

    res_list_miss = client.get("/api/materials?material_type=trending")
    assert res_list_miss.status_code == 200
    assert not any(m["id"] == mat_id for m in res_list_miss.json())

    # 4. Patch Material
    patch_payload = {
        "status": "archived",
        "tags": ["个人思考", "深度沉淀"],
    }
    res_patch = client.patch(f"/api/materials/{mat_id}", json=patch_payload)
    assert res_patch.status_code == 200
    patched_data = res_patch.json()
    assert patched_data["status"] == "archived"
    assert "深度沉淀" in patched_data["tags"]

    # 5. Delete Material
    res_del = client.delete(f"/api/materials/{mat_id}")
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

    # Confirm deletion
    res_check = client.get(f"/api/materials/{mat_id}")
    assert res_check.status_code == 404


def test_collect_url_and_blueprint_extraction(client):
    # Mock skill manager for sandboxed collector execution
    mock_sm = MagicMock(spec=SkillManager)
    mock_sm.execute_skill_sync.return_value = SandboxExecutionResult(
        success=True,
        output={
            "success": True,
            "title": "深度拆解：为什么一流创作者都在搭建自己的思维骨架？",
            "source_author": "认知黑客",
            "source_platform": "wechat",
            "source_url": "https://mp.weixin.qq.com/s/sample-article-123",
            "cleaned_content": "大多数人以为创作是靠灵感突发，实则是靠结构化骨架与个人认知的碰撞。",
            "raw_content": "<article>...</article>",
            "tags": ["微信生态", "爆款结构", "写作方法论"],
            "blueprint_data": {
                "title": "爆款骨架·结构降维打法",
                "hook_style": "以反常识提问开篇制造悬念",
                "structural_stages": [
                    "开篇悬念：指出大众普遍直觉的盲区",
                    "本质拆解：从底层逻辑推导真相",
                    "解决方案：三步实战推导法",
                    "升华号召：形成长效思维复利",
                ],
                "emotional_arc": "困惑 ➔ 顿悟 ➔ 赋能",
                "pacing": "前 15% 抓眼球，中段 65% 硬核，后 20% 升华",
            },
        },
        returncode=0,
    )

    app.dependency_overrides[get_skill_manager] = lambda: mock_sm

    try:
        req = {
            "url": "https://mp.weixin.qq.com/s/sample-article-123",
            "extract_blueprint": True,
            "tags": ["精选标杆"],
            "save": True,
        }
        res = client.post("/api/materials/collect-url", json=req)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["success"] is True
        mat = data["material"]
        assert mat["material_type"] == "benchmark"
        assert mat["source_platform"] == "wechat"
        assert mat["source_author"] == "认知黑客"
        assert "精选标杆" in mat["tags"]
        assert mat["blueprint_data"]["title"] == "爆款骨架·结构降维打法"

        # Check DB persistence
        res_get = client.get(f"/api/materials/{mat['id']}")
        assert res_get.status_code == 200
        assert res_get.json()["blueprint_data"]["hook_style"] == "以反常识提问开篇制造悬念"
    finally:
        app.dependency_overrides.pop(get_skill_manager, None)


def test_fetch_trending_radar_batch(client):
    mock_sm = MagicMock(spec=SkillManager)
    mock_sm.execute_skill_sync.return_value = SandboxExecutionResult(
        success=True,
        output={
            "success": True,
            "items": [
                {
                    "title": "热榜测试：2026超级个体认知工具爆发",
                    "source_platform": "zhihu",
                    "source_author": "趋势观察家",
                    "source_url": "https://zhihu.com/question/trend-test-1",
                    "cleaned_content": "探讨超级个体与认知资产化闭环。",
                    "raw_content": "探讨超级个体与认知资产化闭环。",
                    "tags": ["全网热点", "AI热点"],
                    "meta_info": {"hot_score": 999999, "rank": 1},
                },
                {
                    "title": "热榜测试：为什么长文创作者迎来黄金时代",
                    "source_platform": "wechat",
                    "source_author": "深度写作周刊",
                    "source_url": "https://mp.weixin.qq.com/s/trend-test-2",
                    "cleaned_content": "快餐短视频泛滥后，人们渴望真正有深度的洞察。",
                    "raw_content": "快餐短视频泛滥后，人们渴望真正有深度的洞察。",
                    "tags": ["全网热点", "深度写作"],
                    "meta_info": {"hot_score": 888888, "rank": 2},
                },
            ],
        },
        returncode=0,
    )

    app.dependency_overrides[get_skill_manager] = lambda: mock_sm

    try:
        res = client.post("/api/materials/fetch-trending", json={"platform": "all", "limit": 5, "batch_save": True})
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["success"] is True
        assert data["count"] == 2
        first_item = data["items"][0]
        assert first_item["material_type"] == "trending"
        assert first_item["source_platform"] == "zhihu"

        # Verify saved in list_materials
        res_list = client.get("/api/materials?material_type=trending")
        assert res_list.status_code == 200
        titles = [m["title"] for m in res_list.json()]
        assert "热榜测试：2026超级个体认知工具爆发" in titles
    finally:
        app.dependency_overrides.pop(get_skill_manager, None)


def test_draft_lineage_tracking_and_endpoint(client):
    # 1. Create a source benchmark material
    create_mat_res = client.post(
        "/api/materials",
        json={
            "title": "商业标杆：一人公司的无限复利",
            "material_type": "benchmark",
            "source_platform": "xiaohongshu",
            "source_author": "商业独立思考者",
            "source_url": "https://www.xiaohongshu.com/discovery/item/solopreneur-compounding",
            "cleaned_content": "核心痛点：时间不够用。解决方案：将思维模型固化为数字资产。",
            "blueprint_data": {
                "title": "一人公司复利骨架",
                "hook_style": "痛点反问 + 颠覆性共识",
                "structural_stages": ["痛点剖析", "逻辑重构", "杠杆方案", "复利升华"],
                "emotional_arc": "扎心 ➔ 觉醒 ➔ 笃定",
            },
            "tags": ["标杆拆骨", "一人公司"],
        },
    )
    assert create_mat_res.status_code == 200
    mat = create_mat_res.json()
    mat_id = mat["id"]

    # 2. Archive a draft referencing this material and recording lineage
    draft_id = str(uuid.uuid4())
    draft_payload = {
        "id": draft_id,
        "topic": "基于一人公司骨架的认知重构实践",
        "original_ai_draft": "# 认知重构实践\n\n以一人公司为杠杆...",
        "user_final_draft": "# 认知重构实践（精修版）\n\n以一人公司为杠杆，坚持第一性原理...",
        "source_material_id": mat_id,
        "benchmark_blueprint_id": "bp_solopreneur_01",
        "lineage_snapshot": {
            "source_material_id": mat_id,
            "source_title": mat["title"],
            "source_platform": mat["source_platform"],
            "source_author": mat["source_author"],
            "source_url": mat["source_url"],
            "material_type": "benchmark",
            "blueprint_title": "一人公司复利骨架",
            "inspiration_hook": "痛点反问 + 颠覆性共识",
            "emotional_arc": "扎心 ➔ 觉醒 ➔ 笃定",
        },
        "metadata_": {
            "title": "基于一人公司骨架的认知重构实践",
            "injected_dna": {
                "style_tone": "理性克制、第一性原理",
                "vocabulary_signature": ["认知杠杆", "商业复利", "一人公司"],
                "thinking_archetype": "架构师型思维",
            },
        },
    }
    save_draft_res = client.post("/api/drafts", json=draft_payload)
    assert save_draft_res.status_code == 200, save_draft_res.text
    saved_draft = save_draft_res.json()
    assert saved_draft["source_material_id"] == mat_id
    assert saved_draft["benchmark_blueprint_id"] == "bp_solopreneur_01"
    assert saved_draft["lineage_snapshot"]["source_author"] == "商业独立思考者"

    # 3. Call GET /api/drafts/{draft_id}/lineage
    lineage_res = client.get(f"/api/drafts/{draft_id}/lineage")
    assert lineage_res.status_code == 200, lineage_res.text
    lineage_data = lineage_res.json()
    assert lineage_data["draft_id"] == draft_id
    assert lineage_data["source_material_id"] == mat_id
    assert lineage_data["source_material"] is not None
    assert lineage_data["source_material"]["title"] == "商业标杆：一人公司的无限复利"
    assert lineage_data["source_material"]["source_platform"] == "xiaohongshu"
    assert lineage_data["source_material"]["source_author"] == "商业独立思考者"
    assert lineage_data["lineage_snapshot"]["inspiration_hook"] == "痛点反问 + 颠覆性共识"
    assert lineage_data["thinking_dna_used"]["style_tone"] == "理性克制、第一性原理"

    # 4. Verify deleting material does not cause foreign key constraint crashes on Draft
    del_res = client.delete(f"/api/materials/{mat_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Draft should still exist with source_material_id nullified but lineage_snapshot intact!
    check_draft = client.get(f"/api/drafts/{draft_id}")
    assert check_draft.status_code == 200
    assert check_draft.json()["lineage_snapshot"]["source_title"] == "商业标杆：一人公司的无限复利"

    # 5. Check GET /api/drafts/{draft_id}/lineage fallback after material deletion
    lineage_after_del = client.get(f"/api/drafts/{draft_id}/lineage")
    assert lineage_after_del.status_code == 200
    lineage_after_data = lineage_after_del.json()
    assert lineage_after_data["source_material"]["title"] == "商业标杆：一人公司的无限复利"
    assert lineage_after_data["source_material"]["source_author"] == "商业独立思考者"


def test_generate_from_blueprint_with_material_lineage(client):
    from unittest.mock import AsyncMock
    from app.api.drafts import get_draft_agent
    from app.schemas.draft_schemas import DraftOutput

    mock_agent = MagicMock()
    mock_agent.generate_draft = AsyncMock(
        return_value=DraftOutput(
            title="一人公司的商业变现闭环",
            content="# 一人公司正文\n\n以一人公司为杠杆...",
            word_count=400,
        )
    )
    app.dependency_overrides[get_draft_agent] = lambda: mock_agent

    try:
        # 1. Create a benchmark material with blueprint
        mat_res = client.post(
            "/api/materials",
            json={
                "title": "爆款对标：超级个体的思维模型",
                "material_type": "benchmark",
                "source_platform": "zhihu",
                "source_author": "认知行者",
                "source_url": "https://zhihu.com/question/model-123",
                "cleaned_content": "超级个体需要具备架构师思维，将知识资产化。",
                "blueprint_data": {
                    "title": "认知跃迁三阶骨架",
                    "hook_style": "提问引出反直觉痛点",
                    "structural_stages": ["痛点", "根因", "解法", "总结"],
                    "emotional_arc": "困惑 ➔ 觉醒 ➔ 笃定",
                },
                "tags": ["思维模型", "超级个体"],
            },
        )
        assert mat_res.status_code == 200
        mat = mat_res.json()
        mat_id = mat["id"]

        # 2. Call generate-from-blueprint passing source_material_id and explicit blueprint without id
        bp_req = {
            "topic": "一人公司的商业变现闭环",
            "blueprint": {
                "title": "认知跃迁三阶骨架",
                "hook_style": "提问引出反直觉痛点",
                "structural_stages": ["痛点", "根因", "解法", "总结"],
                "emotional_arc": "困惑 ➔ 觉醒 ➔ 笃定",
            },
            "source_material_id": mat_id,
            "additional_context": "突出反脆弱与杠杆效应",
        }
        gen_res = client.post("/api/drafts/generate-from-blueprint", json=bp_req)
        assert gen_res.status_code == 200, gen_res.text
        gen_data = gen_res.json()

        # Verify DraftOutput fields
        assert gen_data["id"] is not None
        draft_id = gen_data["id"]
        assert gen_data["source_material_id"] == mat_id
        assert gen_data["benchmark_blueprint_id"] != "None"  # MUST NOT be string 'None'!
        assert gen_data["lineage_snapshot"] is not None
        assert gen_data["lineage_snapshot"]["source_title"] == "爆款对标：超级个体的思维模型"
        assert gen_data["lineage_snapshot"]["source_author"] == "认知行者"

        # Verify material status changed to 'used'
        mat_check = client.get(f"/api/materials/{mat_id}")
        assert mat_check.status_code == 200
        assert mat_check.json()["status"] == "used"

        # Verify GET /api/drafts/{draft_id}/lineage
        lin_res = client.get(f"/api/drafts/{draft_id}/lineage")
        assert lin_res.status_code == 200
        lin_data = lin_res.json()
        assert lin_data["source_material"]["title"] == "爆款对标：超级个体的思维模型"
        assert lin_data["source_material"]["source_author"] == "认知行者"
        assert lin_data["benchmark_blueprint"]["title"] == "认知跃迁三阶骨架"
    finally:
        app.dependency_overrides.pop(get_draft_agent, None)


def test_materials_tag_pagination(client):
    tag_x = f"tag_page_{uuid.uuid4().hex[:6]}"
    for i in range(3):
        client.post(
            "/api/materials",
            json={
                "title": f"分页测试文章 {i}",
                "cleaned_content": f"内容 {i}",
                "material_type": "personal",
                "tags": [tag_x, f"extra_{i}"],
            },
        )

    res_p1 = client.get(f"/api/materials?tag={tag_x}&limit=2&offset=0")
    assert res_p1.status_code == 200
    p1_items = res_p1.json()
    assert len(p1_items) == 2

    res_p2 = client.get(f"/api/materials?tag={tag_x}&limit=2&offset=2")
    assert res_p2.status_code == 200
    p2_items = res_p2.json()
    assert len(p2_items) == 1
    assert p2_items[0]["id"] not in [m["id"] for m in p1_items]
