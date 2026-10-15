"""Regression tests for the viral scoring rubric.

These tests pin the *rule structure* and the prompt wiring. They are NOT a
human-labelled accuracy benchmark: score agreement with human judgement is
still unmeasured and stays Partial.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.engine.rubrics.viral_rubric import (  # noqa: E402
    EVIDENCE_RULE,
    HOOK_STRENGTH_RUBRIC,
    REUSE_SCORE_RUBRIC,
    TENSION_LEVEL_RUBRIC,
    render_rubric_block,
    rubric_anchor_map,
)
from app.engine.prompts.viral_prompts import VIRAL_ANALYSIS_SYSTEM_PROMPT  # noqa: E402
from app.schemas.viral_schemas import HookAnalysis, StructuralBeat, TransferAnalysis  # noqa: E402


RUBRICS = {
    "hook_strength": HOOK_STRENGTH_RUBRIC,
    "tension_level": TENSION_LEVEL_RUBRIC,
    "reuse_score": REUSE_SCORE_RUBRIC,
}


@pytest.mark.parametrize("name,rubric", sorted(RUBRICS.items()))
def test_rubric_has_six_levels(name, rubric):
    assert len(rubric) == 6, name
    for level, anchor in enumerate(rubric):
        assert anchor.strip(), f"{name} level {level} is empty"
        assert anchor.lstrip().startswith(str(level)), f"{name} level {level} mislabelled"


def test_render_block_contains_all_fields_and_evidence_rule():
    block = render_rubric_block()
    for name in RUBRICS:
        assert name in block
    assert EVIDENCE_RULE in block
    # Every anchor of every rubric must be present verbatim.
    for rubric in RUBRICS.values():
        for anchor in rubric:
            assert anchor in block


def test_anchor_map_keys():
    assert set(rubric_anchor_map()) == set(RUBRICS)


def test_prompt_injects_rubric_block():
    prompt = VIRAL_ANALYSIS_SYSTEM_PROMPT
    for name in RUBRICS:
        assert name in prompt
    assert EVIDENCE_RULE in prompt
    assert "report the lower level" in prompt


@pytest.mark.parametrize(
    "model,payload,field",
    [
        (HookAnalysis, {"hook_strength": 9}, "hook_strength"),
        (HookAnalysis, {"hook_strength": -4}, "hook_strength"),
        (StructuralBeat, {"tension_level": 42}, "tension_level"),
        (TransferAnalysis, {"reuse_score": 100}, "reuse_score"),
    ],
)
def test_out_of_range_scores_are_clamped(model, payload, field):
    obj = model(**payload)
    assert 0 <= getattr(obj, field) <= 5


@pytest.mark.parametrize("model", [HookAnalysis, StructuralBeat, TransferAnalysis])
def test_missing_score_defaults_to_zero_not_invented(model):
    obj = model()
    for field in ("hook_strength", "tension_level", "reuse_score"):
        if hasattr(obj, field):
            assert getattr(obj, field) == 0


def test_field_descriptions_state_evidence_requirement():
    assert "rubric-anchored" in HookAnalysis.model_fields["hook_strength"].description
    assert "rubric-anchored" in StructuralBeat.model_fields["tension_level"].description
    assert "rubric-anchored" in TransferAnalysis.model_fields["reuse_score"].description
