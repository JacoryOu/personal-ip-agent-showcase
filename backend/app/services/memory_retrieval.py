"""Episodic story retrieval / search (writable path)."""

from datetime import datetime, timezone
import re
from typing import Any, List, Optional
import uuid

from sqlmodel import Session, select

from app.core.db import engine
from app.services.cognitive_service import CognitiveService
from app.services.memory_common import _parse_user_id
from app.services.memory_dna_retrieval import _bytes_to_vec, generate_embedding

def retrieve_relevant_stories(
    cls,
    topic: str,
    user_id: Optional[str | uuid.UUID] = None,
    limit: int = 2,
    session: Optional[Session] = None,
    story_ids: Optional[List[str]] = None,
) -> List[Any]:
    """Retrieves top relevant episodic stories for the user and topic."""
    def _get_stories(sess: Session) -> List[Any]:
        from app.models.story import EpisodicStory
        from app.services.cognitive_service import CognitiveService
        from app.models.persona import DEFAULT_USER_ID
        import re

        parsed_uid = _parse_user_id(user_id)
        if not parsed_uid:
            user = CognitiveService.get_or_create_default_user(sess)
            parsed_uid = user.id

        if story_ids is not None:
            matched = []
            for sid in story_ids:
                try:
                    st = sess.get(EpisodicStory, uuid.UUID(str(sid)))
                    if st and (st.user_id == parsed_uid or st.user_id == DEFAULT_USER_ID):
                        matched.append(st)
                except ValueError:
                    pass
            return matched

        stories = sess.exec(
            select(EpisodicStory).where(EpisodicStory.user_id == parsed_uid)
        ).all()

        if not stories and parsed_uid != DEFAULT_USER_ID:
            stories = sess.exec(
                select(EpisodicStory).where(EpisodicStory.user_id == DEFAULT_USER_ID)
            ).all()

        if not stories:
            return []

        topic_lower = topic.lower()
        topic_keywords = set(re.findall(r"[a-zA-Z0-9_]{2,}", topic_lower))
        chinese_chars = re.findall(r"[\u4e00-\u9fa5]", topic_lower)
        for i in range(len(chinese_chars) - 1):
            topic_keywords.add("".join(chinese_chars[i:i+2]))
        for i in range(len(chinese_chars) - 2):
            topic_keywords.add("".join(chinese_chars[i:i+3]))
        topic_keywords.update(re.findall(r"[\u4e00-\u9fa5]{2,}", topic_lower))

        query_vec = generate_embedding(topic)

        scored = []
        for s in stories:
            tags_list = s.tags if isinstance(s.tags, list) else []
            content_text = f"{s.title} {s.story_content} {' '.join(tags_list)}".lower()
            overlap = sum(1 for kw in topic_keywords if kw in content_text)
            lexical = min(overlap / max(len(topic_keywords), 1), 1.0)

            sem = 0.0
            if query_vec is not None and getattr(s, "embedding", None):
                stored_vec = _bytes_to_vec(s.embedding)
                if stored_vec is not None:
                    sem = max(0.0, _cosine_similarity(query_vec, stored_vec))

            conf = getattr(s, "confidence_score", 1.0) * 0.1
            score = 0.5 * lexical + 0.5 * sem + conf
            scored.append((score, s))

        def _safe_dt_ts(dt: Any) -> float:
            if dt is None:
                return 0.0
            if isinstance(dt, str):
                try:
                    dt = datetime.fromisoformat(dt)
                except Exception:
                    return 0.0
            if isinstance(dt, datetime):
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.timestamp()
            return 0.0

        scored.sort(
            key=lambda x: (x[0], _safe_dt_ts(getattr(x[1], "occurred_at", None))),
            reverse=True
        )
        return [s for _, s in scored[:limit]]

    if session:
        return _get_stories(session)
    else:
        with Session(engine) as sess:
            return _get_stories(sess)
