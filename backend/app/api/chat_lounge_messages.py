# -*- coding: utf-8 -*-
"""`POST /message` route for the Chat Lounge API.

Extracted verbatim from the former monolithic ``app/api/chat_lounge.py``.
The handler body, its identity resolution, the concurrent chat/extraction
fan-out and the capsule assembly are unchanged. The model gateway is resolved
through the facade at call time so that
``patch("app.api.chat_lounge.get_model_gateway")`` keeps working.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.errors import DEPENDENCY_FAILURE, AppError

from app.api.chat_lounge_common import (
    ChatMessage,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSession,
    CognitiveTrait,
    IPPersona,
    _HAS_DB_MODELS,
    _ensure_session_owner,
    _get_db_session,
    _resolve_user_id,
    _session_meta,
    _session_store,
    logger,
    router,
)
from app.api.chat_lounge_prompts import _build_twin_system_prompt, _call_chat, _call_extraction


def _facade():
    """Return the ``app.api.chat_lounge`` facade module (lazy, avoids cycles)."""
    from app.api import chat_lounge as _cl

    return _cl

@router.post("/message", response_model=ChatMessageResponse)
async def post_message(
    request: ChatMessageRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ChatMessageResponse:
    """
    Main chat endpoint.
    1. Generates a conversational reply (mode-specific system prompt).
    2. Runs background DNA/story extraction concurrently.
    Returns reply + extracted capsules.
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=422, detail="message cannot be empty")

    session_id = request.session_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    # Identity comes from the credential only; ``request.user_id`` is ignored.
    uid_str = str(current_user.id)

    if session_id not in _session_store:
        # A brand-new session id is claimable; an existing one (in memory or in
        # the DB) must already belong to the caller before we append to it.
        _ensure_session_owner(session_id, current_user.id, allow_missing=True)
        _session_store[session_id] = []
        _session_meta[session_id] = {
            "user_id": uid_str,
            "created_at": now.isoformat(),
            "mode": request.mode,
            "title": request.message[:20]
        }

    history = _session_store[session_id]

    # IP Persona and DNA — always try to load, use twin prompt regardless
    persona = None
    dna_summary = ""
    if _HAS_DB_MODELS:
        try:
            with _get_db_session() as db:
                # Try to find user's active persona, fall back to DEFAULT_USER_ID presets
                user_uuid = _resolve_user_id(uid_str)
                persona = db.exec(
                    select(IPPersona).where(
                        IPPersona.user_id == user_uuid,
                        IPPersona.is_active == True
                    )
                ).first()
                if persona is None:
                    # Try system presets
                    persona = db.exec(
                        select(IPPersona).where(
                            IPPersona.user_id == DEFAULT_USER_ID,
                            IPPersona.is_active == True
                        )
                    ).first()
                traits = db.exec(
                    select(CognitiveTrait).where(
                        CognitiveTrait.user_id == uid_str,
                        CognitiveTrait.status != "suppressed"
                    ).order_by(desc(CognitiveTrait.confidence_score)).limit(10)
                ).all()
                if traits:
                    dna_summary = "\n".join([f"- {t.statement}" for t in traits])
        except Exception:
            pass

    # ALWAYS use the Cognitive Twin prompt — never fall back to generic chatbot prompts
    system_prompt = _build_twin_system_prompt(request.mode, persona, dna_summary)

    gateway = _facade().get_model_gateway()

    reply_task = asyncio.create_task(
        _call_chat(gateway, system_prompt, history, request.message)
    )
    extraction_task = asyncio.create_task(
        _call_extraction(gateway, request.message, now)
    )

    try:
        reply = await reply_task
    except Exception as exc:
        # The upstream provider message can contain account ids, endpoint URLs
        # and quota detail, so it is logged but never returned.
        logger.exception("chat lounge reply generation failed")
        raise AppError(
            code=DEPENDENCY_FAILURE,
            message="The language model provider could not complete the request.",
        ) from exc

    try:
        capsules = await extraction_task
    except Exception:
        capsules = []

    history.append({"role": "user", "content": request.message, "ts": now.isoformat()})
    history.append({"role": "assistant", "content": reply, "ts": datetime.now(timezone.utc).isoformat()})

    if len(history) > 60:
        _session_store[session_id] = history[-60:]

    # Persist to DB
    if _HAS_DB_MODELS:
        try:
            with _get_db_session() as db:
                sess = db.get(ChatSession, session_id)
                if not sess:
                    sess = ChatSession(
                        id=session_id,
                        user_id=uid_str,
                        title=request.message[:20],
                        mode=request.mode,
                        message_count=0
                    )
                    db.add(sess)
                
                db.add(ChatMessage(session_id=session_id, role="user", content=request.message))
                db.add(ChatMessage(session_id=session_id, role="assistant", content=reply))
                
                sess.message_count += 2
                sess.updated_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass

    return ChatMessageResponse(
        reply=reply,
        session_id=session_id,
        capsules=capsules,
    )



