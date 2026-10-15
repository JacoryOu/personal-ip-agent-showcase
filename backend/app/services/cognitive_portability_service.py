"""Profile export/import and generation-time DNA projection.

Split out of ``cognitive_service``; behaviour is unchanged and the original
module re-exposes the same methods through the ``CognitiveService`` facade.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlmodel import Session

from app.domain.cognitive.models import (
    CognitiveDimension,
    CognitiveProfile,
    CognitiveTrait,
    TraitStatus,
)
from app.models.user import User
from app.schemas.diff_schemas import ThinkingDNA
from app.services.cognitive_common import _parse_user_id



class CognitivePortabilityMixin:


    @classmethod
    def export_profile_json(
        cls, session: Session, user_id: Optional[uuid.UUID | str] = None
    ) -> dict:
        """Exports complete cognitive profile and Thinking DNA as a dictionary."""
        profile = cls.get_or_create_user_profile(session, user_id)
        thinking_dna = profile.export_thinking_dna()
        return {
            "user_id": str(profile.user_id),
            "version": "1.0",
            "total_traits_count": len(profile.traits),
            "traits": [t.model_dump(mode="json") for t in profile.traits],
            "thinking_dna": thinking_dna.model_dump(mode="json") if thinking_dna else None,
        }


    @classmethod
    def import_profile_json(
        cls,
        session: Session,
        data: dict,
        user_id: Optional[uuid.UUID | str] = None,
        mode: str = "merge",
    ) -> CognitiveProfile:
        """Imports traits or Thinking DNA JSON data into the profile."""
        profile = cls.get_or_create_user_profile(session, user_id)
        parsed_id = _parse_user_id(user_id)
        user = session.get(User, parsed_id) if parsed_id else cls.get_or_create_default_user(session)

        if mode == "overwrite":
            profile.traits = []

        raw_traits = data.get("traits") or []
        for t_data in raw_traits:
            if isinstance(t_data, dict) and t_data.get("statement"):
                try:
                    trait_id = t_data.get("id")
                    existing = profile.find_trait(trait_id) if trait_id else None
                    if existing and mode == "merge":
                        if "dimension" in t_data:
                            existing.dimension = CognitiveDimension(t_data["dimension"])
                        existing.statement = str(t_data.get("statement") or existing.statement).strip()
                        if "confidence_score" in t_data:
                            existing.confidence_score = float(t_data["confidence_score"])
                        if "status" in t_data:
                            existing.status = TraitStatus(t_data["status"])
                        from datetime import datetime, timezone
                        existing.updated_at = datetime.now(timezone.utc)
                    else:
                        clean_data = dict(t_data)
                        dim_raw = clean_data.get("dimension")
                        try:
                            clean_data["dimension"] = CognitiveDimension(dim_raw).value
                        except Exception:
                            clean_data["dimension"] = CognitiveDimension.CORE_VALUE.value
                        if not clean_data.get("id"):
                            clean_data["id"] = str(uuid.uuid4())
                        new_trait = CognitiveTrait.model_validate(clean_data)
                        profile.traits.append(new_trait)
                except Exception:
                    pass

        existing_statements = {t.statement.strip().lower() for t in profile.traits}
        dna_dict = data.get("thinking_dna")
        if isinstance(dna_dict, dict):
            for v in dna_dict.get("vocabulary_habits", []):
                if isinstance(v, str) and v.strip() and v.strip().lower() not in existing_statements:
                    profile.add_or_reinforce_trait(CognitiveDimension.VOCABULARY, v.strip())
                    existing_statements.add(v.strip().lower())
            for l in dna_dict.get("logic_preferences", []):
                if isinstance(l, str) and l.strip() and l.strip().lower() not in existing_statements:
                    profile.add_or_reinforce_trait(CognitiveDimension.LOGIC_PREFERENCE, l.strip())
                    existing_statements.add(l.strip().lower())
            for c in dna_dict.get("core_values", []):
                if isinstance(c, str) and c.strip() and c.strip().lower() not in existing_statements:
                    dim = (
                        CognitiveDimension.VIEWPOINT_STANCE
                        if any(prefix in c for prefix in ["观点:", "立场:", "观点", "主张", "价值:"])
                        else CognitiveDimension.CORE_VALUE
                    )
                    profile.add_or_reinforce_trait(dim, c.strip())
                    existing_statements.add(c.strip().lower())

        cls.save_profile(session, user, profile)
        return profile


    @classmethod
    def get_exportable_dna_for_user(
        cls, session: Session, user_id: Optional[uuid.UUID | str] = None
    ) -> Optional[ThinkingDNA]:
        """
        Exports active & pinned DNA for injection into generation.
        Returns None if user has no accumulated traits.
        """
        profile = cls.get_or_create_user_profile(session, user_id)
        active_traits = [
            t for t in profile.traits if t.status in (TraitStatus.ACTIVE, TraitStatus.PINNED)
        ]
        if not active_traits:
            return None
        return profile.export_thinking_dna()

