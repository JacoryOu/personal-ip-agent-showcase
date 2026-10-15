import uuid
import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from app.domain.cognitive.models import (
    CognitiveDimension,
    CognitiveProfile,
    CognitiveTrait,
    TraitStatus,
)
from app.models.user import User
from app.services.cognitive_service import CognitiveService
from app.services.memory_service import MemoryService, Mem0Operation


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(username="mem0_test_user")
        session.add(user)
        session.commit()
        session.refresh(user)
        yield session


def test_mem0_lifecycle_add_update_noop():
    """Tests Mem0 triple: ADD new traits, UPDATE overlapping traits, and NOOP near-duplicates."""
    profile = CognitiveProfile(user_id="test_user", traits=[])
    
    # 1. ADD new trait
    op1, trait1 = MemoryService.apply_mem0_lifecycle(
        profile,
        CognitiveDimension.VOCABULARY,
        "\u504f\u597d\u4f7f\u7528\u6781\u7b80\u7684\u77ed\u53e5\u8868\u8fbe\u6838\u5fc3\u601d\u60f3",
    )
    assert op1 == Mem0Operation.ADD
    assert trait1.confidence_score == 1.0
    assert len(profile.traits) == 1
    
    # 2. UPDATE: overlapping refinement
    op2, trait2 = MemoryService.apply_mem0_lifecycle(
        profile,
        CognitiveDimension.VOCABULARY,
        "\u504f\u597d\u4f7f\u7528\u6781\u7b80\u7684\u77ed\u53e5\u8868\u8fbe\u6838\u5fc3\u89c2\u70b9\u4e0e\u601d\u60f3",
    )
    assert op2 == Mem0Operation.UPDATE
    assert trait2.id == trait1.id
    assert trait2.confidence_score == 1.5
    assert len(profile.traits) == 1
    
    # 3. NOOP: near-identical redundancy
    op3, trait3 = MemoryService.apply_mem0_lifecycle(
        profile,
        CognitiveDimension.VOCABULARY,
        "\u504f\u597d\u4f7f\u7528\u6781\u7b80\u7684\u77ed\u53e5\u8868\u8fbe\u6838\u5fc3\u89c2\u70b9\u4e0e\u601d\u60f3",
    )
    assert op3 == Mem0Operation.NOOP
    assert trait3.id == trait1.id
    assert len(profile.traits) == 1


def test_strict_content_source_separation(session: Session):
    """CRITICAL TEST: Verifies external benchmark articles NEVER contaminate user CognitiveProfile,
    whereas user's own works directly reinforce Thinking DNA.
    """
    user = session.exec(select(User)).first()
    
    # Check baseline profile traits
    initial_profile = CognitiveService.get_or_create_user_profile(session, user.id)
    initial_traits_count = len(initial_profile.traits)
    
    # Action 1: Deconstruct an external benchmark article
    benchmark_text = """
    \u5728\u672a\u6765\u4e94\u5e74\uff0c\u4f20\u7edf\u7684\u5355\u4f53\u5e94\u7528\u67b6\u6784\u5c06\u5f7b\u5e95\u6b7b\u4ea1\uff01\u6240\u6709\u4f01\u4e1a\u90fd\u5fc5\u987b\u5728\u4eca\u5e74\u5168\u9762\u6dd8\u6c70\u65e7\u6280\u672f\u3002
    \u552f\u4e00\u53ef\u884c\u7684\u51fa\u8def\u662f\u62e5\u62b1\u5206\u5e03\u5f0f\u667a\u80fd\u4f53\u96c6\u7fa4\u3002
    """
    bench_result = MemoryService.deconstruct_benchmark(
        content=benchmark_text,
        user_id=user.id,
        session=session,
        title="External Viral Article",
    )
    assert bench_result["success"] is True
    assert "blueprint" in bench_result
    assert len(bench_result["clash_points"]) >= 1
    
    # Verify profile traits were NOT altered (Zero Cognitive Pollution!)
    post_bench_profile = CognitiveService.get_or_create_user_profile(session, user.id)
    assert len(post_bench_profile.traits) == initial_traits_count, "Benchmark article polluted user CognitiveProfile!"
    
    # Verify blueprint was recorded in User.profile_data
    session.refresh(user)
    blueprints = (user.profile_data or {}).get("benchmark_blueprints", [])
    assert len(blueprints) == 1
    assert blueprints[0]["title"] == "External Viral Article"
    
    # Action 2: Ingest user's own historical essay
    own_work_text = """
    \u6211\u4eec\u5728\u67b6\u6784\u8bbe\u8ba1\u4e2d\u5fc5\u987b\u575a\u51b3\u53cd\u5bf9\u76f2\u76ee\u91cd\u6784\u3002\u5e95\u5c42\u903b\u8f91\u5728\u4e8e\uff0c\u6700\u7a33\u5065\u7684\u7cfb\u7edf\u5f80\u5f80\u662f\u81ea\u5e95\u5411\u4e0a\u6f14\u8fdb\u800c\u975e\u98a0\u8986\u51fa\u6765\u7684\u3002
    \u4ee3\u7801\u7684\u7b80\u6d01\u6027\u6c38\u8fdc\u9ad8\u4e8e\u865a\u6d6e\u7684\u6d41\u884c\u6846\u67b6\u3002
    """
    own_result = MemoryService.add_own_work_dna(
        content=own_work_text,
        user_id=user.id,
        session=session,
        title="My Pragmatic Architecture Essay",
    )
    assert own_result["success"] is True
    assert len(own_result["mem0_actions"][Mem0Operation.ADD]) >= 1
    
    # Verify profile traits accumulated user's true Thinking DNA
    post_own_profile = CognitiveService.get_or_create_user_profile(session, user.id)
    assert len(post_own_profile.traits) > initial_traits_count


def test_dialogue_clash_ingestion(session: Session):
    """Verifies capturing user's counter-arguments in debate into Thinking DNA."""
    user = session.exec(select(User)).first()
    
    messages = [
        {"role": "opponent", "content": "\u5fae\u670d\u52a1\u67b6\u6784\u662f\u6bcf\u4e00\u4e2a\u4e2d\u5927\u578b\u7cfb\u7edf\u7684\u552f\u4e00\u6b63\u786e\u9009\u62e9\u3002"},
        {"role": "user", "content": "\u6211\u5b8c\u5168\u4e0d\u540c\u610f\u8fd9\u4e2a\u8bba\u65ad\u3002\u8fc7\u5ea6\u5fae\u670d\u52a1\u5316\u662f\u56e2\u961f\u4ea7\u80fd\u4e0b\u964d\u7684\u5934\u53f7\u5143\u51f6\uff0c\u5355\u4f53\u4f18\u5148\u624d\u662f\u52a1\u5b9e\u4e4b\u4e3e\u3002"},
    ]
    
    result = MemoryService.record_dialogue_clash(
        messages=messages,
        user_id=user.id,
        debate_topic="\u5fae\u670d\u52a1\u4e0e\u5355\u4f53\u67b6\u6784\u4e4b\u4e89",
        session=session,
    )
    
    assert result["success"] is True
    assert len(result["recorded_stances"]) >= 1
    
    profile = CognitiveService.get_or_create_user_profile(session, user.id)
    stances = [t for t in profile.traits if t.dimension == CognitiveDimension.VIEWPOINT_STANCE]
    assert len(stances) >= 1


def test_contextual_dna_retrieval(session: Session):
    """Verifies dynamic topic-based cognitive DNA recall with Chinese semantic ranking."""
    user = session.exec(select(User)).first()
    profile = CognitiveService.get_or_create_user_profile(session, user.id)
    
    profile.add_or_reinforce_trait(CognitiveDimension.VOCABULARY, "经常使用第一性原理与溯源法")
    # Two competing traits in LOGIC_PREFERENCE
    profile.add_or_reinforce_trait(CognitiveDimension.LOGIC_PREFERENCE, "前端组件化与状态管理模式")
    profile.add_or_reinforce_trait(CognitiveDimension.LOGIC_PREFERENCE, "微服务架构与分布式拆分论证")
    profile.add_or_reinforce_trait(CognitiveDimension.CORE_VALUE, "极简工程主义")
    CognitiveService.save_profile(session, user, profile)
    
    # Query topic that matches '微服务' and '架构'
    dna = MemoryService.retrieve_contextual_dna(
        topic="微服务架构重构最佳实践",
        user_id=user.id,
        limit=1,
        session=session,
    )
    
    assert dna is not None
    assert len(dna.vocabulary_habits) >= 1
    assert len(dna.logic_preferences) == 1
    # Trait matching topic must be ranked first!
    assert dna.logic_preferences[0] == "微服务架构与分布式拆分论证"


def test_string_user_id_safety(session: Session):
    """Verifies that non-UUID string user IDs (e.g. 'alice_writer') do not throw ValueError."""
    custom_str_id = "alice_writer_99"
    
    res = MemoryService.add_own_work_dna(
        content="我们在系统设计中必须坚持简单性原则。底层逻辑是消除不必要的状态。",
        user_id=custom_str_id,
        session=session,
        title="Simplicity in Design",
    )
    assert res["success"] is True
    
    dna = MemoryService.retrieve_contextual_dna(
        topic="系统简单性",
        user_id=custom_str_id,
        session=session,
    )
    assert dna is not None
