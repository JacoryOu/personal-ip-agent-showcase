# -*- coding: utf-8 -*-
"""Chat Lounge API - Cognitive Chat Lounge (认知对谈室) — compatibility facade.

The route table and every public name are unchanged; the implementation now
lives in responsibility-scoped modules:

- :mod:`app.api.chat_lounge_common` — DB fallback, identity/ownership, session
  stores, Pydantic schemas, natural-language date parsing.
- :mod:`app.api.chat_lounge_prompts` — system prompts and the LLM call helpers.
- :mod:`app.api.chat_lounge_messages` — ``POST /message``.
- :mod:`app.api.chat_lounge_sessions` — history, list, delete and rename routes.
- :mod:`app.api.chat_lounge_crystallization` — persona crystallization route.

``app.api.chat_lounge`` remains the single supported import path: existing
``from app.api.chat_lounge import ...`` callers, dependency overrides and
``unittest.mock.patch("app.api.chat_lounge.<name>")`` all keep resolving to the
same objects. Submodules resolve ``engine`` and ``get_model_gateway`` through
this facade at call time so those patches still take effect.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from sqlmodel import Session as DbSession, desc, select

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.errors import DEPENDENCY_FAILURE, INTERNAL_ERROR, AppError
from app.core.model_gateway import (
    ModelGateway,
    ModelRole,
    extract_json_from_text,
    get_model_gateway,
)

try:
    from app.core.db import engine
except Exception:  # pragma: no cover - DB deps may be unavailable at import
    engine = None


# ---------------------------------------------------------------------------
# Re-export the shared plumbing. These are the *same* objects the submodules
# use, so state (the in-memory session stores) stays shared.
# ---------------------------------------------------------------------------
from app.api.chat_lounge_common import (  # noqa: E402
    DEFAULT_USER_ID,
    DNACapsule,
    ChatMessage,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSession,
    CognitiveTrait,
    EpisodicStory,
    IPPersona,
    SessionHistoryMessage,
    SessionHistoryResponse,
    SessionItem,
    _HAS_DB_MODELS,
    _ensure_session_owner,
    _get_db_session,
    _parse_natural_date,
    _resolve_user_id,
    _session_meta,
    _session_owner_or_none,
    _session_store,
    logger,
)
from app.api.chat_lounge_common import router  # noqa: E402  (shared route table)

from app.api.chat_lounge_prompts import (  # noqa: E402
    _build_twin_system_prompt,
    _call_chat,
    _call_extraction,
    _COACH_INQUIRY_SYSTEM,
    _EXTRACTION_SYSTEM,
    _FREE_TALK_SYSTEM,
    _TIMELINE_REVIEW_SYSTEM,
)

from app.api.chat_lounge_crystallization import (  # noqa: E402
    _CRYSTALLIZE_SYSTEM_PROMPT,
    CrystallizePersonaRequest,
    crystallize_persona,
)

from app.api.chat_lounge_messages import post_message  # noqa: E402

from app.api.chat_lounge_sessions import (  # noqa: E402
    RenameSessionRequest,
    delete_session,
    get_history,
    list_sessions,
    rename_session,
)
