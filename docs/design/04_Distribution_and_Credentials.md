# 04 — Distribution and Credentials

Status: **Implemented**. Verified against `main@4d643ad`.
Platform account binding, encrypted cookie credentials, benchmark-account
crawling, and multi-platform distribution.

## 1. Scope and code paths

| Path | Role |
| --- | --- |
| `backend/app/api/platforms.py` | Compatibility facade over `backend/app/api/platforms_common.py` and `platforms_routes.py` (Credential + benchmark-account + distribution endpoints; routes unchanged) |
| `backend/app/services/credential_service.py` | Encrypted cookie storage, QR login, migration |
| `backend/app/services/platform_crawler_service.py` | Compatibility facade for the crawler mixins (public methods + `_parse_uid` / `extract_fallback_blueprint` re-exported) |
| `backend/app/services/platform_crawler_support_service.py` | UID parsing and fallback blueprint extraction |
| `backend/app/services/platform_crawler_account_service.py` | Benchmark account parse/serialize and CRUD |
| `backend/app/services/platform_crawler_feed_service.py` | Simulated feed items and account-post retrieval |
| `backend/app/services/platform_crawler_collect_service.py` | Batch benchmark collection and blueprint deconstruction |
| `backend/app/services/playwright_service.py` | Browser worker for QR login and crawling |
| `backend/app/core/crypto/secret_box.py` | Credential encryption |
| `backend/app/core/net_guard.py` | SSRF guard (wired into the image proxy only) |
| `backend/app/models/credential.py` | `PlatformAccountCredential` |
| `backend/app/models/benchmark_account.py` | `BenchmarkAccount` |
| `skills/content-multi-distributor/` | Unattended distribution skill |
| `frontend/src/components/BenchmarkAccountsModal.vue`, `MultiPlatformDistributeModal.vue` | Surfaces |

## 2. Credential lifecycle

```
QR login:   start_qr_login() → check_qr_login_status() → _store_cookies()
Manual:     parse_cookie_string() → save_manual_cookies()
Read:       load_cookies() / load_cookies_with_migration()
Inspect:    check_credential_validity()
Delete:     delete_credential()
```

Cookies are encrypted at rest via `SecretBox`. `load_cookies_with_migration()`
exists because older rows were stored before encryption existed; it upgrades
them on read rather than failing.

`generate_qr_svg` / `wrap_jpeg_as_svg` exist so a QR image can be shown inside
the Vue surface without a binary round-trip.

## 3. Benchmark accounts

`BenchmarkAccount` is a *tracked competitor*, not a bound account. It has a feed
endpoint and a sync endpoint; `platform_crawler_service.extract_fallback_blueprint`
derives a structural blueprint when a crawl yields too little text to analyse.

## 4. Distribution

Two paths reach distribution:

- synchronous — `POST /api/drafts/{draft_id}/distribute` from the editor;
- unattended — `skills/content-multi-distributor` via the Skill Engine.

Both consume the same credential store. See
`../architecture/10_Sandbox_and_Permission_Model.md` for what the unattended path
actually isolates.

## 5. API surface

Credentials: `POST /api/platforms/credentials/qr/start`,
`GET /api/platforms/credentials/qr/status`,
`POST /api/platforms/credentials/qr/simulate-confirm`,
`POST /api/platforms/credentials/manual`, `GET /api/platforms/credentials`,
`GET /api/platforms/credentials/{platform}`,
`POST /api/platforms/credentials/{platform}/check`,
`DELETE /api/platforms/credentials/{credential_id}`

Accounts: `GET|POST /api/platforms/accounts`,
`DELETE /api/platforms/accounts/{account_id}`,
`GET /api/platforms/accounts/{account_id}/feed`,
`POST /api/platforms/accounts/{account_id}/sync`, `POST /api/platforms/batch-ingest`

## 6. Permission and data boundaries

- Cookie material never leaves the encrypted column; `serialize_credential()`
  returns a redacted view for API responses.
- Object-level ownership **is** enforced on the existing platform credential and
  benchmark-account endpoints: `_get_owned_credential()` / `_get_owned_account()`
  in `backend/app/api/platforms.py` resolve the row and call `ensure_same_user()`
  from `core/auth/ownership.py`. A non-owner gets **404**, not 403, so the
  endpoints do not leak the existence of another user's row. Covered today:
  credential delete, benchmark-account delete, feed, and sync.
- `net_guard.py` is still **not** a global outbound policy, but its coverage is
  no longer limited to the proxy endpoint: it is wired into
  `backend/app/api/images.py` and into `backend/app/services/image_service.py`
  (provider calls, including the Agnes native POST). Those paths now share the
  same scheme/credential/DNS/private/metadata checks, the same strict redirect
  re-validation, and the same default port allowlist (`443` only). Other
  outbound callers such as `credential_service.py` still use `httpx` directly,
  so a private/loopback target raises `OutboundRequestBlocked` only on paths
  that actually went through the guard.

## 6b. Error contract (platforms)

`backend/app/api/platforms.py` raises `app.core.errors.AppError` only. No route
interpolates an exception into a response body.

- Expected business failures raise `AppError` with wording owned by the public
  contract. Examples: an unsupported QR-login platform or unparsable cookie
  payload → `VALIDATION_ERROR` / 400 (the parser's own message is not echoed);
  an unresolvable benchmark account → `NOT_FOUND` / 404; an unknown or expired
  QR session key on `simulate-confirm` → `NOT_FOUND` / 404.
- Service `ValueError`s (crawler, cookie parser, QR service) are translated into
  a fixed public message; the original text is never interpolated.
- Unexpected exceptions are **not** caught. They propagate to the global
  `Exception` handler in `backend/app/main.py`, which logs the traceback
  server-side and returns the fixed `INTERNAL_ERROR` / 500 body. Handlers must
  not log the same failure a second time.

Every error body carries `error.code` and `error.request_id`; the request id
equals the `X-Request-ID` response header set by the globally registered
`RequestIdMiddleware`.

## 6c. Trusted identity for credential and account routes

Credential, benchmark-account, feed, sync, and batch-ingest routes take
`current_user: AuthenticatedUser = Depends(get_current_user)`; there is no global
entry-point dependency, so genuinely public endpoints and the BYOK `X-API-Key`
semantics are unaffected.

- Ownership is resolved through the existing helpers `_get_owned_account` /
  `_get_owned_credential`, which delegate to `ensure_same_user` /
  `not_found` from `core/auth/ownership.py`. No parallel ownership mechanism was
  introduced.
- A cross-user credential or benchmark account answers `NOT_FOUND` / 404 rather
  than 403, matching the pre-existing anti-enumeration model.
- Missing or invalid credential → `AUTH_REQUIRED` / 401.
- Owner id passed to the service layer is always `current_user.id`.
## 7. Honest gaps

1. **Ownership is a handler-level helper, not a policy engine.** The checks above
   live in per-handler helpers inside `platforms.py`. There is no router-level or
   dependency-level authorization layer, so a newly added endpoint can silently
   forget the check.
2. **QR login status is not bound to the caller.** `GET
   /api/platforms/credentials/qr/status` resolves `current_user`, but
   `check_qr_login_status()` is called with only `session_key` — the session key is
   not verified to belong to the authenticated user. Authenticated is not the
   same as authorized here.
3. **`simulate-confirm` is a development affordance** shipped in the production
   router. It should be environment-gated.
4. **Playwright is a singleton worker.** Concurrent QR sessions share one browser
   process; this is a concurrency limit, not a bug.
5. **Platform behaviour is brittle by nature.** Each platform's DOM and login
   flow change without notice; there is no contract test against live platforms.

## 8. Related

- `06_Scheduler_and_Unattended_Skills.md` — unattended execution path.
- `08_Data_Model_Reference.md` — `PlatformAccountCredential`, `BenchmarkAccount`.


## Internal Module Layout

skills/content-multi-distributor/ is invoked through its frontmatter
entrypoint scripts/distribute.py. The script is internally split by
responsibility; CLI flags, stdout JSON schema and formatter output are
unchanged.

| File | Responsibility |
| --- | --- |
| skills/content-multi-distributor/scripts/distribute.py | CLI entrypoint, distribute_content, main, compatibility re-exports |
| skills/content-multi-distributor/scripts/_content.py | Title cleaning, content parsing, key sentences, hashtags |
| skills/content-multi-distributor/scripts/_markdown_links.py | Markdown link parsing, reference-definition pattern |
| skills/content-multi-distributor/scripts/_references.py | Footnote extraction and link replacement |
| skills/content-multi-distributor/scripts/_formatters_xhs.py | Xiaohongshu formatter, section illustration prompts |
| skills/content-multi-distributor/scripts/_formatters.py | WeChat / Twitter / video formatters |

Sandbox guarantees are unchanged; see
docs/architecture/10_Sandbox_and_Permission_Model.md.

## 2026-10-15 defect fix: formatter helper availability

The formatter modules called `clean_title_text` and `extract_footnotes` without
defining or importing them, so local formatting/preview for WeChat, Twitter,
video and Xiaohongshu output failed at call time (`NameError`). `_formatters.py`
now defines `clean_title_text` and `extract_footnotes`, and `_formatters_xhs.py`
defines its own `clean_title_text`. This only restores local
formatting/preview; multi-platform auto-publishing remains unimplemented and
unverified against any real platform.
