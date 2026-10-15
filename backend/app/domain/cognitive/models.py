"""Cognitive Domain Models."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
import uuid

from pydantic import BaseModel, Field

from app.schemas.diff_schemas import ThinkingDNA


class CognitiveDimension(str, Enum):
    VOCABULARY = "vocabulary"
    LOGIC_PREFERENCE = "logic_preference"
    CORE_VALUE = "core_value"
    VIEWPOINT_STANCE = "viewpoint_stance"


class TraitStatus(str, Enum):
    ACTIVE = "active"
    PINNED = "pinned"
    SUPPRESSED = "suppressed"


class CognitiveTrait(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dimension: CognitiveDimension
    statement: str
    confidence_score: float = 1.0
    status: TraitStatus = TraitStatus.ACTIVE
    source_draft_id: Optional[str] = None
    evolution_boost_count: int = 0
    last_boosted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ---- Thinking DNA 2.0 evolution fields ----
    version: int = 1
    trait_status: str = "active"  # 'active' | 'superseded' | 'deprecated'
    superseded_by_id: Optional[str] = None
    evolution_reason: Optional[str] = None
    occurred_at: Optional[datetime] = None
    timeline_milestone: Optional[str] = None
    embedding: Optional[bytes] = None


class CognitiveProfile(BaseModel):
    user_id: str
    traits: List[CognitiveTrait] = Field(default_factory=list)

    def find_trait(self, trait_id: str) -> Optional[CognitiveTrait]:
        for trait in self.traits:
            if trait.id == trait_id:
                return trait
        return None

    def boost_trait_confidence(
        self,
        trait_id: str,
        delta: float = 0.5,
    ) -> Optional[CognitiveTrait]:
        trait = self.find_trait(trait_id)
        if not trait:
            return None
        trait.confidence_score = round(trait.confidence_score + delta, 2)
        trait.evolution_boost_count = (trait.evolution_boost_count or 0) + 1
        trait.last_boosted_at = datetime.now(timezone.utc)
        trait.updated_at = datetime.now(timezone.utc)
        return trait

    def add_or_reinforce_trait(
        self,
        dimension: CognitiveDimension,
        statement: str,
        source_draft_id: Optional[str] = None,
    ) -> CognitiveTrait:
        normalized = statement.strip()
        for trait in self.traits:
            if trait.dimension == dimension and trait.statement.strip().lower() == normalized.lower():
                trait.confidence_score = round(trait.confidence_score + 0.5, 2)
                trait.updated_at = datetime.now(timezone.utc)
                if source_draft_id and not trait.source_draft_id:
                    trait.source_draft_id = source_draft_id
                return trait

        new_trait = CognitiveTrait(
            dimension=dimension,
            statement=normalized,
            confidence_score=1.0,
            status=TraitStatus.ACTIVE,
            source_draft_id=source_draft_id,
        )
        self.traits.append(new_trait)
        return new_trait

    def pin_trait(self, trait_id: str) -> bool:
        trait = self.find_trait(trait_id)
        if not trait:
            return False
        trait.status = TraitStatus.PINNED
        trait.confidence_score = round(trait.confidence_score + 1.0, 2)
        trait.updated_at = datetime.now(timezone.utc)
        return True

    def unpin_trait(self, trait_id: str) -> bool:
        trait = self.find_trait(trait_id)
        if not trait:
            return False
        trait.status = TraitStatus.ACTIVE
        trait.updated_at = datetime.now(timezone.utc)
        return True

    def suppress_trait(self, trait_id: str) -> bool:
        trait = self.find_trait(trait_id)
        if not trait:
            return False
        trait.status = TraitStatus.SUPPRESSED
        trait.updated_at = datetime.now(timezone.utc)
        return True

    def toggle_trait(self, trait_id: str, enable: Optional[bool] = None) -> Optional[CognitiveTrait]:
        trait = self.find_trait(trait_id)
        if not trait:
            return None
        if enable is None:
            if trait.status == TraitStatus.SUPPRESSED:
                trait.status = TraitStatus.ACTIVE
            else:
                trait.status = TraitStatus.SUPPRESSED
        else:
            trait.status = TraitStatus.ACTIVE if enable else TraitStatus.SUPPRESSED
        trait.updated_at = datetime.now(timezone.utc)
        return trait

    def update_trait(
        self,
        trait_id: str,
        statement: Optional[str] = None,
        dimension: Optional[CognitiveDimension] = None,
        status: Optional[TraitStatus] = None,
        confidence_score: Optional[float] = None,
    ) -> Optional[CognitiveTrait]:
        trait = self.find_trait(trait_id)
        if not trait:
            return None
        if statement is not None and statement.strip():
            trait.statement = statement.strip()
        if dimension is not None:
            trait.dimension = dimension
        if status is not None:
            trait.status = status
        if confidence_score is not None:
            trait.confidence_score = round(confidence_score, 2)
        trait.updated_at = datetime.now(timezone.utc)
        return trait

    def get_traits(
        self,
        dimension: Optional[CognitiveDimension] = None,
        status: Optional[TraitStatus] = None,
    ) -> List[CognitiveTrait]:
        results = self.traits
        if dimension is not None:
            results = [t for t in results if t.dimension == dimension]
        if status is not None:
            results = [t for t in results if t.status == status]
        return results

    def export_thinking_dna(self, summary: Optional[str] = None) -> ThinkingDNA:
        def _get_sorted_statements(*dimensions: CognitiveDimension) -> List[str]:
            matching = [
                t for t in self.traits
                if t.dimension in dimensions and t.status in (TraitStatus.ACTIVE, TraitStatus.PINNED)
            ]
            matching.sort(
                key=lambda t: (1 if t.status == TraitStatus.PINNED else 0, t.confidence_score),
                reverse=True,
            )
            return [t.statement for t in matching]

        vocab = _get_sorted_statements(CognitiveDimension.VOCABULARY)
        logic = _get_sorted_statements(CognitiveDimension.LOGIC_PREFERENCE)
        values = _get_sorted_statements(CognitiveDimension.CORE_VALUE, CognitiveDimension.VIEWPOINT_STANCE)

        return ThinkingDNA(
            vocabulary_habits=vocab,
            logic_preferences=logic,
            core_values=values,
            summary=summary,
        )
