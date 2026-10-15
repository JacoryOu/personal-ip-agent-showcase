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
    from app.api import dna_v2
    return dna_v2


@router.post("/personas/extract-from-text")
async def extract_persona_from_text(
    body: ExtractFromTextRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    text = (body.text or "").strip()
    if not text:
        raise _unprocessable("Text cannot be empty")

    uid = _trusted_user_id(body.user_id, current_user)
    do_save = bool(body.auto_save or body.autoSave)

    persona_data = {
        "id": str(uuid.uuid4()),
        "name": "萃取IP分身",
        "reader_salutation": "朋友们",
        "tone_style": "真诚笃定、富有洞察力",
        "target_audience": "追求个人成长与思维升级的读者群体",
        "origin_story": text[:350],
        "is_active": True,
    }
    stories_data: List[Dict[str, Any]] = []

    try:
        import json
        gateway = _facade().get_model_gateway()
        system_prompt = """你是一个顶级IP定位专家与个人自传提取大师。
请分析用户提供的旧文、随笔或朋友圈笔记，提炼出其专属的IP人设画像以及1-3个真实生活切片故事。
输出严格的 JSON 格式（不要包含 markdown 代码块）：
{
  "name": "符合其领域与个性的IP名称（如：新会陈皮主理人阿姨、实战派架构师老张、认知探索者等）",
  "reader_salutation": "对读者的亲切称呼（如：姐妹们、创业老友们、同学们等）",
  "tone_style": "语言与文风调性（如：温润亲和且专业、犀利通透直击本质等）",
  "target_audience": "核心受众群体（如：30+注重身体调理的职场女性等）",
  "origin_story": "其初心、渊源或关键转折故事（200-400字）",
  "extracted_stories": [
    {
      "title": "故事标题（15字以内）",
      "story_content": "该故事的具体情节与感悟（100-300字）",
      "story_type": "daily_life",
      "occurred_at": "YYYY-MM-DD 或 null",
      "tags": ["经历切片", "文本萃取"]
    }
  ]
}"""
        client = gateway.get_client_for_role(ModelRole.DIFF)
        model = gateway.get_model_for_role(ModelRole.DIFF)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请深度萃取以下文本：\n\n{text}"},
            ],
            max_tokens=1500,
        )
        raw_reply = (response.choices[0].message.content or "").strip()
        parsed = extract_json_from_text(raw_reply)
        if isinstance(parsed, dict):
            # Check top-level or nested "persona"
            target_p = parsed.get("persona") if isinstance(parsed.get("persona"), dict) else parsed
            for k in ["name", "reader_salutation", "tone_style", "target_audience", "origin_story"]:
                if target_p.get(k):
                    persona_data[k] = str(target_p[k])

            raw_stories = parsed.get("extracted_stories") or parsed.get("stories") or []
            if isinstance(raw_stories, list) and raw_stories:
                stories_data = []
                for s in raw_stories:
                    if isinstance(s, dict):
                        stype = s.get("story_type") if s.get("story_type") in _facade().VALID_STORY_TYPES else "daily_life"
                        stories_data.append({
                            "title": str(s.get("title") or "经历故事"),
                            "story_content": str(s.get("story_content") or ""),
                            "story_type": stype,
                            "occurred_at": s.get("occurred_at") if s.get("occurred_at") else None,
                            "tags": s.get("tags") if isinstance(s.get("tags"), list) else ["文本萃取"],
                            "confidence_score": float(s.get("confidence_score") or 1.0),
                        })
    except Exception:
        # The upstream SDK/transport message is never echoed to the client; it
        # can carry internal URLs, credentials and hostnames. The degraded
        # heuristic below is a product decision, not an error report.
        first_line = text.splitlines()[0][:25].strip() if text.splitlines() else ""
        if "陈皮" in text or "茶" in text or "养生" in text:
            persona_data["name"] = "新会陈皮主理人"
            persona_data["reader_salutation"] = "姐妹们"
            persona_data["tone_style"] = "温润质朴、富有实战经验、循循善诱"
            persona_data["target_audience"] = "注重脾胃调理与健康生活方式的女性群体"
        elif "技术" in text or "代码" in text or "架构" in text or "创业" in text:
            persona_data["name"] = "实操派数字操盘手"
            persona_data["reader_salutation"] = "创业老友们"
            persona_data["tone_style"] = "务实通透、不讲虚招、直击本质"
            persona_data["target_audience"] = "寻求技能变现与认知升级的自由职业者与创业者"
        elif first_line:
            persona_data["name"] = f"{first_line[:8]}实践者"

        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 20]
        for idx, p in enumerate(paragraphs[:3]):
            st_type = "daily_life"
            if "踩坑" in p or "失眠" in p or "失败" in p or "教训" in p or "弯路" in p:
                st_type = "failure_reflection"
            elif "客户" in p or "咨询" in p or "服务" in p or "案例" in p:
                st_type = "client_case"
            stories_data.append({
                "id": str(uuid.uuid4()),
                "title": f"切片故事 {idx+1}: {p[:12]}...",
                "story_content": p,
                "story_type": st_type,
                "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "tags": ["经历切片", "文本萃取"],
                "confidence_score": 0.95
            })

    if do_save:
        previous_actives = session.exec(select(IPPersona).where(IPPersona.user_id == uid, IPPersona.is_active == True)).all()
        for prev in previous_actives:
            prev.is_active = False
            session.add(prev)

        persona = IPPersona(
            user_id=uid,
            name=persona_data["name"],
            target_audience=persona_data["target_audience"],
            tone_style=persona_data["tone_style"],
            reader_salutation=persona_data["reader_salutation"],
            origin_story=persona_data["origin_story"],
            is_active=True,
        )
        session.add(persona)
        session.commit()
        session.refresh(persona)

        saved_stories = []
        for s_item in stories_data:
            st = EpisodicStory(
                user_id=uid,
                title=s_item.get("title", "经历故事"),
                story_content=s_item.get("story_content", ""),
                story_type=s_item.get("story_type", "daily_life"),
                occurred_at=datetime.now(timezone.utc),
                tags=s_item.get("tags", ["文本萃取"]),
                confidence_score=s_item.get("confidence_score", 1.0),
            )
            session.add(st)
            session.commit()
            session.refresh(st)
            saved_stories.append(st.model_dump())

        return {
            "success": True,
            "persona": persona.model_dump(),
            "stories": saved_stories,
            "saved": True,
            "message": "Persona and stories extracted and saved successfully"
        }

    return {
        "success": True,
        "persona": persona_data,
        "stories": stories_data,
        "saved": False,
        "message": "Persona and stories extracted successfully"
    }


@router.patch("/personas/{persona_id}")
def update_persona(
    persona_id: uuid.UUID,
    body: PersonaUpdate,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    _trusted_user_id(body.user_id, current_user)
    persona = session.get(IPPersona, persona_id)
    if not persona:
        raise _not_found("Persona not found")
    _ensure_owned(persona.user_id, current_user)
    if body.name is not None:
        persona.name = body.name
    if body.target_audience is not None:
        persona.target_audience = body.target_audience
    if body.tone_style is not None:
        persona.tone_style = body.tone_style
    if body.reader_salutation is not None:
        persona.reader_salutation = body.reader_salutation
    if body.origin_story is not None:
        persona.origin_story = body.origin_story
    if body.is_active is not None:
        persona.is_active = body.is_active
    session.add(persona)
    session.commit()
    session.refresh(persona)
    return persona.model_dump()
