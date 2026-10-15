# 03 — Viral Semantic Analysis

Status: **Implemented (API thin, engine substantive)**. Verified against `main@4d643ad`.
Decomposes a viral / benchmark article into reusable semantic structure: hook,
rhythm, emotional curve, and a `style_fingerprint`.

## 1. Scope and code paths

| Path | Role |
| --- | --- |
| `backend/app/api/viral_analysis.py` | `POST /viral-analysis/analyze`, `GET /viral-analysis/{id}` |
| `backend/app/services/viral_semantic_service.py` | The actual engine |
| `backend/app/engine/prompts/viral_prompts.py` | Model prompt (rubric block injected at import time) |
| `backend/app/engine/rubrics/viral_rubric.py` | Single source of truth for the 0-5 score anchors |
| `backend/app/models/viral_analysis.py` | `ViralSemanticAnalysisRecord` |
| `backend/app/engine/cognitive_engine.py` | Draft generation; owns the fingerprint ownership/validation gate |
| `backend/app/api/drafts.py` | `POST /drafts/generate`; accepts the optional analysis id |
| `backend/app/schemas/draft_schemas.py` | `DraftGenerateRequest` (`extra="forbid"`), `DraftInput` |
| `frontend/src/components/BenchmarkDeconstructModal.vue` | Deconstruction surface |
| `skills/media-article-extractor/` | Unattended extraction skill |

## 2. Pipeline

```
article text
  → normalize_article_text()      # whitespace / control-char normalisation
  → content_hash()                # sha256, for de-duplication
  → split_sentences()             # zh/en aware sentence split
  → compute_rhythm_stats()        # deterministic sentence-length rhythm
  → build_prompt_block()          # sends stats + text to the model
  → _run_model_analysis()         # ModelGateway call
  → apply_deterministic_overrides()  # code-owned fields win over model output
  → persist ViralSemanticAnalysisRecord
```

If the model call fails, `build_fallback_analysis()` produces a
deterministic-only analysis and the record is stored with
`extraction_mode="fallback"` plus a `warnings` entry. The API never pretends a
fallback result is a model result.

## 3. Deterministic overrides

`apply_deterministic_overrides()` overwrites model output for anything the code
can measure exactly (sentence counts, rhythm statistics, content hash). This is
deliberate: the model supplies judgement, code supplies facts.

## 4. Provenance and retrieval

`_validate_provenance` and `_to_response` keep `user_id`, `material_id`,
`source_url`, `source_platform`, `extraction_mode` and `model_name` attached to
every analysis, so a downstream consumer can always tell where a breakdown came
from and whether a model was involved.

## 5. API surface

`POST /api/viral-analysis/analyze` — analyse supplied text.
`GET /api/viral-analysis/{analysis_id}` — fetch a stored analysis.

## 6. Authentication, ownership and error contract

`POST /api/viral-analysis/analyze` and `GET /api/viral-analysis/{analysis_id}` are
private endpoints. Both resolve the caller through the shared trusted identity
dependency (`app.core.auth.get_current_user`), preserving the local development
identity and the BYOK `X-API-Key` semantics; authentication is not mounted globally
at the application entry point.

The credential is the only identity source. A `user_id` in the analyze request body
is retained only as a backwards-compatible field; when it is present and does not
match the authenticated identity the request is rejected with
`AppError(code=FORBIDDEN, status_code=403)`. The analysis is always persisted under
the authenticated user id, never under a client-supplied one.

`GET /api/viral-analysis/{analysis_id}` checks ownership of the stored record: a
record owned by another user yields 403, an unknown id yields 404, and a missing
identity yields `AppError(code=AUTH_REQUIRED, status_code=401)`.

No endpoint echoes a raw service, SDK or database exception into the response.
Unexpected failures are collapsed to `AppError(code=INTERNAL_ERROR,
status_code=500)` chained with `from exc`, so the response carries only the standard
envelope (public `error.code` plus `request_id`) and never tracebacks, absolute
paths, upstream URLs or credentials. The original exception is recorded server-side
and correlated by request id, and the client-visible `X-Request-ID` header matches
the `request_id` in the response body.

## 7. Honest gaps

1. **The API is thin.** Two endpoints; the substance lives in the service. This
   is not a defect, but do not read the endpoint list as the feature's size.
2. **Selection is three-stage, not explicit-only.** The client may pass
   `viral_analysis_id` to `POST /drafts/generate`, which always wins and skips
   automatic selection. When no id is supplied, `StyleSelectionService`
   automatically ranks the caller's **own** analysed records; when nothing reaches
   the acceptance threshold, Draft falls back to Persona/DNA with
   `persona_dna_no_external_style`. See section 9.
3. **`hook_strength`, `tension_level` and `reuse_score` are rubric-anchored but
   still not human-calibrated.** The three 0-5 scales are defined once in
   `backend/app/engine/rubrics/viral_rubric.py` and injected verbatim into the
   analysis system prompt, so every level has a written definition and a shared
   evidence rule ("raise a score only when the article text itself contains the
   signal; otherwise report the lower level"). This removes ambiguity and makes
   scores auditable against a rule, but a rubric is not a labelled benchmark:
   there is not yet a human-annotated set, so agreement with human judgement
   remains unmeasured. Score accuracy stays **Partial** until such a set exists
   and is evaluated across models and topics.
4. **Fallback analyses are not flagged to the UI beyond `warnings`.** A consumer
   that ignores `extraction_mode` will silently read a weaker result as equal.

## 7b. Scoring rubric (0-5 anchors)

Three subjective integers are emitted by the breakdown layer:

| Field | Meaning |
| --- | --- |
| `hook.hook_strength` | Strength of the opening as a reason to keep reading |
| `structure.beats[].tension_level` | Narrative pressure inside one beat |
| `transfer.reuse_score` | How transferable the article's mechanics are |

They used to be free-form model impressions, so values drifted across prompts,
models and articles. They are now defined once, in
`backend/app/engine/rubrics/viral_rubric.py`:

- `HOOK_STRENGTH_RUBRIC` — 6 anchors, from "no effective hook" (0) to
  "multiple stacked mechanisms with a kept promise" (5).
- `TENSION_LEVEL_RUBRIC` — 6 anchors, from "flat narration" (0) to
  "maximal irreversible pressure, outcome genuinely undecided" (5).
- `REUSE_SCORE_RUBRIC` — 6 anchors, from "bound to this exact article" (0) to
  "topic- and voice-independent mechanics with concrete adaptation notes" (5).
- `EVIDENCE_RULE` — one rule shared by all three: score only what the article
  text evidences; otherwise take the lower level; never score on overall quality
  or topic interest.

`render_rubric_block()` renders them into the analysis system prompt at import
time, so prompt and code can never drift apart. The public schema is unchanged:
field names, types and the `0..5` range stay exactly as before, only the field
descriptions now state the evidence requirement. Code still clamps and defaults
these values, and a fallback analysis still reports `0` rather than inventing a
semantic score.

Regression coverage: `backend/tests/test_viral_rubric.py`. That suite pins the
rubric structure and the prompt wiring; it is a rule/structure regression test,
**not** a human-labelled accuracy benchmark.

## 8. How the fingerprint reaches Draft generation (explicit path)

`POST /drafts/generate` accepts an optional `viral_analysis_id`
(`DraftGenerateRequest`). The flow is deliberately trust-preserving:

1. The public request model is `extra="forbid"`, so a client **cannot** submit
   trusted style text; only an id is accepted.
2. `CognitiveEngine.generate_draft` in `backend/app/engine/cognitive_engine.py` parses the id as a UUID and reads the record
   through `get_readonly_session()` (`ViralSemanticAnalysisRecord`).
3. Ownership is validated **before** any LLM call: missing id -> 404, another
   user's record -> 403.
4. `analysis_data["style_fingerprint"]["prompt_block"]` must be a non-empty
   string and at most `MAX_STYLE_FINGERPRINT_CHARS` (8000); otherwise 422.
5. The text is passed to the agent as `DraftInput.style_fingerprint_prompt`,
   which is declared `exclude=True` so it is never serialized back to a client.
6. `draft_agent.py` appends it under a guarded header/footer block that instructs
   the model to borrow only **structure, rhythm, paragraph organisation and
   narrative mechanism** — never wording, cases, facts or distinctive phrasing,
   never to blur the reference author's identity with the current user, and never
   to invent facts in order to imitate.
7. Persona, Thinking DNA and real source material always take precedence over the
   reference block. The draft's lineage snapshot records `viral_analysis_id` and
   `style_source="viral_semantic_analysis"` for traceability.

Regression coverage: `backend/tests/test_viral_style_draft.py`.

## 9. Automatic style selection when no id is supplied

`backend/app/services/style_selection_service.py` is an **independent** service.
It is deliberately not part of `CognitiveEngine.generate_draft`, the API handler,
or any agent: it only answers "which of my own analysed fingerprints best fits
this request, if any?" and returns a candidate **id**.

Candidate set — the only trust boundary that matters:

- Queried from `ViralSemanticAnalysisRecord` **filtered by the caller's own
  `user_id`**. Records of other users are never candidates.
- The service returns ids only. It never returns, trusts, or injects a
  `style_fingerprint` prompt.
- The winning id is re-loaded by the engine through the same strict loader used
  by the explicit path: UUID parse, ownership, record type, non-empty
  `prompt_block`, `MAX_STYLE_FINGERPRINT_CHARS` (8000). All of these checks are
  unchanged and still run for automatically chosen ids.

Scoring dimensions (all explicit, configurable, with these defaults):

| Dimension | Default weight | Meaning |
| --- | --- | --- |
| `topic_match` | 0.45 | Lexical overlap/containment between the request topic/additional context and the analysis source title / topic |
| `ip_match` | 0.30 | Lexical affinity between the current IP persona/traits and the analysis content |
| `recent_work_affinity` | 0.15 | Similarity to the caller's recent drafts, with a 30-day half-life |
| `transferability` | 0.10 | `transfer.reuse_score` normalised to `[0, 1]` |

```text
score =
    0.45 * topic_match
  + 0.30 * ip_match
  + 0.15 * recent_work_affinity
  + 0.10 * transferability
```

Weights must sum to `1.0` (`ValueError` otherwise). Acceptance threshold is
`0.35`; the candidate cap is `20` and the recent-draft window is `5`. Ties are
broken by recency (newer first), then by UUID for stable ordering.

Behaviour is a strict three stages:

1. Explicit `viral_analysis_id` -> use it; the selector is never called.
2. No id -> automatic selection when `score >= 0.35`.
3. Otherwise -> Persona/DNA fallback, lineage source
   `persona_dna_no_external_style` (semantically "no external style").

`StyleSelectionService` reports a machine-readable `reason`: `selected`,
`no_candidates`, `below_threshold`, `no_authenticated_user`, or
`candidate_lookup_failed`. The engine converts a below-threshold, unvalidated, or
failed selection into a clean fallback — an optimisation-only selector can never
make Draft generation fail. Lineage snapshot records
`style_source` as `viral_semantic_analysis` (explicit),
`viral_semantic_analysis_auto_selected` (automatic), or
`persona_dna_no_external_style` (fallback), plus a `style_auto_selection`
object with `accepted`, `score`, `threshold`, `reason`, and `candidate_count`.

The outward `style_fingerprint` schema shape is unchanged, and clients still
cannot inject style text directly.

Regression coverage: `backend/tests/test_style_selection_service.py` (scoring,
thresholds, ownership scoping, determinism, config validation) and
`backend/tests/test_viral_style_draft.py` (the three-stage integration).


## 10. Rubric benchmark (human-annotated) and accuracy regression

Status: **Partial.** The deterministic evaluator is measured; real model accuracy
is not.

| Path | Role |
| --- | --- |
| `backend/app/engine/rubrics/viral_benchmark.py` | Deterministic evaluator + metric computation. No model gateway, no network. |
| `backend/app/engine/rubrics/data/viral_rubric_benchmark_v1.json` | 43 human-annotated samples with evidence features and gold levels |
| `backend/tests/test_viral_rubric_benchmark.py` | Dataset-structure, evidence-gate, metric and threshold regression |

### 10.1 What is measured, and what is not

The evaluator replays the **same evidence-first ladder the prompt states** over
the annotated `features` of each benchmark sample. It answers: "does the rubric
rule, as implemented in code, reproduce the human-annotated level for these
cases?"

It does **not** answer "how accurate is the production model". No LLM is called,
no model output is replayed, and no production prompt run is involved. Any metric
below must be read as *rubric-rule fidelity*, never as *model accuracy*.

### 10.2 Benchmark composition

- 43 samples, single annotator, no inter-annotator agreement.
- `hook_strength`, `tension_level`, `reuse_score` each cover levels 0-5.
- Strong/weak hooks, high/low tension, high/low reuse are all represented.
- 7 samples are explicitly annotated as boundary cases where the human level
  deliberately differs from the mechanical ladder, plus 7 hook/tension/reuse grid
  anchors. Grid samples are constructed so the ladder is internally consistent
  with the labelled level, which inflates the headline numbers; the boundary
  samples are what the accuracy gap actually reflects.
- MVP scale; not statistically representative of real articles.

### 10.3 Measured metrics

Metric definitions:

- `accuracy` — within-one-level accuracy, `|pred - gold| <= 1`.
- `mae` — mean absolute error.
- `exact_match_rate` — `pred == gold`.

Recommended gate per dimension: `mae <= 0.8` and `exact_match_rate >= 0.60`.

| Dimension | n | accuracy | MAE | exact match | max abs err | gate |
| --- | --- | --- | --- | --- | --- | --- |
| `hook_strength` | 43 | 1.000 | 0.070 | 0.930 | 1 | pass |
| `tension_level` | 43 | 1.000 | 0.070 | 0.930 | 1 | pass |
| `reuse_score` | 43 | 1.000 | 0.070 | 0.930 | 1 | pass |

The residual error is entirely from the boundary cases, where the mechanical
ladder and the human label differ by exactly one level. No sample deviates by
more than one level.

### 10.4 Calibration decisions

No rubric weakening was needed or performed. The evidence-first downgrade is
unchanged and is regression-tested:

- only an explicit boolean `True` counts as evidence;
- the ladder cannot be skipped (a gap stops scoring at the last proven level);
- a case between two anchors stays at the lower anchor unless the higher
  anchor's evidence is present.

Calibration was therefore limited to feature interpretation; the guarantee that
missing evidence can never raise a score is preserved and locked down by tests
(`test_gap_in_the_ladder_stops_scoring`,
`test_non_boolean_evidence_is_not_accepted`,
`test_false_evidence_never_raises_a_score`).

### 10.5 Remaining gaps (why this is Partial)

- No live-LLM replay: production model accuracy on this benchmark is unmeasured.
- Single annotator; no inter-annotator agreement, so label noise is not bounded.
- Evidence features are annotated by hand, and the evaluator consumes the same
  feature vocabulary it was built against.
- No cross-model or cross-topic validation.
- MVP sample size.

Raising confidence in the real pipeline requires a second annotator, a
recorded model run over the same samples, and cross-topic sample expansion.

---

## 11. Related

- `01_Creation_Pipeline.md` — draft generation that consumes the fingerprint.
- `08_Data_Model_Reference.md` — `ViralSemanticAnalysisRecord`.
- `backend/app/engine/rubrics/viral_rubric.py` — the 0-5 anchors and evidence rule.
