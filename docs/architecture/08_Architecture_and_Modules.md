# Architecture and Modules (V0.1 MVP)

## 1. Tech Stack (技术栈)
*   **Backend Framework**: **Python FastAPI** - Lightweight, high performance, async-friendly, great for AI API integration and prompt orchestration.
*   **Frontend Framework**: **Vue 3** (Vite + TypeScript + Tailwind CSS) - For rapid prototyping of the SPA (Single Page Application) that handles A/B draft selection, differences comparison, and rich text editing.
*   **Database ORM**: **SQLModel (backed by PostgreSQL JSONB)** - Relational structure for rigid entities (Users, Sessions, Drafts), combined with `JSONB` for flexible and schema-less storage of `Thinking DNA`, `Cognitive Memory`, and user profiles.
*   **AI Integration**: **Raw OpenAI SDK** - Utilizing lightweight hand-coded state machines for orchestrating the multi-agent system (No LangChain, No LlamaIndex).
*   **Deployment**: **Docker & Docker Compose** - For containerized, reproducible local and staging deployments.

## 2. Directory Structure (目录结构)
```
/
├── backend/                  # Python FastAPI Backend
│   ├── app/
│   │   ├── api/              # API endpoints (Presentation Layer)
│   │   ├── core/             # Core configuration, security, and global dependencies
│   │   ├── engine/           # Core AI Engine (Agents orchestration & LLM logic)
│   │   │   ├── agents/       # Agent implementations (Outline, Draft, Diff)
│   │   │   ├── prompts/      # System prompts and templates (Separation of prompts and code)
│   │   │   └── memory/       # Thinking DNA memory extraction and storage logic
│   │   ├── models/           # SQLModel ORM models (Database schema)
│   │   ├── schemas/          # Pydantic models (Data validation and API contracts)
│   │   ├── services/         # Business logic layer (CRUD, Orchestration)
│   │   └── utils/            # Helper functions and shared utilities
│   ├── tests/                # Backend unit and integration tests
│   ├── pyproject.toml        # Python project dependencies and metadata (uv)
│   ├── uv.lock               # Locked dependencies
│   └── main.py               # Application entry point
├── frontend/                 # Vue 3 Frontend
│   ├── src/
│   │   ├── components/       # Reusable UI components (e.g., DraftCard, DiffViewer)
│   │   ├── views/            # Page views (e.g., Editor, DraftSelection)
│   │   ├── services/         # API client and request wrappers
│   │   ├── store/            # Global state management
│   │   └── assets/           # Static assets (images, styles)
│   ├── package.json          # Node dependencies
│   └── vite.config.js        # Build tool configuration
├── database/                 # Database scripts (migrations, init scripts)
├── docs/                     # Project documentation
│   ├── architecture/         # Architecture and engineering guidelines
│   ├── legacy/               # Legacy design documents
│   └── product/              # Product and project management documents
├── docker-compose.yml        # Docker Compose configuration for infrastructure
└── README.md                 # Project overview
```

## 3. Module Boundaries (模块边界)
*   **API Layer (`backend/app/api/`)**: Exposes RESTful endpoints for the Vue 3 frontend. Responsible for HTTP request and response handling, payload validation (via `schemas`), and delegating business logic to the `services` layer. **Strict Rule**: Does NOT contain any AI logic nor direct database queries.
*   **Services Layer (`backend/app/services/`)**: The central orchestrator. Coordinates between the database layer and the AI Engine layer. Example: Receiving a request to generate drafts, fetching user context from the DB, calling the Engine layer, saving the results, and returning them.
*   **Core Engine Layer (`backend/app/engine/`)**: The AI heart of the system. Implements the Multi-Agent Architecture defined in `AGENTS.md` using the Raw OpenAI SDK. Strictly isolated from HTTP context.
    *   *Divergent Outline Agent*: Generates divergent structural outlines.
    *   *Draft Generation Agent*: Generates A/B drafts based on outlines.
    *   *Diff & DNA Extraction Agent*: Compares texts and extracts cognitive patterns.
*   **Database Layer (`backend/app/models/`)**: Defines the data storage structures mapping to PostgreSQL tables via SQLModel. Manages the persistence of core entities (Users, Drafts, DNA_Records).

---

## 4. CORS and Static Resources (CORS 与静态资源)

Both behaviours are driven by explicit settings in `backend/app/core/config.py`
(`Settings`) and applied in `backend/app/main.py`. No behaviour below is
inferred at runtime from a wildcard.

### CORS

- `CORS_ORIGINS` — explicit origin allowlist. The literal `"*"` is filtered out
  and never reaches `CORSMiddleware`, because `allow_credentials=True` is kept
  and a wildcard origin is illegal alongside credentials.
- `CORS_ALLOW_METHODS` — explicit method allowlist
  (`GET, POST, PUT, PATCH, DELETE, OPTIONS`). Never `"*"`.
- `CORS_ALLOW_HEADERS` — explicit header allowlist covering what the frontend
  actually sends (`X-Model-Name`, `X-Model-Api-Key`, `X-Base-Url`,
  `X-Image-Model`, `X-Image-Api-Key`, `X-Image-Base-Url`, `Content-Type`)
  plus the `Authorization` / `X-API-Key` credentials the backend accepts.
  Never `"*"`.
- `ENVIRONMENT` — when set to `production` (or `prod`), the localhost
  development origins are dropped **and** the localhost origin regex is not
  installed, so no localhost port is reachable from a browser.
- `CORS_ALLOW_LOCALHOST_REGEX` — development-only convenience that accepts any
  `localhost` / `127.0.0.1` port (Vite dynamic ports). Ignored in production.
- If the resulting allowlist is empty and no regex applies, a
  `CORS_ALLOWLIST_EMPTY` warning is logged at import time rather than silently
  leaving the API unreachable from a browser.

### Static uploads

- `UPLOAD_DIR` = `backend/app/data/uploads`, served at `/uploads` through
  Starlette `StaticFiles`.
- `EXPOSE_UPLOADS` (default `True`, so existing frontends keep working) controls
  whether the mount exists at all:
  - `True` → the directory is created if missing and `/uploads` is mounted.
    An `OSError` while preparing the directory is caught and logged as
    `UPLOADS_MOUNT_FAILED` instead of crashing the app at import time.
  - `False` → nothing is mounted and a `UPLOADS_DISABLED` warning explains
    that product image URLs will not resolve.

`/uploads` is **not** an authorization boundary. It serves every file in the
directory to anyone who can reach the backend. Deployments that must not
publish uploaded assets should set `EXPOSE_UPLOADS=false` and serve content
through an authenticated route instead.

Design-level context: `docs/design/07_Surfaces_and_Engagement.md`
("CORS policy and the /uploads static mount").

Regression coverage: `backend/tests/test_cors_and_uploads_config.py`.

> **Status: Legacy / superseded.** Written before the Skill Engine, scheduler,
> multi-platform distribution, material vault, chat lounge, private domain and
> sandbox work existed. Treat it as historical design intent.
> Current architecture: [10_Sandbox_and_Permission_Model.md](10_Sandbox_and_Permission_Model.md),
> [11_Feature_Map_v0.2.md](11_Feature_Map_v0.2.md),
> [12_Skill_Engine_Spec.md](12_Skill_Engine_Spec.md).

## 5. API Authentication Boundary (接口认证边界)

Authentication is declared **once, at the aggregation layer**, not per handler.

- `backend/app/api/auth_boundary.py`
  - `create_private_router(**kwargs)` — an `APIRouter` factory that appends
    `Depends(get_current_user)` to the router-level dependencies.
  - `create_public_router(**kwargs)` — an `APIRouter` factory that explicitly
    drops router-level dependencies.
  - `PUBLIC_ENDPOINTS` — a `frozenset` of `(METHOD, path)` pairs that are
    intentionally anonymous. Currently exactly one entry:
    `("GET", "/api/private-domain/templates")`.
- `backend/app/api/__init__.py`
  - `api_router = create_private_router(prefix="/api")` — every business router
    (outlines, drafts, dna, dna_v2, settings, images, blueprints, materials,
    platforms, scheduler, obsidian, chat_lounge, private_domain,
    viral_analysis) is included below it, so **a newly added handler is
    authenticated by default**. Forgetting `Depends(get_current_user)` can no
    longer create an anonymous endpoint.
  - `public_endpoints_router = create_public_router(prefix="/api")` — holds only
    the explicitly public routers.
- `backend/app/main.py` includes both aggregates.

Handlers that need the identity object still declare
`current_user: AuthenticatedUser = Depends(get_current_user)` explicitly; FastAPI
caches dependencies per request, so this does not parse credentials twice.

Authenticated in this batch: `POST /api/images/generate`,
`GET /api/images/proxy`, `POST /api/images/test-connection`,
`GET /api/dna/skills`, `POST /api/drafts/distribute`.

Not covered by this boundary (honest gaps): per-user ownership/persistence of
generated images, DB-backed per-user scheduler isolation, enforcement of
`skills/*` `permissions` metadata, and the Windows OS sandbox (still Partial).

Regression coverage: `backend/tests/test_api_auth_surface.py` and the local gate
`scripts/check_api_auth.py` (see `13_Documentation_Governance.md`).

## 9. Draft generation API module (code truth)

The draft facade `backend/app/api/drafts.py` is split into responsibility
modules. `backend/app/api/draft_generation.py` owns the outline/draft
generation endpoints. It imports `status` from FastAPI and raises
`status.HTTP_503_SERVICE_UNAVAILABLE` when the model gateway cannot serve a
generation request, so the 503 contract is defined in code and covered by
tests. No authentication or permission behaviour changed with this fix.
