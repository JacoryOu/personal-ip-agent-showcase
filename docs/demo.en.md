# Demo Notes (real model run, 2026-10-15)

> [中文（默认）](demo.md) | English

This file records **one** real end-to-end model run. **This is not an evaluation**: no benchmark set, no latency / cost / quality metrics.

The engine is a **fixed orchestration workflow** (`backend/app/engine/cognitive_engine.py`), not an autonomous planning agent.

| Area | Status this run |
| --- | --- |
| Topic input → A/B outlines → first draft | **Verified with a real model** |
| Draft archive, viewpoint feedback → DNA evolution | Verified previously, **not part of this run record** |
| Manual full-text edit → `diff_agent` two-version diff → DNA extraction | **Mock tests only, not verified in a browser this run** |
| Real Skill execution under the restricted token sandbox | **Not triggered this run** |
| WeChat record import, multi-platform publishing | **Not implemented / not verified** |

## 1. Environment

- Backend: FastAPI on `http://127.0.0.1:8000`.
- Frontend: Vue 3 + Vite dev server; port 5173 was occupied, so this run used `http://127.0.0.1:5177/`.
- Database: a separate demo SQLite file `demo-data/job-demo.db`; **no real business database was read or written**. It is a demo artifact, excluded by `.gitignore`, and not committed.
- Auth: `AUTH_REQUIRED=false`, `AUTH_LOCAL_DEV_MODE=true` (local demo only).
- Model: OpenAI-compatible endpoint, model `deepseek-v4-flash-0731`. Credentials stay in the local `.env` and are **never shown here**.

## 2. Start commands (no credentials in this file)

Backend:

```powershell
cd <repo-root>
$env:DATABASE_URL = "sqlite:///<repo-root>/demo-data/job-demo.db"
$env:AUTH_REQUIRED = "false"
$env:AUTH_LOCAL_DEV_MODE = "true"
<python> -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

Frontend:

```powershell
cd frontend
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev        # this run: http://127.0.0.1:5177/
```

Liveness check: `http://127.0.0.1:8000/api/openapi.json` returns HTTP 200.
Note: this project has **no** `/api/health` route; the earlier mention of it was incorrect and has been removed.

Note: Windows consoles may garble streamed Chinese output; API responses and this file are UTF-8 and correct.

## 3. Reproduction steps in the UI

1. Open the dev server and go to the creation workshop.
2. Enter the synthetic topic
   `AI Agent 工作流的可评估性：如何把重复工作变成可追溯的自动化流程`
   and submit → `POST /api/outlines/generate` → screenshot **01** (input screen).
3. Wait for the two outlines → screenshot **02**. Both outlines come from a real `OutlineAgent` model call.
4. Choose "方案 B", then click "生成初稿并归档" → `POST /api/drafts/generate` → screenshot **03** (draft editor). This draft took about 111 seconds.

## 4. Observed results (the single run this file records)

| Item | Value from this run |
| --- | --- |
| Draft id | `4a072bddea59432ca5f5a412118ee8ea` (demo database only, not a business metric) |
| Draft title | `别急着"评估"AI工作流——先学会"听懂"它的身体语言` |
| Word count (API `metadata.word_count`) | **2908** |
| Raw draft Unicode characters (`len(original_ai_draft)`) | **3703** |
| Outline source | real `OutlineAgent` model call (option A / B) |

**Word-count convention**: the "~2908 字" shown at the top of the editor comes from the backend `metadata.word_count` and is this document's primary convention; the "3703 字符" shown in the body statistics is the Unicode character count of the raw draft string (including punctuation and whitespace). The two use different conventions and must not be mixed.

The title, word count, and draft id match screenshot **03** exactly; all three come from the same real result.

## 5. Screenshot list

| File | Page | What it shows |
| --- | --- | --- |
| `docs/images/01-topic-input.png` | Topic input | real UI + synthetic input |
| `docs/images/02-divergent-outlines.png` | Divergent A/B outlines | real model output + option selection |
| `docs/images/03-draft-generated.png` | Draft editor | real model draft, word-count statistics, archive / layout / DNA / viewpoint actions |

Tooling note: the built-in browser tool failed to initialize (`e.nodeRepl?.setResponseMeta is not a function`), so screenshots were captured with local Playwright + Chrome Headless Shell against the running dev server; the temporary script and page-text dumps were deleted after capture and are not committed.

## 6. Honest limitations of this demo

1. One successful run **is not an evaluation**: no benchmark set, latency, cost, quality, or reliability numbers exist.
2. Model output is non-deterministic; **the same input will not reliably produce the same title and body**. This file records one real result, not a reproducible fixed output.
3. Sandbox isolation is **partial** (restricted token only; no AppContainer, no filesystem ACL, no network isolation, no `WindowsSandbox.exe`).
4. Database read-only isolation covers the agent read path only; draft archiving and the DNA evolution flow are intentionally writable.
5. The real model run only reached outlines and draft generation; the `diff_agent` two-version diff is covered by Mock tests only.
6. Multi-platform distribution and WeChat record import are **not implemented**; LoRA/QLoRA is limited to conceptual knowledge with **no training or evaluation evidence**.
7. This run used `AUTH_REQUIRED=false` and therefore proves nothing about auth isolation.
