# Evaluation and test evidence

> [中文](evaluation.md) | English

All numbers below were produced by running the test suite locally on
2026-10-15 with the repository virtual environment, single process, no CI.

```
cd backend
.\.venv\Scripts\python -m pytest -q
-> 18 failed, 992 passed, 3 skipped, 85 warnings in 66.88s
```

The desensitized copy in this directory was re-tested with the same command and
produced the **same** result as the source repository: `18 failed, 992 passed, 3 skipped` (70.64s).

The system interpreter (`python -m pytest`) fails because it lacks
`pydantic_settings`; that is an environment error and is **not** counted as a
project test result.

## 1. What kind of testing this is

| Layer | What it proves | What it does NOT prove |
| --- | --- | --- |
| Unit / integration tests (pytest; 55 files under `backend/tests` plus 18 root-level `backend/test_*.py` files) | that the code paths execute and the contracts hold | nothing about a real LLM, real PostgreSQL, real network egress, or real users |
| Mocked model gateway | prompt assembly, schema parsing, gating, ownership, persistence | model quality, latency, cost, hallucination rate |
| Real model call | run **once** for the flow in section 6 (no corpus, no quality metrics) | anything about reliability, quality, latency or cost |
| Real PostgreSQL | **not run in this pass** (default is SQLite) | - |
| Real multi-user security exercise | **not performed** | - |

Most agent tests substitute the model gateway, so they are deterministic and
fast. Treat "992 passed" as "the harness works", not as "the product works".

## 2. Failures (real defects, not environment)

| Test | Count | Root cause |
| --- | --- | --- |
| `test_blueprint_creation_and_distribution.py` | 15 | `skills/content-multi-distributor/scripts/_formatters_xhs.py` and `_formatters.py` call `clean_title_text` without importing it from `_content`. Breaks WeChat / Xiaohongshu formatting. |
| `test_dna_conflict_and_management.py::test_viewpoint_conflict_detection` | 1 | `backend/app/services/memory_conflicts.py:124` annotates a parameter as `CognitiveTrait` without importing it. |
| `test_api_routes.py::test_generate_draft_error_handling` | 1 | `backend/app/api/draft_generation.py:68` uses `status.HTTP_422_UNPROCESSABLE_CONTENT` but `status` is not imported. Only affects the ValueError failure path. |
| `tests/test_api_auth_surface.py::test_public_endpoint_registry_matches_application` | 1 | `ModuleNotFoundError: No module named 'scripts'` when pytest runs from `backend/`. This is a sys.path / run-location issue, not a business defect. |

All three business defects are one-line import fixes. They are left in place
because this pass was documentation-only.

## 3. Benchmark with a real dataset

`backend/app/engine/rubrics/data/viral_rubric_benchmark_v1.json` holds **43
human-labeled samples**. `backend/app/engine/rubrics/viral_benchmark.py` scores
the deterministic rubric implementation against those labels using:

- within-one-level accuracy
- mean absolute error (MAE)
- exact match

Recommended thresholds in the code: MAE <= 0.8, exact match >= 0.60.

**Critical caveat**: this measures whether the rule-based rubric reproduces
human labels. It does **not** measure LLM generation quality, and the reviewer
must know who produced those 43 labels (unconfirmed - see resume-notes).

## 4. Explicitly not measured

Do not put any of these on a resume; there is no evidence in this repository:

- Retrieval recall / precision / MRR / nDCG. The hybrid retriever has no
  labeled retrieval set.
- Answer or draft quality scores from human raters.
- End-to-end latency, time-to-first-token, throughput, token cost.
- Any "improved X%" or "reduced Y%" claim.
- User counts, active users, published posts, GMV, hours saved.
- Real-model reliability, safety or jailbreak rates.

## 5. Security regression suites (all currently passing)

| Area | Tests |
| --- | --- |
| Read-only DB enforcement | `tests/test_agent_db_readonly.py` |
| Route auth surface | `tests/test_api_auth_surface.py` (one sys.path failure), `tests/test_auth_and_ownership.py` |
| SSRF | `tests/test_net_guard.py`, `test_net_guard_image_service.py`, `test_settings_ssrf.py` |
| Credential encryption | `tests/test_credential_encryption.py`, `test_secret_box.py` |
| Prompt / secret leakage | `tests/test_security_*.py`, `test_error_contract.py` |
| Sandbox | `tests/test_restricted_token.py`, `test_sandbox_mode_transparency.py`, `test_sandbox_acl_integration.py`, `test_os_network_boundary.py`, `test_job_object.py`, `test_sandbox_permission_gate.py` |
| Workflow permissions | `tests/test_workflow_permissions.py`, `test_workflow_permission_gate.py` |
| Governance gates | `tests/test_code_style.py`, `tests/test_doc_coverage.py` |

## 6. Reproducing the governance gates

```powershell
python scripts/check_doc_coverage.py --base main
python -m pytest backend/tests/test_doc_coverage.py -q
python scripts/check_code_style.py
python scripts/check_code_style.py --base main
python -m pytest backend/tests/test_code_style.py -q
```

## 6. Real-model end-to-end run (added 2026-10-15, this pass)

One functional run was executed with a real OpenAI-compatible model
(`deepseek-v4-flash-0731`) against a **dedicated demo SQLite database**, driven
through the browser UI:

```
topic input -> A/B outline (real model) -> outline B selected
-> draft generation (real model, 1301 words) -> draft archived
-> POST /api/drafts/{id}/feedback/evolve -> Thinking DNA trait persisted
-> GET /api/dna/profile returns the new trait
```

What this proves: the wired pipeline executes end to end with a real model and
that a `feedback/evolve` judgment mutates the stored profile.

What this does **not** prove:

- Answer/draft quality, hallucination rate, consistency across runs (n = 1).
- Latency, token cost, throughput.
- The full "human edits the article, `diff_agent` compares both revisions" path
  (only mocked in tests).
- Behaviour on real PostgreSQL.
- Skill execution under the restricted-token sandbox.
- Any multi-user / auth-isolation behaviour in this run (`AUTH_REQUIRED=false`).

Screenshots 01-03 in `README.md` come from this run and contain real model
output for synthetic input. The demo database and service logs were deleted
after the capture; the draft id above is not a business metric.

## 7. Export verification run (independent public copy)

Executed inside the standalone export directory
(`Personal-IP-Agent-Showcase`), with the project's own virtualenv interpreter and
no network credentials:

```powershell
python -m pytest -q --no-header -p no:cacheprovider
```

Result:

- passed: 992
- skipped: 3
- failed: 18
- warnings: 97

The 18 failures are **not** hidden or reclassified. They fall into the categories
already declared as broken/partial in `README.md` and `docs/feature-status.md`:

1. `skills/content-multi-distributor` platform formatters raise `NameError`
   (`test_blueprint_creation_and_distribution.py`).
2. Viewpoint-conflict detection raises `NameError`
   (`test_dna_conflict_and_management.py::test_viewpoint_conflict_detection`).
3. `test_api_routes.py::test_generate_draft_error_handling` raises `NameError`.
4. `tests/test_api_auth_surface.py::test_public_endpoint_registry_matches_application`
   fails and was not triaged in this pass.

This pass added no business functionality and did not modify source to make the
suite green. Governance gates (`scripts/check_code_style.py`,
`scripts/check_doc_coverage.py`) were run in the original worktree and passed
there; the export copy is a subset snapshot and is not the gated worktree.
