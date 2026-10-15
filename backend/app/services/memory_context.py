"""Contextual Thinking DNA retrieval for a topic."""

import re
from typing import List, Optional
import uuid

from sqlmodel import Session

from app.core.db import engine
from app.domain.cognitive.models import (
    CognitiveDimension,
    CognitiveTrait,
    TraitStatus,
)
from app.schemas.diff_schemas import ThinkingDNA
from app.services.cognitive_service import CognitiveService

def retrieve_contextual_dna(
    cls,
    topic: str,
    user_id: Optional[str | uuid.UUID] = None,
    limit: int = 5,
    session: Optional[Session] = None,
) -> Optional[ThinkingDNA]:
    """Retrieves contextual thinking DNA scored against topic relevance and confidence."""
    def _get_contextual(sess: Session) -> Optional[ThinkingDNA]:
        profile = CognitiveService.get_or_create_user_profile(sess, user_id)
        active_traits = [
            t for t in profile.traits if t.status in (TraitStatus.ACTIVE, TraitStatus.PINNED)
        ]
        if not active_traits:
            return None

        topic_lower = topic.lower()
        # Extract keywords: alphanumeric words + Chinese phrases/ngrams
        topic_keywords = set(re.findall(r"[a-zA-Z0-9_]{2,}", topic_lower))
        chinese_chars = re.findall(r"[\u4e00-\u9fa5]", topic_lower)
        for i in range(len(chinese_chars) - 1):
            topic_keywords.add("".join(chinese_chars[i:i+2]))
        for i in range(len(chinese_chars) - 2):
            topic_keywords.add("".join(chinese_chars[i:i+3]))
        chinese_runs = re.findall(r"[\u4e00-\u9fa5]{2,}", topic_lower)
        topic_keywords.update(chinese_runs)

        def score_trait(trait: CognitiveTrait) -> float:
            score = trait.confidence_score
            if trait.status == TraitStatus.PINNED:
                score += 2.0
            statement_lower = trait.statement.lower()
            overlap = sum(1 for kw in topic_keywords if kw in statement_lower)
            score += overlap * 1.5
            return score

        def get_top_statements(*dimensions: CognitiveDimension) -> List[str]:
            matched = [t for t in active_traits if t.dimension in dimensions]
            matched.sort(key=score_trait, reverse=True)
            return [t.statement for t in matched[:limit]]

        vocab = get_top_statements(CognitiveDimension.VOCABULARY)
        logic = get_top_statements(CognitiveDimension.LOGIC_PREFERENCE)
        values = get_top_statements(CognitiveDimension.CORE_VALUE, CognitiveDimension.VIEWPOINT_STANCE)

        return ThinkingDNA(
            vocabulary_habits=vocab,
            logic_preferences=logic,
            core_values=values,
            summary=f"Contextual Thinking DNA retrieved for topic '{topic}'",
        )

    if session:
        return _get_contextual(session)
    else:
        with Session(engine) as sess:
            return _get_contextual(sess)

