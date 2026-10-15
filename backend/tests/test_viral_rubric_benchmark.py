"""Regression tests for the human-annotated viral rubric benchmark.

Scope honesty
-------------
These tests measure the *deterministic rubric evaluator* against hand-annotated
labels. They do **not** measure live-LLM accuracy: no model is called anywhere
in this path. What they lock down is (a) the benchmark dataset is structurally
valid and broad enough, (b) the evidence-first downgrade can never be
circumvented, and (c) the reported metrics are computed with the documented
definitions and hold against the recommended gate.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.engine.rubrics.viral_benchmark import (  # noqa: E402
    DEFAULT_BENCHMARK_PATH,
    DIMENSIONS,
    EXACT_MATCH_THRESHOLD,
    MAE_THRESHOLD,
    benchmark_metadata,
    benchmark_report,
    evaluate_benchmark,
    evaluate_dimension,
    load_benchmark,
    predict,
    score_hook,
    score_reuse,
    score_tension,
)
from app.engine.rubrics.viral_rubric import EVIDENCE_RULE, render_rubric_block  # noqa: E402
from app.engine.prompts.viral_prompts import VIRAL_ANALYSIS_SYSTEM_PROMPT  # noqa: E402


MIN_SAMPLES = 30


@pytest.fixture(scope="module")
def samples():
    return load_benchmark()


@pytest.fixture(scope="module")
def report():
    return benchmark_report()


# --------------------------------------------------------------------------
# Dataset structure
# --------------------------------------------------------------------------


def test_benchmark_has_at_least_minimum_samples(samples):
    assert len(samples) >= MIN_SAMPLES


def test_sample_ids_are_unique(samples):
    ids = [s["id"] for s in samples]
    assert len(ids) == len(set(ids))


def test_every_sample_has_annotation_note_and_case(samples):
    for s in samples:
        assert s["case"].strip(), s["id"]
        assert len(s["annotation_note"].strip()) > 20, s["id"]


def test_gold_scores_are_integers_in_range(samples):
    for s in samples:
        for dim in DIMENSIONS:
            value = s["gold"][dim]
            assert isinstance(value, int) and not isinstance(value, bool), (s["id"], dim)
            assert 0 <= value <= 5, (s["id"], dim)


def test_benchmark_covers_every_level_of_every_dimension(samples):
    for dim in DIMENSIONS:
        levels = {s["gold"][dim] for s in samples}
        assert levels == set(range(6)), f"{dim} missing levels: {sorted(levels)}"


def test_benchmark_includes_explicit_boundary_cases(samples):
    assert any("boundary" in s["case"] for s in samples)
    boundary = [s for s in samples if "boundary" in s["case"]]
    assert len(boundary) >= 4


def test_metadata_states_single_annotator_and_no_llm_replay():
    meta = benchmark_metadata()
    joined = " ".join(meta["known_limitations"]).lower()
    assert "single annotator" in joined
    assert "llm" in joined


def test_benchmark_file_is_valid_json_with_header():
    payload = json.loads(DEFAULT_BENCHMARK_PATH.read_text(encoding="utf-8"))
    for key in ("version", "title", "description", "dimensions", "coverage", "annotation_protocol"):
        assert key in payload
    assert list(payload["dimensions"]) == list(DIMENSIONS)


# --------------------------------------------------------------------------
# Evidence-first downgrade: the load-bearing guarantee
# --------------------------------------------------------------------------


def test_empty_features_score_zero_on_every_dimension():
    assert score_hook({}) == 0
    assert score_tension({}) == 0
    assert score_reuse({}) == 0
    assert score_hook(None) == 0


def test_missing_top_level_evidence_cannot_reach_five():
    # Everything except the level-5 requirement is present.
    features = {
        "hook": {
            "states_topic": True,
            "mild_friction": True,
            "concrete_stake": True,
            "identity_money_status": True,
            "cost_or_promise_in_opening": True,
            "unresolved_question": True,
            # commits_to_payoff deliberately absent
        }
    }
    assert score_hook(features) == 4


def test_gap_in_the_ladder_stops_scoring():
    # Level-4 evidence present but level-3 evidence missing: cannot jump the gap.
    features = {
        "hook": {
            "states_topic": True,
            "mild_friction": True,
            "concrete_stake": False,
            "identity_money_status": True,
            "cost_or_promise_in_opening": True,
        }
    }
    assert score_hook(features) == 2


@pytest.mark.parametrize("bad_value", [None, 1, "true", "yes", [], {}])
def test_non_boolean_evidence_is_not_accepted(bad_value):
    # A non-boolean must not count as proof for the level-1 anchor.
    assert score_tension({"tension": {"minor_complication": bad_value}}) == 0
    assert score_reuse({"reuse": {"vague_shape": bad_value}}) == 0
    # Sanity check that the value really would have raised the score if boolean.
    assert score_tension({"tension": {"minor_complication": True}}) == 1
    assert score_reuse({"reuse": {"vague_shape": True}}) == 1


def test_false_evidence_never_raises_a_score():
    assert score_tension({"tension": {"minor_complication": False}}) == 0
    assert score_hook({"hook": {"states_topic": False, "mild_friction": True}}) == 0


def test_tension_and_reuse_ladders_stop_at_missing_evidence():
    # Level-1 evidence present, level-2 explicitly false -> stop at 1.
    assert score_tension(
        {"tension": {"minor_complication": True, "problem_stated": False}}
    ) == 1
    # Level-2 evidence present, level-3 explicitly false -> stop at 2.
    assert score_reuse(
        {
            "reuse": {
                "vague_shape": True,
                "shape_transfers": True,
                "two_mechanics_transfer": False,
            }
        }
    ) == 2
    # Higher-level evidence without the lower level never skips ahead.
    assert score_tension(
        {"tension": {"problem_stated": True, "obstacle_or_deadline": True}}
    ) == 0


# --------------------------------------------------------------------------
# Metric definitions
# --------------------------------------------------------------------------


def test_evaluate_dimension_uses_within_one_accuracy():
    gold = [0, 3, 5, 2]
    pred = [1, 3, 4, 2]
    metrics = evaluate_dimension(gold, pred)
    assert metrics["errors"] == [1, 0, 1, 0]
    # accuracy counts |err| <= 1 -> all four
    assert metrics["accuracy"] == 1.0
    assert metrics["exact_match_rate"] == 0.5
    assert metrics["mae"] == pytest.approx(0.5)
    assert metrics["max_abs_error"] == 1


def test_evaluate_dimension_counts_large_errors_against_accuracy():
    metrics = evaluate_dimension([0, 5], [3, 1])
    assert metrics["accuracy"] == 0.0
    assert metrics["exact_match_rate"] == 0.0
    assert metrics["mae"] == pytest.approx(3.5)


def test_evaluate_dimension_rejects_mismatched_and_empty_input():
    with pytest.raises(ValueError):
        evaluate_dimension([1, 2], [1])
    with pytest.raises(ValueError):
        evaluate_dimension([], [])


def test_evaluate_benchmark_rejects_empty_sample_list():
    with pytest.raises(ValueError):
        evaluate_benchmark([])


def test_predict_covers_all_dimensions():
    predicted = predict({"features": {"hook": {}, "tension": {}, "reuse": {}}})
    assert set(predicted) == set(DIMENSIONS)
    assert all(v == 0 for v in predicted.values())


# --------------------------------------------------------------------------
# Gate
# --------------------------------------------------------------------------


def test_report_shape(report):
    assert report["sample_count"] >= MIN_SAMPLES
    assert set(report["dimensions"]) == set(DIMENSIONS)
    assert report["thresholds"]["mae_max"] == MAE_THRESHOLD
    assert report["thresholds"]["exact_match_rate_min"] == EXACT_MATCH_THRESHOLD
    assert report["thresholds"]["accuracy_definition"] == "within_one_level"


@pytest.mark.parametrize("dim", DIMENSIONS)
def test_each_dimension_meets_the_recommended_gate(report, dim):
    metrics = report["dimensions"][dim]
    assert metrics["n"] == report["sample_count"]
    assert metrics["accuracy"] == 1.0, f"{dim} within-one accuracy regressed"
    assert metrics["mae"] <= MAE_THRESHOLD, f"{dim} MAE regressed"
    assert metrics["exact_match_rate"] >= EXACT_MATCH_THRESHOLD, f"{dim} exact match regressed"
    assert metrics["max_abs_error"] <= 1, f"{dim} produced an off-by-more-than-one score"
    assert metrics["passed"] is True


def test_overall_gate_passes(report):
    assert report["passed"] is True


def test_gate_marks_failure_when_threshold_not_met():
    """A deliberately terrible evaluator must be reported as failing, not passed."""
    samples = [
        {
            "id": "x",
            "features": {
                "hook": {
                    "states_topic": True,
                    "mild_friction": True,
                    "concrete_stake": True,
                    "identity_money_status": True,
                    "cost_or_promise_in_opening": True,
                    "unresolved_question": True,
                    "commits_to_payoff": True,
                },
                "tension": {
                    "minor_complication": True,
                    "problem_stated": True,
                    "obstacle_or_deadline": True,
                    "escalation": True,
                    "peak_irreversible_pressure": True,
                },
                "reuse": {
                    "vague_shape": True,
                    "shape_transfers": True,
                    "two_mechanics_transfer": True,
                    "devices_transfer": True,
                    "voice_independent": True,
                    "adaptation_notes": True,
                },
            },
            "gold": {"hook_strength": 0, "tension_level": 0, "reuse_score": 0},
        }
    ]
    result = evaluate_benchmark(samples)
    assert result["dimensions"]["hook_strength"]["passed"] is False
    assert result["dimensions"]["hook_strength"]["mae"] > MAE_THRESHOLD
    assert result["passed"] is False


# --------------------------------------------------------------------------
# Determinism / no model, and the rubric text itself is untouched
# --------------------------------------------------------------------------


def test_evaluator_is_deterministic(samples):
    first = benchmark_report()["dimensions"]
    second = benchmark_report()["dimensions"]
    assert first == second


def test_evaluator_module_does_not_import_model_gateways():
    source = (Path(ROOT) / "app/engine/rubrics/viral_benchmark.py").read_text(encoding="utf-8")
    for forbidden in ("ModelGateway", "openai", "requests", "httpx", "anthropic", "http.client"):
        assert forbidden not in source, forbidden


def test_evidence_rule_and_between_anchors_rule_still_in_prompt():
    assert EVIDENCE_RULE in VIRAL_ANALYSIS_SYSTEM_PROMPT
    assert "report the lower level" in VIRAL_ANALYSIS_SYSTEM_PROMPT
    block = render_rubric_block()
    assert "choose the lower one" in block
