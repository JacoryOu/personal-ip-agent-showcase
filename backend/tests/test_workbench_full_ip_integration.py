import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.core.db import get_readonly_session, get_session
from app.core.model_gateway import ModelGateway, ModelRole
from app.domain.cognitive.models import (
    CognitiveDimension,
    CognitiveProfile,
    CognitiveTrait,
    TraitStatus,
)
from app.engine.agents.draft_agent import DraftAgent
from app.engine.agents.outline_agent import OutlineAgent
from app.engine.cognitive_engine import CognitiveEngine
from app.engine.prompts.dna_context import (
    format_dna_prompt_section,
    format_full_ip_context_prompt,
)
from app.main import app
from app.models.draft import Draft
from app.models.persona import IPPersona, PERSONA_PRESETS
from app.models.product import ProductVault, PRODUCT_PRESETS
from app.models.story import EpisodicStory
from app.models.user import User
from app.schemas.diff_schemas import ThinkingDNA
from app.schemas.draft_schemas import (
    BlueprintDraftInput,
    CoreViewpoint,
    DraftInput,
    DraftOutput,
    ViewpointOption,
)
from app.schemas.outline_schemas import (
    Outline,
    OutlineInput,
    OutlineOutput,
    OutlineSection,
)
from app.services.cognitive_service import CognitiveService
from app.services.memory_service import MemoryService, naturalize_time_expression


# ---------------------------------------------------------------------------
# Test Fixtures & DB Setup
# ---------------------------------------------------------------------------

@pytest.fixture(name="mem_engine")
def mem_engine_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="db_session")
def db_session_fixture(mem_engine):
    with Session(mem_engine) as session:
        yield session


# ---------------------------------------------------------------------------
# 1. Prompt Assembler Unit Tests
# ---------------------------------------------------------------------------

def test_format_full_ip_context_prompt_complete():
    persona = IPPersona(
        name="中医食疗调理实践者",
        target_audience="25-45岁都市亚健康女性",
        tone_style="温润从容、专业克制",
        reader_salutation="调养搭子",
        origin_story="源自三年自身慢性脾胃病的食疗自救历程",
    )
    dna = ThinkingDNA(
        vocabulary_habits=["内养", "节律", "顺时而食"],
        logic_preferences=["因果溯源", "辩证分析"],
        core_values=["身心不二", "治未病"],
        summary="倡导温和、无痛、可持续的生活化养生哲学",
    )
    now = datetime.now(timezone.utc)
    story1 = EpisodicStory(
        title="脾胃调理的转折点",
        story_content="早年经常胃胀气，尝试过各种极端断食，后来才领悟温和润养之道。",
        story_type="failure_reflection",
        occurred_at=now - timedelta(days=200),
        tags=["脾胃调理", "断食反思"],
    )
    product = ProductVault(
        product_name="新会五年陈皮老白茶",
        category="养生茶饮",
        core_ingredients="新会大红柑陈皮、福鼎老白茶",
        suitable_conditions="饭后腹胀、脾胃湿寒、痰湿体质",
        taboos="阴虚火旺慎服",
        personal_usage_experience="每次吃完大餐后喝一杯，15分钟内胃胀感明显缓解，身体通透温暖。",
        conversion_hooks="五年醇化，温润不燥，日常代茶饮无负担。",
    )

    prompt = format_full_ip_context_prompt(
        thinking_dna=dna,
        persona=persona,
        stories=[story1],
        product=product,
        dna_evolution_notes=["V2: 从单纯清湿热演进至温补脾阳为主"],
        time_narrative_mode="fuzzy",
    )

    # 1. Four section headers must exist
    assert "=== 👤 创作者 IP 人设与灵魂定位 (IP PERSONA) ===" in prompt
    assert "=== 🧠 认知底色与演进树 (THINKING DNA 2.0) ===" in prompt
    assert "=== USER'S COGNITIVE PROFILE & THINKING DNA" in prompt
    assert "=== 📖 真实个人经历与案例背书 (EPISODIC STORIES) ===" in prompt
    assert "=== 📦 交付方案与产品心智 (PRODUCT VAULT) ===" in prompt

    # 2. Persona details
    assert "中医食疗调理实践者" in prompt
    assert "调养搭子" in prompt
    assert "温润从容、专业克制" in prompt
    assert "自身慢性脾胃病" in prompt

    # 3. DNA details
    assert "内养" in prompt
    assert "因果溯源" in prompt
    assert "身心不二" in prompt
    assert "从单纯清湿热演进至温补脾阳为主" in prompt

    # 4. Stories & Natural Time
    assert "脾胃调理的转折点" in prompt
    assert "之前有段时间" in prompt  # 200 days falls into "之前有段时间"
    assert "胃胀气" in prompt

    # 5. Product details
    assert "新会五年陈皮老白茶" in prompt
    assert "饭后腹胀、脾胃湿寒" in prompt
    assert "15分钟内胃胀感明显缓解" in prompt


def test_format_full_ip_context_prompt_empty_and_partial():
    # Empty case
    assert format_full_ip_context_prompt() == ""
    assert format_dna_prompt_section() == ""

    # Partial case: only Persona
    persona = IPPersona(name="极简内养IP", reader_salutation="同行者")
    p1 = format_full_ip_context_prompt(persona=persona)
    assert "=== 👤 创作者 IP 人设与灵魂定位" in p1
    assert "极简内养IP" in p1
    assert "同行者" in p1
    assert "=== 📦 交付方案" not in p1


# ---------------------------------------------------------------------------
# 2. Agent Prompt Injection Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_outline_agent_injects_full_ip_context():
    captured_messages = []

    mock_gateway = ModelGateway()
    async def mock_generate(*args, **kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        return OutlineOutput(
            outline_a=Outline(title="大纲A", sections=[]),
            outline_b=Outline(title="大纲B", sections=[]),
        )

    mock_gateway.generate_structured = mock_generate
    agent = OutlineAgent(gateway=mock_gateway)

    persona = IPPersona(name="职场精力管理师", reader_salutation="精力满格伙伴")
    dna = ThinkingDNA(vocabulary_habits=["微习惯重塑", "能量循环"])
    story = EpisodicStory(title="连续加班崩溃切片", story_content="连续3个月高强度加班后身体报警")

    inp = OutlineInput(
        topic="打工人如何抵抗慢性疲劳",
        thinking_dna=dna,
        persona=persona,
        stories=[story],
    )
    result = await agent.generate_outlines(inp)

    assert result.outline_a.title == "大纲A"
    assert len(captured_messages) == 1
    content = captured_messages[0]["content"]

    assert "Topic: 打工人如何抵抗慢性疲劳" in content
    assert "=== 👤 创作者 IP 人设与灵魂定位 (IP PERSONA) ===" in content
    assert "职场精力管理师" in content
    assert "精力满格伙伴" in content
    assert "=== 🧠 认知底色与演进树 (THINKING DNA 2.0) ===" in content
    assert "微习惯重塑" in content
    assert "=== 📖 真实个人经历与案例背书 (EPISODIC STORIES) ===" in content
    assert "连续加班崩溃切片" in content


@pytest.mark.asyncio
async def test_draft_agent_injects_full_ip_context_and_records_metadata():
    captured_messages = []

    mock_gateway = ModelGateway()
    async def mock_generate(*args, **kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        return DraftOutput(
            title="以微习惯告别慢性疲劳",
            summary="文章纲要",
            content="# 以微习惯告别慢性疲劳\n\n精力满格伙伴，你好！",
            word_count=60,
            core_viewpoints=[CoreViewpoint(id="vp_1", claim="恢复精力需重构能量循环", options=[])],
        )

    mock_gateway.generate_structured = mock_generate
    agent = DraftAgent(gateway=mock_gateway)

    persona = IPPersona(id=uuid.uuid4(), name="职场女性精力主理人", reader_salutation="亲爱的精力伙伴")
    product = ProductVault(id=uuid.uuid4(), product_name="草本滋补饮", category="功能茶饮")
    story_id = str(uuid.uuid4())

    outline = Outline(
        title="大纲结构",
        rationale="从痛点到解法",
        sections=[OutlineSection(title="第一阶段", bullet_points=["审视日常能量消耗"])]
    )

    inp = DraftInput(
        topic="如何摆脱职场内耗与疲劳",
        outline=outline,
        persona=persona,
        persona_id=str(persona.id),
        product=product,
        product_id=str(product.id),
        story_ids=[story_id],
    )

    draft_res = await agent.generate_draft(inp)

    assert draft_res.title == "以微习惯告别慢性疲劳"
    assert draft_res.persona_id == str(persona.id)
    assert draft_res.product_id == str(product.id)
    assert draft_res.story_ids == [story_id]

    content = captured_messages[0]["content"]
    assert "职场女性精力主理人" in content
    assert "草本滋补饮" in content


# ---------------------------------------------------------------------------
# 3. CognitiveEngine Four-in-One Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cognitive_engine_explore_outlines_auto_binds_full_ip(db_session):
    test_user_id = uuid.uuid4()
    user = User(id=test_user_id, username="ip_tester")
    db_session.add(user)

    # 1. Create active persona
    active_persona = IPPersona(
        user_id=test_user_id,
        name="循证营养与生活医学家",
        target_audience="受代谢紊乱困扰的久坐上班族",
        tone_style="科学严谨且富有人文关怀",
        reader_salutation="身心健康合伙人",
        origin_story="从病房临床走向慢病生活方式干预",
        is_active=True,
    )
    db_session.add(active_persona)

    # 2. Create Episodic Story
    story = EpisodicStory(
        user_id=test_user_id,
        title="关于血糖震荡的亲测记录",
        story_content="连续佩戴动态血糖仪30天，发现早餐吃高GI精制碳水导致午后断崖式犯困。",
        story_type="daily_life",
        occurred_at=datetime.now(timezone.utc) - timedelta(days=45),
        tags=["血糖管理", "饮食记录"],
        confidence_score=1.0,
    )
    db_session.add(story)

    # 3. Create Product
    product = ProductVault(
        user_id=test_user_id,
        product_name="低GI慢消化复合谷物粉",
        category="代餐冲饮",
        core_ingredients="燕麦麸皮、青稞、白芸豆提取物",
        suitable_conditions="餐后血糖波动大、下午易犯困嗜睡",
        personal_usage_experience="早晨冲泡一杯，饱腹感持续到中午，下午精神明显平稳。",
        conversion_hooks="无添加蔗糖，双重控糖黑科技。",
        is_active=True,
    )
    db_session.add(product)

    # 4. Cognitive Profile & Trait
    profile = CognitiveProfile(user_id=str(test_user_id))
    trait = CognitiveTrait(
        dimension=CognitiveDimension.VOCABULARY,
        statement="稳态胰岛素反应",
        confidence_score=1.5,
        version=2,
        evolution_reason="由关注单纯热量摄入演变为关注激素调节稳态",
    )
    profile.traits.append(trait)
    CognitiveService.save_profile(db_session, user, profile)
    db_session.commit()

    captured_payloads = []
    class MockOutlineAgent(OutlineAgent):
        async def generate_outlines(self, input_data: OutlineInput) -> OutlineOutput:
            captured_payloads.append(input_data)
            return OutlineOutput(
                outline_a=Outline(title="血糖平稳篇", sections=[]),
                outline_b=Outline(title="精力唤醒篇", sections=[]),
            )

    engine = CognitiveEngine()
    result = await engine.explore_outlines(
        topic="如何改善早餐后犯困与血糖震荡",
        user_id=test_user_id,
        agent=MockOutlineAgent(),
        readonly_session=db_session,
    )

    assert result.outline_a.title == "血糖平稳篇"
    assert len(captured_payloads) == 1
    payload = captured_payloads[0]

    # Verify four-in-one binding in OutlineInput
    assert payload.persona_id == str(active_persona.id)
    assert payload.persona.name == "循证营养与生活医学家"
    assert payload.product_id == str(product.id)
    assert len(payload.story_ids) >= 1
    assert payload.story_ids[0] == str(story.id)

    # Verify assembled IP prompt
    prompt = payload.ip_context_prompt
    assert "循证营养与生活医学家" in prompt
    assert "身心健康合伙人" in prompt
    assert "关于血糖震荡的亲测记录" in prompt
    assert "低GI慢消化复合谷物粉" in prompt
    assert "稳态胰岛素反应" in prompt
    assert "由关注单纯热量摄入演变为关注激素调节稳态" in prompt


@pytest.mark.asyncio
async def test_cognitive_engine_generate_draft_full_ip_binding(db_session):
    test_user_id = uuid.uuid4()
    user = User(id=test_user_id, username="draft_ip_user")
    db_session.add(user)

    persona = IPPersona(
        user_id=test_user_id,
        name="身心整合疗愈导师",
        tone_style="深邃、柔和、有力",
        reader_salutation="同频旅人",
        origin_story="十年正念实践与神经科学探索",
        is_active=True,
    )
    db_session.add(persona)

    story = EpisodicStory(
        user_id=test_user_id,
        title="雪山下的静修体悟",
        story_content="在海拔4000米的高原闭关七天，真正感受到了呼吸与情绪节奏的联结。",
        occurred_at=datetime.now(timezone.utc) - timedelta(days=100),
        tags=["正念", "情绪疗愈"],
    )
    db_session.add(story)
    db_session.commit()

    captured_draft_inputs = []
    class MockDraftAgent(DraftAgent):
        async def generate_draft(self, input_data: DraftInput) -> DraftOutput:
            captured_draft_inputs.append(input_data)
            return DraftOutput(
                title="在高压生活中找回呼吸的节律",
                summary="正念与神经调节",
                content="# 在高压生活中找回呼吸的节律\n\n同频旅人，请停下片刻。",
                word_count=100,
                core_viewpoints=[CoreViewpoint(id="vp_1", claim="深呼吸可瞬时重置自主神经", options=[])],
            )

    outline = Outline(
        title="呼吸疗愈指南",
        rationale="从生理机制到日常练习",
        sections=[OutlineSection(title="第一节：被忽视的呼吸模式", bullet_points=["浅短胸式呼吸的危害"])]
    )

    engine = CognitiveEngine()
    draft_res = await engine.generate_draft(
        topic="如何通过呼吸重塑焦虑神经回路",
        outline=outline,
        user_id=test_user_id,
        agent=MockDraftAgent(),
        readonly_session=db_session,
        session=db_session,
    )

    assert draft_res.title == "在高压生活中找回呼吸的节律"
    assert draft_res.persona_id == str(persona.id)
    assert len(draft_res.story_ids) >= 1
    assert str(story.id) in draft_res.story_ids

    # Verify Draft persisted into DB
    saved_draft = db_session.get(Draft, uuid.UUID(draft_res.id))
    assert saved_draft is not None
    assert saved_draft.metadata_["persona_id"] == str(persona.id)
    assert str(story.id) in saved_draft.metadata_["story_ids"]


# ---------------------------------------------------------------------------
# 4. API Endpoints Schema Acceptance Tests
# ---------------------------------------------------------------------------

def test_api_outlines_and_drafts_accept_four_in_one_fields(mem_engine):
    def get_test_session():
        with Session(mem_engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    app.dependency_overrides[get_readonly_session] = get_test_session
    client = TestClient(app)

    # 1. Test /api/outlines/generate accepts persona_id, product_id, story_ids
    test_pid = str(uuid.uuid4())
    test_prid = str(uuid.uuid4())
    test_sid = str(uuid.uuid4())

    mock_gateway = ModelGateway()
    async def mock_outline_gen(*args, **kwargs):
        return OutlineOutput(
            outline_a=Outline(title="A", sections=[]),
            outline_b=Outline(title="B", sections=[]),
        )
    async def mock_draft_gen(*args, **kwargs):
        return DraftOutput(
            title="Draft Title",
            summary="Summary",
            content="# Draft Content",
            word_count=50,
            core_viewpoints=[],
        )

    mock_gateway.generate_structured = mock_outline_gen
    from app.api.outlines import get_outline_agent
    from app.api.drafts import get_draft_agent
    app.dependency_overrides[get_outline_agent] = lambda: OutlineAgent(gateway=mock_gateway)
    app.dependency_overrides[get_draft_agent] = lambda: DraftAgent(gateway=mock_gateway)

    res_outline = client.post(
        "/api/outlines/generate",
        json={
            "topic": "中医调养春季排毒",
            "persona_id": test_pid,
            "product_id": test_prid,
            "story_ids": [test_sid],
        }
    )
    assert res_outline.status_code == 200
    assert "outline_a" in res_outline.json()

    # 2. Test /api/drafts/generate accepts persona_id, product_id, story_ids
    mock_gateway.generate_structured = mock_draft_gen
    res_draft = client.post(
        "/api/drafts/generate",
        json={
            "topic": "中医调养春季排毒",
            "outline": {
                "title": "春季排毒",
                "rationale": "顺天应时",
                "sections": [{"title": "肝木生发", "bullet_points": ["早睡早起"]}]
            },
            "persona_id": test_pid,
            "product_id": test_prid,
            "story_ids": [test_sid],
        }
    )
    assert res_draft.status_code == 200
    draft_data = res_draft.json()
    assert draft_data["title"] == "Draft Title"

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. Robustness & Edge-Case Verification Tests (Anti-Regression & Attack Tests)
# ---------------------------------------------------------------------------

def test_retrieve_relevant_stories_safe_datetime_sorting(db_session):
    """Verifies that tie-score story ranking safely sorts mixed naive, aware, and old/none occurred_at."""
    u_id = uuid.uuid4()
    user = User(id=u_id, username="dt_test_user")
    db_session.add(user)

    now = datetime.now(timezone.utc)
    # 1. Recent aware datetime
    s1 = EpisodicStory(
        user_id=u_id,
        title="Recent Aware Story",
        story_content="Irrelevant content 1",
        occurred_at=now,
        confidence_score=1.0,
    )
    # 2. Intermediate naive datetime (would crash with TypeError without timezone normalization)
    s2 = EpisodicStory(
        user_id=u_id,
        title="Naive Datetime Story",
        story_content="Irrelevant content 2",
        occurred_at=datetime(2024, 6, 1, 12, 0, 0),
        confidence_score=1.0,
    )
    # 3. Older aware datetime
    s3 = EpisodicStory(
        user_id=u_id,
        title="Old Story",
        story_content="Irrelevant content 3",
        occurred_at=datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        confidence_score=1.0,
    )
    db_session.add_all([s1, s2, s3])
    db_session.commit()

    # Query with a completely unrelated topic so lexical and semantic match are 0 for all
    # All stories tie at score = 0.1, forcing secondary sort by occurred_at
    stories = MemoryService.retrieve_relevant_stories(
        topic="完全无关的量子力学与拓扑学话题",
        user_id=u_id,
        limit=3,
        session=db_session,
    )
    assert len(stories) == 3
    # Most recent should be first (aware now > 2024 naive > 2020)
    assert stories[0].id == s1.id
    assert stories[1].id == s2.id
    assert stories[2].id == s3.id


def test_multi_tenant_persona_and_story_isolation(db_session):
    """Verifies that User B cannot inadvertently leak or query User A's private IP persona or stories."""
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()

    db_session.add(User(id=user_a_id, username="user_a"))
    db_session.add(User(id=user_b_id, username="user_b"))

    persona_a = IPPersona(
        user_id=user_a_id,
        name="User A Private Secret IP",
        reader_salutation="A的信徒",
        is_active=True,
    )
    story_a = EpisodicStory(
        user_id=user_a_id,
        title="User A Private Story",
        story_content="User A confidential experience",
    )
    prod_a = ProductVault(
        user_id=user_a_id,
        product_name="User A Exclusive Elixir",
        is_active=True,
    )
    db_session.add_all([persona_a, story_a, prod_a])
    db_session.commit()

    engine = CognitiveEngine()
    # User B assembles IP bundle without specifying IDs
    bundle_b = engine._assemble_ip_bundle(
        topic="普通话题",
        sess=db_session,
        user_id=user_b_id,
    )

    # User B must NOT receive User A's persona, story, or product
    assert bundle_b["persona"].id != persona_a.id
    assert bundle_b["persona"].name != "User A Private Secret IP"
    assert bundle_b["persona"].name == PERSONA_PRESETS[0].name

    assert not any(s.id == story_a.id for s in bundle_b["stories"])
    assert bundle_b["product"] is None or bundle_b["product"].id != prod_a.id

    # User B explicitly tries to pass User A's story_id
    stories_attempt = MemoryService.retrieve_relevant_stories(
        topic="普通话题",
        user_id=user_b_id,
        story_ids=[str(story_a.id)],
        session=db_session,
    )
    # Must reject cross-tenant story access
    assert len(stories_attempt) == 0


@pytest.mark.asyncio
async def test_product_vault_relevance_gating_and_opt_out(db_session):
    """Verifies that single active product is NOT force-injected into unrelated topics, and opt-out works."""
    u_id = uuid.uuid4()
    db_session.add(User(id=u_id, username="prod_gating_user"))

    product = ProductVault(
        user_id=u_id,
        product_name="健脾温中调理茶",
        category="草本养生茶饮",
        core_ingredients="生姜、红枣、茯苓",
        suitable_conditions="脾胃虚寒、食欲不振、腹胀腹泻",
        is_active=True,
    )
    db_session.add(product)
    db_session.commit()

    engine = CognitiveEngine()

    # 1. Unrelated topic: should NOT bind product even though len(active_prods) == 1
    bundle_unrelated = engine._assemble_ip_bundle(
        topic="Python异步并发事件循环机制剖析与实战演练",
        sess=db_session,
        user_id=u_id,
    )
    assert bundle_unrelated["product"] is None
    assert "健脾温中调理茶" not in bundle_unrelated["ip_context_prompt"]

    # 2. Related topic: SHOULD bind product
    bundle_related = engine._assemble_ip_bundle(
        topic="冬天容易食欲不振且脾胃虚寒该如何调理",
        sess=db_session,
        user_id=u_id,
    )
    assert bundle_related["product"] is not None
    assert bundle_related["product"].id == product.id
    assert "健脾温中调理茶" in bundle_related["ip_context_prompt"]

    # 3. Explicit opt-out via product_id="none"
    bundle_opt_out = engine._assemble_ip_bundle(
        topic="冬天容易食欲不振且脾胃虚寒该如何调理",
        sess=db_session,
        user_id=u_id,
        product_id="none",
    )
    assert bundle_opt_out["product"] is None
    assert "健脾温中调理茶" not in bundle_opt_out["ip_context_prompt"]


def test_format_full_ip_context_prompt_invisible_mode():
    """Verifies that invisible time mode omits '时间修辞：' from story descriptions."""
    now = datetime.now(timezone.utc)
    story = EpisodicStory(
        title="无时间痕迹故事",
        story_content="故事细节内容",
        occurred_at=now,
    )
    prompt_invisible = format_full_ip_context_prompt(
        stories=[story],
        time_narrative_mode="invisible",
    )
    assert "无时间痕迹故事" in prompt_invisible
    assert "时间修辞：" not in prompt_invisible
    assert "之前" not in prompt_invisible


@pytest.mark.asyncio
async def test_generate_from_blueprint_full_ip_binding(db_session):
    """Verifies that 爆款拆骨二创 (generate_from_blueprint) fully binds IP Persona, Thinking DNA, Stories, and Product."""
    u_id = uuid.uuid4()
    db_session.add(User(id=u_id, username="blueprint_ip_user"))

    persona = IPPersona(
        user_id=u_id,
        name="极简商业认知教练",
        reader_salutation="创业进化伙伴",
        tone_style="一针见血、逻辑严密",
        origin_story="穿越两次互联网周期破产重生的认知复盘",
        is_active=True,
    )
    story = EpisodicStory(
        user_id=u_id,
        title="现金流断裂的惊魂48小时",
        story_content="公司账面仅剩最后半个月工资时的生死谈判与战略收缩。",
        occurred_at=datetime.now(timezone.utc) - timedelta(days=300),
        tags=["创业生死", "现金流"],
    )
    product = ProductVault(
        user_id=u_id,
        product_name="商业模式破局咨询工作坊",
        category="咨询服务",
        suitable_conditions="业务陷入增长瓶颈、商业模式盈利迟缓",
        core_ingredients="1对1商业骨架诊断、现金流压力测试模型",
        personal_usage_experience="亲自验证过的反脆弱模型，帮30+初创团队避开现金流深坑。",
        is_active=True,
    )
    db_session.add_all([persona, story, product])
    db_session.commit()

    captured_inputs = []
    mock_gateway = ModelGateway()
    async def mock_generate(*args, **kwargs):
        captured_inputs.extend(kwargs.get("messages", []))
        return DraftOutput(
            title="拆解爆款骨架后的认知跃迁",
            summary="商业模式反脆弱",
            content="# 拆解爆款骨架后的认知跃迁\n\n创业进化伙伴，你好！",
            word_count=80,
            core_viewpoints=[CoreViewpoint(id="vp_1", claim="现金流是初创企业的唯一血液", options=[])],
        )
    mock_gateway.generate_structured = mock_generate
    agent = DraftAgent(gateway=mock_gateway)

    blueprint = {
        "id": "bp_test_101",
        "title": "认知颠覆型商业长文",
        "hook_style": "提出99%创业者常犯的致命盲区",
        "emotional_arc": "痛点刺痛 ➔ 逻辑破局 ➔ 行动指南",
        "structural_stages": [
            "戳破致命幻想",
            "底层逻辑归因",
            "交付抗周期方案",
        ],
    }

    engine = CognitiveEngine()
    result = await engine.generate_from_blueprint(
        topic="初创企业如何度过业务现金流寒冬",
        blueprint=blueprint,
        user_id=u_id,
        agent=agent,
        readonly_session=db_session,
        session=db_session,
    )

    assert result.title == "拆解爆款骨架后的认知跃迁"
    assert result.persona_id == str(persona.id)
    assert result.product_id == str(product.id)
    assert str(story.id) in result.story_ids

    # Verify LLM prompt received both Blueprint bone instructions AND full IP Context
    user_prompt = captured_inputs[0]["content"]
    assert "对标爆款骨架约束 (Bone Architecture)" in user_prompt
    assert "认知颠覆型商业长文" in user_prompt
    assert "极简商业认知教练" in user_prompt
    assert "创业进化伙伴" in user_prompt
    assert "现金流断裂的惊魂48小时" in user_prompt
    assert "商业模式破局咨询工作坊" in user_prompt


@pytest.mark.asyncio
async def test_outline_agent_propagates_ip_fields_to_output():
    """Verifies that OutlineAgent.generate_outlines populates persona_id, product_id, story_ids in OutlineOutput."""
    mock_gateway = ModelGateway()
    async def mock_generate(*args, **kwargs):
        return OutlineOutput(
            outline_a=Outline(title="大纲A", sections=[]),
            outline_b=Outline(title="大纲B", sections=[]),
        )
    mock_gateway.generate_structured = mock_generate
    agent = OutlineAgent(gateway=mock_gateway)

    inp = OutlineInput(
        topic="测试大纲输出字段透传",
        persona_id="persona_123",
        product_id="prod_456",
        story_ids=["story_789"],
        ip_context_prompt="FULL_IP_PROMPT_MOCK",
    )
    out = await agent.generate_outlines(inp)

    assert out.persona_id == "persona_123"
    assert out.product_id == "prod_456"
    assert out.story_ids == ["story_789"]
    assert out.ip_context_prompt == "FULL_IP_PROMPT_MOCK"


def test_api_blueprint_endpoint_accepts_four_in_one_fields(mem_engine):
    """Verifies /api/drafts/generate-from-blueprint endpoint accepts persona_id, product_id, story_ids."""
    def get_test_session():
        with Session(mem_engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    app.dependency_overrides[get_readonly_session] = get_test_session
    client = TestClient(app)

    test_pid = str(uuid.uuid4())
    test_prid = str(uuid.uuid4())
    test_sid = str(uuid.uuid4())

    mock_gateway = ModelGateway()
    async def mock_draft_gen(*args, **kwargs):
        return DraftOutput(
            title="Blueprint Output",
            summary="Summary",
            content="# Blueprint Content",
            word_count=60,
            core_viewpoints=[],
        )
    mock_gateway.generate_structured = mock_draft_gen
    from app.api.drafts import get_draft_agent
    app.dependency_overrides[get_draft_agent] = lambda: DraftAgent(gateway=mock_gateway)

    res = client.post(
        "/api/drafts/generate-from-blueprint",
        json={
            "topic": "业务破局二创长文",
            "blueprint": {
                "title": "爆款骨架A",
                "structural_stages": ["阶段一", "阶段二"],
            },
            "persona_id": test_pid,
            "product_id": test_prid,
            "story_ids": [test_sid],
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Blueprint Output"

    app.dependency_overrides.clear()
