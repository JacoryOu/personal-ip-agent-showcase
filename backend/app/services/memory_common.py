"""Shared primitives for the memory subsystem.

Holds the Mem0 operation enum and the shared user-id coercion helper used by
every responsibility module. Structural extraction only: behaviour is
unchanged from the original ``memory_service`` module.
"""

from typing import Optional
import uuid

class Mem0Operation(str):
    ADD = "ADD"
    UPDATE = "UPDATE"
    NOOP = "NOOP"



def _parse_user_id(user_id: Optional[str | uuid.UUID]) -> Optional[uuid.UUID]:
    if not user_id:
        return None
    if isinstance(user_id, uuid.UUID):
        return user_id
    try:
        return uuid.UUID(str(user_id))
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(user_id))
