"""Thinking DNA 2.0 API facade.

The route implementations now live in focused ``dna_v2_*`` modules. This
module keeps every previously importable name (router, schemas, helpers and
handlers) available, and registers the routes on a single router in the
original order. Pure structural refactor: no URL, method, schema, dependency,
exception or fallback behaviour changed.
"""

from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, List, Optional
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.auth.ownership import normalize_user_id
from app.core.db import get_session
from app.core.errors import (
    FORBIDDEN,
    INTERNAL_ERROR,
    NOT_FOUND,
    VALIDATION_ERROR,
    AppError,
)
from app.core.model_gateway import ModelRole, extract_json_from_text, get_model_gateway
from app.models.persona import IPPersona
from app.models.story import EpisodicStory
from app.models.product import ProductVault
from app.services.cognitive_service import CognitiveService

from app.api.dna_v2_common import (
    router,
    VALID_STORY_TYPES,
    _trusted_user_id,
    _ensure_owned,
    _not_found,
    _unprocessable,
)

# --- Personas: /personas, /personas/extract-from-text, /personas/{id} ------
from app.api.dna_v2_persona_schemas import (  # noqa: E402
    PersonaCreate,
    PersonaUpdate,
    ExtractFromTextRequest,
    list_personas,
    create_persona,
)
from app.api.dna_v2_persona_extraction import (  # noqa: E402
    extract_persona_from_text,
    update_persona,
)
from app.api.dna_v2_persona_extract import (  # noqa: E402
    PersonaExtractRequest,
    PERSONA_EXTRACTION_SYSTEM_PROMPT,
    extract_persona_from_text,  # noqa: F811  (second handler, same as before)
)

# --- Products --------------------------------------------------------------
from app.api.dna_v2_product_helpers import (  # noqa: E402
    _normalize_product_field,
    _extract_field_value,
    _fallback_parse_product_text,
    ALLOWED_IMAGE_TYPES,
    MAX_IMAGE_SIZE,
    PRODUCT_UPLOAD_DIR,
    ProductCreate,
    ProductUpdate,
    ProductExtractRequest,
    PRODUCT_EXTRACTION_SYSTEM_PROMPT,
    _detect_image_type,
    _serialize_product,
)
from app.api.dna_v2_product_routes_a import (  # noqa: E402
    list_products,
    upload_product_image,
    create_product,
)
from app.api.dna_v2_product_routes_b import (  # noqa: E402
    extract_product_from_text,
    get_product,
    update_product,
    delete_product,
)

# --- Stories / Timeline / Supersede ---------------------------------------
from app.api.dna_v2_stories import (  # noqa: E402
    StoryCreate,
    list_stories,
    create_story,
)
from app.api.dna_v2_timeline import get_timeline  # noqa: E402
from app.api.dna_v2_supersede import SupersedeRequest, supersede_trait  # noqa: E402

__all__ = [
    "router",
    "_trusted_user_id",
    "_ensure_owned",
    "_not_found",
    "_unprocessable",
    "PersonaCreate",
    "PersonaUpdate",
    "ExtractFromTextRequest",
    "PersonaExtractRequest",
    "PERSONA_EXTRACTION_SYSTEM_PROMPT",
    "_normalize_product_field",
    "_extract_field_value",
    "_fallback_parse_product_text",
    "ALLOWED_IMAGE_TYPES",
    "MAX_IMAGE_SIZE",
    "PRODUCT_UPLOAD_DIR",
    "ProductCreate",
    "ProductUpdate",
    "ProductExtractRequest",
    "PRODUCT_EXTRACTION_SYSTEM_PROMPT",
    "_detect_image_type",
    "_serialize_product",
    "VALID_STORY_TYPES",
    "StoryCreate",
    "SupersedeRequest",
    "list_personas",
    "create_persona",
    "extract_persona_from_text",
    "update_persona",
    "list_products",
    "upload_product_image",
    "create_product",
    "extract_product_from_text",
    "get_product",
    "update_product",
    "delete_product",
    "list_stories",
    "create_story",
    "get_timeline",
    "supersede_trait",
]
