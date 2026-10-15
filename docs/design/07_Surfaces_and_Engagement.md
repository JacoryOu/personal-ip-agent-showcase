# 07 — Surfaces & Engagement

Baseline: `main@4d643ad`.
Status vocabulary: **Implemented** / **Partial** / **Not implemented**.

This domain covers everything the user directly touches outside the creation
pipeline: the cognitive chat lounge, private-domain (WeChat Moments) tooling,
image generation, model settings, and the Vue frontend that consumes them.

## 1. Cognitive Chat Lounge — Implemented

Code: `backend/app/api/chat_lounge.py` (compatibility facade over
`backend/app/api/chat_lounge_common.py`, `backend/app/api/chat_lounge_crystallization.py`,
`backend/app/api/chat_lounge_messages.py`, `backend/app/api/chat_lounge_prompts.py`,
`backend/app/api/chat_lounge_sessions.py`; routes and behaviour unchanged), models
`backend/app/models/chat_session.py` (`chat_session`, `chat_message`),
frontend `frontend/src/components/CognitiveChatLounge.vue` and
`frontend/src/services/api/chat.ts`.

Flow of `POST /api/chat/lounge/message`:

1. Resolve the acting user (`_resolve_user_id`).
2. Load the active `IPPersona` and DNA summary.
3. **Always** build the Cognitive Twin system prompt via
   `_build_twin_system_prompt` — there is deliberately no generic-chatbot
   fallback.
4. Call the model gateway (`_call_chat`).
5. Concurrently run `_call_extraction`, which returns `DNACapsule` values
   (episodic story / DNA candidates). Extraction failures do not fail the
   reply; they only yield empty capsules.
6. Persist the user message and the assistant reply, bump `message_count`,
   parse a session title from the first exchange (`_parse_natural_date`
   normalises timestamps such as "昨天").

Session ownership: `_ensure_session_owner` / `_session_owner_or_none` gate
history, rename, delete and crystallize on the session owner.

Endpoints:

- `POST /api/chat/lounge/message`
- `GET  /api/chat/lounge/history`
- `GET  /api/chat/lounge/sessions`
- `DELETE /api/chat/lounge/sessions/{session_id}`
- `POST /api/chat/lounge/sessions/{session_id}/title`
- `POST /api/chat/lounge/sessions/{session_id}/crystallize-persona`

`crystallize-persona` runs a dedicated "传记结晶" prompt and proposes a
persona draft; it does not silently overwrite the active persona — the caller
confirms before persisting.

### Known limitations

- Session ownership is enforced per handler, not by a shared dependency; a new
  endpoint can forget the check.
- Extraction quality is unvalidated; capsules are stored as-is.
- No streaming: each turn is a single blocking completion.

## 2. Private Domain (WeChat Moments) — Implemented

Code: `backend/app/api/private_domain.py` (compatibility facade over
`backend/app/api/private_domain_common.py`, `backend/app/api/private_domain_community.py`,
`backend/app/api/private_domain_fallback.py`, `backend/app/api/private_domain_moment.py`,
`backend/app/api/private_domain_schemas.py`, `backend/app/api/private_domain_text.py`;
routes and behaviour unchanged), frontend
`frontend/src/components/PrivateDomainHub.vue`,
`frontend/src/services/api/privateDomain.ts`,
`frontend/src/utils/momentsCanvasExporter.ts`.

- `POST /api/private-domain/generate-moment` — five categories (专业沉淀 /
  生活切片 / 好物自用 / 互动截流 / 岁月反思). Generation is rule-based
  (`_build_rule_based_moment`) with an LLM branch; the rule path always runs as
  a fallback.
- Formatting post-processing is code-enforced, not prompt-dependent:
  `calculate_moments_lines` estimates folded lines in the Moments feed,
  `clean_mechanical_dates` rewrites absolute dates, and
  `enforce_anti_fold_formatting` inserts the visual breaks that keep the text
  from folding. The response reports `total_lines`, `will_fold` and
  `fold_preview` so the UI can warn.
- `POST /api/private-domain/generate-community` — community copy variant.
- `GET  /api/private-domain/templates` — static matrix template list.

### Known limitations

- Fold estimation is a heuristic width calculation, not a real WeChat render.
- Templates are hardcoded in the module.
- Generated posts are not persisted; they exist only in the response.

## 3. Image Generation — Partial

Code: `backend/app/api/images.py`, `backend/app/services/image_service.py`,
frontend `frontend/src/services/api/image.ts`.

- `POST /api/images/generate` — text/image generation through the configured
  provider.
- `GET  /api/images/proxy` — proxies a remote image so the browser is not
  blocked by third-party origins. It calls `safe_fetch()` from
  `backend/app/core/net_guard.py`, and `backend/app/services/image_service.py`
  routes its provider calls through the same guard, so both image outbound
  paths are SSRF-guarded.
- `POST /api/images/test-connection` — connectivity probe.

Provider quirks live in `image_service.py`: `is_agnes_model` detects the Agnes
endpoint and `map_agnes_params` translates neutral parameters into that
provider's dialect. `get_image_service()` / `set_image_service()` provide a
process-wide singleton.

### Known limitations

- Single global service instance: per-user provider configuration is not
  isolated.
- `map_agnes_params` is provider-specific and will need extending for each new
  provider rather than being a general adapter.
- The proxy is guarded, but the guard is configurable rather than strict:
  `OUTBOUND_ALLOWED_HOSTS` is an **optional** allowlist, so with it unset the
  guard falls back to blocking private/loopback/metadata targets and
  numeric-IP literals, not to restricting hosts. A public-IP host is still
  reachable. Tightening this is a config change, not a code change.
- `image_service.py` no longer bypasses the guard (host allowlist,
  private-network denial, `443`-only port allowlist), but
  `credential_service.py` still calls `httpx` directly.

## 4. Model Settings — Implemented

Code: `backend/app/api/settings.py` (compatibility facade over
`backend/app/api/settings_common.py` and `backend/app/api/settings_routes.py`;
routes and behaviour unchanged), `backend/app/core/config.py`,
frontend `frontend/src/components/ModelSettingsModal.vue`,
`frontend/src/components/ModelSelectorPill.vue`,
`frontend/src/services/api/modelSettings.ts`.

- `GET  /api/settings/current` — effective model, base URL and provider.
- `POST /api/settings/test-connection` — issues a minimal completion/chat call
  against the supplied credentials before the user commits them.
- `normalize_model_for_provider` strips provider-specific prefixes so the UI
  shows a clean model name.

### Known limitations

- Settings are process/env configuration, not per-user; the settings screen is
  effectively an operator tool.
- Credentials are not persisted through this API — it only reports and tests.

## 5. Frontend — Partial

Vue 3 + Vite SPA under `frontend/src`:

- `App.vue`, `main.ts`, `style.css` — shell and routing-free navigation.
- Components: `TopicInput`, `Workbench`, `DraftSelection`, `DraftEditor`,
  `DNAResult`, `ViewpointReview`, `CreationHistory`, `FeedbackModal`,
  `MaterialVault`, `CognitiveProfile`, `CognitiveChatLounge`,
  `CognitiveTimelineView`, `PrivateDomainHub`, `MultiPlatformDistributeModal`,
  `BenchmarkAccountsModal`, `BenchmarkDeconstructModal`,
  `DailyBriefingModal`, `ExtractPersonaModal`, `ExtractProductModal`,
  `ModelSettingsModal`, `ModelSelectorPill`, `HelloWorld`.
- API layer: `frontend/src/services/api/*.ts`, one module per domain
  (`drafting`, `dna`, `chat`, `materials`, `obsidian`, `distribution`,
  `platformAccounts`, `privateDomain`, `scheduler`, `image`,
  `modelSettings`, `personaExtraction`, `productVault`, `timeline`,
  `benchmarks`, `feedback`, `core`, `client`), all funnelled through
  `client.ts`.
- Rendering/export utils: `utils/doocsRenderer`, `utils/cardCanvasExporter`,
  `utils/wechatRenderer`, `utils/xhsRenderer`, `utils/momentsCanvasExporter`.
- i18n: `frontend/src/i18n/locales/{zh,en}.ts`.

### Known limitations

- No router or global store: navigation state is local component state, so
  deep-linking and cross-page refresh lose context.
- No frontend test suite; `scripts/` holds only build helpers.
- Layout is desktop-oriented; no responsive pass.

## Error contract and request IDs — Implemented

Code: `backend/app/core/errors.py`, `backend/app/core/request_id.py`,
handlers in `backend/app/main.py`.

Every failure returns the same shape:

```json
{
  "error": { "code": "INTERNAL_ERROR", "message": "Internal server error.", "request_id": "..." },
  "detail": "Internal server error."
}
```

- `detail` is retained for frontend compatibility and always carries the same
  safe message as `error.message` — never the raw exception.
- 5xx responses never expose DB errors, SDK errors, file paths or submitted
  payloads; those go to the server log only. Validation errors no longer echo
  the request body.
- `X-Request-ID` is accepted only when it matches `^[A-Za-z0-9._-]{1,64}$`,
  otherwise a UUID hex is generated. It is stored on `request.state`, returned
  on the response (including error responses produced by handlers), and used to
  correlate logs.
- Application code should raise `AppError` with a stable code
  (`AUTH_REQUIRED`, `FORBIDDEN`, `NOT_FOUND`, `VALIDATION_ERROR`, `CONFLICT`,
  `DEPENDENCY_FAILURE`, `INTERNAL_ERROR`) instead of returning
  `detail=str(e)`.
- Scope note: this is a shared foundation, and it is now applied across the
  private routers. Raw-exception 5xx responses and client-supplied `user_id`
  authorization have been removed from the routers listed below.

## Authentication coverage across routers — Implemented with honest gaps

Authentication is no longer a per-handler convention. `backend/app/api/auth_boundary.py`
provides two router factories:

- `create_private_router()` applies `Depends(get_current_user)` to every route it
  creates.
- `create_public_router()` applies no authentication dependency and is reserved for
  an explicit allowlist.

`backend/app/api/__init__.py` mounts every business router under
`api_router = create_private_router(prefix="/api")`, so a newly added handler
inherits authentication by construction. The only public router is
`public_endpoints_router`, and its routes must match `PUBLIC_ENDPOINTS` exactly.

| Router | Authentication |
| --- | --- |
| `platforms.py` | inherited from the private aggregate (facade over `platforms_common.py` / `platforms_routes.py`) |
| `chat_lounge.py` | inherited from the private aggregate (facade over the `chat_lounge_*` modules) |
| `blueprints.py` | inherited from the private aggregate |
| `drafts.py` | inherited from the private aggregate (facade over the `draft_*` modules) |
| `dna.py` | inherited from the private aggregate (facade over the `dna_*` modules) |
| `dna_v2.py` | inherited from the private aggregate (facade over the `dna_v2_*` modules) |
| `scheduler.py` | inherited from the private aggregate |
| `materials.py` | inherited from the private aggregate (facade over the `materials_*` modules) |
| `obsidian.py` | inherited from the private aggregate |
| `settings.py` | inherited from the private aggregate (facade over `settings_common.py` / `settings_routes.py`) |
| `viral_analysis.py` | inherited from the private aggregate |
| `outlines.py` | inherited from the private aggregate |
| `images.py` | inherited from the private aggregate; endpoints now authenticated |
| `private_domain.py` (templates) | public via `public_router`, allowlisted |

What this branch changed:

- The authenticated credential is the only identity source. A `user_id` in a
  request body or query string is ignored for authorization.
- Object ownership is checked: Material, Persona/Product, Chat Lounge session,
  and platform credentials/accounts all resolve to the caller's own records.
- A cross-user record, a missing record, and a malformed UUID return the same
  redacted public `404`, so existence is not disclosed.
- Scheduler runs resolve the acting user through `_resolve_acting_user_id`;
  the legacy body `user_id` is ignored. Isolation is **in-process only** —
  it does not survive a restart and is not consistent across multiple workers.
- `POST /api/images/generate`, `GET /api/images/proxy` and
  `POST /api/images/test-connection` are authenticated. SSRF protections
  (base URL allowlist, per-hop redirect checks, size and content-type limits)
  are unchanged.
- `GET /api/dna/skills` and `POST /api/drafts/distribute` are authenticated.
- `GET /api/private-domain/templates` is the single intentional public API.

Local regression gates (no CI yet):

- `scripts/check_api_auth.py` — static: the aggregate routers must come from the
  factories, only `private_domain.py` may declare a `public_router`, and anonymous
  routes must match `PUBLIC_ENDPOINTS` exactly.
- `backend/tests/test_api_auth_surface.py` — runtime: the endpoints above must
  return `401` anonymously, and the templates endpoint must stay reachable.

Remaining honest gaps:

- Image endpoints are authenticated, but **per-user ownership and persistence are
  not implemented** — an authenticated user may still operate on shared image
  configuration state.
- Scheduler per-user isolation is in-process only.
- `SKILL.md` `permissions` metadata is not yet enforced by the Skill Engine.

## Permissions and data boundaries

- The primary authoring entry point is
  `frontend/src/components/Workbench.vue`.
- Model calls are centralized through `backend/app/core/model_gateway.py`;
  provider selection and settings stay outside the agent read-only
  isolation described above.
- Every one of these surfaces writes through a normal writable session
  (`get_session`). The read-only engine described in
  `docs/architecture/10_Sandbox_and_Permission_Model.md` protects the Outline /
  Draft **read path** only; chat, moments, images and settings are outside it.
- Image generation and model settings cause outbound network calls to whatever
  provider the operator configured. `backend/app/core/net_guard.py` is
  is not applied to model-call handlers, and it is not a skill-execution
  sandbox component either — its callers today are the image proxy endpoint
  and `backend/app/services/image_service.py`. There is still no global
  outbound policy; `credential_service.py` remains unguarded.

## CORS policy and the /uploads static mount — Implemented

Code: `backend/app/main.py` (application assembly, `CORSMiddleware`,
`/uploads` mount) and `backend/app/core/config.py` (the settings that drive it).

- Origins, methods and headers are explicit allowlists. `CORS_ORIGINS` is
  filtered so the literal `"*"` can never reach `CORSMiddleware`, because
  `allow_credentials=True` is kept and a wildcard origin is illegal with it.
  `CORS_ALLOW_METHODS` and `CORS_ALLOW_HEADERS` are explicit lists, never `"*"`.
- The header allowlist covers what the frontend actually sends
  (`X-Model-Name`, `X-Model-Api-Key`, `X-Base-Url`, `X-Image-Model`,
  `X-Image-Api-Key`, `X-Image-Base-Url`, `Content-Type`) plus the
  `X-Api-Key` and `Authorization` credentials the backend accepts. Note
  that `X-Model-Api-Key` is the BYOK header for model credentials, while
  `X-Api-Key` / `Authorization` carry the *application* identity. BYOK key
  resolution order is `payload.api_key` -> `X-Model-Api-Key` -> `X-Api-Key`.
- `ENVIRONMENT=production` drops the localhost origins *and* the localhost
  origin regex, so no localhost port is browser-reachable. The regex is a
  development-only convenience for Vite dynamic ports, gated by
  `CORS_ALLOW_LOCALHOST_REGEX`. An empty resulting allowlist is logged as
  `CORS_ALLOWLIST_EMPTY` rather than silently failing.
- `backend/app/data/uploads` is mounted at `/uploads` only while `EXPOSE_UPLOADS`
  is true (default true, so the frontend keeps working). When false nothing is
  mounted and a `UPLOADS_DISABLED` warning is emitted; directory-preparation
  failures are logged as `UPLOADS_MOUNT_FAILED` instead of crashing at import.
- `/uploads` is not an authorization boundary — every file in the directory is
  public to anyone who can reach the backend. Deployments that must not publish
  uploads should set `EXPOSE_UPLOADS=false` and serve content through an
  authenticated route.

Regression coverage: `backend/tests/test_cors_and_uploads_config.py`.