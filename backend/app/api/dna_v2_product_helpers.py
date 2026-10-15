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


def _facade():
    """Late-bound access to the facade module (keeps monkeypatching working)."""
    from app.api import dna_v2
    return dna_v2


def _normalize_product_field(val: Any) -> str:
    """Normalizes string or list from LLM output into clean human-readable Chinese string."""
    if val is None:
        return ""
    if isinstance(val, list):
        return "、".join(str(item).strip() for item in val if str(item).strip())
    if isinstance(val, dict):
        return json.dumps(val, ensure_ascii=False)
    return str(val).strip()


def _extract_field_value(data: Dict[str, Any], keys: List[str]) -> str:
    """Extracts first matching key with normalization."""
    for k in keys:
        if k in data and data[k] is not None:
            normalized = _normalize_product_field(data[k])
            if normalized:
                return normalized
    return ""


def _fallback_parse_product_text(raw_text: str) -> Dict[str, str]:
    """Fallback parser when LLM returns plain text key-value lines instead of JSON."""
    res: Dict[str, str] = {}
    lines = raw_text.splitlines()
    patterns = [
        ("product_name", r"^[-*#>\s]*(?:产品品名|产品名称|产品名|品名|产品|Name)[:：]\s*(.+)"),
        ("category", r"^[-*#>\s]*(?:品类|形态|类型|分类|Category)[:：]\s*(.+)"),
        ("core_ingredients", r"^[-*#>\s]*(?:核心成分(?:与工艺亮点)?|成分与工艺|原料与成分|成分|原料|Ingredients)[:：]\s*(.+)"),
        ("suitable_conditions", r"^[-*#>\s]*(?:精准适用人群(?:与体质)?|适用人群|适合体质|适用体质|适合人群|精准适用|Suitable)[:：]\s*(.+)"),
        ("taboos", r"^[-*#>\s]*(?:禁忌(?:与)?劝退人群|禁忌劝退|劝退人群|禁忌|慎用人群|不适宜人群|Taboos?)[:：]\s*(.+)"),
        ("personal_usage_experience", r"^[-*#>\s]*(?:第一人称真实自用体验(?:与体感)?|第一人称自用体验|真实自用体验|自用体验|自用感受|真实体感|体感|自用|Experience)[:：]\s*(.+)"),
        ("conversion_hooks", r"^[-*#>\s]*(?:低阻力转化引流钩子|转化引子|转化钩子|引流钩子|低阻力引流|Hooks?)[:：]\s*(.+)"),
    ]
    for line in lines:
        cleaned = line.strip()
        for field, pat in patterns:
            if field not in res:
                m = re.match(pat, cleaned, re.IGNORECASE)
                if m:
                    res[field] = m.group(1).strip()
    return res


# ===========================================================================
# Products
# ===========================================================================

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
PRODUCT_UPLOAD_DIR = (Path(__file__).resolve().parent.parent.parent / "data" / "uploads" / "products")
PRODUCT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _detect_image_type(raw: bytes) -> Optional[str]:
    """Inspect magic bytes to detect image format (JPEG, PNG, WebP)."""
    if len(raw) >= 3 and raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(raw) >= 8 and raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return None


def _serialize_product(p: ProductVault) -> Dict[str, Any]:
    """Ensure product dictionary serialization has non-null image fields."""
    d = p.model_dump()
    d["cover_image"] = d.get("cover_image") or ""
    d["gallery_images"] = d.get("gallery_images") or []
    d["service_rights_images"] = d.get("service_rights_images") or []
    return d


class ProductCreate(BaseModel):
    product_name: Optional[str] = None
    productName: Optional[str] = None
    category: Optional[str] = ""
    core_ingredients: Optional[str] = None
    coreIngredients: Optional[str] = None
    suitable_conditions: Optional[str] = None
    suitableConditions: Optional[str] = None
    taboos: Optional[str] = ""
    personal_usage_experience: Optional[str] = None
    personalUsageExperience: Optional[str] = None
    conversion_hooks: Optional[str] = None
    conversionHooks: Optional[str] = None
    cover_image: Optional[str] = None
    coverImage: Optional[str] = None
    gallery_images: Optional[List[str]] = None
    galleryImages: Optional[List[str]] = None
    service_rights_images: Optional[List[str]] = None
    serviceRightsImages: Optional[List[str]] = None
    is_active: Optional[bool] = None
    isActive: Optional[bool] = None
    user_id: Optional[str] = None
    userId: Optional[str] = None


class ProductUpdate(BaseModel):
    product_name: Optional[str] = None
    productName: Optional[str] = None
    category: Optional[str] = None
    core_ingredients: Optional[str] = None
    coreIngredients: Optional[str] = None
    suitable_conditions: Optional[str] = None
    suitableConditions: Optional[str] = None
    taboos: Optional[str] = None
    personal_usage_experience: Optional[str] = None
    personalUsageExperience: Optional[str] = None
    conversion_hooks: Optional[str] = None
    conversionHooks: Optional[str] = None
    cover_image: Optional[str] = None
    coverImage: Optional[str] = None
    gallery_images: Optional[List[str]] = None
    galleryImages: Optional[List[str]] = None
    service_rights_images: Optional[List[str]] = None
    serviceRightsImages: Optional[List[str]] = None
    is_active: Optional[bool] = None
    isActive: Optional[bool] = None


class ProductExtractRequest(BaseModel):
    text: str
    user_id: Optional[str] = None
    auto_save: Optional[bool] = False
    autoSave: Optional[bool] = False
    cover_image: Optional[str] = None
    coverImage: Optional[str] = None
    gallery_images: Optional[List[str]] = None
    galleryImages: Optional[List[str]] = None
    service_rights_images: Optional[List[str]] = None
    serviceRightsImages: Optional[List[str]] = None


PRODUCT_EXTRACTION_SYSTEM_PROMPT = """你是一位顶级的私域商业操盘手与个人IP产品心智提炼大师。
你的任务是从用户提供的杂乱产品宣传文案、朋友圈种草帖、电商详情页或产品说明书中，反向萃取并提炼出高度适配私域高信任交付的【产品心智档案】。

不同于传统电商ERP单纯罗列库存或参数，私域个人IP产品核心在于【信任背书】、【精准劝退】与【真实自用体感】。
请深度分析输入文本，提炼并输出严格的 JSON 格式（不要包含任何额外文字说明或markdown代码块）：
{
  "product_name": "产品品名（简洁清晰，如新会陈皮五年老白茶）",
  "category": "品类/形态（如养生茶饮、食疗糕点、知识咨询等）",
  "core_ingredients": "核心成分与工艺亮点（提炼出最硬核的原料产地、年份或制作工艺）",
  "suitable_conditions": "精准适用人群与体质（如脾胃虚寒、熬夜上火、湿气重人群等）",
  "taboos": "禁忌与劝退人群（私域建立极高信任的核心锚点！指出不适合谁、哪些情况慎用或禁服，如孕妇慎用、阴虚火旺不宜、经期停服等）",
  "personal_usage_experience": "第一人称真实自用体验与体感（以IP主理人真实第一人称'我'的口吻，描述自己或家人的真实使用过程、口感与阶段性身心体感，富有温度和细节）",
  "conversion_hooks": "低阻力转化引流钩子（给读者一个轻松互动的理由，如'私信领三日养生茶谱'、'加微信免费寄品鉴装'、'评论区扣1送搭配方案'）"
}
"""
