# Demo guide (real run, synthetic data)

> [中文](demo.md) | English

> All content in this guide and in the screenshots is **synthetic** demo input.
> No real user, client, WeChat log or article is used. Screenshots were captured
> from the running browser UI against a **real model call** — nothing is a mock,
> a static page or a design mock-up.

## 0. Verification matrix for this pass

| Verification type | Status |
| --- | --- |
| OpenAI-compatible minimal real chat call | **passed** |
| Real model + dedicated demo SQLite, full flow in the browser | **passed** (once) |
| Browser UI interaction + screenshots 01-03 | **passed** (Chrome headless via Playwright) |
| Mocked model gateway | used by the existing pytest suite, **not** used for any screenshot |
| Static checks / repo gates | see `docs/evaluation.md` |
| Real PostgreSQL | **not tested** |
| Restricted-token sandbox execution of a real skill | **not triggered in this pass** |
| WeChat record import, multi-platform publishing | **not implemented / not verified** |

The engine is a **fixed orchestration workflow**
(`backend/app/engine/cognitive_engine.py`), not an autonomous planner agent.

## 1. Environment used

- Backend: project venv, FastAPI on `http://127.0.0.1:8000`
- Frontend: Vue 3 + Vite dev server. Port 5173 was occupied, so Vite served the
  demo on `http://127.0.0.1:5176/`.
- Database: a dedicated demo SQLite file
  `demo-data/job-demo.db`, i.e. **no real business database was read or written**.
  The file and the service logs were deleted after the capture.
- Auth: `AUTH_REQUIRED=false`, `AUTH_LOCAL_DEV_MODE=true` (local demo only).
- Model: OpenAI-compatible endpoint, model `deepseek-v4-flash-0731`.
  The API key lives in the local root `.env` and is **never** reproduced here.

## 2. Start commands (no credentials in this file)

Backend:

```powershell
cd <repo-root>
$env:DATABASE_URL = "sqlite:///<repo-root>/demo-data/job-demo.db"
$env:AUTH_REQUIRED = "false"
$env:AUTH_LOCAL_DEV_MODE = "true"
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

Frontend:

```powershell
cd frontend
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev        # served on http://127.0.0.1:5176/ in this run
```

Health checks that returned HTTP 200 in this run:
`http://127.0.0.1:8000/api/health` and the Vite dev server root.

Note: the Windows console may show garbled Chinese for streamed output; the API
responses and this document are UTF-8 and are correct.

A non-blocking startup warning was observed and deliberately **not** changed
(business code is out of scope for this pass): `StyleFingerprint.register`
shadows a `BaseModel` attribute name.

## 3. Reproduction steps in the UI

1. Open the Vite dev server, land on the workbench.
2. Enter the synthetic topic
   `AI Agent 工作流的可评估性：如何把重复工作变成可追溯的自动化流程`
   and submit → `POST /api/outlines/generate`
   → screenshot **01** (input screen).
3. Wait for the two outlines → screenshot **02**. Both outlines come from
   `OutlineAgent` via a real model call.
4. Click "选择方案 B", then "选定此方向并扩写初稿"
   → `POST /api/drafts/generate` → screenshot **03** (generated draft editor).
5. (Optional, verified via API rather than UI) submit a viewpoint judgment with
   `POST /api/drafts/{draft_id}/feedback/evolve`, then read
   `GET /api/dna/profile`.

## 4. Observed results

| Item | Value in this run |
| --- | --- |
| Draft id | `d856099c-1c6b-43ae-9fe2-5cd9cc97fe26` (demo DB only, not a metric) |
| Draft title | `【手把手教学】别只学框架了，AI Agent 应该这样学` |
| Draft length | 1301 words |
| `feedback/evolve` | HTTP success |
| Persisted DNA trait | `core_value`, confidence `1.5`, status `active`, `evolution_boost_count = 1` |
| Read-back | `GET /api/dna/profile` returned the new trait, `source_draft_id` matching the demo draft |

This run verified the **`feedback/evolve` → profile evolution** path. It did
**not** verify the full "human edits the whole article, then `diff_agent`
compares both versions" path in the browser; that path is covered by mocked
tests only.

## 5. Screenshots

| File | Screen | Shows |
| --- | --- | --- |
| `docs/images/01-topic-input.png` | Workbench topic input | real UI, synthetic input |
| `docs/images/02-divergent-outlines.png` | Divergent A/B outlines | real model output + selection step |
| `docs/images/03-draft-generated.png` | Draft editor | real model draft, refinement diff, archive / reformat / DNA / viewpoint actions |

Tooling note: the in-app browser tool failed to initialize
(`e.nodeRepl?.setResponseMeta is not a function`), so screenshots were taken with
a local Playwright 1.64.1 + Chrome Headless Shell 156 session against the running
dev servers. The temporary script directory was removed afterwards.

## 6. Honest limitations of this demo

1. One successful run is **not** an evaluation: no benchmark set, no latency,
   cost, quality or reliability numbers exist for this flow.
2. Sandbox isolation is **partial** (restricted token only; no AppContainer, no
   filesystem ACL, no network isolation, no `WindowsSandbox.exe`).
3. DB read-only isolation covers the agent read path only; draft archiving and
   the DNA-evolution flow are intentionally writable.
4. WeChat / Xiaohongshu formatting and viewpoint-conflict detection currently
   contain known one-line import defects (`NameError`) — see `docs/evaluation.md`.
5. Multi-platform distribution, WeChat record import and LoRA/QLoRA fine-tuning
   are **not** implemented; do not present them as features.

