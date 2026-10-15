"""Deterministic evaluator for the viral semantic scoring rubric.

Why this module exists
----------------------
``viral_rubric.py`` defines what each 0-5 level *means*. It does not prove that
anything actually lands on the right level. This module pairs the rubric with a
small human-annotated benchmark and reports, per dimension:

- ``accuracy``       — within-one-level accuracy (|pred - gold| <= 1)
- ``mae``            — mean absolute error
- ``exact_match_rate`` — fraction of samples with |pred - gold| == 0

The scorer is fully deterministic: it reads the annotated ``features`` of each
benchmark sample and maps them to a level using the same evidence-first rule the
prompt states. **It never calls an LLM and never touches the network.** That
means it measures "does the rubric rule, as implemented, reproduce the
human-annotated labels for these cases?" — it is *not* an offline replay of
real model output and must not be reported as model accuracy. See
``docs/design/03_Viral_Semantic_Analysis.md`` for the honest status.

Evidence-first downgrade (deliberately preserved)
-------------------------------------------------
Every scorer starts at level 0 and only raises the level when the required
evidence feature is explicitly present and ``True``. Missing evidence can never
raise a score, and there is no "round up when between anchors" behaviour: an
unproven higher level always stays down. Calibration may adjust feature
interpretation, but must not remove these gates.

Between-anchors rule
--------------------
``_finalize`` implements the documented rule "when a case sits between two
anchors, choose the lower one unless the higher anchor's evidence is present".
So the score is the highest level whose evidence is fully satisfied.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

DIMENSIONS = ("hook_strength", "tension_level", "reuse_score")

DEFAULT_BENCHMARK_PATH = (
    Path(__file__).resolve().parent / "data" / "viral_rubric_benchmark_v1.json"
)

# Recommended acceptance gate, per dimension.
MAE_THRESHOLD = 0.8
EXACT_MATCH_THRESHOLD = 0.60

DIMENSION_FEATURE_KEYS = {
    "hook_strength": ("hook",),
    "tension_level": ("tension",),
    "reuse_score": ("reuse",),
}


def _levels(features: Optional[Dict[str, Any]], group: str) -> Dict[str, Any]:
    """Return the feature block for a dimension, or an empty dict."""
    if not isinstance(features, dict):
        return {}
    block = features.get(group)
    return block if isinstance(block, dict) else {}


def _evidence(level: int, block: Dict[str, Any], *keys: str) -> bool:
    """True only when *every* named evidence flag is explicitly True.

    Absent / falsy / non-boolean evidence never counts as proof.
    """
    for key in keys:
        if block.get(key) is not True:
            return False
    return True


def _finalize(block: Dict[str, Any], ladder: Sequence[tuple]) -> int:
    """Highest level whose full evidence ladder is satisfied, else 0.

    ``ladder`` is a tuple of ``(level, required_evidence_keys)`` ordered from 0
    upward. Lowering is always allowed, raising requires the evidence keys of
    that exact level to be present.
    """
    score = 0
    for level, keys in ladder:
        if not keys:  # level 0 always holds
            score = max(score, level)
            continue
        if _evidence(level, block, *keys):
            score = level
        else:
            break
    return score


HOOK_LADDER = (
    (0, ()),
    (1, ("states_topic",)),
    (2, ("mild_friction",)),
    (3, ("concrete_stake",)),
    (4, ("identity_money_status", "cost_or_promise_in_opening")),
    (5, ("identity_money_status", "cost_or_promise_in_opening", "unresolved_question", "commits_to_payoff")),
)

TENSION_LADDER = (
    (0, ()),
    (1, ("minor_complication",)),
    (2, ("problem_stated",)),
    (3, ("obstacle_or_deadline",)),
    (4, ("escalation",)),
    (5, ("peak_irreversible_pressure",)),
)

REUSE_LADDER = (
    (0, ()),
    (1, ("vague_shape",)),
    (2, ("shape_transfers",)),
    (3, ("two_mechanics_transfer",)),
    (4, ("devices_transfer",)),
    (5, ("voice_independent", "adaptation_notes")),
)


def score_hook(features: Dict[str, Any]) -> int:
    """Deterministic hook_strength score in 0-5."""
    return _finalize(_levels(features, "hook"), HOOK_LADDER)


def score_tension(features: Dict[str, Any]) -> int:
    """Deterministic tension_level score in 0-5."""
    return _finalize(_levels(features, "tension"), TENSION_LADDER)


def score_reuse(features: Dict[str, Any]) -> int:
    """Deterministic reuse_score in 0-5."""
    return _finalize(_levels(features, "reuse"), REUSE_LADDER)


SCORERS = {
    "hook_strength": score_hook,
    "tension_level": score_tension,
    "reuse_score": score_reuse,
}


def predict(sample: Dict[str, Any]) -> Dict[str, int]:
    """Predict all three dimensions for one benchmark sample."""
    features = sample.get("features") or {}
    return {dim: SCORERS[dim](features) for dim in DIMENSIONS}


def evaluate_dimension(gold_values: Sequence[int], predicted_values: Sequence[int]) -> Dict[str, Any]:
    """Metrics for one dimension. Accuracy is within-one-level accuracy."""
    if len(gold_values) != len(predicted_values):
        raise ValueError("gold/predicted length mismatch")
    if not gold_values:
        raise ValueError("empty sample set")

    errors = [abs(int(g) - int(p)) for g, p in zip(gold_values, predicted_values)]
    total = len(errors)
    within_one = sum(1 for e in errors if e <= 1)
    exact = sum(1 for e in errors if e == 0)
    return {
        "n": total,
        "accuracy": within_one / total,
        "mae": sum(errors) / total,
        "exact_match_rate": exact / total,
        "max_abs_error": max(errors),
        "errors": errors,
    }


def evaluate_benchmark(samples: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Evaluate every dimension; report metrics plus the pass/fail gate."""
    if not samples:
        raise ValueError("benchmark is empty")

    gold: Dict[str, List[int]] = {d: [] for d in DIMENSIONS}
    pred: Dict[str, List[int]] = {d: [] for d in DIMENSIONS}
    for sample in samples:
        gold_scores = sample["gold"]
        predicted = predict(sample)
        for dim in DIMENSIONS:
            gold[dim].append(int(gold_scores[dim]))
            pred[dim].append(int(predicted[dim]))

    dimensions: Dict[str, Any] = {}
    for dim in DIMENSIONS:
        metrics = evaluate_dimension(gold[dim], pred[dim])
        metrics.pop("errors")
        metrics["passed"] = (
            metrics["mae"] <= MAE_THRESHOLD and metrics["exact_match_rate"] >= EXACT_MATCH_THRESHOLD
        )
        dimensions[dim] = metrics

    return {
        "sample_count": len(samples),
        "thresholds": {
            "mae_max": MAE_THRESHOLD,
            "exact_match_rate_min": EXACT_MATCH_THRESHOLD,
            "accuracy_definition": "within_one_level",
        },
        "dimensions": dimensions,
        "passed": all(d["passed"] for d in dimensions.values()),
    }


def load_benchmark(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load and structurally validate the benchmark JSON."""
    target = Path(path) if path else DEFAULT_BENCHMARK_PATH
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "samples" not in payload:
        raise ValueError("benchmark file must be an object with a 'samples' array")
    samples = payload["samples"]
    if not isinstance(samples, list) or not samples:
        raise ValueError("benchmark 'samples' must be a non-empty array")

    seen_ids = set()
    for sample in samples:
        for key in ("id", "case", "annotation_note", "features", "gold"):
            if key not in sample:
                raise ValueError(f"sample missing '{key}': {sample.get('id')!r}")
        if sample["id"] in seen_ids:
            raise ValueError(f"duplicate sample id: {sample['id']!r}")
        seen_ids.add(sample["id"])
        gold = sample["gold"]
        for dim in DIMENSIONS:
            if dim not in gold:
                raise ValueError(f"sample {sample['id']!r} missing gold.{dim}")
            value = gold[dim]
            if not isinstance(value, int) or not 0 <= value <= 5:
                raise ValueError(f"sample {sample['id']!r} gold.{dim} out of range: {value!r}")
    return samples


def benchmark_metadata(path: Optional[Path] = None) -> Dict[str, Any]:
    """Return the non-sample header of the benchmark file."""
    target = Path(path) if path else DEFAULT_BENCHMARK_PATH
    payload = json.loads(target.read_text(encoding="utf-8"))
    return {k: v for k, v in payload.items() if k != "samples"}


def benchmark_report(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load the benchmark and return the full evaluation report."""
    samples = load_benchmark(path)
    report = evaluate_benchmark(samples)
    report["metadata"] = benchmark_metadata(path)
    return report
