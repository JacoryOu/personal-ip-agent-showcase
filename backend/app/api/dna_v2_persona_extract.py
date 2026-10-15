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


from app.api.dna_v2_persona_schemas import (  # noqa: F401
    PersonaCreate,
    PersonaUpdate,
    ExtractFromTextRequest,
)


def _facade():
    """Late-bound access to the facade module (keeps monkeypatching working)."""
    from app.api import dna_v2
    return dna_v2


class PersonaExtractRequest(BaseModel):
    text: str
    user_id: Optional[str] = None
    auto_save: Optional[bool] = False


PERSONA_EXTRACTION_SYSTEM_PROMPT = """你是一位顶级的个人IP操盘手与认知传记作家。
你的任务是从用户提供的原始文本（如过往公众号文章、朋友圈随笔、个人自白、随感笔记或对谈实录）中，深度反向提炼创作者的IP人设资产（IP Persona）以及具有代表性的人性化故事切片（Episodic Stories）。

请严格遵守以下提炼原则：
1. 真实与温度：避免假大空的行业套话或简历式陈述，捕捉创作者最鲜活、真实的口吻、价值观与转折故事。
2. 读者心智定位：准确刻画创作者面对的真实受众画像，以及最自然舒适的读者称谓。
3. 故事切片：提取创作者亲身经历的关键事件，分类为 daily_life（日常生活/生活切片）、failure_reflection（踩坑与反思/至暗时刻与跃迁）、client_case（学员/客户实战案例）。
4. 时间推断：尝试从文本语境推断故事发生时间（格式YYYY-MM-DD，若无法确定填 null）。

请严格输出如下 JSON 格式：
{
  "name": "推荐的IP代号或称谓",
  "target_audience": "受众画像（例如：25-40岁对亚健康调理有需求的女性）",
  "tone_style": "语言风格特征（例如：温润亲和、松弛、拒绝制造焦虑）",
  "reader_salutation": "最自然的读者称谓（例如：姐妹们、朋友们、同行者）",
  "origin_story": "从文本中提炼出的创作者真实心路历程与起源故事（第一人称或第三人称视角，具有温度和说服力）",
  "extracted_stories": [
    {
      "title": "故事标题",
      "story_type": "daily_life",
      "story_content": "故事内容细节",
      "occurred_at": "YYYY-MM-DD 或 null",
      "tags": ["标签1", "标签2"]
    }
  ]
}
"""


@router.post("/personas/extract-from-text")
async def extract_persona_from_text(
    body: PersonaExtractRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Reverse-engineers creator's IP Persona and episodic story slices from raw text.
    If auto_save is True, saves to database and marks as the active persona.
    """
    if not body.text or not body.text.strip():
        raise _unprocessable("text cannot be empty")

    uid = _trusted_user_id(body.user_id, current_user)

    gateway = _facade().get_model_gateway()
    client = gateway.get_client_for_role(ModelRole.DIFF)
    model = gateway.get_model_for_role(ModelRole.DIFF)

    user_prompt = f"以下是创作者提供的原始文本材料：\n\n{body.text}\n\n请按要求反向推导提炼其IP人设与生活切片故事，并输出严格的JSON格式。"

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": PERSONA_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1500,
        )
        raw_content = (response.choices[0].message.content or "").strip()
        extracted_data = extract_json_from_text(raw_content)
    except Exception as e:
        # Never echo the upstream SDK/transport message: it can carry URLs,
        # credentials and internal hostnames. The cause is logged with the
        # request id by the global handler.
        raise AppError(code=INTERNAL_ERROR, status_code=500) from e

    persona_dict = {
        "name": str(extracted_data.get("name") or "个人IP创作者"),
        "target_audience": str(extracted_data.get("target_audience") or ""),
        "tone_style": str(extracted_data.get("tone_style") or ""),
        "reader_salutation": str(extracted_data.get("reader_salutation") or ""),
        "origin_story": str(extracted_data.get("origin_story") or ""),
    }

    raw_stories = extracted_data.get("extracted_stories") or []
    stories_list = []
    for s in raw_stories:
        if not isinstance(s, dict):
            continue
        stype = s.get("story_type") if s.get("story_type") in _facade().VALID_STORY_TYPES else "daily_life"
        stories_list.append({
            "title": str(s.get("title") or ""),
            "story_type": stype,
            "story_content": str(s.get("story_content") or ""),
            "occurred_at": s.get("occurred_at") if s.get("occurred_at") else None,
            "tags": s.get("tags") if isinstance(s.get("tags"), list) else [],
        })

    saved = False
    if body.auto_save:
        # Deactivate existing active personas for this user
        existing_active = session.exec(
            select(IPPersona).where(IPPersona.user_id == uid, IPPersona.is_active == True)
        ).all()
        for ep in existing_active:
            ep.is_active = False
            session.add(ep)

        new_persona = IPPersona(
            user_id=uid,
            name=persona_dict["name"],
            target_audience=persona_dict["target_audience"],
            tone_style=persona_dict["tone_style"],
            reader_salutation=persona_dict["reader_salutation"],
            origin_story=persona_dict["origin_story"],
            is_active=True,
        )
        session.add(new_persona)

        saved_stories = []
        for s in stories_list:
            occurred = None
            if s.get("occurred_at"):
                try:
                    occurred = datetime.fromisoformat(s["occurred_at"])
                    if occurred.tzinfo is None:
                        occurred = occurred.replace(tzinfo=timezone.utc)
                except Exception:
                    occurred = None
            if occurred is None:
                occurred = datetime.now(timezone.utc)

            story_obj = EpisodicStory(
                user_id=uid,
                title=s["title"],
                story_content=s["story_content"],
                story_type=s["story_type"],
                occurred_at=occurred,
                tags=s["tags"],
                confidence_score=1.0,
            )
            session.add(story_obj)
            saved_stories.append(story_obj)

        session.commit()
        session.refresh(new_persona)
        for so in saved_stories:
            session.refresh(so)

        persona_dict = new_persona.model_dump()
        stories_list = [so.model_dump() for so in saved_stories]
        saved = True

    return {
        "success": True,
        "persona": persona_dict,
        "stories": stories_list,
        "saved": saved,
    }
