# -*- coding: utf-8 -*-
"""Persona crystallization route for the Chat Lounge API.

Extracted verbatim from the former monolithic ``app/api/chat_lounge.py``.
The request schema, the system prompt, the transcript assembly, the model call
and the DB persistence are unchanged. The model gateway is resolved through the
facade at call time so ``patch("app.api.chat_lounge.get_model_gateway")`` works.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.errors import DEPENDENCY_FAILURE, INTERNAL_ERROR, AppError
from app.core.model_gateway import ModelRole, extract_json_from_text

from app.api.chat_lounge_common import (
    ChatMessage,
    ChatSession,
    EpisodicStory,
    IPPersona,
    _HAS_DB_MODELS,
    _ensure_session_owner,
    _get_db_session,
    _session_store,
    logger,
    router,
)


def _facade():
    """Return the ``app.api.chat_lounge`` facade module (lazy, avoids cycles)."""
    from app.api import chat_lounge as _cl

    return _cl

class CrystallizePersonaRequest(BaseModel):
    # Deprecated/ignored: identity is derived from the request credential.
    user_id: Optional[str] = None


_CRYSTALLIZE_SYSTEM_PROMPT = """你是一位顶级的个人IP操盘手与传记结晶专家。
你的任务是将创作者与访谈主持人的一整场“灵魂专访”对话录，深度结晶提炼为完整的个人IP资产（IP Persona）以及具有代表性的人生经历与生活切片故事（Episodic Stories）。

提炼要求：
1. 真实与温度：
   - 绝不使用简历式、公文式的空洞语言，捕捉创作者在对话中流露的真性情、独特洞见、底层价值观与人生转折点。
   - 忠实还原创作者最鲜活的思考与态度（例如对行业某些乱象的痛恨、坚守的原则、对读者的交付心境）。
2. IP人设资产 (IP Persona)：
   - name: 推荐的IP代号或称谓（贴切、有辨识度）
   - target_audience: 明确的受众画像（例如：25-40岁在职场与健康之间寻求平衡的都市女性）
   - tone_style: 独特的表达气质与风格（例如：温润亲和、松弛但有力量、拒绝焦虑）
   - reader_salutation: 最自然真诚的读者称呼（例如：同行者、姐妹们、朋友们）
   - origin_story: 完整、有温度的创作者起源与心路历程故事（第一人称视角或第三人称视角，充满感染力与说服力）
3. 故事切片 (Episodic Stories)：
   - 从对话中挖掘创作者提及的具体生活细节、人生经历、踩坑反思或学员/客户实战案例。
   - 每个故事切片包含：
     * title: 故事标题
     * story_type: "daily_life" | "failure_reflection" | "client_case"
     * story_content: 故事详细内容与细节
     * occurred_at: 推断的发生时间（格式YYYY-MM-DD，若无法确定则为 null）
     * tags: 关键标签列表（例如 ["创业经历", "至暗时刻"]）

请严格输出如下 JSON 格式：
{
  "name": "推荐的IP代号或称谓",
  "target_audience": "受众画像",
  "tone_style": "语言风格特征",
  "reader_salutation": "最自然的读者称谓",
  "origin_story": "从访谈中提炼出的创作者真实心路历程与起源故事",
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


@router.post("/sessions/{session_id}/crystallize-persona")
async def crystallize_persona(
    session_id: str,
    body: Optional[CrystallizePersonaRequest] = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Gathers conversation history from the interview session, uses LLM to
    crystallize the interview into an IPPersona and EpisodicStory records,
    and saves them to the database as the active IPPersona.
    """
    _ensure_session_owner(session_id, current_user.id)

    messages: List[Dict[str, str]] = []
    # ``body.user_id`` is ignored; the crystallization always targets the
    # authenticated caller.
    target_user_id: Optional[str] = None

    if _HAS_DB_MODELS:
        try:
            with _get_db_session() as db:
                sess = db.get(ChatSession, session_id)
                if sess and sess.user_id:
                    target_user_id = sess.user_id

                db_msgs = db.exec(
                    select(ChatMessage)
                    .where(ChatMessage.session_id == session_id)
                    .order_by(ChatMessage.id)
                ).all()
                if db_msgs:
                    messages = [{"role": m.role, "content": m.content} for m in db_msgs]
        except Exception:
            pass

    if not messages and session_id in _session_store:
        messages = [{"role": m["role"], "content": m["content"]} for m in _session_store[session_id]]

    if not messages:
        raise HTTPException(
            status_code=404,
            detail="Session not found or has no conversation history to crystallize.",
        )

    uid = current_user.id

    # Format dialogue
    dialogue_lines = []
    for m in messages:
        speaker = "创作者" if m.get("role") == "user" else "访谈主持人"
        dialogue_lines.append(f"{speaker}：{m.get('content', '')}")
    dialogue_text = "\n".join(dialogue_lines)

    gateway = _facade().get_model_gateway()
    client = gateway.get_client_for_role(ModelRole.DIFF)
    model = gateway.get_model_for_role(ModelRole.DIFF)

    user_prompt = f"以下是完整的深度灵魂访谈对话记录：\n\n{dialogue_text}\n\n请深度萃取并结晶创作者的IP人设与人生故事切片，严格输出JSON格式。"

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _CRYSTALLIZE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1500,
        )
        raw_content = (response.choices[0].message.content or "").strip()
        extracted_data = extract_json_from_text(raw_content)
    except Exception as e:
        logger.exception("persona crystallization LLM call failed")
        raise AppError(
            code=DEPENDENCY_FAILURE,
            message="The language model provider could not complete the request.",
        ) from e

    persona_data = {
        "name": str(extracted_data.get("name") or "个人IP创作者"),
        "target_audience": str(extracted_data.get("target_audience") or ""),
        "tone_style": str(extracted_data.get("tone_style") or ""),
        "reader_salutation": str(extracted_data.get("reader_salutation") or ""),
        "origin_story": str(extracted_data.get("origin_story") or ""),
    }

    raw_stories = extracted_data.get("extracted_stories") or []
    valid_story_types = {"daily_life", "failure_reflection", "client_case"}
    stories_data = []
    for s in raw_stories:
        if not isinstance(s, dict):
            continue
        stype = s.get("story_type") if s.get("story_type") in valid_story_types else "daily_life"
        stories_data.append({
            "title": str(s.get("title") or ""),
            "story_type": stype,
            "story_content": str(s.get("story_content") or ""),
            "occurred_at": s.get("occurred_at") if s.get("occurred_at") else None,
            "tags": s.get("tags") if isinstance(s.get("tags"), list) else [],
        })

    saved_persona_dict = None
    saved_stories_list = []

    if _HAS_DB_MODELS:
        try:
            with _get_db_session() as db:
                # Deactivate existing active personas for this user
                existing_active = db.exec(
                    select(IPPersona).where(IPPersona.user_id == uid, IPPersona.is_active == True)
                ).all()
                for p in existing_active:
                    p.is_active = False
                    db.add(p)

                new_persona = IPPersona(
                    user_id=uid,
                    name=persona_data["name"],
                    target_audience=persona_data["target_audience"],
                    tone_style=persona_data["tone_style"],
                    reader_salutation=persona_data["reader_salutation"],
                    origin_story=persona_data["origin_story"],
                    is_active=True,
                )
                db.add(new_persona)

                saved_story_objs = []
                for s in stories_data:
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
                    db.add(story_obj)
                    saved_story_objs.append(story_obj)

                db.commit()
                db.refresh(new_persona)
                for so in saved_story_objs:
                    db.refresh(so)

                saved_persona_dict = new_persona.model_dump()
                saved_stories_list = [so.model_dump() for so in saved_story_objs]
        except Exception as db_err:
            logger.exception("failed to persist crystallized persona")
            raise AppError(
                code=INTERNAL_ERROR,
                message="Failed to save the crystallized persona.",
            ) from db_err

    if saved_persona_dict is None:
        saved_persona_dict = {
            "id": str(uuid.uuid4()),
            "user_id": str(uid),
            "name": persona_data["name"],
            "target_audience": persona_data["target_audience"],
            "tone_style": persona_data["tone_style"],
            "reader_salutation": persona_data["reader_salutation"],
            "origin_story": persona_data["origin_story"],
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        saved_stories_list = stories_data

    return {
        "success": True,
        "persona": saved_persona_dict,
        "stories": saved_stories_list,
    }

