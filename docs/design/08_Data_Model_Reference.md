# 08 — Data Model Reference

Baseline: `main@4d643ad`.

All persistent state is declared with SQLModel in `backend/app/models/`
(13 model files, 14 tables). Schema is created with
`SQLModel.metadata.create_all`; there is **no Alembic migration history**, so
see "Migration notes" below.

Ownership rule: rows that belong to a person carry `user_id`. Models created
before the FK convention (`ip_personas`, `product_vault`, `episodic_stories`,
`inspection_quotas`, `chat_session`) store `user_id` as a plain indexed column
without a foreign key.

## Table index

| Table | Model | File | Domain doc |
|---|---|---|---|
| `users` | `User` | `user.py` | 02 |
| `chat_session` | `ChatSession` | `chat_session.py` | 07 |
| `chat_message` | `ChatMessage` | `chat_session.py` | 07 |
| `ip_personas` | `IPPersona` | `persona.py` | 02 |
| `product_vault` | `ProductVault` | `product.py` | 02 |
| `episodic_stories` | `EpisodicStory` | `story.py` | 02 |
| `dna_records` | `DNARecord` | `dna_record.py` | 02 |
| `drafts` | `Draft` | `draft.py` | 01 |
| `draft_feedbacks` | `DraftFeedback` | `feedback.py` | 02 |
| `materials` | `Material` | `material.py` | 05 |
| `viral_semantic_analyses` | `ViralSemanticAnalysisRecord` | `viral_analysis.py` | 03 |
| `platform_credentials` | `PlatformAccountCredential` | `credential.py` | 04 |
| `benchmark_accounts` | `BenchmarkAccount` | `benchmark_account.py` | 04 |
| `inspection_quotas` | `InspectionQuota` | `inspection_quota.py` | 06 |
| `scheduler_user_states` | `SchedulerUserState` | `scheduler_state.py` | 06 |

## 1. Identity — `backend/app/models/user.py`

- `id` UUID PK; `username` unique indexed; `email` optional unique indexed.
- `profile_data`: JSON map of profile facts.
- Timestamps: `created_at`, `updated_at`.

## 2. Chat — `backend/app/models/chat_session.py`

- `ChatSession`: **string** `id` (uuid4 rendered as str), `user_id` (indexed,
  no FK), `title` (default "新对话"), `mode` (default `free_talk`),
  `message_count`, `created_at`, `updated_at`.
- `ChatMessage`: integer autoincrement `id`, `session_id` (indexed, no FK),
  role/content, `ts`.
- There is no FK from `chat_message.session_id` to `chat_session.id`, so
  deleting a session relies on application-level cleanup.

## 3. Persona / Product / Story — `persona.py`, `product.py`, `story.py`

- `IPPersona`: `user_id` indexed, `name` indexed, `target_audience`,
  `tone_style`, `reader_salutation`, `origin_story`, `is_active`. One active
  persona per user is a convention enforced in code, not a DB constraint.
- `ProductVault`: product copy fields (`product_name`, `category`,
  `core_ingredients`, `suitable_conditions`, `taboos`,
  `personal_usage_experience`, `conversion_hooks`) plus image lists
  (`cover_image`, `gallery_images`, `service_rights_images`) and `is_active`.
- `EpisodicStory`: `title`, `story_content`, `story_type`, `occurred_at`,
  `tags` (JSON), `confidence_score`, and an optional `embedding` blob used for
  similarity retrieval.

## 4. DNA and feedback — `dna_record.py`, `feedback.py`

- `DNARecord`: `user_id` FK → `users.id`, optional `draft_id` FK →
  `drafts.id`, `dna_data` JSON (`sa_column=JSON` on PostgreSQL, JSON text on
  SQLite), `created_at`. Append-only history; evolution appends new records.
- `DraftFeedback`: `draft_id` FK, `user_id` FK, `comments_text`, `metrics`
  JSON, `extracted_insights` JSON, `boosted_dna_traits` JSON list,
  `saved_material_ids` list.

## 5. Drafts — `draft.py`

- `Draft`: `user_id` FK, `user_final_draft` (the human-edited text),
  optional `source_material_id`, `benchmark_blueprint_id`,
  `lineage_snapshot` JSON, `metadata_` JSON (the attribute name avoids
  shadowing SQLModel's `metadata`), timestamps.
- Draft archive is written on a **writable** session even though the Outline /
  Draft agent read path is read-only.

## 6. Materials — `material.py`

- `Material`: `user_id` FK, `material_type` (default `benchmark`),
  `source_platform` / `source_url` / `source_author`, `title`, `raw_content`,
  `cleaned_content`, `blueprint_data` JSON, `tags` JSON list, `status`
  (default `inbox`, indexed), `meta_info` JSON.

## 7. Viral analyses — `viral_analysis.py`

- `ViralSemanticAnalysisRecord`: optional `user_id` FK and optional
  `material_id` FK, `source_title`, indexed `source_content_hash`,
  `source_platform` / `source_url`, `status` (default `completed`),
  `extraction_mode` (default `llm`; `deterministic` / `fallback` also occur),
  `analysis_data` JSON holding the fingerprint / hook structure,
  `warnings` JSON list, `model_name`, timestamps.
- `user_id` is nullable so an analysis can be produced for a URL that was never
  saved as a material.

## 8. Credentials and benchmark accounts — `credential.py`,
`benchmark_account.py`

- `PlatformAccountCredential`: `user_id` FK, `platform` indexed,
  `account_identifier`, **encrypted** `cookies` JSON, `status`
  (default `pending_login`; e.g. `active`), `qr_code_data`, indexed
  `session_key`, `last_checked_at`, `expires_at`, `meta_info` JSON.
  Encryption is provided by the `backend/app/core/crypto/` package (`__init__.py`, `secret_box.py`); `credential_service.py` imports from `app.core.crypto`. There is no single-module `core/crypto.py`.
- `BenchmarkAccount`: `user_id` FK, `platform` / `account_name` /
  `account_id` indexed, optional `home_url`, `avatar_url`, `bio`,
  `follower_count`, `notes_count`, `last_synced_at`, `status` (default
  `active`), `meta_info` JSON.

## 9. Inspection quota — `inspection_quota.py`

- `InspectionQuota`: `user_id` **unique** (one row per user), `enabled`
  (default true), `authorized` (default **false** — unattended skill runs are
  opt-in), `daily_limit` (default 5), `per_run_limit` (default 1), `day`
  (current quota day string), `used_today`, `used_this_run`, `last_run_at`,
  `last_denied_at`, `last_denial_reason`, `last_error`, `total_runs`,
  `total_denied`, `extra_data` JSON, timestamps (timezone-aware UTC).

## 9a. Scheduler per-user state - `scheduler_state.py`

- `SchedulerUserState`: table `scheduler_user_states`, **new table only** (no
  existing table's columns changed, so it does not collide with other schema
  work in flight).
- `user_id` **unique** - one row per real user, mirroring `InspectionQuota`'s
  convention (plain indexed column, no FK; see the note below).
- `settings` JSON: serialized `SchedulerSettings` (the `model_dump()` of
  `app.schemas.scheduler_schemas.SchedulerSettings`), so interval / briefing
  time / interest tags / automated toggles survive a restart.
- `dismissed_date`: optional `YYYY-MM-DD` string - the last briefing the user
  read or confirmed.
- `quota_decision` JSON: last quota-gate decision payload; `last_summary` JSON:
  last execution summary surfaced on the status endpoint.
- `created_at` / `updated_at` timezone-aware UTC.

Scope: rows exist only for *real* users. The background scheduler loop has no
acting user and keeps its `DEFAULT_SCOPE` configuration in process memory - it
deliberately never writes a row, because there is no `users` row to attach to.

## Foreign keys and delete behaviour

Every declared foreign key (`benchmark_accounts.user_id`, `materials.user_id`,
`platform_credentials.user_id`, `drafts.user_id`, `drafts.source_material_id`,
`viral_semantic_analyses.user_id`, `viral_semantic_analyses.material_id`,
`dna_records.user_id`, `dna_records.draft_id`, `draft_feedbacks.user_id`,
`draft_feedbacks.draft_id`) is declared **without `ondelete=`**, so the database
has no `ON DELETE` rule for any of them. Deleting a parent row therefore relies
on the database's default `NO ACTION` behaviour rather than a configured
cascade.

The only explicit cascade in the ORM layer is:

```python
Draft.feedbacks  # sa_relationship_kwargs={"cascade": "all, delete-orphan"}
```

so deleting a `Draft` removes its `DraftFeedback` rows through SQLAlchemy.

Consequences that documentation must not overstate:

- Removing a user does **not** automatically remove their credentials,
  materials, drafts, DNA records or analyses at the database level.
- Deleting a `Material` does **not** cascade to `drafts.source_material_id` or
  `viral_semantic_analyses.material_id` in the database.
- Relationships other than `Draft.feedbacks` set neither `cascade` nor
  `passive_deletes`, so their runtime delete behaviour depends on whether the
  parent object is loaded in the session.

## Migration notes

- Schema is applied by `SQLModel.metadata.create_all`, which **creates missing
  tables but does not alter existing ones**. Adding a column to an existing
  model will not be applied to an existing database.
- There is no migration tool or version table, so there is no ordered upgrade
  path and no rollback story.
- JSON columns are declared with a variant that works on SQLite and
  PostgreSQL; the same field can be JSONB on PostgreSQL and TEXT on SQLite.
  Queries must not assume a specific physical type.
- If a real migration path is introduced later, every table above needs a
  baseline revision, and `create_all` should become a fallback for tests only.

## Known limitations

- No foreign keys on chat tables, personas, products, stories or quotas.
- `IPPersona` uniqueness per user is convention-only.
- `metadata_` / `meta_info` / `extra_data` are loosely typed JSON bags; their
  contents are only defined by the writing service.
- `EpisodicStory.embedding` has no index or vector column, so retrieval is done
  in application code.
- No soft-delete or audit columns anywhere.
- `EpisodicStory.tags` is a plain `JSON` column (not the PostgreSQL
  JSONB variant used by most other JSON fields) and defaults to an empty list.
