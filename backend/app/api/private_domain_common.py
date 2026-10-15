"""
Private Domain IP Hub API (私域 IP 操盘中枢)
WeChat Moments 5-Dimensional Generator, Anti-Fold Simulator, Comment Pin Extractor.
"""

from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.db import get_session
from app.core.errors import NOT_FOUND, VALIDATION_ERROR, AppError
from app.core.model_gateway import ModelGateway, ModelRole, get_model_gateway
from app.models.persona import IPPersona, PERSONA_PRESETS
from app.models.product import ProductVault, PRODUCT_PRESETS
from app.services.cognitive_service import CognitiveService
from app.services.memory_service import MemoryService, naturalize_time_expression

router = APIRouter(tags=["private_domain"])

#: Endpoints mounted here are reachable **without** a credential. They are
#: attached through ``create_public_router`` in :mod:`app.api`, never through
#: the default-authenticated aggregation router, and every route on it must
#: also appear in ``app.api.auth_boundary.PUBLIC_ENDPOINTS``.
public_router = APIRouter(tags=["private_domain_public"])

PERSONA_NOT_FOUND_MESSAGE = "Persona not found."
PRODUCT_NOT_FOUND_MESSAGE = "Product not found."


def _parse_uuid_or_none(raw: Optional[str]) -> Optional[uuid.UUID]:
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except (ValueError, AttributeError, TypeError):
        return None


def _load_owned_persona(
    session: Session,
    persona_id: Optional[str],
    uid: uuid.UUID,
) -> Optional[IPPersona]:
    """Load a persona only if it belongs to the authenticated user.

    Invalid ids and rows owned by somebody else collapse into the same
    NOT_FOUND error so the endpoint cannot be used to probe for existence.
    """
    pid = _parse_uuid_or_none(persona_id)
    if pid is None:
        if persona_id:
            raise AppError(NOT_FOUND, PERSONA_NOT_FOUND_MESSAGE)
        return None
    persona = session.exec(
        select(IPPersona).where(IPPersona.id == pid, IPPersona.user_id == uid)
    ).first()
    if persona is None:
        raise AppError(NOT_FOUND, PERSONA_NOT_FOUND_MESSAGE)
    return persona


def _load_owned_product(
    session: Session,
    product_id: Optional[str],
    uid: uuid.UUID,
) -> Optional[ProductVault]:
    """Load a ProductVault row owned by the authenticated user.

    Public PRODUCT_PRESETS stay usable (they are not user data); any DB row
    belonging to another user is treated as not found.
    """
    pr_id = _parse_uuid_or_none(product_id)
    if pr_id is None:
        if product_id:
            # Not a UUID: only the public preset catalogue may match.
            for preset in PRODUCT_PRESETS:
                if str(preset.id) == str(product_id) or preset.product_name == product_id:
                    return preset
            raise AppError(NOT_FOUND, PRODUCT_NOT_FOUND_MESSAGE)
        return None
    product = session.exec(
        select(ProductVault).where(ProductVault.id == pr_id, ProductVault.user_id == uid)
    ).first()
    if product is None:
        for preset in PRODUCT_PRESETS:
            if str(preset.id) == str(product_id):
                return preset
        raise AppError(NOT_FOUND, PRODUCT_NOT_FOUND_MESSAGE)
    return product


