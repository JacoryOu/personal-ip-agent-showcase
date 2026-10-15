# 02 — Cognitive Profile & DNA

Status: **Implemented** (with honest gaps in section 7). Verified against `main@4d643ad`.
Owns the long-term representation of *who the user is as a thinker and writer*.

## 1. Code paths

| Path | Role |
| --- | --- |
| `backend/app/services/cognitive_service.py` | Profile, IP bundle, trait CRUD, export/import |
| `backend/app/services/memory_service.py` | Stable facade for `MemoryService` (public API unchanged) |
| `backend/app/services/memory_common.py` | `Mem0Operation` + `_parse_user_id` |
| `backend/app/services/memory_similarity.py` | String-similarity helper |
| `backend/app/services/memory_lifecycle.py` | Mem0 lifecycle, own-work DNA ingestion |
| `backend/app/services/memory_benchmarks.py` | Benchmark deconstruction + dialogue clash |
| `backend/app/services/memory_blueprints.py` | Blueprint persistence / CRUD |
| `backend/app/services/memory_conflicts.py` | Viewpoint conflict detection |
| `backend/app/services/memory_context.py` | Context Thinking DNA assembly |
| `backend/app/services/memory_retrieval.py` | Relevant-story retrieval (writable path) |
| `backend/app/services/memory_readonly.py` | Relevant-story retrieval (`*_readonly`, explicit session required) |
| `backend/app/services/memory_dna_retrieval.py` | Embedding + hybrid DNA retrieval (read-only and writable) |
| `backend/app/services/memory_evolution.py` | Trait supersession + time-expression naturalization |
| `backend/app/services/cognitive_service.py` | Compatibility facade for the cognitive service mixins (public methods + module-level `_parse_user_id` unchanged) |
| `backend/app/services/cognitive_common.py` | Shared user-id parsing used by the cognitive mixins |
| `backend/app/services/cognitive_profile_service.py` | Profile load/persist, default user, readonly context assembly |
| `backend/app/services/cognitive_evolution_service.py` | DNA sync/evolution and Thinking Trait CRUD |
| `backend/app/services/cognitive_portability_service.py` | Profile import/export and generation-time DNA selection |
| `backend/app/services/memory_service.py` | Mem0 lifecycle, benchmark blueprints, story retrieval, hybrid retrieval |
| `backend/app/services/feedback_service.py` | Feedback capture + insight extraction |
| `backend/app/api/dna.py` | Compatibility facade for DNA extraction, traits, profile, export/import, conflicts; see `dna_common.py`, `dna_extraction.py`, `dna_portability.py`, `dna_traits.py` |
| `backend/app/api/dna_v2.py` | Compatibility facade for personas, products, stories, timeline, supersede; see the `dna_v2_*` responsibility modules |
| `backend/app/models/dna_record.py`, `persona.py`, `product.py`, `story.py`, `user.py` | Persistence |
| `backend/app/engine/prompts/dna_context.py` | DNA context assembly for prompts |
| `frontend/src/components/CognitiveProfile.vue`, `DNAResult.vue`, `ViewpointReview.vue`, `CognitiveTimelineView.vue`, `ExtractPersonaModal.vue`, `ExtractProductModal.vue` | Surfaces |

## 2. Core concepts

- **CognitiveProfile** — the aggregate view of a user's traits, persona, and
  product, returned by `GET /api/dna/profile`.
- **Trait** — a single thinking/values tendency. It can be **pinned** (always
  used), **suppressed** (never used), **custom** (user-authored), or evolved
  from feedback.
- **Benchmark blueprint** — a structural skeleton extracted from a competitor's
  article, reusable as a draft starting point.
- **Persona** — a creator identity preset (audience, tone, salutation, origin
  story). Pre-seeded with three Chinese personas.
- **Product** — a product/offer extracted from text or image, used for
  private-domain and distribution surfaces.
- **Story** — a dated life event used in the timeline and memory retrieval.

## 3. DNA extraction entry points

| Endpoint | Meaning |
| --- | --- |
| `POST /api/dna/extract` | Extract DNA from a draft + human version pair |
| `POST /api/dna/ingest-own-work` | Learn from the user's own published work |
| `POST /api/dna/deconstruct-benchmark` | Learn structure from a competitor article |
| `POST /api/dna/dialogue-clash` | Record a viewpoint clash that reveals a trait |
| `POST /api/dna/import` / `GET /api/dna/export` | Portable profile JSON |

Extraction is **LLM-driven** through `ModelGateway`. Where a comparison target is
identical to the source, `diff_agent.py` short-circuits (see doc 01).

## 4. Memory and retrieval

`memory_service.py` is the stable facade; the mem0-style lifecycle is implemented
across the `memory_*` responsibility modules listed in section 1 (a structural
split, no behaviour change):

- `add_own_work_dna`, `deconstruct_benchmark`, `record_dialogue_clash` — write paths.
- `retrieve_relevant_stories` / `retrieve_relevant_stories_readonly` — recall.
- `hybrid_retrieve_dna` / `hybrid_retrieve_dna_readonly` — **hybrid retrieval**
  combining vector similarity (embedding bytes + cosine) with a heuristic trait
  score (`_score_dna_traits`). Returns the most relevant traits for a topic.
- `detect_viewpoint_conflicts` — surfaces contradictory traits.
- `supersede_dna_trait` — retires a trait in favour of a newer one.

The `_readonly` variants avoid all INSERT/UPDATE/COMMIT and are the ones used by
the agent read path.

## 5. Feedback evolution

1. `POST /drafts/{id}/feedback` records comments.
2. `POST /drafts/{id}/feedback/extract` derives insights — LLM first, heuristic
   fallback (`_heuristic_feedback_analysis`).
3. `POST /drafts/{id}/feedback/evolve` writes those insights into traits via
   `cognitive_service.evolve_traits_from_feedback`.

## 6. Persona / product / story (DNA 2.0)

`dna_v2.py` is now a compatibility facade; the routes themselves live in focused
modules — `backend/app/api/dna_v2_common.py`,
`backend/app/api/dna_v2_persona_schemas.py`,
`backend/app/api/dna_v2_persona_extraction.py`,
`backend/app/api/dna_v2_persona_extract.py`,
`backend/app/api/dna_v2_product_helpers.py`,
`backend/app/api/dna_v2_product_routes_a.py`,
`backend/app/api/dna_v2_product_routes_b.py`, `backend/app/api/dna_v2_stories.py`,
`backend/app/api/dna_v2_timeline.py`, `backend/app/api/dna_v2_supersede.py`.
URLs, methods, schemas, dependency injection and fallbacks are unchanged; this is
a structural split, not a new feature.

The facade still manages three richer entities plus a merged timeline:

- Personas: list / create / extract-from-text / update.
- Products: list / create / **upload-image** + extract / update / delete.
- Stories: list / create.
- `GET /api/dna/v2/timeline` — persona + story + product timeline.
- `POST /api/dna/v2/supersede` — retire an entity.

Product image upload is why `IPProduct` carries image fields; the goal is to let
the private-domain and distribution surfaces reference the real offer.

## 7. Honest gaps

1. **Trait scoring is not human-calibrated.** `_score_dna_traits` weights recency
   and similarity heuristically. No ground-truth eval exists.
2. **The embedding path is optional.** If embeddings are unavailable, retrieval
   degrades to the heuristic branch. This is a silent quality cliff.
3. **Mem0 lifecycle is app-level, not the real mem0 stack.** The service mimics
   the lifecycle API; it does not embed the upstream library.
4. **Conflict detection surfaces contradictions but does not resolve them.**

## 8. API surface

`GET|POST /api/dna/v2/personas`, `POST /api/dna/v2/personas/extract-from-text`, `PATCH /api/dna/v2/personas/{persona_id}`

`GET|POST /api/dna/v2/products`, `POST /api/dna/v2/products/upload-image`,
`POST /api/dna/v2/products/extract-from-text`, `GET|PATCH|DELETE /api/dna/v2/products/{product_id}`

`GET|POST /api/dna/v2/stories`, `GET /api/dna/v2/timeline`, `POST /api/dna/v2/supersede`

Traits: `GET|POST /api/dna/traits`, `PUT|PATCH|DELETE /api/dna/traits/{id}`
(no `GET /traits/{id}` single-trait endpoint exists),
`POST /api/dna/traits/{id}/toggle`, `POST /api/dna/traits/pin|unpin|suppress`,
`POST /api/dna/traits/toggle`

Profile: `GET /api/dna/profile`, `GET /api/dna/benchmarks` (read-only; there is no
`POST /api/dna/benchmarks` — blueprints are created via `/api/dna/deconstruct-benchmark`
or `/blueprints/extract`), `GET /api/dna/skills`,
`POST /api/dna/conflicts/detect` (and an alias `POST /api/dna/detect-conflicts`), `GET /api/dna/records`, `GET|POST /api/dna/export|import`

## 9. Authentication, ownership and error contract

### 9.1 Trusted identity

All DNA endpoints in `backend/app/api/dna.py` and `backend/app/api/dna_v2.py` that
read or write user-private state resolve the caller through the shared trusted
identity dependency (`app.core.auth.get_current_user`). This preserves the local
development identity and the BYOK `X-API-Key` semantics, and it is deliberately not
mounted globally at the application entry point, because the app has genuinely
public endpoints.

The credential is the **only** identity source. A `user_id` supplied in a request
body or query string is kept only as a backwards-compatible field; it is never
trusted on its own. When such an explicit `user_id` is present and does not match
the authenticated identity, the request is rejected with
`AppError(code=FORBIDDEN, status_code=403)`. A missing identity yields
`AppError(code=AUTH_REQUIRED, status_code=401)`.

`GET /api/dna/skills` is authenticated. It is mounted on the private aggregate
router, so it inherits `Depends(get_current_user)` from
`create_private_router()` in `backend/app/api/auth_boundary.py`, and an anonymous
request returns `401`.

### 9.2 Resource ownership

Private resources are checked against the authenticated owner:

- Drafts referenced by `/api/dna/extract`, and by trait/profile/history reads and
  writes: a draft owned by another user yields 403, a draft that does not exist
  yields 404.
- `GET /api/dna/records` only ever queries records belonging to the authenticated
  user.
- Personas, products, stories, timeline entries and supersede operations are
  resolved through the authenticated owner; a resource owned by another user yields
  403 and an unknown resource id yields 404.
- Traits, profile, import/export and conflict detection all operate on the
  authenticated user's identity.

### 9.3 Error handling

No endpoint in these two modules echoes a raw exception into the response body.
Expected business failures raise `AppError` with an appropriate public code
(`VALIDATION_ERROR`, `NOT_FOUND`, `FORBIDDEN`, `CONFLICT`). Unexpected SDK,
database, or filesystem failures are collapsed to
`AppError(code=INTERNAL_ERROR, status_code=500)` chained with `from exc`; the
response therefore never contains tracebacks, absolute file paths, provider or
upstream URLs, API keys, internal hostnames, or echoed request payloads.

Product image upload follows the same rule: a filesystem `OSError` (for example an
unwritable vault directory) becomes the standard envelope, and the absolute path is
written to the server-side log only.

`POST /api/dna/v2/personas/extract-from-text` deliberately degrades rather than
failing: when the upstream provider call fails, the endpoint still answers 200 with
a heuristic persona and never surfaces the provider exception text. By contrast,
`POST /api/dna/v2/products/extract-from-text` returns the uniform 500 envelope on an
internal failure. Both behaviours are covered by tests.

The original exception is recorded server-side and correlated by request id; the
client-visible `X-Request-ID` header matches the `request_id` in the response body.
The exact sandbox and logging behaviour is specified in
`docs/architecture/10_Sandbox_and_Permission_Model.md`.
## 2026-10-15 defect fix: `memory_conflicts.py` import

`backend/app/services/memory_conflicts.py` builds `CognitiveTrait` rows for
viewpoint-conflict detection but never imported the model, so any path that
actually persisted a detected conflict raised `NameError`. The fix imports
`CognitiveTrait` from `app.models`; conflict-detection semantics are unchanged.
