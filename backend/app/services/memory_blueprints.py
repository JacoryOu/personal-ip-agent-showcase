"""Persistence / CRUD for stored benchmark blueprints."""

from typing import Any, Dict, List, Optional
import uuid

from sqlmodel import Session

from app.core.db import engine
from app.models.user import User
from app.services.cognitive_service import CognitiveService
from app.services.memory_common import _parse_user_id

def get_benchmark_blueprints(
    cls,
    user_id: Optional[str | uuid.UUID] = None,
    session: Optional[Session] = None,
) -> List[Dict[str, Any]]:
    """Retrieves saved benchmark blueprints for user."""
    def _get_blueprints(sess: Session) -> List[Dict[str, Any]]:
        user = (
            sess.get(User, _parse_user_id(user_id))
            if user_id
            else CognitiveService.get_or_create_default_user(sess)
        )
        if not user:
            return []
        return (user.profile_data or {}).get("benchmark_blueprints", [])

    if session:
        return _get_blueprints(session)
    else:
        with Session(engine) as sess:
            return _get_blueprints(sess)

def delete_benchmark_blueprint(
    cls,
    blueprint_id: str,
    user_id: Optional[str | uuid.UUID] = None,
    session: Optional[Session] = None,
) -> bool:
    """Deletes a benchmark blueprint by ID."""
    def _delete(sess: Session) -> bool:
        parsed_uid = _parse_user_id(user_id)
        user = (
            sess.get(User, parsed_uid)
            if parsed_uid
            else CognitiveService.get_or_create_default_user(sess)
        )
        if not user or not user.profile_data or not any(str(b.get("id")) == str(blueprint_id) for b in user.profile_data.get("benchmark_blueprints", [])):
            user = CognitiveService.get_or_create_default_user(sess)
        if not user or not user.profile_data:
            return False
        data = dict(user.profile_data)
        blueprints = data.get("benchmark_blueprints", [])
        initial_len = len(blueprints)
        blueprints = [b for b in blueprints if str(b.get("id")) != str(blueprint_id)]
        if len(blueprints) == initial_len:
            return False
        data["benchmark_blueprints"] = blueprints
        user.profile_data = data
        sess.add(user)
        sess.commit()
        sess.refresh(user)
        return True

    if session:
        return _delete(session)
    else:
        with Session(engine) as sess:
            return _delete(sess)

def update_benchmark_blueprint(
    cls,
    blueprint_id: str,
    updates: Dict[str, Any],
    user_id: Optional[str | uuid.UUID] = None,
    session: Optional[Session] = None,
) -> Optional[Dict[str, Any]]:
    """Updates an existing benchmark blueprint by ID."""
    def _update(sess: Session) -> Optional[Dict[str, Any]]:
        parsed_uid = _parse_user_id(user_id)
        user = (
            sess.get(User, parsed_uid)
            if parsed_uid
            else CognitiveService.get_or_create_default_user(sess)
        )
        if not user or not user.profile_data or not any(str(b.get("id")) == str(blueprint_id) for b in user.profile_data.get("benchmark_blueprints", [])):
            user = CognitiveService.get_or_create_default_user(sess)
        if not user or not user.profile_data:
            return None
        data = dict(user.profile_data)
        blueprints = list(data.get("benchmark_blueprints", []))
        target_bp = None
        for i, b in enumerate(blueprints):
            if str(b.get("id")) == str(blueprint_id):
                updated = dict(b)
                for k, v in updates.items():
                    if v is not None:
                        updated[k] = v
                blueprints[i] = updated
                target_bp = updated
                break
        if not target_bp:
            return None
        data["benchmark_blueprints"] = blueprints
        user.profile_data = data
        sess.add(user)
        sess.commit()
        sess.refresh(user)
        return target_bp

    if session:
        return _update(session)
    else:
        with Session(engine) as sess:
            return _update(sess)
