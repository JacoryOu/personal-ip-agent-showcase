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
    _trusted_user_id,
    _ensure_owned,
    _not_found,
    _unprocessable,
)


from app.api.dna_v2_product_helpers import (  # noqa: F401
    _normalize_product_field,
    _extract_field_value,
    _fallback_parse_product_text,
    _detect_image_type,
    _serialize_product,
    ALLOWED_IMAGE_TYPES,
    MAX_IMAGE_SIZE,
    PRODUCT_UPLOAD_DIR,
    ProductCreate,
    ProductUpdate,
    ProductExtractRequest,
)


def _facade():
    """Late-bound access to the facade module (keeps monkeypatching working)."""
    from app.api import dna_v2
    return dna_v2


@router.get("/products")
def list_products(
    user_id: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    uid = _trusted_user_id(user_id, current_user)
    stmt = select(ProductVault).where(ProductVault.user_id == uid)
    if is_active is not None:
        stmt = stmt.where(ProductVault.is_active == is_active)
    products = session.exec(stmt).all()
    return [_serialize_product(p) for p in products]


@router.post("/products/upload-image")
async def upload_product_image(
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Upload product image (cover, lifestyle gallery, or service guarantee).
    Validates MIME type (jpeg/png/webp), inspects magic bytes, and enforces max 10MB file size.
    Saves to data/uploads/products/<unique_id>.<ext> and returns static URL.
    """
    del current_user  # identity is enforced, but the upload is owner-scoped by filename
    raw_content_type = (file.content_type or "").split(";")[0].strip().lower()
    if raw_content_type not in _facade().ALLOWED_IMAGE_TYPES:
        raise _unprocessable(
            "Invalid image type. Allowed types: image/jpeg, image/png, image/webp"
        )

    # Chunked streaming read to avoid loading unbounded payload into memory
    content = bytearray()
    chunk_size = 64 * 1024
    while chunk := await file.read(chunk_size):
        content.extend(chunk)
        if len(content) > _facade().MAX_IMAGE_SIZE:
            raise _unprocessable("File size exceeds maximum allowed size of 10MB.")

    if len(content) == 0:
        raise _unprocessable("Uploaded file is empty.")

    detected_mime = _detect_image_type(bytes(content))
    if not detected_mime:
        raise _unprocessable("Corrupted or invalid image file content.")

    # Map to proper canonical extension based on detected mime type
    client_ext = Path(file.filename or "").suffix.lower()
    if detected_mime == "image/jpeg":
        ext = ".jpeg" if client_ext == ".jpeg" else ".jpg"
    elif detected_mime == "image/png":
        ext = ".png"
    elif detected_mime == "image/webp":
        ext = ".webp"
    else:
        ext = _facade().ALLOWED_IMAGE_TYPES[detected_mime]

    unique_filename = f"{uuid.uuid4().hex}{ext}"
    try:
        _facade().PRODUCT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        file_path = _facade().PRODUCT_UPLOAD_DIR / unique_filename
        file_path.write_bytes(content)
    except OSError as e:
        # Never surface the absolute server path or the OS error text.
        raise AppError(code=INTERNAL_ERROR, status_code=500) from e

    return {
        "success": True,
        "url": f"/uploads/products/{unique_filename}",
        "filename": unique_filename,
    }


@router.post("/products", status_code=201)
def create_product(
    body: ProductCreate,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = _trusted_user_id(body.user_id or body.userId, current_user)
    p_name = body.product_name or body.productName
    if not p_name or not p_name.strip():
        raise _unprocessable("product_name is required")
    active_val = body.is_active if body.is_active is not None else (body.isActive if body.isActive is not None else True)
    cover_img = body.cover_image if body.cover_image is not None else (body.coverImage or "")
    gallery_imgs = body.gallery_images if body.gallery_images is not None else (body.galleryImages if body.galleryImages is not None else [])
    service_imgs = body.service_rights_images if body.service_rights_images is not None else (body.serviceRightsImages if body.serviceRightsImages is not None else [])

    product = ProductVault(
        user_id=uid,
        product_name=p_name.strip(),
        category=body.category or "",
        core_ingredients=(body.core_ingredients if body.core_ingredients is not None else (body.coreIngredients or "")),
        suitable_conditions=(body.suitable_conditions if body.suitable_conditions is not None else (body.suitableConditions or "")),
        taboos=body.taboos or "",
        personal_usage_experience=(body.personal_usage_experience if body.personal_usage_experience is not None else (body.personalUsageExperience or "")),
        conversion_hooks=(body.conversion_hooks if body.conversion_hooks is not None else (body.conversionHooks or "")),
        cover_image=cover_img,
        gallery_images=gallery_imgs,
        service_rights_images=service_imgs,
        is_active=active_val,
    )
    session.add(product)
    session.commit()
    session.refresh(product)
    return _serialize_product(product)
