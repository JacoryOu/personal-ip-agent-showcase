# 05 — Material Vault and Obsidian

Status: **Partial**. Verified against `main@4d643ad`.
Material storage is complete. The Obsidian bridge is implemented, but its
permission boundary is not finished, and the `sync` endpoint does **not** do what
its name suggests — it imports, it does not push material into a vault.

## 1. Scope and code paths

| Path | Role |
| --- | --- |
| `backend/app/api/materials.py` | Compatibility facade over `backend/app/api/materials_common.py`, `materials_crud.py`, `materials_item.py`, `materials_collect.py` (Material CRUD + URL collection + trending fetch; routes unchanged) |
| `backend/app/services/material_service.py` | Storage, trending fetch, classification |
| `backend/app/api/obsidian.py` | Vault scan / sync / status / allowed roots |
| `backend/app/services/obsidian_service.py` | Markdown parsing, candidate classification, DNARecord import |
| `backend/app/core/vault_path_guard.py` | Confines vault access to allowed roots |
| `backend/app/models/material.py` | `Material` |
| `skills/content-collector/` | Unattended collection skill |
| `skills/trending-radar/` | Unattended trending skill |
| `frontend/src/components/MaterialVault.vue` | Surface |

## 2. Material flow

```
pasted text ─────────────┐
POST /materials/collect-url ─┼→ Material row (kind, title, content, hash)
POST /materials/fetch-trending ┘
  → GET /materials            list
  → GET|PATCH|DELETE /materials/{id}
```

`material_service` performs its DB work through an injected session and is the
only place that knows the write shape; the API layer stays thin.

## 3. Obsidian bridge — real direction of data flow

```
POST /obsidian/scan     → walk allowed roots, parse *.md, return candidates
POST /obsidian/sync     → import SELECTED vault notes as DNARecord rows (DB write)
GET  /obsidian/status   → configured? root? last sync?
GET  /obsidian/allowed-roots → what the guard currently permits
```

The direction is **Vault → DNARecord**, not Material → vault.
`obsidian_service.sync_items()` is explicit about this: it *does not write
anything to the vault*. Its docstring states it does not touch the vault; the
selected notes are parsed and committed as `DNARecord` rows through the
injected session.

Consequences worth being precise about:

- `/obsidian/sync` is a historical name. It is an **import / ingest**, not a
  two-way sync.
- There is **no** Material → vault export path anywhere in the codebase.
- Vault edits are never written back to `Material` rows.
- The `session` dependency exists because the import commits to the DB, not
  because the vault is written to. `scan` and `status` do not write.
- `GET /obsidian/status` does take a session, but it only **reads**: it counts
  `.md` files under the vault and then counts Obsidian-sourced `DNARecord`
  rows. That synced-record count is computed over the whole `DNARecord`
  table, not filtered by user, so it is a global figure rather than a
  per-user one.

`obsidian_service` parses YAML front matter (`_parse_frontmatter`), derives a
date (`_extract_date`), tags (`_extract_tags`), an excerpt plus candidate spans
(`_extract_excerpt_and_candidates`), and classifies each candidate
(`_classify_candidate`).

## 4. Path boundary

`vault_path_guard.py` raises `VaultPathError` / `VaultPathNotFound` /
`VaultPathNotADirectory`. Only configured roots are reachable; a path that
escapes them via `..` or a symlink is rejected. With no valid root configured it
fails closed onto a narrow default root
(`backend/data/obsidian_vaults`, overridable via `OBSIDIAN_ALLOWED_ROOTS`).

This guard contains **path traversal only**. It does not establish identity,
authentication, authorization, or multi-tenant ownership. Do not read it as a
security boundary on its own.

### 4.1 Vault traversal containment (implemented)

`obsidian_service.py` does **not** use `vault.rglob("*.md")` for the scan or for
the note count in `GET /obsidian/status`. Both call
`iter_safe_markdown_files()` from `vault_path_guard.py`, which:

- walks the vault without following symlinks, junctions, or any other Windows
  reparse point (`os.path.islink()` plus
  `st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT` / `FILE_ATTRIBUTE_DEVICE`);
- re-`resolve()`s every candidate and requires it to satisfy
  `relative_to(vault_root_resolved)`, so a second line of defence still applies
  after the walk;
- skips any candidate whose `resolve()` raises (`OSError`, or `RuntimeError` on a
  symlink loop, or a permission error) instead of failing the whole scan;
- returns a stably sorted list, so scan order and the reported note count stay
  deterministic.

Consequence: a junction planted inside the vault can no longer make the bridge
read Markdown from outside the vault root, and can no longer inflate or leak the
external-file count through `GET /obsidian/status`.

Note the scope, honestly: `vault_path_guard.py` still contains **path
containment only**. It establishes nothing about identity, authentication,
authorization, or multi-tenant ownership. See section 6.

## 5. API surface

`GET|POST /api/materials`, `POST /api/materials/collect-url`,
`POST /api/materials/fetch-trending`,
`GET|PATCH|DELETE /api/materials/{material_id}`

`POST /api/obsidian/scan`, `POST /api/obsidian/sync`, `GET /api/obsidian/status`,
`GET /api/obsidian/allowed-roots`

## 6. Permission boundaries — implemented

Both routers now require an authenticated identity, and the authenticated
credential is the only identity source:

- Every Material route declares `get_current_user` as a dependency.
- Every Obsidian route (`scan`, `sync`, `status`, `allowed-roots`) declares
  `get_current_user` as a dependency.
- A `user_id` supplied in a request body or query string is **ignored** for
  authorization purposes. It is never used to decide ownership.

Material resources are scoped to the caller:

- `Material.user_id == current_user.id` is applied to list, patch, delete, and
  fetch-trending.
- A material belonging to another user, a material that does not exist, and a
  malformed UUID all return the same redacted `404` with the message
  `Material not found.` The distinction is never leaked.

Obsidian specifics:

- `POST /obsidian/sync` ignores the body `user_id`; imported `DNARecord` rows
  are owned by `current_user.id`.
- `VaultPathError` maps to a fixed public error: HTTP `422`, code
  `VALIDATION_ERROR`, message `Vault path is not allowed.` The absolute path is
  never echoed back to the client.

Two independent boundaries apply to Obsidian:

1. Authentication/authorization — who may call the bridge at all, and whose
   DNA records the import writes.
2. Path containment (`vault_path_guard`) — which files on disk the bridge may
   read.

Neither substitutes for the other. The path guard is still **path containment
only**; it establishes nothing about identity.

## 7. Honest gaps

1. **Vault roots are server-configured, not per-user.** The allowed-roots
   allow-list is process configuration, so two authenticated users share the
   same set of readable vault roots. This is authentication plus path
   containment, not a per-user Vault ACL.
2. **The `sync` endpoint name is misleading.** It reads as a push into the
   vault; it is actually a pull out of it. Renaming it to `import` would make
   the direction unambiguous.
3. **`GET /obsidian/status` reports a global synced-record count**, so the
   number is not scoped to the calling user.
4. **Candidate classification is heuristic.** A mis-tagged note stays mis-tagged
   until the user moves it.
5. **Trending fetch depends on external sources** and degrades silently to an
   empty result rather than raising.
6. **No dedup across sources.** `collect-url` and `fetch-trending` can create two
   rows for the same article; there is no content-hash uniqueness constraint.

## 8. Related

- `02_Cognitive_Profile_and_DNA.md` — `DNARecord`, the import target.
- `03_Viral_Semantic_Analysis.md` — the consumer that analyses collected material.
- `08_Data_Model_Reference.md` — `Material`.
- `../architecture/10_Sandbox_and_Permission_Model.md` — why path guards are not
  an authorization layer.

## Internal Module Layout

skills/trending-radar/ is invoked through its frontmatter entrypoint
scripts/radar.py. The script is internally split by responsibility; CLI flags,
stdout JSON schema and offline fallback behaviour are unchanged.

| File | Responsibility |
| --- | --- |
| skills/trending-radar/scripts/radar.py | CLI entrypoint + compatibility re-exports |
| skills/trending-radar/scripts/_data.py | User agent, fallback topic pool, platform weights |
| skills/trending-radar/scripts/_fetchers.py | Per-platform HTTP fetchers and dispatch map |
| skills/trending-radar/scripts/_core.py | Relevance scoring, aggregation, result shaping |

Sandbox guarantees are unchanged; see
docs/architecture/10_Sandbox_and_Permission_Model.md.
