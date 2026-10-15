from fastapi import APIRouter

from app.api.draft_common import (  # noqa: F401
    get_draft_agent,
    _forbidden,
    _get_owned_draft,
    _not_found,
    _reject_body_user_id,
    _resolve_draft_id,
)
from app.api import (  # noqa: F401
    draft_generation,
    draft_lineage,
    draft_archive,
    draft_feedback,
)

router = APIRouter(tags=["drafts"])

# Extend (rather than include_router) so every route keeps its exact original
# path, including the "" and "/" archive aliases. include_router rejects an
# empty path when the prefix is also empty.
for _mod in (draft_generation, draft_lineage, draft_archive, draft_feedback):
    router.routes.extend(_mod.router.routes)

from app.api.draft_generation import (  # noqa: E402,F401
    distribute_content,
    distribute_draft_by_id,
    generate_draft,
    generate_from_blueprint,
)
from app.api.draft_lineage import get_draft_lineage  # noqa: E402,F401
from app.api.draft_archive import (  # noqa: E402,F401
    delete_draft,
    get_draft,
    list_drafts,
    save_draft_archive,
    update_draft,
)
from app.api.draft_feedback import (  # noqa: E402,F401
    FeedbackEvolveRequest,
    FeedbackEvolveResponse,
    evolve_feedback,
    extract_feedback_insights,
    list_feedbacks,
    record_feedback,
)
