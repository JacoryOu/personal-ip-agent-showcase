# Feature status (code-verified, 2026-10-15)

> [中文](feature-status.md) | English

Legend:
**A** = implemented and covered by a passing test
**B** = implemented but not run against a real dependency in this pass
**C** = in development or has a known defect
**P** = planned only, not implemented

## Core content loop

| # | Feature | Status | Code evidence |
| --- | --- | --- | --- |
| 1 | Divergent A/B outline generation | A | `engine/agents/outline_agent.py`, `api/outlines.py`, `tests/test_outline_agent_mock.py` |
| 2 | Draft generation with IP context | A | `engine/agents/draft_agent.py`, `api/draft_generation.py` |
| 3 | Draft failure-path error contract | C | `api/draft_generation.py:68` NameError on `status` |
| 4 | Draft archive + lineage | A | `api/draft_archive.py`, `api/draft_lineage.py`, `tests/test_drafts_archive_api.py` |
| 5 | Draft feedback | A | `api/draft_feedback.py`, `tests/test_feedback_and_evolution.py` |
| 6 | Diff-based Thinking DNA extraction | A | `engine/agents/diff_agent.py`, `tests/test_diff_agent.py` |
| 7 | Zero-diff baseline gate (skips LLM) | A | `diff_agent.py`, `tests/test_diff_agent.py` |
| 8 | DNA v2 + timeline + supersede | A | `api/dna_v2*.py`, `tests/test_dna_v2_and_timeline.py` |
| 9 | Persona extraction / cognitive interview | A | `api/dna_v2_persona_extract*.py`, `tests/test_persona_extraction_and_interview.py` |
| 10 | Viewpoint-conflict detection | C | `services/memory_conflicts.py:124` NameError |
| 11 | Closed-loop profile evolution | A | `services/cognitive_evolution_service.py`, `tests/test_closed_loop_and_profile.py` |
| 12 | DNA portability (export/import) | A | `api/dna_portability.py`, `services/cognitive_portability_service.py` |
| 13 | Style fingerprint selection for drafts | A | `services/style_selection_service.py`, `tests/test_style_selection_service.py` |
| 14 | Viral semantic analysis (style fingerprint) | A | `api/viral_analysis.py`, `tests/test_viral_semantic_analysis.py` |
| 15 | Viral rubric benchmark (43 samples) | B | `engine/rubrics/`, `tests/test_viral_rubric_benchmark.py` (label provenance unconfirmed) |
| 16 | Chat lounge (session + crystallization) | B | `api/chat_lounge*.py`, `tests/test_chat_lounge.py` |
| 17 | WeChat chat-record import | P | no import path found in code |
| 18 | Image generation | B | `services/image_service.py`, `tests/test_image_generation.py` |
| 19 | Product vault | B | `models/product.py`, `tests/test_product_image_vault.py`, `test_product_vault_extraction.py` |
| 20 | Material vault + Obsidian bridge | B | `services/material_service.py`, `obsidian_service.py`, `tests/test_materials_and_lineage.py`, `test_obsidian_bridge.py` |
| 21 | Private domain surfaces (moments/community) | B | `api/private_domain*.py`, `tests/test_private_domain.py` |

## Memory

| # | Feature | Status | Code evidence |
| --- | --- | --- | --- |
| 22 | Episodic stories CRUD | A | `services/memory_service.py`, `models/story.py` |
| 23 | Hybrid retrieval (lexical + cosine embedding) | A | `services/memory_retrieval.py`, `memory_dna_retrieval.py`, `memory_similarity.py` |
| 24 | Blueprint skeletons from benchmark articles | A | `services/memory_blueprints.py`, `api/blueprints.py`, `tests/test_blueprint_extraction_api.py` |
| 25 | DNA embedding + similarity retrieval | A | `memory_dna_retrieval.py` |
| 26 | Memory benchmarking helpers | B | `services/memory_benchmarks.py` |

## Platform / distribution

| # | Feature | Status | Code evidence |
| --- | --- | --- | --- |
| 27 | Platform account management | A | `services/platform_crawler_account_service.py`, `tests/test_platform_accounts_and_ingestion.py` |
| 28 | Platform feed collection (crawler) | B | `services/platform_crawler_*.py`, `tests/test_platform_accounts_and_ingestion.py` (no live network run) |
| 29 | Live QR login | B | `tests/test_live_qr_login.py` (needs a real account) |
| 30 | Multi-platform formatting (wechat / xhs / x / short video) | C | `skills/content-multi-distributor/scripts/_formatters*.py` NameError |
| 31 | Automatic publishing to platforms | P | no publish API exists; only formatting + preview |
| 32 | Trending radar skill | B | `skills/trending-radar/` |

## Skill engine and sandbox

| # | Feature | Status | Code evidence |
| --- | --- | --- | --- |
| 33 | SKILL.md discovery + policy | A | `core/skill_engine/`, `tests/test_skill_engine.py`, `test_skill_permission_policy.py` |
| 34 | Windows Restricted Token execution | B | `core/skill_engine/restricted_token.py`, `tests/test_restricted_token.py` (real run needs Windows host) |
| 35 | Job object for child processes | B | `core/skill_engine/job_object.py`, `tests/test_job_object.py` |
| 36 | ACL path guard | A | `core/skill_engine/acl_guard.py`, `tests/test_acl_guard.py`, `test_path_containment.py` |
| 37 | Fail-closed mode transparency | A | `core/skill_engine/windows_sandbox.py`, `tests/test_sandbox_mode_transparency.py` |
| 38 | Windows Sandbox (`.wsb`) execution | P | `runner_mode="wsb_unsupported"`, never launched |
| 39 | AppContainer / filesystem / network isolation | P | not implemented |
| 40 | OS-level network boundary | B | `core/skill_engine/os_network_boundary.py`, `tests/test_os_network_boundary.py` |

## Platform concerns

| # | Feature | Status | Code evidence |
| --- | --- | --- | --- |
| 41 | Public/private route boundary | A | `api/auth_boundary.py`, `tests/test_api_auth_surface.py` |
| 42 | Ownership enforcement | A | `tests/test_auth_and_ownership.py`, `test_security_private_surfaces.py` |
| 43 | SSRF guard | A | `core/net_guard.py`, `tests/test_net_guard*.py` |
| 44 | Credential encryption at rest | A | `core/crypto/secret_box.py`, `tests/test_credential_encryption.py` |
| 45 | Vault path containment | A | `core/vault_path_guard.py`, `tests/test_path_containment.py`, `test_sec_path_quota.py` |
| 46 | Driver-level read-only DB engine | A | `core/db.py`, `tests/test_agent_db_readonly.py` |
| 47 | Error contract (no traceback leakage) | A | `core/errors.py`, `tests/test_error_contract.py` |
| 48 | Rate / inspection quota | B | `services/inspection_quota_service.py`, `tests/test_inspection_quota*.py` |

## Governance

| # | Feature | Status | Code evidence |
| --- | --- | --- | --- |
| 49 | Code style gate (line caps, naming, prompt location) | A | `scripts/check_code_style.py`, `scripts/code_style_baseline.txt`, `tests/test_code_style.py` |
| 50 | Doc coverage gate (commit must declare doc impact) | A | `scripts/check_doc_coverage.py`, `tests/test_doc_coverage.py` |
| 51 | Shared git hooks (pre-commit / commit-msg / post-merge) | B | `scripts/install_git_hooks.ps1`, `scripts/install_git_hooks.sh` |
| 52 | CI pipeline | P | no CI configuration in the repository |
| 53 | Deployment configuration | P | none found |
| 54 | Fine-tuning (LoRA / QLoRA) | P | not implemented; conceptual knowledge only |
| 55 | RAG chat with citations / re-ranking / answer scoring | P | hybrid retrieval exists, but no grounded QA pipeline, no reranker, no answer-quality eval |

## Not measured / unknown

- Real-model end-to-end run.
- Real PostgreSQL run.
- Live external network collection.
- Latency / cost / throughput.
- Who authored the 43 rubric labels.
