"""Private Domain IP Hub API (私域 IP 操盘中枢).

Pure structural facade: the implementation now lives in focused sibling
modules. This module keeps the original public names importable and the
``router`` / ``public_router`` registration order unchanged.
"""

from app.api.private_domain_common import (  # noqa: F401
    PERSONA_NOT_FOUND_MESSAGE,
    PRODUCT_NOT_FOUND_MESSAGE,
    _load_owned_persona,
    _load_owned_product,
    _parse_uuid_or_none,
    public_router,
    router,
)
from app.api.private_domain_schemas import *  # noqa: F401,F403
from app.api.private_domain_schemas import (  # noqa: F401
    GenerateCommunityRequest,
    GenerateCommunityResponse,
    GenerateMomentRequest,
    GenerateMomentResponse,
    LengthTier,
    MomentCategory,
    TemplateItem,
    TimeNarrativeMode,
    TriggerType,
)
from app.api.private_domain_text import *  # noqa: F401,F403
from app.api.private_domain_text import (  # noqa: F401
    calculate_moments_lines,
    clean_mechanical_dates,
    enforce_anti_fold_formatting,
)
from app.api.private_domain_fallback import *  # noqa: F401,F403
from app.api.private_domain_fallback import (  # noqa: F401
    DEFAULT_CATEGORY_DATA,
    _build_rule_based_moment,
)
from app.api.private_domain_moment import *  # noqa: F401,F403
from app.api.private_domain_moment import generate_moment  # noqa: F401
from app.api.private_domain_community import *  # noqa: F401,F403
from app.api.private_domain_community import (  # noqa: F401
    generate_community,
    list_templates,
)

__all__ = [
    "router",
    "public_router",
    "PERSONA_NOT_FOUND_MESSAGE",
    "PRODUCT_NOT_FOUND_MESSAGE",
    "_parse_uuid_or_none",
    "_load_owned_persona",
    "_load_owned_product",
    "MomentCategory",
    "TimeNarrativeMode",
    "TriggerType",
    "LengthTier",
    "GenerateMomentRequest",
    "GenerateMomentResponse",
    "GenerateCommunityRequest",
    "GenerateCommunityResponse",
    "TemplateItem",
    "calculate_moments_lines",
    "clean_mechanical_dates",
    "enforce_anti_fold_formatting",
    "DEFAULT_CATEGORY_DATA",
    "_build_rule_based_moment",
    "generate_moment",
    "generate_community",
    "list_templates",
]
