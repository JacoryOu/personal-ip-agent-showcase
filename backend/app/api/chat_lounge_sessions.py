# -*- coding: utf-8 -*-
"""Session history / listing / deletion / rename routes for the Chat Lounge API.

Extracted verbatim from the former monolithic ``app/api/chat_lounge.py``.
Every handler body, the ownership gate, the in-memory-then-DB lookup order and
the ``AppError`` wrapping are unchanged. ``app.api.chat_lounge`` re-exports all
of these names.
"""

from __future__ import annotations

import re
from typing import List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.errors import INTERNAL_ERROR, AppError
from sqlmodel import desc, select

from app.api.chat_lounge_common import (
    ChatMessage,
    ChatSession,
    SessionHistoryMessage,
    SessionHistoryResponse,
    SessionItem,
    _HAS_DB_MODELS,
    _ensure_session_owner,
    _get_db_session,
    _session_meta,
    _session_store,
    logger,
    router,
)
@router.get("/history", response_model=SessionHistoryResponse)
async def get_history(
    session_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> SessionHistoryResponse:
    """Return all stored messages for a session owned by the caller."""
    _ensure_session_owner(session_id, current_user.id)

    if session_id in _session_store and _session_store[session_id]:
        messages = [
            SessionHistoryMessage(
                role=m["role"],
                content=m["content"],
                ts=m.get("ts", ""),
            )
            for m in _session_store[session_id]
        ]
        return SessionHistoryResponse(session_id=session_id, messages=messages)

    if _HAS_DB_MODELS:
        try:
            with _get_db_session() as db:
                db_msgs = db.exec(
                    select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id)
                ).all()
                if db_msgs:
                    messages = [
                        SessionHistoryMessage(
                            role=m.role,
                            content=m.content,
                            ts=m.ts.isoformat()
                        )
                        for m in db_msgs
                    ]
                    _session_store[session_id] = [{"role": m.role, "content": m.content, "ts": m.ts.isoformat()} for m in db_msgs]
                    return SessionHistoryResponse(session_id=session_id, messages=messages)
        except Exception:
            pass

    raise HTTPException(status_code=404, detail="Session not found.")


@router.get("/sessions", response_model=List[SessionItem])
async def list_sessions(
    user_id: Optional[str] = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[SessionItem]:
    """List all chat sessions owned by the caller (most recent first)."""
    # ``user_id`` is accepted for backwards compatibility but ignored: identity
    # is derived from the credential.
    uid_str = str(current_user.id)

    # Try DB first
    if _HAS_DB_MODELS:
        try:
            with _get_db_session() as db:
                db_sessions = db.exec(select(ChatSession).where(ChatSession.user_id == uid_str).order_by(desc(ChatSession.updated_at))).all()
                if db_sessions:
                    return [
                        SessionItem(
                            session_id=s.id,
                            title=s.title,
                            updated_at=s.updated_at.isoformat(),
                            mode=s.mode,
                            message_count=s.message_count,
                        )
                        for s in db_sessions
                    ]
        except Exception:
            pass

    sessions: List[SessionItem] = []
    for sid, meta in _session_meta.items():
        # Strict ownership: no more "show everything when the caller happens to
        # be the default user" behaviour.
        if str(meta.get("user_id")) != uid_str:
            continue
        history = _session_store.get(sid, [])
        sessions.append(
            SessionItem(
                session_id=sid,
                title=meta.get("title", "新对话"),
                updated_at=meta.get("created_at", ""),
                mode=meta.get("mode", "free_talk"),
                message_count=len(history)
            )
        )

    sessions.sort(key=lambda s: s.updated_at, reverse=True)
    return sessions

@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    _ensure_session_owner(session_id, current_user.id)

    if _HAS_DB_MODELS:
        try:
            with _get_db_session() as db:
                sess = db.get(ChatSession, session_id)
                if sess:
                    db_msgs = db.exec(select(ChatMessage).where(ChatMessage.session_id == session_id)).all()
                    for m in db_msgs:
                        db.delete(m)
                    db.delete(sess)
                    db.commit()
        except Exception as exc:
            # Previously swallowed, which reported success even when nothing
            # was actually removed. The cause stays server-side.
            logger.exception("failed to delete chat session")
            raise AppError(
                code=INTERNAL_ERROR, message="Failed to delete the session."
            ) from exc

    if session_id in _session_store:
        del _session_store[session_id]
    if session_id in _session_meta:
        del _session_meta[session_id]

    return {"success": True}

class RenameSessionRequest(BaseModel):
    title: str

@router.post("/sessions/{session_id}/title")
async def rename_session(
    session_id: str,
    body: RenameSessionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    _ensure_session_owner(session_id, current_user.id)

    title = body.title
    if _HAS_DB_MODELS:
        try:
            with _get_db_session() as db:
                sess = db.get(ChatSession, session_id)
                if sess:
                    sess.title = title
                    db.commit()
        except Exception as exc:
            logger.exception("failed to rename chat session")
            raise AppError(
                code=INTERNAL_ERROR, message="Failed to rename the session."
            ) from exc

    if session_id in _session_meta:
        _session_meta[session_id]["title"] = title

    return {"success": True}

