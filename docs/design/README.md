# Design Docs Index

Status: **current**. Introduced on `codex/design-docs`. This layer answers a
question the architecture layer cannot: *for a given feature, what is actually
designed, what is deliberately not designed, and where is the boundary?*

## Why this layer exists

Before this layer the repository had:

- `docs/architecture/` — how the system is put together (layers, security model).
- `docs/architecture/11_Feature_Map_v0.2.md` — a one-line-per-module inventory.

What it did **not** have was a per-feature design record. A new surface could be
added by writing one table row in the feature map. That is inventory, not design.

This directory adds the missing layer. It is organised **by domain, not by file**:
one design document per coherent capability, listing every code path it owns.
60+ individual module documents would be unmaintainable and would rot faster than
the code they describe.

## The documents

| Doc | Domain | Owns |
| --- | --- | --- |
| `01_Creation_Pipeline.md` | Outline → draft → edit → archive → diff/DNA evolution | `api/outlines.py`, `api/drafts.py`, `api/blueprints.py`, `engine/cognitive_engine.py`, `engine/agents/*` |
| `02_Cognitive_Profile_and_DNA.md` | Thinking DNA, persona, product, story, timeline, memory | `api/dna.py`, `api/dna_v2.py`, `services/cognitive_service.py`, `services/memory_service.py`, `services/feedback_service.py` |
| `03_Viral_Semantic_Analysis.md` | Viral/benchmark article semantic decomposition | `api/viral_analysis.py`, `services/viral_semantic_service.py`, `engine/prompts/viral_prompts.py` |
| `04_Distribution_and_Credentials.md` | Platform accounts, cookies, crawling, distribution | `api/platforms.py`, `services/credential_service.py`, `services/platform_crawler_service.py`, `services/playwright_service.py` |
| `05_Material_Vault_and_Obsidian.md` | Material assets, URL collection, Obsidian bridge | `api/materials.py`, `api/obsidian.py`, `services/material_service.py`, `services/obsidian_service.py` |
| `06_Scheduler_and_Unattended_Skills.md` | Scheduled inspection, quota, daily briefing, skill execution | `api/scheduler.py`, `services/inspection_scheduler_service.py`, `services/inspection_quota_service.py`, `core/skill_engine/*`, `skills/*` |
| `07_Surfaces_and_Engagement.md` | Chat lounge, private domain, images, settings, feedback | `api/chat_lounge.py`, `api/private_domain.py`, `api/images.py`, `api/settings.py`, `frontend/src/components/*` |
| `08_Data_Model_Reference.md` | Every table, field group, and relation | `models/*` |

Security and isolation truth is **not** duplicated here. It lives in
`../architecture/10_Sandbox_and_Permission_Model.md` and is referenced, not
restated, so the two documents cannot drift apart.

## Rules for these documents

1. **Code is the current fact.** If a document disagrees with the code, the
   document is the bug.
2. **Every claim names a code path.** A reader must be able to verify any
   statement by opening a file.
3. **Status vocabulary is fixed**: Implemented / Partial / Not started / Planned.
   A planned item is never described as if it existed.
4. **No secrets, endpoints or credentials.** Behaviour is described; connection
   strings and keys are not.
5. **New public surface requires a design doc or an explicit waiver.** This is
   enforced by `scripts/check_doc_coverage.py`; see
   `../architecture/13_Documentation_Governance.md`.

## Coverage contract

`11_Feature_Map_v0.2.md` remains the per-module inventory. Each row there should be
reachable from one of the design docs above. When you add a module, add it to the
feature map **and** to the owning design doc in the same change.
