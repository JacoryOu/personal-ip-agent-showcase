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
    PRODUCT_EXTRACTION_SYSTEM_PROMPT,
)


def _facade():
    """Late-bound access to the facade module (keeps monkeypatching working)."""
    from app.api import dna_v2
    return dna_v2


@router.post("/products/extract-from-text")
async def extract_product_from_text(
    body: ProductExtractRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Reverse-engineers product knowledge from unstructured text using ModelGateway (DIFF).
    Extracts 7 dimensions: product_name, category, core_ingredients, suitable_conditions,
    taboos, personal_usage_experience, conversion_hooks.
    If auto_save is True, saves to ProductVault table in SQLite with user_id.
    Returns { success: bool, product: dict, saved: bool }.
    """
    if not body.text or not body.text.strip():
        raise _unprocessable("text cannot be empty")

    uid = _trusted_user_id(body.user_id, current_user)

    gateway = _facade().get_model_gateway()
    client = gateway.get_client_for_role(ModelRole.DIFF)
    model = gateway.get_model_for_role(ModelRole.DIFF)

    user_prompt = f"""以下是产品相关的原始文本材料：

{body.text}

请按要求反向推导萃取其产品心智档案，并输出严格的JSON格式。"""

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": PRODUCT_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1500,
        )
    except Exception as e:
        # Never echo the upstream SDK/transport message: it can carry URLs,
        # credentials and internal hostnames. The cause is logged with the
        # request id by the global handler.
        raise AppError(code=INTERNAL_ERROR, status_code=500) from e

    raw_content = (response.choices[0].message.content or "").strip()

    extracted_data = None
    try:
        extracted_data = extract_json_from_text(raw_content)
    except ValueError:
        extracted_data = _fallback_parse_product_text(raw_content)

    if isinstance(extracted_data, list) and extracted_data and isinstance(extracted_data[0], dict):
        p_data = extracted_data[0]
    elif isinstance(extracted_data, dict):
        p_data = extracted_data.get("product") if isinstance(extracted_data.get("product"), dict) else extracted_data
    else:
        p_data = _fallback_parse_product_text(raw_content)

    prod_name = _extract_field_value(p_data, [
        "product_name", "productName", "name", "品名", "产品名称", "产品品名", "产品名", "产品"
    ])
    if not prod_name or prod_name == "未命名产品":
        first_line = body.text.strip().splitlines()[0][:30].strip().strip("#*【】[]:：")
        prod_name = first_line[:20] if first_line else "未命名产品"

    cat = _extract_field_value(p_data, [
        "category", "type", "品类", "形态", "分类"
    ])
    ingredients = _extract_field_value(p_data, [
        "core_ingredients", "coreIngredients", "ingredients", "核心成分", "核心成分与工艺亮点", "成分", "原料", "工艺亮点"
    ])
    suitable = _extract_field_value(p_data, [
        "suitable_conditions", "suitableConditions", "suitable_for", "适用人群", "精准适用人群与体质", "适合体质", "适宜体质", "适用体质", "适合人群"
    ])
    taboos = _extract_field_value(p_data, [
        "taboos", "contraindications", "禁忌", "劝退人群", "禁忌与劝退人群", "注意事项", "慎用人群", "不适宜人群"
    ])
    experience = _extract_field_value(p_data, [
        "personal_usage_experience", "personalUsageExperience", "usage_experience", "自用体验", "第一人称真实自用体验与体感", "真实自用体感", "自用感受", "体感", "自用"
    ])
    hooks = _extract_field_value(p_data, [
        "conversion_hooks", "conversionHooks", "hooks", "转化引子", "引流钩子", "低阻力转化引流钩子", "转化钩子", "引流钩子"
    ])

    cover_img = body.cover_image if body.cover_image is not None else (body.coverImage or "")
    gallery_imgs = body.gallery_images if body.gallery_images is not None else (body.galleryImages if body.galleryImages is not None else [])
    service_imgs = body.service_rights_images if body.service_rights_images is not None else (body.serviceRightsImages if body.serviceRightsImages is not None else [])

    product_dict = {
        "product_name": prod_name,
        "category": cat,
        "core_ingredients": ingredients,
        "suitable_conditions": suitable,
        "taboos": taboos,
        "personal_usage_experience": experience,
        "conversion_hooks": hooks,
        "cover_image": cover_img,
        "gallery_images": gallery_imgs,
        "service_rights_images": service_imgs,
        "is_active": True,
    }

    is_auto_save = bool(body.auto_save or body.autoSave)
    saved = False

    if is_auto_save:
        product_obj = ProductVault(
            user_id=uid,
            product_name=product_dict["product_name"],
            category=product_dict["category"],
            core_ingredients=product_dict["core_ingredients"],
            suitable_conditions=product_dict["suitable_conditions"],
            taboos=product_dict["taboos"],
            personal_usage_experience=product_dict["personal_usage_experience"],
            conversion_hooks=product_dict["conversion_hooks"],
            cover_image=cover_img,
            gallery_images=gallery_imgs,
            service_rights_images=service_imgs,
            is_active=True,
        )
        session.add(product_obj)
        session.commit()
        session.refresh(product_obj)
        product_dict = _serialize_product(product_obj)
        saved = True

    return {
        "success": True,
        "product": product_dict,
        "saved": saved,
    }


@router.get("/products/{product_id}")
def get_product(
    product_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    product = session.get(ProductVault, product_id)
    if not product:
        raise _not_found("Product not found")
    _ensure_owned(product.user_id, current_user)
    return _serialize_product(product)


@router.patch("/products/{product_id}")
def update_product(
    product_id: uuid.UUID,
    body: ProductUpdate,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    product = session.get(ProductVault, product_id)
    if not product:
        raise _not_found("Product not found")
    _ensure_owned(product.user_id, current_user)

    p_name = body.product_name if body.product_name is not None else body.productName
    if p_name is not None:
        product.product_name = p_name
    if body.category is not None:
        product.category = body.category
    ing = body.core_ingredients if body.core_ingredients is not None else body.coreIngredients
    if ing is not None:
        product.core_ingredients = ing
    sc = body.suitable_conditions if body.suitable_conditions is not None else body.suitableConditions
    if sc is not None:
        product.suitable_conditions = sc
    if body.taboos is not None:
        product.taboos = body.taboos
    pue = body.personal_usage_experience if body.personal_usage_experience is not None else body.personalUsageExperience
    if pue is not None:
        product.personal_usage_experience = pue
    ch = body.conversion_hooks if body.conversion_hooks is not None else body.conversionHooks
    if ch is not None:
        product.conversion_hooks = ch
    cover_img = body.cover_image if body.cover_image is not None else body.coverImage
    if cover_img is not None:
        product.cover_image = cover_img
    gallery_imgs = body.gallery_images if body.gallery_images is not None else body.galleryImages
    if gallery_imgs is not None:
        product.gallery_images = gallery_imgs
    service_imgs = body.service_rights_images if body.service_rights_images is not None else body.serviceRightsImages
    if service_imgs is not None:
        product.service_rights_images = service_imgs

    active_val = body.is_active if body.is_active is not None else body.isActive
    if active_val is not None:
        product.is_active = active_val

    session.add(product)
    session.commit()
    session.refresh(product)
    return _serialize_product(product)


@router.delete("/products/{product_id}")
def delete_product(
    product_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    product = session.get(ProductVault, product_id)
    if not product:
        raise _not_found("Product not found")
    _ensure_owned(product.user_id, current_user)

    session.delete(product)
    session.commit()
    return {"success": True, "message": "Product deleted successfully", "id": str(product_id)}
