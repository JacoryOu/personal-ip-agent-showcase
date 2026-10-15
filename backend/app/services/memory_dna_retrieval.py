"""Embedding, scoring and hybrid Thinking DNA retrieval."""

from datetime import datetime, timezone
import logging
import math
import struct

logger = logging.getLogger(__name__)

def generate_embedding(text: str):
    """Calls the configured LLM Embedding API and returns a numpy-compatible
    float32 ndarray, or None if the API is unavailable / numpy is missing.

    Stores as raw bytes: 4 bytes per float32 value (little-endian struct pack).
    """
    try:
        import numpy as np
    except ImportError:
        logger.warning("numpy not installed; embedding unavailable.")
        return None

    try:
        from app.core.config import settings
        import openai

        api_key = settings.OPENAI_API_KEY or ""
        base_url = settings.OPENAI_BASE_URL
        if not api_key:
            return None

        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = openai.OpenAI(**client_kwargs)
        response = client.embeddings.create(
            input=text,
            model="text-embedding-3-small",
        )
        vec = np.array(response.data[0].embedding, dtype=np.float32)
        return vec
    except Exception as exc:
        logger.warning("generate_embedding failed: %s", exc)
        return None


def _bytes_to_vec(raw: bytes):
    """Deserialise numpy float32 bytes back to a list of floats."""
    try:
        import numpy as np
        n = len(raw) // 4
        vec = np.frombuffer(raw, dtype="<f4").copy()
        return vec
    except Exception:
        return None


def _cosine_similarity(a, b) -> float:
    """Cosine similarity between two numpy arrays; returns 0 on error."""
    try:
        import numpy as np
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
    except Exception:
        return 0.0


def _score_dna_traits(topic: str, traits: list, now: datetime, limit: int = 5) -> list:
    """Pure scoring over already-loaded traits. Performs NO database access.

    Shared by the writable and read-only retrieval entrypoints so both use
    identical scoring semantics.
    """
    import re

    # --- Build topic keywords ---
    topic_lower = topic.lower()
    topic_keywords = set(re.findall(r"[a-zA-Z0-9_]{2,}", topic_lower))
    chinese_chars = re.findall(r"[\u4e00-\u9fa5]", topic_lower)
    for i in range(len(chinese_chars) - 1):
        topic_keywords.add("".join(chinese_chars[i:i+2]))
    for i in range(len(chinese_chars) - 2):
        topic_keywords.add("".join(chinese_chars[i:i+3]))
    topic_keywords.update(re.findall(r"[\u4e00-\u9fa5]{2,}", topic_lower))

    # --- Query embedding (Plan B) ---
    query_vec = generate_embedding(topic)

    scored = []
    for trait in traits:
        stmt_lower = trait.statement.lower()

        # LexicalScore
        overlap = sum(1 for kw in topic_keywords if kw in stmt_lower)
        lexical = min(overlap / max(len(topic_keywords), 1), 1.0)

        # SemanticScore
        sem = 0.0
        if query_vec is not None and trait.embedding:
            stored_vec = _bytes_to_vec(trait.embedding)
            if stored_vec is not None:
                sem = max(0.0, _cosine_similarity(query_vec, stored_vec))

        # TimeDecayPenalty (lambda=0.0005 for DNA traits)
        td_lambda = 0.0005
        occurred = getattr(trait, "occurred_at", None) or trait.created_at
        if occurred and occurred.tzinfo is None:
            occurred = occurred.replace(tzinfo=timezone.utc)
        delta_days = (now - occurred).total_seconds() / 86400 if occurred else 0
        time_decay = math.exp(-td_lambda * delta_days)

        # ConfidenceBonus
        conf_bonus = trait.confidence_score * 0.1

        final_score = 0.4 * lexical + 0.6 * sem + conf_bonus - (1 - time_decay)
        scored.append((final_score, trait))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"score": s, "trait": t} for s, t in scored[:limit]]

def hybrid_retrieve_dna_readonly(topic: str, user_id, session, limit: int = 5) -> list:
    """Read-only variant of hybrid_retrieve_dna for the agent layer.

    Uses get_user_profile_readonly (no INSERT/COMMIT) plus the shared pure
    scoring helper, so it is safe on a physically read-only session.
    """
    from app.domain.cognitive.models import TraitStatus
    from app.services.cognitive_service import CognitiveService

    profile = CognitiveService.get_user_profile_readonly(session, user_id)
    if profile is None:
        return []
    active_traits = [
        t for t in profile.traits
        if t.status in (TraitStatus.ACTIVE, TraitStatus.PINNED)
        and getattr(t, "trait_status", "active") == "active"
    ]
    if not active_traits:
        return []
    return _score_dna_traits(topic, active_traits, datetime.now(timezone.utc), limit)


def hybrid_retrieve_dna(topic: str, user_id, session, limit: int = 5) -> list:
    """Hybrid retrieval combining lexical (Plan A) + semantic (Plan B) scoring.

    FinalScore = 0.4 * LexicalScore + 0.6 * SemanticScore
                 + ConfidenceBonus - TimeDecayPenalty

    - LexicalScore: N-gram/keyword overlap (mirrors retrieve_contextual_dna logic)
    - SemanticScore: cosine_similarity(query_embedding, stored_embedding) if available, else 0
    - ConfidenceBonus: trait.confidence_score * 0.1 (normalised)
    - TimeDecayPenalty: exp(-lambda * delta_days)
      lambda = 0.05 for episodic stories, 0.0005 for core DNA traits
    """
    from app.domain.cognitive.models import TraitStatus
    from app.services.cognitive_service import CognitiveService

    profile = CognitiveService.get_or_create_user_profile(session, user_id)
    active_traits = [
        t for t in profile.traits
        if t.status in (TraitStatus.ACTIVE, TraitStatus.PINNED)
        and getattr(t, "trait_status", "active") == "active"
    ]
    if not active_traits:
        return []
    return _score_dna_traits(topic, active_traits, datetime.now(timezone.utc), limit)
