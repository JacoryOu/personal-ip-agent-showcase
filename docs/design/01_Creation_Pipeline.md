# 01 — Creation Pipeline

Status: **Implemented**. Verified against `main@4d643ad`.
Owns the core authoring chain: topic → divergent outlines → draft → human edit →
archive → diff/DNA evolution.

## 1. Scope and code paths

| Path | Role |
| --- | --- |
| `backend/app/engine/cognitive_engine.py::CognitiveEngine` | Orchestrator for the whole chain |
| `backend/app/engine/agents/outline_agent.py` | Divergent outline generation (A/B) |
| `backend/app/engine/agents/draft_agent.py` | Draft expansion, archival |
| `backend/app/engine/agents/diff_agent.py` | Draft-vs-human diff → DNA |
| `backend/app/engine/prompts/outline_prompts.py` | Outline prompts |
| `backend/app/engine/prompts/draft_prompts.py` | Draft prompts |
| `backend/app/engine/prompts/diff_prompts.py` | Diff prompts |
| `backend/app/utils/lexical_filter.py` | Code-level removal of AI filler |
| `backend/app/api/outlines.py` | `POST /api/outlines/generate` |
| `backend/app/api/drafts.py` | Compatibility facade for draft generate / read / update / delete / archive; see `draft_common.py`, `draft_generation.py`, `draft_archive.py`, `draft_feedback.py`, `draft_lineage.py` |
| `backend/app/api/blueprints.py` | Blueprint registry over the workflow |

## 2. Flow

```
topic
  → CognitiveEngine.explore_outlines()      → outline A + outline B
  → user picks one
  → CognitiveEngine.generate_draft()        → draft text
  → user edits (DraftEditor.vue)
  → PUT /drafts/{id}                         → human version stored
  → CognitiveEngine.evolve_with_diff()       → Thinking DNA updated
```

Alternate entry: `generate_from_blueprint()` starts from a stored blueprint
(extracted from a benchmark) instead of a fresh outline pair.

## 3. Design decisions

1. **Two divergent outlines, not one.** The system deliberately produces
   structurally different options so the choice is a real editorial decision.
2. **Lexical stripping is code, not prompt.** `lexical_filter.py` removes
   filler/replacement patterns with RegEx before the text is stored, so
   "AI-ness" does not depend on prompt adherence. Called by both
   `draft_agent.py` and `diff_agent.py`.
3. **Diff gating.** `diff_agent.py` aborts **before** the LLM call when the AI
   draft and the human version are identical and no active viewpoint judgments
   were supplied. There is nothing to learn from an unchanged draft.
4. **Read path is physically isolated.** Outline and draft *input assembly*
   (IP bundle, DNA, profile, memory retrieval) runs on
   `db.get_readonly_session()`. Draft **archival** deliberately uses a writable
   session. See `10_Sandbox_and_Permission_Model.md` and `AGENTS.md`.
5. **Distribution is a separate concern.** `distribute_content()` exists on the
   engine but the real platform path lives in doc 04.

## 4. API surface

`POST /api/outlines/generate`

`POST /drafts/generate`, `POST /drafts/generate-from-blueprint`

`GET|PUT|PATCH|DELETE /drafts/{draft_id}`, `GET /drafts` (archive listing),
`POST /drafts` (archive creation), `GET /drafts/{draft_id}/lineage`

`POST /drafts/{draft_id}/feedback`, `POST /drafts/{draft_id}/feedback/extract`,
`GET /drafts/{draft_id}/feedback`, `POST /drafts/{draft_id}/feedback/evolve`

Distribution entry points exposed here: `POST /drafts/distribute` and
`POST /drafts/{draft_id}/distribute` (thin wrappers; real behaviour in doc 04)

Blueprint registry: `GET /blueprints` (listing), `GET|PUT|PATCH|DELETE /blueprints/{id}`,
`POST /blueprints/extract`. There is **no** `POST /blueprints` creation route; blueprint
records are produced by `/blueprints/extract` or by blueprint persistence in the
draft archival flow.

## 5. Error contract and trusted identity (drafts / blueprints)

### 5.1 Errors never echo the raw exception

`POST /drafts/generate` (`backend/app/api/drafts.py`) accepts an optional
`viral_analysis_id`; `backend/app/engine/cognitive_engine.py` resolves and
ownership-checks it in a read-only session before any LLM call, and
`backend/app/engine/agents/draft_agent.py` consumes the resolved
`style_fingerprint_prompt` as a structure-only reference block. See
`03_Viral_Semantic_Analysis.md` section 8.

### 5.0 Viral style selection: explicit id, automatic selection, fallback

The Draft chain resolves an external viral style in exactly three stages. The
scoring logic itself lives **outside** the Draft flow, in the independent
`backend/app/services/style_selection_service.py`; the engine only decides which
path to take and which record to load.

1. **Explicit id wins.** If the request carries `viral_analysis_id`, that exact
   record is used. Automatic selection is not invoked and the explicit choice is
   never overridden.
2. **No id -> automatic selection.** `StyleSelectionService` ranks candidate
   fingerprints from the caller's **own** analysed records only, using the
   current IP, the topic, additional context and recent drafts. Default score:

   ```text
   score =
       0.45 * topic_match
     + 0.30 * ip_match
     + 0.15 * recent_work_affinity
     + 0.10 * transferability
   ```

   Weights, acceptance threshold (`0.35`), candidate cap (`20`), recent-draft
   window (`5`) and recency half-life (30 days) are explicit and configurable.
   The service returns a candidate **id** only; the engine then re-validates it
   through the same strict loader used by the explicit path.
3. **No suitable candidate -> Persona/DNA.** No candidates, a score below the
   threshold, a failed re-validation or a selector error all fall back cleanly to
   Persona/DNA with lineage source `persona_dna_no_external_style`, i.e. "no
   external style". Draft never fails because an optimisation-only selector
   failed.

Lineage records which stage produced the style: `viral_semantic_analysis`
(explicit), `viral_semantic_analysis_auto_selected` (automatic) or
`persona_dna_no_external_style` (fallback). The trusted prompt schema is
unchanged: clients still cannot submit `style_fingerprint` or style prompt text,
only an id they own and that the system already analysed. The outward
`style_fingerprint` schema shape is untouched.

`backend/app/api/drafts.py` and `backend/app/api/blueprints.py` raise
`app.core.errors.AppError` only. No route formats an exception, SDK payload, DB
driver message, filesystem path, traceback, upstream URL, or request payload into
a response body.

- Expected business failures raise `AppError(code=..., status_code=...)` with
  wording owned by the public contract. Examples: empty blueprint input →
  `VALIDATION_ERROR` / 422; an unresolvable draft → `NOT_FOUND` / 404;
  a draft that exists but belongs to somebody else → `FORBIDDEN` / 403; a
  client-supplied `user_id` that disagrees with the credential → `FORBIDDEN` / 403.
- Service `ValueError`s are translated into a fixed public message; the original
  text is never interpolated.
- Unexpected exceptions are **not** caught. They propagate to the global
  `Exception` handler registered in `backend/app/main.py`, which logs the
  traceback server-side and returns the fixed `INTERNAL_ERROR` / 500 body with
  `error.code` and `error.request_id`. Handlers therefore must not log the same
  failure a second time.

Every error body carries `error.code` and `error.request_id`; the request id is
the same value as the `X-Request-ID` response header (from the globally
registered `RequestIdMiddleware`), so a client can quote one id that also appears
in the server log.

### 5.2 Identity comes from the credential, never from the payload

Routes that read or write user-private drafts resolve the caller through the
trusted-identity dependency (`app.core.auth.get_current_user`), which also carries
the local development identity and the BYOK `X-API-Key` semantics.

The dependency is no longer applied handler by handler. `backend/app/api/auth_boundary.py`
exposes `create_private_router()` / `create_public_router()`, and every business
router is mounted under `api_router = create_private_router(prefix="/api")` in
`backend/app/api/__init__.py`. A new handler therefore inherits authentication by
construction, and forgetting `Depends(get_current_user)` is a gate failure rather
than a silent exposure.

Public endpoints are explicit: they must live on a `create_public_router()` instance
and match the `PUBLIC_ENDPOINTS` allowlist. `GET /api/private-domain/templates` is the
only such endpoint today. BYOK `X-API-Key` credentials remain provider-scoped secrets
and are distinct from the application identity credential.

`scripts/check_api_auth.py` and `backend/tests/test_api_auth_surface.py` guard this
boundary locally.

Covered draft routes: `POST /generate`, `POST /generate-from-blueprint`,
`GET /api/drafts` (both slash forms), `POST /api/drafts` (both slash forms),
`GET|PUT|PATCH|DELETE /{draft_id}`, `POST /{draft_id}/distribute`,
`GET /{draft_id}/lineage`, and all four feedback routes.

Ownership rules:

- Generation, archive write, and feedback write use `current_user.id` as the
  owner; a `user_id` in the body or query string is never used as identity.
- Archive listing is always filtered by `current_user.id`.
- A body/query `user_id` that disagrees with the credential → `FORBIDDEN` / 403.
- Missing or invalid credential → `AUTH_REQUIRED` / 401.
- Draft absent → `NOT_FOUND` / 404; draft present but owned by another user →
  `FORBIDDEN` / 403.
- `POST /{draft_id}/distribute` on its own (no id) stays public: it transforms
  caller-supplied raw text and touches no stored resource.

Blueprint routes were already credential-scoped and keep their existing
anti-enumeration behaviour: a blueprint that belongs to another user answers the
same `NOT_FOUND` / 404 as one that does not exist.
## 6. Known limits

- Feedback evolution (`/feedback/evolve`) updates traits, but trait scoring is
  heuristic, not human-calibrated.
- Draft → distribution handoff exists but is not the same as an end-to-end
  automated publish loop.
- The lexical filter is RegEx-based; it cannot judge nuance and does not try to.

## 6. Outline generation: identity and error contract

`POST /api/outlines/generate` is a private endpoint. It resolves the caller through
the shared trusted-identity dependency (`app.core.auth.get_current_user`), including
the local development identity and the BYOK `X-API-Key` semantics. The credential
is the **only** identity source: a `user_id` in the request body is retained purely
as a backwards-compatible field and is never trusted. If it is present and does not
match the authenticated identity, the request is rejected with
`AppError(code=FORBIDDEN, status_code=403)`. The outline engine is always called with
the authenticated user id.

Error handling:

- Expected input failures are raised as `AppError(code=VALIDATION_ERROR,
  status_code=422)`; the upstream `ValueError` text is not echoed.
- Unexpected SDK / engine / database failures are collapsed to
  `AppError(code=INTERNAL_ERROR, status_code=500)` chained with `from exc`, so the
  response carries only the standard envelope (public `error.code` plus
  `request_id`) and never tracebacks, absolute paths, upstream URLs, provider
  payloads or credentials.
- The original exception is recorded server-side and correlated by request id;
  the client-visible `X-Request-ID` header matches the `request_id` in the body.
