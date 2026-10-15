"""Automatic viral style-fingerprint selection for the Draft pipeline.

Layering: CognitiveEngine -> this Service -> SQLModel. The service only
*ranks* candidates; it never returns trusted prompt text. The chosen id is
re-validated by the engine's strict ``_load_owned_style_fingerprint`` before it
can reach an LLM, so this module can never widen the trust boundary.

Scoring is fully deterministic and code-based: lexical overlap plus a few
mechanical signals already present in ``analysis_data``. Weights and the accept
threshold are explicit, defaulted and injectable (never client-supplied).

Candidate scope is hard-limited to analyses owned by the authenticated user.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import Session, select

from app.models.draft import Draft
from app.models.viral_analysis import ViralSemanticAnalysisRecord

# Lineage value recorded when neither an explicit id nor an automatic match
# produced a usable external style.
STYLE_SOURCE_NONE = "persona_dna_no_external_style"
STYLE_SOURCE_AUTO = "viral_semantic_analysis_auto_selected"
STYLE_SOURCE_EXPLICIT = "viral_semantic_analysis"

_ASCII_WORD = re.compile(r"[a-z0-9]+")
_CJK = re.compile(r"[\u4e00-\u9fff]")


def tokenize(text: Optional[str]) -> set:
    """Mixed CJK-bigram + ASCII-word tokenizer (stable, dependency-free)."""
    if not text:
        return set()
    lowered = text.lower()
    tokens = set(_ASCII_WORD.findall(lowered))
    cjk = _CJK.findall(lowered)
    for i in range(len(cjk) - 1):
        tokens.add(cjk[i] + cjk[i + 1])
    if len(cjk) == 1:
        tokens.add(cjk[0])
    return tokens


def overlap_score(query: set, candidate: set) -> float:
    """Symmetric containment score in [0, 1]."""
    if not query or not candidate:
        return 0.0
    shared = query & candidate
    if not shared:
        return 0.0
    return len(shared) / min(len(query), len(candidate))


@dataclass(frozen=True)
class StyleSelectionWeights:
    """Explicit scoring dimensions. Must sum to 1.0."""

    topic_match: float = 0.45
    ip_match: float = 0.30
    recent_work_affinity: float = 0.15
    transferability: float = 0.10

    def validate(self) -> None:
        total = (
            self.topic_match
            + self.ip_match
            + self.recent_work_affinity
            + self.transferability
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Style selection weights must sum to 1.0, got {total}.")


DEFAULT_WEIGHTS = StyleSelectionWeights()
DEFAULT_MIN_MATCH_SCORE = 0.35
DEFAULT_MAX_CANDIDATES = 20
DEFAULT_RECENT_DRAFT_LIMIT = 5

# Recency half-life in days for the recent-work dimension.
_RECENCY_HALF_LIFE_DAYS = 30.0


@dataclass
class StyleSelectionResult:
    """Explainable outcome of an automatic selection attempt."""

    analysis_id: Optional[uuid.UUID] = None
    score: float = 0.0
    threshold: float = DEFAULT_MIN_MATCH_SCORE
    accepted: bool = False
    reason: str = "no_candidates"
    candidate_count: int = 0
    considered: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def style_source(self) -> str:
        return STYLE_SOURCE_AUTO if self.accepted else STYLE_SOURCE_NONE


def _coerce_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _analysis_text(record: ViralSemanticAnalysisRecord) -> str:
    """Best-effort textual surface of one analysis, used for lexical scoring."""
    data = record.analysis_data or {}
    parts: List[str] = [record.source_title or ""]
    fingerprint = data.get("style_fingerprint")
    if isinstance(fingerprint, dict):
        parts.append(str(fingerprint.get("voice") or ""))
        parts.append(str(fingerprint.get("register") or ""))
        parts.append(str(fingerprint.get("sentence_style") or ""))
    value_promise = data.get("value_promise")
    if isinstance(value_promise, dict):
        parts.append(str(value_promise.get("core_value") or ""))
        parts.append(str(value_promise.get("target_audience") or ""))
    hook = data.get("hook")
    if isinstance(hook, dict):
        parts.append(str(hook.get("hook_type") or ""))
        parts.append(str(hook.get("hook_text") or ""))
    return " ".join(p for p in parts if p)


def _transferability(record: ViralSemanticAnalysisRecord) -> float:
    """Mechanical reusability signal, normalized into [0, 1]."""
    data = record.analysis_data or {}
    transfer = data.get("transfer")
    raw = None
    if isinstance(transfer, dict):
        raw = _coerce_float(transfer.get("reuse_score"))
    if raw is None and isinstance(data.get("style_fingerprint"), dict):
        raw = _coerce_float(data["style_fingerprint"].get("transferability"))
    if raw is None:
        return 0.0
    # reuse_score is authored on a 0..5 scale; clamp defensively.
    return max(0.0, min(1.0, raw / 5.0))


def _recency_weight(created_at: Optional[datetime]) -> float:
    if not isinstance(created_at, datetime):
        return 0.0
    reference = created_at
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (datetime.now(timezone.utc) - reference).total_seconds() / 86400.0)
    return 0.5 ** (age_days / _RECENCY_HALF_LIFE_DAYS)


class StyleSelectionService:
    """Ranks the caller's own analysed articles for Draft style reuse."""

    def __init__(
        self,
        weights: StyleSelectionWeights = DEFAULT_WEIGHTS,
        min_match_score: float = DEFAULT_MIN_MATCH_SCORE,
        max_candidates: int = DEFAULT_MAX_CANDIDATES,
        recent_draft_limit: int = DEFAULT_RECENT_DRAFT_LIMIT,
    ) -> None:
        weights.validate()
        if not 0.0 <= min_match_score <= 1.0:
            raise ValueError("min_match_score must be within [0, 1].")
        self.weights = weights
        self.min_match_score = min_match_score
        self.max_candidates = max_candidates
        self.recent_draft_limit = recent_draft_limit

    def _load_candidates(
        self, sess: Session, user_id: uuid.UUID
    ) -> List[ViralSemanticAnalysisRecord]:
        stmt = (
            select(ViralSemanticAnalysisRecord)
            .where(ViralSemanticAnalysisRecord.user_id == user_id)
            .order_by(ViralSemanticAnalysisRecord.created_at.desc())
            .limit(self.max_candidates)
        )
        return list(sess.exec(stmt).all())

    def _load_recent_drafts(
        self, sess: Session, user_id: uuid.UUID
    ) -> List[Draft]:
        stmt = (
            select(Draft)
            .where(Draft.user_id == user_id)
            .order_by(Draft.created_at.desc())
            .limit(self.recent_draft_limit)
        )
        return list(sess.exec(stmt).all())

    def select(
        self,
        sess: Session,
        user_id: Optional[uuid.UUID],
        topic: str,
        ip_text: str = "",
        additional_context: Optional[str] = None,
    ) -> StyleSelectionResult:
        """Return the best owned candidate, or a clean rejection.

        Never raises for business reasons: an unusable input degrades to
        ``no_candidates`` so the Draft flow falls back to Persona/DNA.
        """
        result = StyleSelectionResult(
            threshold=self.min_match_score,
        )
        if user_id is None:
            result.reason = "no_authenticated_user"
            return result

        try:
            candidates = self._load_candidates(sess, user_id)
            recent_drafts = self._load_recent_drafts(sess, user_id)
        except Exception:  # pragma: no cover - defensive, DB-level degradation
            result.reason = "candidate_lookup_failed"
            return result

        result.candidate_count = len(candidates)
        if not candidates:
            result.reason = "no_candidates"
            return result

        topic_tokens = tokenize(topic)
        context_tokens = tokenize(additional_context)
        ip_tokens = tokenize(ip_text)
        recent_tokens: set = set()
        for draft in recent_drafts:
            recent_tokens |= tokenize(draft.topic)
            recent_tokens |= tokenize((draft.original_ai_draft or "")[:2000])
        query_topic = topic_tokens | context_tokens

        scored: List[Tuple[float, datetime, str, ViralSemanticAnalysisRecord]] = []
        considered: List[Dict[str, Any]] = []
        for record in candidates:
            analysis_tokens = tokenize(_analysis_text(record))
            topic_component = overlap_score(query_topic, analysis_tokens)
            ip_component = overlap_score(ip_tokens, analysis_tokens)
            recent_component = (
                overlap_score(recent_tokens, analysis_tokens) * _recency_weight(record.created_at)
                if recent_tokens
                else 0.0
            )
            transfer_component = _transferability(record)

            score = (
                self.weights.topic_match * topic_component
                + self.weights.ip_match * ip_component
                + self.weights.recent_work_affinity * recent_component
                + self.weights.transferability * transfer_component
            )
            score = max(0.0, min(1.0, score))
            considered.append(
                {
                    "analysis_id": str(record.id),
                    "score": round(score, 4),
                    "topic_match": round(topic_component, 4),
                    "ip_match": round(ip_component, 4),
                    "recent_work_affinity": round(recent_component, 4),
                    "transferability": round(transfer_component, 4),
                }
            )
            created = record.created_at if isinstance(record.created_at, datetime) else datetime.min.replace(tzinfo=timezone.utc)
            scored.append((score, created, str(record.id), record))

        # Deterministic ordering: score desc, then recency desc, then id asc.
        scored.sort(key=lambda item: (-item[0], -item[1].timestamp(), item[2]))
        considered.sort(key=lambda item: (-item["score"], item["analysis_id"]))
        result.considered = considered

        best_score, _, _, best = scored[0]
        result.score = round(best_score, 4)
        if best_score < self.min_match_score:
            result.reason = "below_threshold"
            return result

        result.analysis_id = best.id
        result.accepted = True
        result.reason = "selected"
        return result
