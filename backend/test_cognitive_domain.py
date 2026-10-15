import pytest
from app.domain.cognitive.models import (
    CognitiveDimension,
    CognitiveProfile,
    CognitiveTrait,
    TraitStatus,
)
from app.domain.creation.models import CreationWorkspace
from app.schemas.draft_schemas import CoreViewpoint, DraftOutput, ViewpointOption
from app.schemas.outline_schemas import Outline, OutlineOutput, OutlineSection


def test_cognitive_profile_creation():
    profile = CognitiveProfile(user_id="user_123")
    assert profile.user_id == "user_123"
    assert profile.traits == []


def test_add_and_reinforce_trait():
    profile = CognitiveProfile(user_id="user_123")

    # Add new trait
    trait1 = profile.add_or_reinforce_trait(
        dimension=CognitiveDimension.VOCABULARY,
        statement="深入浅出",
        source_draft_id="draft_001",
    )
    assert trait1.dimension == CognitiveDimension.VOCABULARY
    assert trait1.statement == "深入浅出"
    assert trait1.confidence_score == 1.0
    assert trait1.status == TraitStatus.ACTIVE
    assert trait1.source_draft_id == "draft_001"
    assert len(profile.traits) == 1

    # Reinforce existing trait with whitespace/case variation
    reinforced = profile.add_or_reinforce_trait(
        dimension=CognitiveDimension.VOCABULARY,
        statement="  深入浅出  ",
    )
    assert reinforced.id == trait1.id
    assert reinforced.confidence_score == 1.5
    assert len(profile.traits) == 1

    # Add another trait under a different dimension
    trait2 = profile.add_or_reinforce_trait(
        dimension=CognitiveDimension.LOGIC_PREFERENCE,
        statement="金字塔结构",
    )
    assert trait2.id != trait1.id
    assert trait2.confidence_score == 1.0
    assert len(profile.traits) == 2


def test_pin_unpin_suppress_trait():
    profile = CognitiveProfile(user_id="user_123")
    trait = profile.add_or_reinforce_trait(
        dimension=CognitiveDimension.CORE_VALUE,
        statement="以用户为中心",
    )

    # Pin trait
    success = profile.pin_trait(trait.id)
    assert success is True
    assert trait.status == TraitStatus.PINNED
    assert trait.confidence_score == 2.0

    # Unpin trait
    success = profile.unpin_trait(trait.id)
    assert success is True
    assert trait.status == TraitStatus.ACTIVE

    # Suppress trait
    success = profile.suppress_trait(trait.id)
    assert success is True
    assert trait.status == TraitStatus.SUPPRESSED

    # Non-existent trait id operations
    assert profile.pin_trait("non_existent_id") is False
    assert profile.unpin_trait("non_existent_id") is False
    assert profile.suppress_trait("non_existent_id") is False


def test_export_thinking_dna():
    profile = CognitiveProfile(user_id="user_123")

    # Add vocabulary traits
    t1 = profile.add_or_reinforce_trait(CognitiveDimension.VOCABULARY, "极简表达")
    t2 = profile.add_or_reinforce_trait(CognitiveDimension.VOCABULARY, "严谨精确")
    profile.add_or_reinforce_trait(CognitiveDimension.VOCABULARY, "严谨精确")  # score = 1.5

    # Add logic preference traits
    t3 = profile.add_or_reinforce_trait(CognitiveDimension.LOGIC_PREFERENCE, "归纳法")
    t4 = profile.add_or_reinforce_trait(CognitiveDimension.LOGIC_PREFERENCE, "第一性原理")
    profile.pin_trait(t4.id)  # pinned and confidence boosted to 2.0

    # Add core value and stance traits
    t5 = profile.add_or_reinforce_trait(CognitiveDimension.CORE_VALUE, "技术向善")
    t6 = profile.add_or_reinforce_trait(CognitiveDimension.VIEWPOINT_STANCE, "AI应辅助而非替代人类判断")

    # Add a suppressed trait that should be excluded
    t7 = profile.add_or_reinforce_trait(CognitiveDimension.VOCABULARY, "陈词滥调")
    profile.suppress_trait(t7.id)

    dna = profile.export_thinking_dna(summary="Author cognitive blueprint")

    # Verify vocabulary sorting (1.5 before 1.0) and exclusion of suppressed
    assert dna.vocabulary_habits == ["严谨精确", "极简表达"]
    assert "陈词滥调" not in dna.vocabulary_habits

    # Verify logic preference sorting (pinned 2.0 before 1.0)
    assert dna.logic_preferences == ["第一性原理", "归纳法"]

    # Verify core values contains active/pinned values and stances
    assert "技术向善" in dna.core_values
    assert "AI应辅助而非替代人类判断" in dna.core_values
    assert dna.summary == "Author cognitive blueprint"


def test_creation_workspace_outline_selection():
    workspace = CreationWorkspace(topic="AI Native Architecture")

    # Selecting outline before generation should raise ValueError
    with pytest.raises(ValueError, match="outlines have not been generated"):
        workspace.select_outline("A")

    workspace.outlines = OutlineOutput(
        outline_a=Outline(
            title="Conventional Architecture",
            rationale="Standard 3-tier",
            sections=[OutlineSection(title="Introduction", bullet_points=["Point 1"])],
        ),
        outline_b=Outline(
            title="Agentic Swarm Architecture",
            rationale="Autonomous agents",
            sections=[OutlineSection(title="Swarm Core", bullet_points=["Point 2"])],
        ),
    )

    # Select Option A
    selected_a = workspace.select_outline("A")
    assert selected_a.title == "Conventional Architecture"
    assert workspace.selected_outline_option == "A"

    # Select Option B (case-insensitive)
    selected_b = workspace.select_outline("b")
    assert selected_b.title == "Agentic Swarm Architecture"
    assert workspace.selected_outline_option == "B"

    # Invalid option should raise ValueError
    with pytest.raises(ValueError, match="Invalid outline option"):
        workspace.select_outline("C")


def test_creation_workspace_judgments_and_divergence():
    workspace = CreationWorkspace(
        topic="AI in Software Engineering",
        draft=DraftOutput(
            title="The Future of Coding",
            content="AI tools will fundamentally transform software engineering.",
            core_viewpoints=[
                CoreViewpoint(
                    id="vp_1",
                    claim="AI tools will replace junior developers",
                    options=[
                        ViewpointOption(key="agree", label="认同", text="AI tools will replace junior developers"),
                        ViewpointOption(key="counter", label="反驳", text="AI tools empower rather than replace developers"),
                    ],
                )
            ],
        ),
        user_final_draft="AI tools will fundamentally transform software engineering.",
    )

    # Initially identical drafts and no judgments: no divergence
    assert workspace.has_cognitive_divergence() is False

    # Apply agree judgment
    j1 = workspace.apply_viewpoint_judgment(
        viewpoint_id="vp_1",
        selected_key="agree",
        selected_text="AI tools will replace junior developers",
    )
    assert j1.claim == "AI tools will replace junior developers"
    assert j1.selected_key == "agree"
    assert workspace.has_cognitive_divergence() is False

    # Update judgment to counter -> divergence should become True
    j1_updated = workspace.apply_viewpoint_judgment(
        viewpoint_id="vp_1",
        selected_key="counter",
        selected_text="AI tools empower rather than replace developers",
    )
    assert j1_updated.selected_key == "counter"
    assert len(workspace.judgments) == 1
    assert workspace.has_cognitive_divergence() is True

    # Revert judgment back to agree -> divergence is False again
    workspace.apply_viewpoint_judgment(
        viewpoint_id="vp_1",
        selected_key="agree",
        selected_text="AI tools will replace junior developers",
    )
    assert workspace.has_cognitive_divergence() is False

    # User modifies text draft -> divergence should become True
    workspace.user_final_draft = "AI tools will transform developer workflows, but human creativity remains central."
    assert workspace.has_cognitive_divergence() is True

    # Restore matching text, but add custom note to judgment -> divergence should become True
    workspace.user_final_draft = "AI tools will fundamentally transform software engineering."
    workspace.apply_viewpoint_judgment(
        viewpoint_id="vp_1",
        selected_key="agree",
        selected_text="AI tools will replace junior developers",
        custom_note="Only in repetitive routine coding tasks",
    )
    assert workspace.has_cognitive_divergence() is True
