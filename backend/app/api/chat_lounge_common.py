# -*- coding: utf-8 -*-
"""Shared plumbing for the Chat Lounge API modules.

Extracted verbatim from the former monolithic ``app/api/chat_lounge.py``.
No behaviour change: this module owns the DB availability fallback, the
identity/ownership helpers, the in-memory session stores, the request/response
schemas and the natural-language date parser.

The dynamic lookups of :func:`_get_db_session` and the facade re-exports keep
``app.api.chat_lounge`` the single supported import path, so tests and callers
that patch ``app.api.chat_lounge.engine`` keep working exactly as before.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Shared route table. The facade re-exports this exact object so
# app.api.chat_lounge.router and every submodule stay identical.
router = APIRouter(tags=["chat_lounge"])

try:
    from app.models.persona import IPPersona
    from app.domain.cognitive.models import CognitiveTrait
    from app.models.story import EpisodicStory
    from app.models.chat_session import ChatSession, ChatMessage
    from app.core.db import engine
    from sqlmodel import Session as DbSession, select, desc
    from contextlib import contextmanager

    _HAS_DB_MODELS = True
except ImportError:
    _HAS_DB_MODELS = False


def _facade():
    """Return the ``app.api.chat_lounge`` facade module (lazy, avoids cycles)."""
    from app.api import chat_lounge as _cl

    return _cl


@contextmanager
def _get_db_session():
    # Resolved on every call so that patching ``app.api.chat_lounge.engine``
    # keeps its original effect on this module.
    with DbSession(_facade().engine) as session:
        yield session

# (IPPersona rows seeded for the local install); it is never used as a caller's
# identity and never used as a fallback for write paths.
DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _resolve_user_id(user_id_val: Any) -> uuid.UUID:
    """Strictly resolve a user id.

    Previously this silently fell back to ``DEFAULT_USER_ID`` for any missing or
    malformed value, which meant an unauthenticated or mistyped id silently
    became a specific user. Identity now always comes from the request
    credential (see :mod:`app.core.auth`), so this only parses an id that was
    already resolved from that credential and rejects anything ambiguous.
    """
    if isinstance(user_id_val, uuid.UUID):
        return user_id_val
    if not user_id_val:
        raise HTTPException(status_code=401, detail="Unauthenticated: no user identity.")
    try:
        return uuid.UUID(str(user_id_val))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=401, detail="Unauthenticated: malformed user identity."
        )


def _session_owner_or_none(session_id: str) -> Optional[str]:
    meta = _session_meta.get(session_id)
    if meta and meta.get("user_id"):
        return str(meta["user_id"])
    return None


def _ensure_session_owner(
    session_id: str, caller_id: uuid.UUID, *, allow_missing: bool = False
) -> None:
    """Return silently when the caller owns the session, else raise 404.

    A session owned by another user and a session that does not exist both
    produce the same 404 so the API never reveals that another user's session
    id is valid.

    ``allow_missing=True`` is only used by the create path (``POST /message``
    with a caller-supplied ``session_id``): a session id that exists nowhere
    yet is a brand-new session and is therefore claimable by its creator.
    """
    from app.core.auth.ownership import ensure_same_user, not_found

    # Fixed message: never echo the caller-supplied session id, so a 404 cannot
    # be used to confirm that a specific session id exists somewhere.
    detail = "Session not found."

    owner = _session_owner_or_none(session_id)
    if owner is not None:
        ensure_same_user(caller_id, owner, detail)
        return

    if _HAS_DB_MODELS:
        try:
            with _get_db_session() as db:
                sess = db.get(ChatSession, session_id)
                if sess is not None and sess.user_id:
                    ensure_same_user(caller_id, sess.user_id, detail)
                    return
                if sess is not None and not sess.user_id:
                    # An ownerless row is never user-addressable.
                    raise not_found(detail)
        except HTTPException:
            raise
        except Exception:
            # Fail closed: if ownership cannot be established, the session is
            # treated as not owned rather than granted.
            raise not_found(detail)

    if allow_missing:
        return

    raise not_found(detail)


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory session store (per-process, sufficient for MVP / Phase 2)
# ---------------------------------------------------------------------------
_session_store: Dict[str, List[Dict[str, Any]]] = {}
_session_meta: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ChatMessageRequest(BaseModel):
    message: str
    mode: Literal["free_talk", "coach_inquiry", "timeline_review", "interview"] = "free_talk"
    session_id: Optional[str] = None
    # Deprecated/ignored: identity is derived from the request credential.
    user_id: Optional[str] = None


class DNACapsule(BaseModel):
    type: Literal["story", "dna", "timeline_pin", "evolution"]
    title: str
    summary: str
    occurred_at: Optional[str] = None


class ChatMessageResponse(BaseModel):
    reply: str
    session_id: str
    capsules: List[DNACapsule] = Field(default_factory=list)


class SessionHistoryMessage(BaseModel):
    role: str
    content: str
    ts: str


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: List[SessionHistoryMessage]


class SessionItem(BaseModel):
    session_id: str
    title: str
    updated_at: str
    mode: str
    message_count: int


# ---------------------------------------------------------------------------
# Natural date parser
# ---------------------------------------------------------------------------

def _parse_natural_date(text: str, reference: datetime) -> Optional[str]:
    """
    Convert natural Chinese date expressions to ISO-8601 date string (YYYY-MM-DD).
    Supported patterns: 今天/昨天/上个月/去年/前年/2023年冬/三年前/上个月15号 etc.
    """
    ref = reference

    if re.search(r"今天|今日", text):
        return ref.strftime("%Y-%m-%d")
    if re.search(r"昨天", text):
        return (ref - timedelta(days=1)).strftime("%Y-%m-%d")

    season_month = {
        "春": 3, "春天": 3, "春季": 3,
        "夏": 6, "夏天": 6, "夏季": 6,
        "秋": 9, "秋天": 9, "秋季": 9,
        "冬": 12, "冬天": 12, "冬季": 12,
    }

    m = re.search(r"(\d{4})年(春天?|夏天?|秋天?|冬天?|春季|夏季|秋季|冬季)", text)
    if m:
        year = int(m.group(1))
        month = season_month.get(m.group(2), 1)
        return f"{year}-{month:02d}-01"

    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})[日号]?", text)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{year}-{month:02d}-{day:02d}"

    m = re.search(r"(\d{4})年(\d{1,2})月", text)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        return f"{year}-{month:02d}-01"

    m = re.search(r"(\d{4})年", text)
    if m:
        return f"{m.group(1)}-01-01"

    if re.search(r"去年", text):
        year = ref.year - 1
        season_m = re.search(r"(春天?|夏天?|秋天?|冬天?|春季|夏季|秋季|冬季)", text)
        month = season_month.get(season_m.group(1), 1) if season_m else 1
        return f"{year}-{month:02d}-01"

    if re.search(r"前年", text):
        year = ref.year - 2
        season_m = re.search(r"(春天?|夏天?|秋天?|冬天?|春季|夏季|秋季|冬季)", text)
        month = season_month.get(season_m.group(1), 1) if season_m else 1
        return f"{year}-{month:02d}-01"

    _cn_num = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

    m = re.search(r"(\d+|[一二两三四五六七八九十]+)年前", text)
    if m:
        num_str = m.group(1)
        val = int(num_str) if num_str.isdigit() else _cn_num.get(num_str, 1)
        year = ref.year - val
        return f"{year}-01-01"

    m = re.search(r"上个月(\d{1,2})[日号]", text)
    if m:
        last_month = ref.replace(day=1) - timedelta(days=1)
        day = min(int(m.group(1)), 28)
        return f"{last_month.year}-{last_month.month:02d}-{day:02d}"

    if re.search(r"上个月|上月", text):
        last_month = ref.replace(day=1) - timedelta(days=1)
        return f"{last_month.year}-{last_month.month:02d}-01"

    m = re.search(r"(\d+|[一二两三四五六七八九十]+)个月前", text)
    if m:
        num_str = m.group(1)
        months = int(num_str) if num_str.isdigit() else _cn_num.get(num_str, 1)
        # Compute exact month difference
        y = ref.year
        m_idx = ref.month - months
        while m_idx <= 0:
            m_idx += 12
            y -= 1
        return f"{y}-{m_idx:02d}-01"

    if re.search(r"上上周", text):
        target = ref - timedelta(weeks=2)
        return target.strftime("%Y-%m-%d")
    if re.search(r"上周|上星期", text):
        target = ref - timedelta(weeks=1)
        return target.strftime("%Y-%m-%d")

    return None


