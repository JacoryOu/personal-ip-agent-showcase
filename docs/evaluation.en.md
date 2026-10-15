# Evaluation and Test Evidence

> [中文（默认）](evaluation.md) | English

## 0. Current results (2026-10-15, re-run inside the showcase copy)

In the standalone export directory `Personal-IP-Agent-Showcase`, using the original project's virtualenv interpreter and no network credentials:

```powershell
cd <repo-root>
<python> -m pytest -q --no-header -p no:cacheprovider
```

Result:

```
1010 passed, 3 skipped, 86 warnings in 67.89s
```

## 1. What the old "18 failures" were, and why failures remained at the time

An earlier version of this file recorded `992 passed / 18 failed / 3 skipped / 97 warnings`. To be precise:

1. **That was a locally saved historical snapshot, not a GitHub Actions CI report**, and not the final state.
2. The code changed after the public export snapshot was taken, so the first re-run this round showed **17 failures** (one fewer than the old snapshot); the 18 did not reproduce verbatim.
3. All 17 were root-caused and fixed this round. Failures went **17 → 12 → 0**.

Five root-cause classes, all deterministic defects rather than environment flakiness:

| Class | Location | Symptom |
| --- | --- | --- |
| Helpers used at call sites but not defined/imported in the formatters | `skills/content-multi-distributor/scripts/_formatters.py`, `_formatters_xhs.py` | WeChat / Xiaohongshu layout breaks; `extract_footnotes` was also missing |
| `status` used without import | `backend/app/api/draft_generation.py` | Only affects the ValueError 422 failure path |
| `CognitiveTrait` used without import | `backend/app/services/memory_conflicts.py` | Viewpoint conflict detection raised `NameError` |
| Integration tests not sending API Key headers while auth is enabled | `backend/test_blueprint_creation_and_distribution.py` | Requests rejected with 401; **production auth was not weakened** |
| Exception wrapping in Skill subprocess tests | the formatter-related cases above | One root cause surfaced as several failures |

All fixes are minimal: adding the missing imports/helper definitions, or adding request headers in tests. **No new business features were added, and production auth or assertions were not relaxed to make tests pass.**

## 2. Scope of the 3 skips and 86 warnings

- **3 skips**: environment-condition dependent (e.g. platform capabilities or external dependencies); not failures, not hidden tests.
- **86 warnings**: mostly deprecation warnings, plus FastAPI/OpenAPI duplicate `operation_id` notices. They do not affect assertions.

## 3. Which layer these tests belong to

| Layer | What it proves | What it does **not** prove |
| --- | --- | --- |
| Unit / integration tests (pytest) | Code paths execute; contracts hold | Anything about real LLMs, real PostgreSQL, real network egress, real users |
| Mock model gateway | Prompt assembly, schema parsing, gating, attribution, persistence | Model quality, latency, cost, hallucination rate |
| Governance gate scripts | Mechanical code-style and doc-coverage constraints | Functional correctness |
| Real model call | The single end-to-end run recorded in `docs/demo.md` | Reliability, quality, latency, cost |
| Real PostgreSQL | **Not run** (SQLite by default) | — |
| Real multi-user security drill | **Not executed** | — |

Read "1010 passed" as "every code path currently covered by automation passes", not "the product is validated".

## 4. Benchmark with real data

`backend/app/engine/rubrics/data/viral_rubric_benchmark_v1.json` holds **43 human-annotated samples**. `backend/app/engine/rubrics/viral_benchmark.py` scores the deterministic rule implementation with:

- within-one-level accuracy
- mean absolute error (MAE)
- exact match rate

Suggested thresholds in code: MAE <= 0.8, exact match >= 0.60.

**Important**: this benchmark measures "can the rule implementation reproduce human labels", **not** LLM generation quality; and who produced those 43 labels is unconfirmed (see `docs/resume-notes.md`).

## 5. Explicitly untested metrics

Do not put these on a resume; this repository has no evidence for them:

- Retrieval recall / accuracy / MRR / nDCG. The hybrid retriever has no labeled retrieval set.
- Human-scored answer or draft quality.
- End-to-end latency, time-to-first-token, throughput, token cost.
- Any "improved X%" or "reduced Y%" claim.
- User counts, active users, published posts, GMV, hours saved.
- Reliability, security, or jailbreak rate under real models.
- LoRA/QLoRA fine-tuning quality (no training or evaluation at all).

## 6. Security regression suite (all passing)

| Area | Tests |
| --- | --- |
| Enforced read-only DB | `tests/test_agent_db_readonly.py` |
| Route auth surface | `tests/test_api_auth_surface.py`, `tests/test_auth_and_ownership.py` |
| SSRF | `tests/test_net_guard.py`, `test_net_guard_image_service.py`, `test_settings_ssrf.py` |
| Credential encryption | `tests/test_credential_encryption.py`, `test_secret_box.py` |
| Prompt / secret leakage | `tests/test_security_*.py`, `test_error_contract.py` |
| Sandbox | `tests/test_restricted_token.py`, `test_sandbox_mode_transparency.py`, `test_sandbox_acl_integration.py`, `test_os_network_boundary.py`, `test_job_object.py`, `test_sandbox_permission_gate.py` |
| Workflow permissions | `tests/test_workflow_permissions.py`, `test_workflow_permission_gate.py` |
| Governance gates | `tests/test_code_style.py`, `tests/test_doc_coverage.py` |

## 7. How to reproduce

Full suite:

```powershell
<python> -m pytest -q --no-header -p no:cacheprovider
```

Governance gates:

```powershell
<python> scripts/check_doc_coverage.py --base main
<python> -m pytest backend/tests/test_doc_coverage.py -q
<python> scripts/check_code_style.py
<python> scripts/check_code_style.py --base main
<python> -m pytest backend/tests/test_code_style.py -q
```

Rule benchmark:

```powershell
<python> -m pytest backend/tests -q -k rubric
```

## 8. Real model end-to-end run (2026-10-15)

See `docs/demo.md`. Using a real OpenAI-compatible model (`deepseek-v4-flash-0731`) and a **separate demo SQLite database**, the browser UI completed:

```
topic input -> A/B outlines (real model) -> choose option B
-> draft generation (real model, metadata.word_count = 2908) -> draft editor
```

**What it proves**: the wired pipeline runs end to end through draft generation.

**What it does not prove**:

- Draft quality, hallucination rate, run-to-run consistency (n = 1, and model output is non-deterministic).
- Latency, token cost, throughput.
- The full "manual full-text edit → `diff_agent` two-version diff" path (Mock only).
- Behavior on real PostgreSQL.
- Skill execution under the restricted token sandbox.
- Any multi-user / auth isolation behavior for this run (`AUTH_REQUIRED=false`).

Screenshots 01–03 come from that run with synthetic input; the draft id is not a business metric.
