"""Mem0-Architecture Cognitive Memory Subsystem (facade).

This module is the stable public surface of the memory subsystem. The
implementation is split into single-responsibility modules:

- ``memory_common``          shared primitives (``Mem0Operation``, ``_parse_user_id``)
- ``memory_similarity``      normalized string similarity
- ``memory_lifecycle``       Mem0 ADD/UPDATE/NOOP lifecycle + own-work DNA ingest
- ``memory_benchmarks``      benchmark deconstruction + dialogue clash capture
- ``memory_blueprints``      benchmark blueprint CRUD
- ``memory_conflicts``       viewpoint conflict detection
- ``memory_context``         contextual Thinking DNA retrieval
- ``memory_retrieval``       relevant-story retrieval (writable path)
- ``memory_readonly``        relevant-story retrieval (read-only agent path)
- ``memory_dna_retrieval``   embeddings + hybrid DNA retrieval
- ``memory_evolution``       trait supersession + time naturalisation

Structural extraction only: every method below delegates to the extracted
implementation with the original explicit signature, so behaviour, SQL,
transaction handling, logging and return shapes are unchanged, and dynamic
dispatch (``cls._compute_similarity``, ``cls.apply_mem0_lifecycle``) still
routes through ``MemoryService`` so monkeypatching keeps working.
"""

from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlmodel import Session

from app.domain.cognitive.models import (
    CognitiveDimension,
    CognitiveProfile,
    CognitiveTrait,
)
from app.schemas.diff_schemas import ThinkingDNA

from app.services import (
    memory_benchmarks as _benchmarks,
    memory_blueprints as _blueprints,
    memory_conflicts as _conflicts,
    memory_context as _context,
    memory_evolution as _evolution,
    memory_lifecycle as _lifecycle,
    memory_readonly as _readonly,
    memory_retrieval as _retrieval,
    memory_similarity as _similarity,
)
from app.services.memory_common import Mem0Operation, _parse_user_id
from app.services.memory_dna_retrieval import (
    generate_embedding,
    hybrid_retrieve_dna,
    hybrid_retrieve_dna_readonly,
)
from app.services.memory_evolution import (
    naturalize_time_expression,
    supersede_dna_trait,
)

__all__ = [
    "MemoryService",
    "Mem0Operation",
    "hybrid_retrieve_dna",
    "hybrid_retrieve_dna_readonly",
    "naturalize_time_expression",
    "supersede_dna_trait",
    "generate_embedding",
]


class MemoryService:
    @staticmethod
    def _compute_similarity(s1: str, s2: str) -> float:
        """Calculates normalized string similarity ratio."""
        return _similarity._compute_similarity(s1, s2)

    @classmethod
    def apply_mem0_lifecycle(
        cls,
        profile: CognitiveProfile,
        dimension: CognitiveDimension,
        statement: str,
        source_id: Optional[str] = None,
        similarity_threshold: float = 0.72,
    ) -> Tuple[Mem0Operation, CognitiveTrait]:
        return _lifecycle.apply_mem0_lifecycle(
            cls,
            profile,
            dimension,
            statement,
            source_id,
            similarity_threshold,
        )

    @classmethod
    def add_own_work_dna(
        cls,
        content: str,
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        return _lifecycle.add_own_work_dna(
            cls,
            content,
            user_id,
            session,
            title,
        )

    @classmethod
    def deconstruct_benchmark(
        cls,
        content: str,
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None,
        title: Optional[str] = None,
        source_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        return _benchmarks.deconstruct_benchmark(
            cls,
            content,
            user_id,
            session,
            title,
            source_url,
        )

    @classmethod
    def record_dialogue_clash(
        cls,
        messages: List[Dict[str, str]],
        user_id: Optional[str | uuid.UUID] = None,
        debate_topic: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        return _benchmarks.record_dialogue_clash(
            cls,
            messages,
            user_id,
            debate_topic,
            session,
        )

    @classmethod
    def retrieve_contextual_dna(
        cls,
        topic: str,
        user_id: Optional[str | uuid.UUID] = None,
        limit: int = 5,
        session: Optional[Session] = None,
    ) -> Optional[ThinkingDNA]:
        return _context.retrieve_contextual_dna(
            cls,
            topic,
            user_id,
            limit,
            session,
        )

    @classmethod
    def get_benchmark_blueprints(
        cls,
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        return _blueprints.get_benchmark_blueprints(cls, user_id, session)

    @classmethod
    def delete_benchmark_blueprint(
        cls,
        blueprint_id: str,
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None,
    ) -> bool:
        return _blueprints.delete_benchmark_blueprint(
            cls,
            blueprint_id,
            user_id,
            session,
        )

    @classmethod
    def update_benchmark_blueprint(
        cls,
        blueprint_id: str,
        updates: Dict[str, Any],
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None,
    ) -> Optional[Dict[str, Any]]:
        return _blueprints.update_benchmark_blueprint(
            cls,
            blueprint_id,
            updates,
            user_id,
            session,
        )

    @classmethod
    def detect_viewpoint_conflicts(
        cls,
        session: Optional[Session] = None,
        user_id: Optional[str | uuid.UUID] = None,
        statement: Optional[str] = None,
        statements: Optional[List[str]] = None,
        draft_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        return _conflicts.detect_viewpoint_conflicts(
            cls,
            session,
            user_id,
            statement,
            statements,
            draft_content,
        )

    @classmethod
    def retrieve_relevant_stories(
        cls,
        topic: str,
        user_id: Optional[str | uuid.UUID] = None,
        limit: int = 2,
        session: Optional[Session] = None,
        story_ids: Optional[List[str]] = None,
    ) -> List[Any]:
        return _retrieval.retrieve_relevant_stories(
            cls,
            topic,
            user_id,
            limit,
            session,
            story_ids,
        )

    @classmethod
    def retrieve_relevant_stories_readonly(
        cls,
        topic: str,
        user_id: Optional[str | uuid.UUID] = None,
        limit: int = 2,
        session: Optional[Session] = None,
        story_ids: Optional[List[str]] = None,
    ) -> List[Any]:
        return _readonly.retrieve_relevant_stories_readonly(
            cls,
            topic,
            user_id,
            limit,
            session,
            story_ids,
        )
