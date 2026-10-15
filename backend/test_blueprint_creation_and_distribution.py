import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.main import app
from app.core.db import get_session
from app.api.drafts import get_draft_agent
from app.engine.cognitive_engine import CognitiveEngine
from app.models.draft import Draft
from app.models.user import User
from app.schemas.draft_schemas import DraftOutput
from app.schemas.diff_schemas import ThinkingDNA


BP_OWNER_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
BP_OWNER_KEY = "blueprint-owner-key"
BP_AUTH = {"X-API-Key": BP_OWNER_KEY}


@pytest.fixture(autouse=True)
def blueprint_auth_settings():
    old_keys, old_local, old_required = settings.API_KEYS, settings.AUTH_LOCAL_DEV_MODE, settings.AUTH_REQUIRED
    settings.API_KEYS = f"{BP_OWNER_ID}={BP_OWNER_KEY}"
    settings.AUTH_LOCAL_DEV_MODE = False
    settings.AUTH_REQUIRED = True
    try:
        yield
    finally:
        settings.API_KEYS, settings.AUTH_LOCAL_DEV_MODE, settings.AUTH_REQUIRED = old_keys, old_local, old_required


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(
            id=BP_OWNER_ID,
            username="blueprint_tester",
            profile_data={
                "benchmark_blueprints": [
                    {
                        "id": "bp_test_123",
                        "title": "爆款认知突围拆解模板",
                        "hook_style": "开门见山提出颠覆常识的尖锐问题",
                        "structural_stages": [
                            "刺痛读者常识认知盲区",
                            "剖析传统方法的底层缺陷",
                            "提出颠覆性重构策略",
                            "给出实战行动路径与升华",
                        ],
                        "emotional_arc": "困惑/受挫 ➔ 顿悟/重构 ➔ 笃定行动",
                        "pacing": "开篇20%快速立论，中段60%案例推演，收尾20%升华",
                    }
                ]
            },
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_engine_generate_from_blueprint_explicit(session: Session):
    """Verifies CognitiveEngine generates a draft using an explicit blueprint dictionary."""
    engine = CognitiveEngine()
    user = session.exec(select(User)).first()

    mock_agent = MagicMock()
    mock_agent.generate_draft = AsyncMock(
        return_value=DraftOutput(
            title="基于爆款骨架的AI工作流设计",
            summary="用认知重构打造超级个体",
            content="# 标题\n\n正文内容...",
            word_count=500,
        )
    )

    explicit_blueprint = {
        "title": "爆款骨架A",
        "hook_style": "反直觉开篇",
        "structural_stages": ["第一阶段", "第二阶段", "第三阶段"],
        "emotional_arc": "焦虑 ➔ 释然",
        "pacing": "稳扎稳打",
    }

    dna = ThinkingDNA(
        vocabulary_habits=["底层逻辑", "第一性原理"],
        logic_preferences=["因果推导"],
        core_values=["长期主义"],
    )

    result = await engine.generate_from_blueprint(
        topic="超级个体的AI工作流",
        blueprint=explicit_blueprint,
        additional_context="面向独立开发者",
        user_id=user.id,
        thinking_dna=dna,
        agent=mock_agent,
        session=session,
    )

    assert result.title == "基于爆款骨架的AI工作流设计"
    assert result.word_count == 500
    mock_agent.generate_draft.assert_called_once()
    called_input = mock_agent.generate_draft.call_args[0][0]
    assert "爆款骨架A" in called_input.outline.title
    assert len(called_input.outline.sections) == 3
    assert "对标爆款骨架约束" in called_input.additional_context
    assert "面向独立开发者" in called_input.additional_context


@pytest.mark.asyncio
async def test_engine_generate_from_blueprint_by_id(session: Session):
    """Verifies CognitiveEngine retrieves blueprint from user profile by blueprint_id."""
    engine = CognitiveEngine()
    user = session.exec(select(User)).first()

    mock_agent = MagicMock()
    mock_agent.generate_draft = AsyncMock(
        return_value=DraftOutput(
            title="个人IP资产化实践指南",
            content="# 个人IP资产化\n\n正文内容...",
            word_count=620,
        )
    )

    result = await engine.generate_from_blueprint(
        topic="个人IP资产化",
        blueprint_id="bp_test_123",
        user_id=user.id,
        agent=mock_agent,
        readonly_session=session,
        session=session,
    )

    assert result.title == "个人IP资产化实践指南"
    mock_agent.generate_draft.assert_called_once()
    called_input = mock_agent.generate_draft.call_args[0][0]
    assert "爆款认知突围拆解模板" in called_input.outline.title
    assert len(called_input.outline.sections) == 4


@pytest.mark.asyncio
async def test_engine_generate_from_blueprint_validation_errors(session: Session):
    """Verifies edge cases: empty topic and non-existent blueprint_id."""
    engine = CognitiveEngine()

    with pytest.raises(ValueError, match="Topic cannot be empty"):
        await engine.generate_from_blueprint(topic="   ", blueprint_id="bp_1")

    with pytest.raises(ValueError, match="Benchmark blueprint not found"):
        await engine.generate_from_blueprint(topic="Valid Topic", blueprint_id="non_existent_id", session=session)


def test_engine_distribute_content():
    """Verifies Multi-Platform Content Distribution Formatter runs inside sandbox."""
    engine = CognitiveEngine()
    sample_article = (
        "# 个人商业闭环的本质思考\n\n"
        "很多人以为创业就是追逐风口，其实核心在于沉淀难以被复制的认知资产与信任飞轮。\n\n"
        "## 第一、破除信息焦虑\n"
        "泛滥的信息只会带来认知过载，真正重要的是建立自洽的筛选逻辑与思考模型。\n\n"
        "## 第二、一鱼多吃的高效分发\n"
        "把一篇深度原创文章，根据不同平台受众心理自适应转译，是超级个体的杠杆解。"
    )

    output = engine.distribute_content(
        content=sample_article,
        title="个人商业闭环的本质思考",
    )

    assert output.get("success") is True
    platforms = output.get("platforms", {})
    assert "xiaohongshu" in platforms
    assert "wechat" in platforms
    assert "twitter" in platforms
    assert "video" in platforms

    # Xiaohongshu checks
    xhs = platforms["xiaohongshu"]
    assert len(xhs["tags"]) == 5
    assert "🔥" in xhs["title"] or "💡" in xhs["title"]
    assert "赞藏" in xhs["content"] or "评论区" in xhs["content"]

    # WeChat checks
    wechat = platforms["wechat"]
    assert "导读" in wechat["content"]
    assert "### 01" in wechat["content"]
    assert "互动时刻" in wechat["content"]
    assert "section_illustrations" in wechat
    assert isinstance(wechat["section_illustrations"], list)
    assert len(wechat["section_illustrations"]) >= 2
    first_illus = wechat["section_illustrations"][0]
    assert "section_index" in first_illus
    assert "section_title" in first_illus
    assert "image_prompt" in first_illus
    assert "caption" in first_illus
    assert "anchor_paragraph" in first_illus
    assert "16:9" in first_illus["image_prompt"]
    assert "footnotes" in wechat

    # Twitter checks
    twitter = platforms["twitter"]
    assert len(twitter["thread"]) >= 5
    assert twitter["thread"][0].startswith("1/")
    assert "🔁 转发" in twitter["thread"][-1]

    # Video monologue checks
    video = platforms["video"]
    assert "【前3秒黄金钩子】" in video["hook"]
    assert "[镜头" in video["content"]
    assert video["estimated_duration_seconds"] > 0


def test_api_generate_from_blueprint_endpoint(client: TestClient):
    """Tests POST /api/drafts/generate-from-blueprint."""
    mock_agent = MagicMock()
    mock_agent.generate_draft = AsyncMock(
        return_value=DraftOutput(
            title="对标骨架原创输出",
            content="# 骨架文章\n\n精彩正文",
            word_count=350,
        )
    )

    app.dependency_overrides[get_draft_agent] = lambda: mock_agent

    try:
        res = client.post(
            "/api/drafts/generate-from-blueprint",
            headers=BP_AUTH,
            json={
                "topic": "知识博主的商业闭环",
                "blueprint": {
                    "title": "骨架模版",
                    "hook_style": "提问法",
                    "structural_stages": ["痛点", "解法", "升华"],
                    "emotional_arc": "受挫 ➔ 释然",
                    "pacing": "紧凑",
                },
                "additional_context": "突出实操",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["title"] == "对标骨架原创输出"
        assert data["word_count"] == 350
        mock_agent.generate_draft.assert_called_once()
    finally:
        app.dependency_overrides.pop(get_draft_agent, None)


def test_api_distribute_endpoint(client: TestClient):
    """Tests POST /api/drafts/distribute."""
    res = client.post(
        "/api/drafts/distribute",
        headers=BP_AUTH,
        json={
            "content": "# 测试分发\n\n核心在于打造超级个体生产力。\n\n## 阶段一\n快速验证想法。\n\n## 阶段二\n多平台分发传播。",
            "title": "测试分发",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "xiaohongshu" in data["platforms"]
    assert "wechat" in data["platforms"]
    assert "twitter" in data["platforms"]
    assert "video" in data["platforms"]


def test_api_distribute_draft_by_id_endpoint(client: TestClient, session: Session):
    """Tests POST /api/drafts/{draft_id}/distribute."""
    user = session.exec(select(User)).first()
    draft = Draft(
        user_id=user.id,
        topic="通过Draft ID分发测试",
        original_ai_draft="# AI草稿\n\n初始内容",
        user_final_draft="# 定稿长文\n\n这是用户精修后的最终定稿，拥有极高的思考密度与金句。\n\n## 破局点\n找到关键支点，放大个体价值。",
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)

    res = client.post(f"/api/drafts/{draft.id}/distribute", headers=BP_AUTH)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "xiaohongshu" in data["platforms"]
    assert "破局点" in data["platforms"]["wechat"]["content"]


def test_api_distribute_draft_by_id_not_found(client: TestClient):
    """Tests 404 handling for unknown draft_id."""
    random_id = uuid.uuid4()
    res = client.post(f"/api/drafts/{random_id}/distribute", headers=BP_AUTH)
    assert res.status_code == 404
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.engine.cognitive_engine import CognitiveEngine
from app.models.draft import Draft
from app.models.user import User
from app.schemas.draft_schemas import DraftOutput


@pytest.mark.asyncio
async def test_engine_generate_from_blueprint_dict_stages(session: Session):
    engine = CognitiveEngine()
    mock_agent = MagicMock()
    mock_agent.generate_draft = AsyncMock(
        return_value=DraftOutput(
            title="Dict Stage Test",
            content="# Title\n\nBody text",
            word_count=400,
        )
    )

    blueprint_with_dicts = {
        "title": "Dict Blueprint",
        "structural_stages": [
            {"title": "Stage 1: Hook", "desc": "Break old mindset"},
            {"title": "Stage 2: Deep Dive", "desc": "Underlying mechanism"},
            {"title": "Stage 3: Action", "desc": "Actionable steps"},
        ],
    }

    result = await engine.generate_from_blueprint(
        topic="Testing dict stages",
        blueprint=blueprint_with_dicts,
        agent=mock_agent,
        readonly_session=session,
        session=session,
    )

    assert result.title == "Dict Stage Test"
    called_input = mock_agent.generate_draft.call_args[0][0]
    assert len(called_input.outline.sections) == 3
    assert "Stage 1: Hook" in called_input.outline.sections[0].title


def test_distribute_short_content_guaranteed_thread_length():
    engine = CognitiveEngine()
    short_content = "This is a short essay about cognitive iteration. Execution alone is not enough. Finding leverage is key."

    output = engine.distribute_content(content=short_content)
    assert output.get("success") is True
    platforms = output.get("platforms", {})

    twitter = platforms["twitter"]
    assert 5 <= len(twitter["thread"]) <= 8
    for i, tw in enumerate(twitter["thread"], 1):
        assert tw.startswith(f"{i}/{len(twitter['thread'])}")
        assert len(tw.strip()) > 10

    xhs = platforms["xiaohongshu"]
    assert len(xhs["tags"]) == 5

    video = platforms["video"]
    assert "[手势比出 1]" in video["content"]
    assert "[手势比出 2]" in video["content"]
    assert "[手势比出 3]" in video["content"]
    assert video["estimated_duration_seconds"] >= 45


def test_distribute_platform_filter():
    engine = CognitiveEngine()
    output = engine.distribute_content(
        content="Creators must build their personal cognitive IP and automated distribution workflows.",
        platforms=["twitter"],
    )
    assert output.get("success") is True
    assert list(output.get("platforms", {}).keys()) == ["twitter"]


def test_api_generate_from_blueprint_missing_blueprint_or_id(client: TestClient):
    res = client.post(
        "/api/drafts/generate-from-blueprint",
        headers=BP_AUTH,
        json={"topic": "Topic missing blueprint"},
    )
    assert res.status_code == 422


def test_api_distribute_draft_by_id_empty_content(client: TestClient, session: Session):
    user = session.exec(select(User)).first()
    draft = Draft(
        user_id=user.id,
        topic="Empty draft test",
        original_ai_draft="",
        user_final_draft="",
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)

    res = client.post(f"/api/drafts/{draft.id}/distribute", headers=BP_AUTH)
    assert res.status_code == 422
    assert "no content" in res.json().get("detail", "").lower()


def test_wechat_distribution_section_illustrations_details():
    """Verifies that WeChat section illustrations contain complete prompt and metadata attributes."""
    engine = CognitiveEngine()
    article = (
        "# 个人认知超级IP打造\n\n"
        "认知资产的壁垒远高于体力劳动。\n\n"
        "## 第一、破局点挖掘\n"
        "在存量竞争中寻找结构性红利，构建最小可行性杠杆认知。\n\n"
        "## 第二、多渠道触达\n"
        "用全渠道矩阵分发优质长文，建立去中心化的信任资产。\n\n"
        "## 第三、商业飞轮闭环\n"
        "通过认知沉淀打通商业变现路径，实现长周期复利价值。"
    )

    output = engine.distribute_content(content=article, platforms=["wechat"])
    assert output.get("success") is True
    wechat = output["platforms"]["wechat"]

    illustrations = wechat.get("section_illustrations", [])
    assert len(illustrations) >= 3

    for idx, item in enumerate(illustrations, 1):
        assert item["section_index"] == idx
        assert item["section_title"]
        assert "16:9" in item["image_prompt"]
        assert "--ar 16:9" in item["image_prompt"]
        assert "caption" in item
        assert item["caption"].startswith(f"图 0{idx}：") or item["caption"].startswith(f"图 {idx}：")
        assert "anchor_paragraph" in item
        assert item["aspect_ratio"] == "16:9"


def test_wechat_distribution_footnotes_extraction_and_replacement():
    """Verifies that WeChat format extracts Markdown links into footnotes and transforms inline text."""
    engine = CognitiveEngine()
    article_with_links = (
        "# AI时代的开发者进化论\n\n"
        "大语言模型正在重塑软件研发范式。\n\n"
        "## 认知觉醒\n"
        "参考最新的 [DeepSeek技术报告](https://arxiv.org/abs/2501.12948)，强化学习改变了推理路径。\n\n"
        "## 工具重构\n"
        "结合 [LangChain官方手册](https://python.langchain.com) 快速构建多智能体编排系统。"
    )

    output = engine.distribute_content(content=article_with_links, platforms=["wechat"])
    assert output.get("success") is True
    wechat = output["platforms"]["wechat"]

    footnotes = wechat.get("footnotes", [])
    assert len(footnotes) == 2

    # Footnote items
    fn1 = footnotes[0]
    assert fn1["index"] == 1
    assert "DeepSeek技术报告" in fn1["title"]
    assert fn1["url"] == "https://arxiv.org/abs/2501.12948"
    assert "[1]" in fn1["formatted"]

    fn2 = footnotes[1]
    assert fn2["index"] == 2
    assert "LangChain官方手册" in fn2["title"]
    assert fn2["url"] == "https://python.langchain.com"
    assert "[2]" in fn2["formatted"]

    # Verify content transforms: inline link converted to text + [index]
    wechat_content = wechat["content"]
    assert "DeepSeek技术报告 [1]" in wechat_content
    assert "LangChain官方手册 [2]" in wechat_content
    assert "(https://arxiv.org/abs/2501.12948)" not in wechat_content
    assert "📚 参考资料与引用：" in wechat_content
    assert "[1] DeepSeek技术报告" in wechat_content
    assert "[2] LangChain官方手册" in wechat_content


def test_wechat_distribution_without_links_has_empty_footnotes():
    """Verifies that an article without hyperlinks produces empty footnotes and no reference block."""
    engine = CognitiveEngine()
    article = (
        "# 纯净思考长文\n\n"
        "这是一篇没有外链的纯思考长文。\n\n"
        "## 核心思考\n"
        "专注底层规律，不受碎片化外部信息干扰。"
    )

    output = engine.distribute_content(content=article, platforms=["wechat"])
    assert output.get("success") is True
    wechat = output["platforms"]["wechat"]

    assert wechat.get("footnotes") == []
    assert "📚 参考资料与引用" not in wechat["content"]
    assert len(wechat.get("section_illustrations", [])) >= 1


def test_wechat_distribution_footnotes_reference_links_and_images():
    """Verifies that Markdown images are not treated as footnotes and reference-style definitions are properly captured."""
    engine = CognitiveEngine()
    article = (
        "# 知识系统的多重引用\n\n"
        "![知识图谱架构图](https://cdn.example.com/images/architecture.png)\n\n"
        "## 理论起源\n"
        "本研究基于前沿工作 [Cognitive Engine][ref1]，探索AI时代的沉淀机制。\n\n"
        "[ref1]: https://cognitive-engine.ai/docs"
    )

    output = engine.distribute_content(content=article, platforms=["wechat"])
    assert output.get("success") is True
    wechat = output["platforms"]["wechat"]

    footnotes = wechat.get("footnotes", [])
    # Architecture image should NOT be in footnotes!
    assert not any("cdn.example.com" in fn["url"] for fn in footnotes)
    # The reference link ref1 should be captured!
    assert any("cognitive-engine.ai" in fn["url"] for fn in footnotes)


def test_wechat_distribution_balanced_parens_and_titles():
    """Verifies that URLs with balanced parens (e.g. Wikipedia) and titles are parsed without truncation or rogue parens."""
    engine = CognitiveEngine()
    article = (
        "# ?????????\n\n"
        "????????????????\n\n"
        "## ????\n"
        "??? [????](https://en.wikipedia.org/wiki/Python_(programming_language)) ????????\n"
        "?? [Google??](https://google.com \"????\") ?? [Bracketed](<https://bracketed.com>) ? [API](<https://example.com/api> 'API Spec')?\n\n"
        "## ????\n"
        "?????????????"
    )

    output = engine.distribute_content(content=article, platforms=["wechat"])
    assert output.get("success") is True
    wechat = output["platforms"]["wechat"]
    content = wechat["content"]
    footnotes = wechat.get("footnotes", [])

    assert len(footnotes) == 4

    # 1. Wikipedia with balanced parens
    wiki_fn = footnotes[0]
    assert wiki_fn["url"] == "https://en.wikipedia.org/wiki/Python_(programming_language)"
    assert "???? [1]" in content
    assert "???? [1])" not in content  # Crucial: NO stray paren!

    # 2. Google with title
    google_fn = footnotes[1]
    assert google_fn["url"] == "https://google.com"
    assert "????" in google_fn["title"]
    assert "Google?? [2]" in content

    # 3. Bracketed URL <https://...>
    bracketed_fn = footnotes[2]
    assert bracketed_fn["url"] == "https://bracketed.com"
    assert "Bracketed [3]" in content

    # 4. Bracketed URL with title
    api_fn = footnotes[3]
    assert api_fn["url"] == "https://example.com/api"
    assert "API Spec" in api_fn["title"]
    assert "API [4]" in content


def test_wechat_distribution_reference_links_and_definitions_cleaning():
    """Verifies that reference-style citations are replaced in body and definition lines do not leak into paragraphs."""
    engine = CognitiveEngine()
    article = (
        "# ???????\n\n"
        "???????????????????\n\n"
        "## ????\n"
        "?????? [DeepSeek AI][ds-paper] ?????? [LangChain][] ??????\n\n"
        "## ????\n"
        "????????????\n\n"
        "[ds-paper]: https://arxiv.org/abs/2501.12948 \"DeepSeek-R1 Paper\"\n"
        "[LangChain]: https://python.langchain.com\n"
    )

    output = engine.distribute_content(content=article, platforms=["wechat"])
    assert output.get("success") is True
    wechat = output["platforms"]["wechat"]
    content = wechat["content"]
    footnotes = wechat.get("footnotes", [])

    assert len(footnotes) == 2
    fn1 = footnotes[0]
    assert fn1["index"] == 1
    assert "DeepSeek-R1 Paper" in fn1["title"]
    assert fn1["url"] == "https://arxiv.org/abs/2501.12948"

    fn2 = footnotes[1]
    assert fn2["index"] == 2
    assert "LangChain" in fn2["title"]
    assert fn2["url"] == "https://python.langchain.com"

    # Both citations must be replaced with footnote numbers
    assert "DeepSeek AI [1]" in content
    assert "LangChain [2]" in content
    assert "[ds-paper]" not in content
    assert "[LangChain]" not in content

    # Raw reference definition lines MUST NOT appear in body paragraphs
    body_before_refs = content.split("?? ????????")[0]
    assert "[ds-paper]:" not in body_before_refs
    assert "[LangChain]:" not in body_before_refs


def test_wechat_distribution_images_not_bolded_and_anchor_clean():
    """Verifies that Markdown images are neither bolded nor wrongly picked as anchor_paragraphs."""
    engine = CognitiveEngine()
    article = (
        "# ??????\n\n"
        "?????????????????\n\n"
        "## ????\n"
        "![???????](https://cdn.example.com/arch-topology.png)\n"
        "????????????????????\n\n"
        "## ????\n"
        "???????????????"
    )

    output = engine.distribute_content(content=article, platforms=["wechat"])
    assert output.get("success") is True
    wechat = output["platforms"]["wechat"]
    content = wechat["content"]
    illustrations = wechat["section_illustrations"]

    # Image should NOT be wrapped in **![...]**
    assert "**![???????]" not in content
    assert "![???????](https://cdn.example.com/arch-topology.png)" in content

    # In section illustrations, anchor_paragraph should be the real text paragraph, not the image!
    sec1_illus = illustrations[0]
    assert "??????????" in sec1_illus["anchor_paragraph"]
    assert "arch-topology.png" not in sec1_illus["anchor_paragraph"]


def test_wechat_distribution_duplicate_urls_deduplication():
    """Verifies that identical URLs referenced across multiple sections share the same footnote index."""
    engine = CognitiveEngine()
    article = (
        "# ??????\n\n"
        "???????????????\n\n"
        "## ???\n"
        "?????? [DeepSeek ??](https://deepseek.com) ?????\n\n"
        "## ???\n"
        "???? [DeepSeek ??](https://deepseek.com/) ???\n\n"
        "## ???\n"
        "???? [Python??](https://python.org) ?????"
    )

    output = engine.distribute_content(content=article, platforms=["wechat"])
    assert output.get("success") is True
    wechat = output["platforms"]["wechat"]
    content = wechat["content"]
    footnotes = wechat.get("footnotes", [])

    # Exactly 2 footnotes: deepseek.com and python.org (deepseek duplicate is merged)
    assert len(footnotes) == 2
    assert footnotes[0]["index"] == 1
    assert "deepseek.com" in footnotes[0]["url"]
    assert footnotes[1]["index"] == 2
    assert "python.org" in footnotes[1]["url"]

    # Both references to DeepSeek should cite [1]
    assert "DeepSeek ?? [1]" in content
    assert "DeepSeek ?? [1]" in content
    assert "Python?? [2]" in content

def test_xiaohongshu_card_budget_limits():
    """Verifies strict character budget limits on Xiaohongshu 3:4 cards."""
    engine = CognitiveEngine()
    long_article = (
        "# 深度剖析认知架构与思维模型的终极破局演进之路\n\n"
        "导读：这是一篇用来极限测试长文本截断与字符预算保护机制的超长篇幅深度干货文章。\n\n"
        "## 01. 传统线性思维在极端复杂环境下的致命缺陷与严重系统内耗剖析\n"
        "很多职场人士和知识创作者在面对复杂非线性系统时，往往习惯于沿用过去单向线性的思考定势，这种陈旧范式会导致执行链条严重拉长并且产生巨量的沟通冗余和精神内耗，最终陷入停滞不前的窘境。\n"
        "通过建立模块化反脆弱结构可以从根源上化解这种系统性风险并激活自组织创造力。\n"
        "定期复盘认知盲区是打破成长天花板的关键法门。\n\n"
        "## 02. 敏捷迭代与高密度认知输入对于个人IP打造的决定性驱动作用\n"
        "知识资产的积累绝对不是简单的信息堆砌，而是需要通过高频次的实战碰撞与认知反馈闭环来淬炼出真正具备穿透力的思考指纹与个人认知IP。\n"
        "小步快跑胜过旷日持久的完美主义幻想。\n"
        "在实践中快速拿到正向反馈是持续输出的动力之源。\n"
    )

    output = engine.distribute_content(content=long_article, platforms=["xiaohongshu"])
    assert output.get("success") is True
    xhs = output["platforms"]["xiaohongshu"]
    assert "cards" in xhs
    cards = xhs["cards"]
    assert len(cards) >= 3

    # Check body point cards
    point_cards = [c for c in cards if c.get("card_type") == "point"]
    assert len(point_cards) >= 2
    for c in point_cards:
        if c.get("pain_point_analysis"):
            assert len(c["pain_point_analysis"]) <= 85, f"pain_point_analysis too long: {len(c['pain_point_analysis'])}"
        if c.get("key_points"):
            for kp in c["key_points"]:
                assert len(kp) <= 80, f"key_point too long: {len(kp)}"
        if c.get("highlight"):
            assert len(c["highlight"]) <= 60, f"highlight too long: {len(c['highlight'])}"

    # Check summary card
    summary_cards = [c for c in cards if c.get("card_type") == "summary"]
    assert len(summary_cards) == 1
    sc = summary_cards[0]
    if sc.get("checklist"):
        for item in sc["checklist"]:
            assert len(item) <= 50, f"checklist item too long: {len(item)}"
    if sc.get("golden_quote"):
        assert len(sc["golden_quote"]) <= 70, f"golden_quote too long: {len(sc['golden_quote'])}"
