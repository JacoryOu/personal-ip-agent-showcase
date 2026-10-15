"""Policy tables for the documentation coverage gate.

Pure data only: which documents form the code-truth set, which paths are public
surfaces, and which design document owns which surface. Kept separate from
``check_doc_coverage.py`` so the gate logic and the policy can change
independently and neither file grows without bound.
"""

from __future__ import annotations

import re

# Docs that constitute the code-truth set.
FEATURE_MAP = "docs/architecture/11_Feature_Map_v0.2.md"
SANDBOX_DOC = "docs/architecture/10_Sandbox_and_Permission_Model.md"
SKILL_DOC = "docs/architecture/12_Skill_Engine_Spec.md"
ARCHITECTURE_DOC = "docs/architecture/08_Architecture_and_Modules.md"
AGENTS_DOC = "AGENTS.md"

CODE_TRUTH_DOCS = (
    FEATURE_MAP,
    SANDBOX_DOC,
    SKILL_DOC,
    ARCHITECTURE_DOC,
    AGENTS_DOC,
)

TRUTH_DOCS_MUTABLE = tuple(
    d for d in CODE_TRUTH_DOCS if d != ARCHITECTURE_DOC
)

# Declared-waiver file: one directive per changed public surface.
WAIVER_FILE = "docs/.doc-coverage-waivers"

# Directives accepted in the CURRENT commit message (never in history).

PUBLIC_SURFACE_GLOBS = [
    "backend/app/api/*",
    "backend/app/services/*",
    "backend/app/models/*",
    "backend/app/core/*",
    "backend/app/engine/*",
    "frontend/src/components/*",
    "frontend/src/views/*",
    "frontend/src/services/*",
    "frontend/src/router/*",
    "frontend/src/main.*",
    "backend/app/main.py",
    "frontend/package.json",
    "skills/*",
]

# Changes that must always trigger a doc-coverage check (permission/isolation).
SECURITY_GLOBS = [
    "backend/app/core/skill_engine/*",
    "backend/app/core/db.py",
    "backend/app/core/net_guard.py",
    "backend/app/core/vault_path_guard.py",
    "backend/app/core/crypto/*",
    "backend/app/core/auth/*",
]

# Files whose name marks sandbox machinery. Used for reporting only; it never
# silently waives the sandbox-doc requirement.
SANDBOX_SENSITIVE = re.compile(
    r"skill_engine|restricted_token|windows_sandbox|network_guard|sandbox",
    re.IGNORECASE,
)

# For each public code surface, the docs allowed to cover it. Keeping this
# explicit is what stops an unrelated doc edit from satisfying the gate for
# every code change on the branch.
SURFACE_DOC_MAP = [
    ("backend/app/api/", (ARCHITECTURE_DOC, FEATURE_MAP)),
    ("backend/app/engine/", (FEATURE_MAP, SKILL_DOC)),
    ("backend/app/services/", (FEATURE_MAP,)),
    ("backend/app/models/", (FEATURE_MAP,)),
    ("backend/app/core/", (FEATURE_MAP,)),
    ("frontend/src/", (FEATURE_MAP,)),
    ("skills/", (SKILL_DOC, FEATURE_MAP)),
]

# Feature-level design docs (docs/design/). These are required in ADDITION to
# the architecture truth docs: a public surface change must be reflected both in
# the Feature Map (index) and in the design doc that owns that surface.
DESIGN_DIR = "docs/design"
DESIGN_INDEX = "docs/design/README.md"

DESIGN_CREATION = "docs/design/01_Creation_Pipeline.md"
DESIGN_DNA = "docs/design/02_Cognitive_Profile_and_DNA.md"
DESIGN_VIRAL = "docs/design/03_Viral_Semantic_Analysis.md"
DESIGN_DISTRIBUTION = "docs/design/04_Distribution_and_Credentials.md"
DESIGN_MATERIALS = "docs/design/05_Material_Vault_and_Obsidian.md"
DESIGN_SCHEDULER = "docs/design/06_Scheduler_and_Unattended_Skills.md"
DESIGN_SURFACES = "docs/design/07_Surfaces_and_Engagement.md"
DESIGN_DATA_MODEL = "docs/design/08_Data_Model_Reference.md"

DESIGN_DOCS = (
    DESIGN_INDEX,
    DESIGN_CREATION,
    DESIGN_DNA,
    DESIGN_VIRAL,
    DESIGN_DISTRIBUTION,
    DESIGN_MATERIALS,
    DESIGN_SCHEDULER,
    DESIGN_SURFACES,
    DESIGN_DATA_MODEL,
)

# Which design doc owns which public surface. Ordered, most specific first.
DESIGN_DOC_MAP = [
    # Split API modules share the design doc of the facade they belong to.
    ("backend/app/api/draft_", (DESIGN_CREATION,)),
    ("backend/app/api/dna_", (DESIGN_DNA,)),
    ("backend/app/api/dna_v2_", (DESIGN_DNA,)),
    ("backend/app/api/materials_", (DESIGN_MATERIALS,)),
    ("backend/app/api/platforms_", (DESIGN_DISTRIBUTION,)),
    ("backend/app/api/private_domain_", (DESIGN_SURFACES,)),
    ("backend/app/api/settings_", (DESIGN_SURFACES,)),
    ("backend/app/api/chat_lounge_", (DESIGN_SURFACES,)),
    ("backend/app/api/outlines.py", (DESIGN_CREATION,)),
    ("backend/app/api/drafts.py", (DESIGN_CREATION,)),
    ("backend/app/api/blueprints.py", (DESIGN_CREATION,)),
    ("backend/app/api/dna.py", (DESIGN_DNA,)),
    ("backend/app/api/dna_v2.py", (DESIGN_DNA,)),
    ("backend/app/api/viral_analysis.py", (DESIGN_VIRAL,)),
    ("backend/app/api/platforms.py", (DESIGN_DISTRIBUTION,)),
    ("backend/app/api/materials.py", (DESIGN_MATERIALS,)),
    ("backend/app/api/obsidian.py", (DESIGN_MATERIALS,)),
    ("backend/app/api/scheduler.py", (DESIGN_SCHEDULER,)),
    ("backend/app/api/chat_lounge.py", (DESIGN_SURFACES,)),
    ("backend/app/api/private_domain.py", (DESIGN_SURFACES,)),
    ("backend/app/api/images.py", (DESIGN_SURFACES,)),
    ("backend/app/api/settings.py", (DESIGN_SURFACES,)),
    ("backend/app/services/cognitive_service.py", (DESIGN_DNA,)),
    ("backend/app/services/cognitive_common.py", (DESIGN_DNA,)),
    ("backend/app/services/cognitive_profile_service.py", (DESIGN_DNA,)),
    ("backend/app/services/cognitive_evolution_service.py", (DESIGN_DNA,)),
    ("backend/app/services/cognitive_portability_service.py", (DESIGN_DNA,)),
    ("backend/app/services/memory_", (DESIGN_DNA,)),
    ("backend/app/services/feedback_service.py", (DESIGN_DNA,)),
    ("backend/app/services/viral_semantic_service.py", (DESIGN_VIRAL,)),
    ("backend/app/services/style_selection_service.py", (DESIGN_VIRAL,)),
    ("backend/app/services/credential_service.py", (DESIGN_DISTRIBUTION,)),
    ("backend/app/services/platform_crawler_service.py", (DESIGN_DISTRIBUTION,)),
    ("backend/app/services/platform_crawler_support_service.py", (DESIGN_DISTRIBUTION,)),
    ("backend/app/services/platform_crawler_account_service.py", (DESIGN_DISTRIBUTION,)),
    ("backend/app/services/platform_crawler_feed_service.py", (DESIGN_DISTRIBUTION,)),
    ("backend/app/services/platform_crawler_collect_service.py", (DESIGN_DISTRIBUTION,)),
    ("backend/app/services/playwright_service.py", (DESIGN_DISTRIBUTION,)),
    ("backend/app/services/material_service.py", (DESIGN_MATERIALS,)),
    ("backend/app/services/obsidian_service.py", (DESIGN_MATERIALS,)),
    ("backend/app/services/image_service.py", (DESIGN_SURFACES,)),
    ("backend/app/core/auth/ownership.py", (DESIGN_DISTRIBUTION,)),
    ("backend/app/core/config.py", (DESIGN_SURFACES,)),
    ("backend/app/core/model_gateway.py", (DESIGN_SURFACES, DESIGN_CREATION)),
    ("backend/app/core/net_guard.py", (DESIGN_DISTRIBUTION,)),
    ("backend/app/core/vault_path_guard.py", (DESIGN_MATERIALS,)),
    ("backend/app/core/crypto/", (DESIGN_DISTRIBUTION,)),
    ("backend/app/core/skill_engine/", (DESIGN_SCHEDULER,)),
    ("backend/app/core/workflow_permissions/", (SANDBOX_DOC, FEATURE_MAP)),
    ("backend/app/core/db.py", (DESIGN_DATA_MODEL,)),
    ("backend/app/main.py", (DESIGN_SURFACES,)),
    ("backend/app/core/errors.py", (DESIGN_SURFACES,)),
    ("backend/app/core/request_id.py", (DESIGN_SURFACES,)),
    ("backend/app/api/__init__.py", (DESIGN_SURFACES,)),
    ("backend/app/api/auth_boundary.py", (DESIGN_SURFACES,)),
    ("backend/app/services/inspection_quota_service.py", (DESIGN_SCHEDULER,)),
    # Scheduler facade + responsibility-split siblings share one design doc.
    ("backend/app/services/inspection_scheduler_", (DESIGN_SCHEDULER,)),
    ("frontend/package.json", (DESIGN_SURFACES,)),
    # Viral-analysis engine surfaces are owned by the viral design doc, not
    # the creation-pipeline doc. Keep these before the generic engine rule.
    ("backend/app/engine/rubrics/", (DESIGN_VIRAL,)),
    ("backend/app/engine/prompts/viral_", (DESIGN_VIRAL,)),
    ("backend/app/services/viral_", (DESIGN_VIRAL,)),
    ("backend/app/engine/", (DESIGN_CREATION,)),
    ("backend/app/models/", (DESIGN_DATA_MODEL,)),
    ("skills/", (DESIGN_SCHEDULER,)),
    ("frontend/src/", (DESIGN_SURFACES,)),
]

# Doc-only paths: editing them must never look like a public feature change.
DOC_ONLY_GLOBS = [
    "docs/architecture/*",
    "docs/design/*",
]

DECLARATION_PREFIXES = (
    "Doc-Impact:",
    "Doc-Impact :",
    "Documentation-Impact:",
    "Documentation Impact:",
)

IGNORED_PATH_PARTS = {"__pycache__", ".venv", "node_modules", ".git", ".pytest_cache"}

# Package initialisers carry no behaviour of their own: they only re-export or
# declare a package. They are still public-surface *files* (a change there can
# alter imports), so the gate keeps flagging them for doc impact -- but they do
# not need their own design-doc route. Only bare __init__.py is exempt.
PACKAGE_METADATA_SUFFIXES = ("__init__.py",)
