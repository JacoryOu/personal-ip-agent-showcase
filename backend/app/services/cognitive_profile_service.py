"""Cognitive profile persistence and the read-only agent read path.

Split out of ``cognitive_service`` to keep that module small. Behaviour is
unchanged: the original module keeps a ``CognitiveService`` facade built from
these mixins, so every public signature and ``cls``-based call path is the same.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlmodel import Session, select

from app.domain.cognitive.models import CognitiveDimension, CognitiveProfile
from app.models.dna_record import DNARecord
from app.models.user import User
from app.schemas.diff_schemas import ThinkingDNA
from app.services.cognitive_common import _parse_user_id



class CognitiveProfileMixin:


    @staticmethod
    def get_default_user_readonly(session: Session) -> Optional[User]:
        """Read-only variant of get_or_create_default_user. Never writes.

        Returns the first existing user, or None when the database is empty.
        """
        return session.exec(select(User)).first()


    @classmethod
    def get_user_profile_readonly(
        cls, session: Session, user_id: Optional[uuid.UUID | str] = None
    ) -> Optional[CognitiveProfile]:
        """Read-only variant of get_or_create_user_profile. Never writes.

        Returns the persisted profile when available, otherwise synthesizes one
        from historical DNARecord rows *in memory* without persisting it.
        Returns None when the user does not exist at all.
        """
        if user_id:
            parsed_id = _parse_user_id(user_id)
            user = session.get(User, parsed_id) if parsed_id else None
        else:
            user = cls.get_default_user_readonly(session)

        if not user:
            return None

        profile_dict = (user.profile_data or {}).get("cognitive_profile")
        if profile_dict:
            try:
                return CognitiveProfile.model_validate(profile_dict)
            except Exception:
                pass

        historical_records = session.exec(
            select(DNARecord)
            .where(DNARecord.user_id == user.id)
            .order_by(DNARecord.created_at.asc())
        ).all()

        if not historical_records:
            return None

        # Same synthesis logic as get_or_create_user_profile, minus save_profile.
        profile = CognitiveProfile(user_id=str(user.id), traits=[])
        for record in historical_records:
            dna_data = record.dna_data or {}
            source_draft_id = str(record.draft_id) if record.draft_id else None

            for v in dna_data.get("vocabulary_habits", []):
                if isinstance(v, str) and v.strip():
                    profile.add_or_reinforce_trait(
                        CognitiveDimension.VOCABULARY, v.strip(), source_draft_id=source_draft_id
                    )
            for l in dna_data.get("logic_preferences", []):
                if isinstance(l, str) and l.strip():
                    profile.add_or_reinforce_trait(
                        CognitiveDimension.LOGIC_PREFERENCE, l.strip(), source_draft_id=source_draft_id
                    )
            for c in dna_data.get("core_values", []):
                if isinstance(c, str) and c.strip():
                    dim = (
                        CognitiveDimension.VIEWPOINT_STANCE
                        if "主张:" in c or "观点" in c
                        else CognitiveDimension.CORE_VALUE
                    )
                    profile.add_or_reinforce_trait(dim, c.strip(), source_draft_id=source_draft_id)

        return profile


    @staticmethod
    def get_or_create_default_user(session: Session) -> User:
        """Retrieves the default user or creates one if none exists."""
        user = session.exec(select(User)).first()
        if not user:
            user = User(username="default_user", profile_data={})
            session.add(user)
            session.commit()
            session.refresh(user)
        return user


    @classmethod
    def get_or_create_user_profile(
        cls, session: Session, user_id: Optional[uuid.UUID | str] = None
    ) -> CognitiveProfile:
        """
        Loads the user's CognitiveProfile from User.profile_data,
        or synthesizes it from historical DNARecords if not yet initialized.
        """
        if user_id:
            parsed_id = _parse_user_id(user_id)
            user = session.get(User, parsed_id)
            if not user:
                user = User(id=parsed_id, username=f"user_{str(parsed_id)[:8]}", profile_data={})
                session.add(user)
                session.commit()
                session.refresh(user)
        else:
            user = cls.get_or_create_default_user(session)

        # 1. Check if profile already exists in profile_data
        profile_dict = (user.profile_data or {}).get("cognitive_profile")
        if profile_dict:
            try:
                return CognitiveProfile.model_validate(profile_dict)
            except Exception:
                pass

        # 2. Synthesize from historical DNARecord records
        profile = CognitiveProfile(user_id=str(user.id), traits=[])
        historical_records = session.exec(
            select(DNARecord)
            .where(DNARecord.user_id == user.id)
            .order_by(DNARecord.created_at.asc())
        ).all()

        for record in historical_records:
            dna_data = record.dna_data or {}
            source_draft_id = str(record.draft_id) if record.draft_id else None

            # Vocabulary
            for v in dna_data.get("vocabulary_habits", []):
                if isinstance(v, str) and v.strip():
                    profile.add_or_reinforce_trait(
                        CognitiveDimension.VOCABULARY, v.strip(), source_draft_id=source_draft_id
                    )
            # Logic
            for l in dna_data.get("logic_preferences", []):
                if isinstance(l, str) and l.strip():
                    profile.add_or_reinforce_trait(
                        CognitiveDimension.LOGIC_PREFERENCE, l.strip(), source_draft_id=source_draft_id
                    )
            # Core values & viewpoints
            for c in dna_data.get("core_values", []):
                if isinstance(c, str) and c.strip():
                    dim = (
                        CognitiveDimension.VIEWPOINT_STANCE
                        if "主张:" in c or "观点" in c
                        else CognitiveDimension.CORE_VALUE
                    )
                    profile.add_or_reinforce_trait(dim, c.strip(), source_draft_id=source_draft_id)

        # Save initialized profile
        cls.save_profile(session, user, profile)
        return profile


    @staticmethod
    def save_profile(session: Session, user: User, profile: CognitiveProfile) -> None:
        """Persists the updated CognitiveProfile into User.profile_data."""
        current_data = dict(user.profile_data or {})
        current_data["cognitive_profile"] = profile.model_dump(mode="json")
        user.profile_data = current_data
        session.add(user)
        session.commit()
        session.refresh(user)

