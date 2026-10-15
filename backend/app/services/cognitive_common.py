"""Shared helpers for the cognitive service split modules.

Holds ``_parse_user_id`` so the profile / evolution / portability mixins can
share it without importing the ``cognitive_service`` facade (which imports
them). The facade still re-exports the helper, so existing importers such as
``feedback_service`` keep working unchanged.
"""

from __future__ import annotations

import uuid
from typing import Optional


def _parse_user_id(user_id: Optional[uuid.UUID | str]) -> Optional[uuid.UUID]:
    if not user_id:
        return None
    if isinstance(user_id, uuid.UUID):
        return user_id
    try:
        return uuid.UUID(str(user_id))
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(user_id))
