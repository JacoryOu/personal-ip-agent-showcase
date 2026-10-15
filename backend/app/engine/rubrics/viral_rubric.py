"""Scoring rubrics for viral semantic analysis.

Why this module exists
----------------------
The semantic breakdown layer emits three subjective 0-5 integers:

- ``HookAnalysis.hook_strength``
- ``StructuralBeat.tension_level``
- ``TransferAnalysis.reuse_score``

Those numbers previously had no written definition, so the model scored them on
impressions and the values drifted across prompts, models and articles. The
anchors below are the single source of truth for what each level means, and they
are injected verbatim into the analysis system prompt.

Honest status
-------------
The anchors define the scale and make every score auditable against a written
rule. They are **not** a human-labelled calibration set: a rubric removes
ambiguity, it does not prove the model's scores match human judgement. Treat
score accuracy as **Partial** until a human-annotated benchmark exists. See
``docs/design/03_Viral_Semantic_Analysis.md``.
"""

from typing import Dict, List, Tuple

# Evidence rule shared by every rubric below.
EVIDENCE_RULE = (
    "Evidence rule: raise a score only when the article text itself contains the "
    "concrete signal described in that level. If the evidence is missing, choose a "
    "lower level. Never score on overall quality, on how 'good' the writing feels, "
    "or on how interesting the topic is."
)

HOOK_STRENGTH_RUBRIC: Tuple[str, ...] = (
    "0 - No effective hook. The piece opens as pure background, meta-commentary "
    "about writing, throat-clearing, or an announcement with no stakes attached.",
    "1 - Background only. The opening states a topic or context. The reader gains "
    "no reason to continue.",
    "2 - Weak friction. A mild problem, doubt or mild surprise appears, but there "
    "is no clear promise of gain, no visible cost, and no open question the article "
    "commits to answering.",
    "3 - Clear stake. The opening commits to a concrete question, promise, loss or "
    "benefit that the reader can name after one sentence.",
    "4 - Strong pull. Curiosity, identity, money, status or a real cost is engaged "
    "in the first one to two sentences, and the opening text itself evidences it "
    "rather than merely implying it.",
    "5 - Compounding pull. Several of the above mechanisms stack in the opening "
    "(for example identity threat plus a concrete cost plus an unresolved question), "
    "and the piece clearly commits to cashing all of them out.",
)

TENSION_LEVEL_RUBRIC: Tuple[str, ...] = (
    "0 - Flat. Narration only; no unresolved question, obstacle or consequence is "
    "introduced.",
    "1 - Background friction. A minor complication is mentioned but does not "
    "threaten the outcome.",
    "2 - A problem is stated. The reader understands what could go wrong, but no "
    "cost is attached and nothing is at risk yet.",
    "3 - Stakes are visible. An obstacle, deadline, cost or opposing force is "
    "introduced and is not yet resolved.",
    "4 - Escalation. The situation worsens, a partial attempt fails, or an "
    "alternative is ruled out by evidence present in this beat.",
    "5 - Peak. Maximum irreversible pressure at this point in the article: the "
    "outcome is genuinely in doubt, or a decisive turn or realization lands here.",
)

REUSE_SCORE_RUBRIC: Tuple[str, ...] = (
    "0 - Not transferable. Every element is bound to this exact article's facts; "
    "another author could copy nothing.",
    "1 - Barely transferable. At most a vague structural shape survives the topic "
    "change.",
    "2 - Shape transfers. The overall skeleton can be reused on another topic, but "
    "the devices that made it work cannot.",
    "3 - Mechanism transfers. At least two concrete mechanics (for example hook "
    "formula, beat order, promise structure) work on another topic in the genre.",
    "4 - Most transfers. The full structure plus specific devices transfer; only "
    "surface wording is article-specific.",
    "5 - Fully reusable. The mechanics are topic- and voice-independent and "
    "adaptation_notes concretely explain how to port them.",
)


def _render(name: str, anchors: Tuple[str, ...]) -> str:
    lines = [f"{name} (0-5):"]
    lines.extend(f"  - {anchor}" for anchor in anchors)
    return "\n".join(lines)


def render_rubric_block() -> str:
    """Render the rubric block injected into the analysis system prompt."""
    return "\n\n".join(
        [
            EVIDENCE_RULE,
            _render("hook_strength", HOOK_STRENGTH_RUBRIC),
            _render("tension_level (per structural beat)", TENSION_LEVEL_RUBRIC),
            _render("reuse_score", REUSE_SCORE_RUBRIC),
            (
                "When a case sits between two anchors, choose the lower one unless "
                "the higher anchor's evidence is present in the article."
            ),
        ]
    )


def rubric_anchor_map() -> Dict[str, List[str]]:
    """Machine-readable view of the rubrics, for tests and future tooling."""
    return {
        "hook_strength": list(HOOK_STRENGTH_RUBRIC),
        "tension_level": list(TENSION_LEVEL_RUBRIC),
        "reuse_score": list(REUSE_SCORE_RUBRIC),
    }
