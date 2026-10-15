# Provenance and public-release status

This directory is a **desensitized showcase copy** of a private working repository.
It was assembled by file selection only; no business logic was changed.

## What was removed on purpose

- `.env`, `app.db`, `.git/`, `.venv/`, `node_modules/`, `__pycache__/`,
  `screenshots/`, `test_renders/`, `backend/data/`, model caches, logs.
- Author name / email from `backend/pyproject.toml` (replaced with a placeholder).
- Documentation folders not needed to explain or reproduce the core loop:
  `docs/legacy`, `docs/product`, `docs/audit`.
- `docs/design/*` **is** kept: the repository governance test
  (`backend/tests/test_doc_coverage.py`) asserts the existence and content of
  those design documents, so removing them would make the shipped gate
  un-runnable in this copy.

## What still needs your confirmation before publishing

| Item | Where | Note |
| --- | --- | --- |
| Third-party / reference code | `backend/app/**`, `frontend/src/**` | Mostly first-party, but a few patterns (SQLModel CRUD layout, FastAPI router layout) follow public framework conventions. Not independently audited for license provenance. |
| Company or client material | none copied | No client documents were copied. If any future file references internal hostnames, remove it before publishing. |
| Synthetic test data | `backend/tests/test_security_*.py`, `test_materials_and_lineage.py`, `test_live_qr_login.py` | Contains obviously fake credentials, fake internal hostnames and Windows sample paths used to prove redaction/guard behaviour. Do not print their literal values in public material; they exist only as fixtures. `test_live_qr_login.py` and `test_materials_and_lineage.py` still contain name-like strings that must be confirmed as synthetic before publishing. |
| Rubric benchmark labels | `backend/app/engine/rubrics/data/viral_rubric_benchmark_v1.json` | 43 human-labeled samples. **Author and licensing of the labels are unconfirmed.** Confirm provenance and publication right before publishing. |
| Screenshot rights | not copied | Original `screenshots/` are excluded. If you want to include them, confirm they contain no personal or client data first. |
| Skills definitions | `skills/*/SKILL.md` | First-party skill definitions. Confirm whether any embed third-party snippets. |
| Public-release license | none | No LICENSE file was added. You must choose one (e.g. MIT) before publishing. |

## Not verified

- No claim is made that every line is publishable. A manual review pass is
  required before any remote publication.

## Demo-run additions (2026-10-15)

- `docs/images/01-03*.png` were captured from the running local UI with a real
  model call on synthetic input. No screenshot contains a credential, a real
  user record, a client document or a WeChat log.
- The demo run used a dedicated SQLite file (`demo-data/job-demo.db`) that has
  been deleted; no real business database was read or written.
- `docs/demo.md` uses `<repo-root>` placeholders instead of local absolute paths.
- Residual scanner hits for `sk-…` / `C:\Users\…` inside
  `backend/tests/test_security_*.py` are **negative-test fixtures**
  (deliberate fake secrets used to prove the redaction code works), not real
  credentials.
