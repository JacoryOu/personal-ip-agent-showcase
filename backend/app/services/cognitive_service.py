"""Cognitive Domain Service facade for user cognitive profiles and DNA re-injection.

The implementation now lives in three focused mixins so that no single file
carries persistence, evolution and portability responsibility at once:

- ``cognitive_profile_service`` -- persistence + the read-only agent read path
- ``cognitive_evolution_service`` -- closed-loop DNA evolution and trait curation
- ``cognitive_portability_service`` -- profile import/export and generation-time DNA

Public behaviour is unchanged: ``CognitiveService`` still exposes every method
with the same signature, ``cls``-based dispatch is preserved, and
``_parse_user_id`` is still importable from this module (``feedback_service``
imports it).
"""

from __future__ import annotations

import uuid
from typing import Optional

from app.services.cognitive_evolution_service import CognitiveEvolutionMixin
from app.services.cognitive_portability_service import CognitivePortabilityMixin
from app.services.cognitive_profile_service import CognitiveProfileMixin


def _parse_user_id(user_id: Optional[uuid.UUID | str]) -> Optional[uuid.UUID]:
    if not user_id:
        return None
    if isinstance(user_id, uuid.UUID):
        return user_id
    try:
        return uuid.UUID(str(user_id))
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(user_id))


class CognitiveService(
    CognitiveProfileMixin, CognitiveEvolutionMixin, CognitivePortabilityMixin
):
    """Facade over the cognitive profile / evolution / portability mixins.

    The mixins contribute no ``__init__``, so instances share the plain
    ``object`` construction path and every ``classmethod`` keeps working across
    the mixin chain.
    """


__all__ = ["CognitiveService", "_parse_user_id"]
