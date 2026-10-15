from app.api.auth_boundary import (
    PUBLIC_ENDPOINTS,
    create_private_router,
    create_public_router,
)
from app.api.outlines import router as outlines_router
from app.api.drafts import router as drafts_router
from app.api.dna import router as dna_router
from app.api.dna_v2 import router as dna_v2_router
from app.api.settings import router as settings_router
from app.api.images import router as images_router
from app.api.blueprints import router as blueprints_router
from app.api.materials import router as materials_router
from app.api.platforms import router as platforms_router
from app.api.scheduler import router as scheduler_router
from app.api.obsidian import router as obsidian_router
from app.api.chat_lounge import router as chat_lounge_router
from app.api.private_domain import public_router as private_domain_public_router
from app.api.private_domain import router as private_domain_router
from app.api.viral_analysis import router as viral_analysis_router

#: Every business router mounted below ``api_router`` inherits
#: ``Depends(get_current_user)``. A handler therefore does not have to remember
#: to add the dependency to stay authenticated -- forgetting it can no longer
#: create an anonymous endpoint. Handlers that need the identity object still
#: declare it explicitly.
api_router = create_private_router(prefix="/api")
api_router.include_router(outlines_router, prefix="/outlines")
api_router.include_router(drafts_router, prefix="/drafts")
api_router.include_router(dna_router, prefix="/dna")
api_router.include_router(dna_v2_router, prefix="/dna/v2")
api_router.include_router(settings_router, prefix="/settings")
api_router.include_router(images_router, prefix="/images")
api_router.include_router(blueprints_router, prefix="/blueprints")
api_router.include_router(materials_router, prefix="/materials")
api_router.include_router(platforms_router, prefix="/platforms")
api_router.include_router(scheduler_router, prefix="/scheduler")
api_router.include_router(obsidian_router, prefix="/obsidian")
api_router.include_router(chat_lounge_router, prefix="/chat/lounge")
api_router.include_router(private_domain_router, prefix="/private-domain")
api_router.include_router(viral_analysis_router, prefix="/viral-analysis")

#: The complete list of deliberately anonymous endpoints. Anything not listed
#: here requires a credential.
public_endpoints_router = create_public_router(prefix="/api")
public_endpoints_router.include_router(private_domain_public_router, prefix="/private-domain")

__all__ = [
    "PUBLIC_ENDPOINTS",
    "api_router",
    "public_endpoints_router",
    "outlines_router",
    "drafts_router",
    "dna_router",
    "dna_v2_router",
    "settings_router",
    "images_router",
    "blueprints_router",
    "materials_router",
    "platforms_router",
    "scheduler_router",
    "obsidian_router",
    "chat_lounge_router",
    "private_domain_router",
    "private_domain_public_router",
    "viral_analysis_router",
]
