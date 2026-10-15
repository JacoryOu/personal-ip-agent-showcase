"""Daily inspection briefing assembly, vault hand-off and read receipts."""

from __future__ import annotations

from typing import Any
from app.services.cognitive_service import CognitiveService
from typing import Dict
from app.models.material import Material
from typing import Optional
from sqlmodel import Session
from datetime import datetime
import logging
from sqlmodel import select
from datetime import timedelta
from datetime import timezone
import uuid
from app.services.inspection_scheduler_helpers import (
    _facade_engine,
    DEFAULT_SCOPE,
    _parse_uid,
    _serialize_material,
)
import app.services.inspection_scheduler_state as _state
import app.services.inspection_scheduler_wheels as _wheels

logger = logging.getLogger(__name__)

def get_today_briefing(
    self,
    session: Optional[Session] = None,
    user_id: Optional[str | uuid.UUID] = None,
) -> Dict[str, Any]:
    """Aggregates today's briefing containing new trending topics and benchmark viral blueprints."""
    target_uid = _parse_uid(user_id)

    def _execute(sess: Session) -> Dict[str, Any]:
        nonlocal target_uid
        if not target_uid:
            user = CognitiveService.get_or_create_default_user(sess)
            target_uid = user.id

        now = datetime.now(timezone.utc)
        today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        today_str = today_start.strftime("%Y-%m-%d")

        # 1. Query today's inbox trending topics
        trending_q = (
            select(Material)
            .where(
                Material.user_id == target_uid,
                Material.material_type == "trending",
                Material.status == "inbox",
                Material.created_at >= today_start,
            )
            .order_by(Material.created_at.desc())
        )
        trending_materials = sess.exec(trending_q).all()

        # 2. Query today's inbox benchmark blueprints
        benchmark_q = (
            select(Material)
            .where(
                Material.user_id == target_uid,
                Material.material_type == "benchmark",
                Material.status == "inbox",
                Material.created_at >= today_start,
            )
            .order_by(Material.created_at.desc())
        )
        benchmark_materials = sess.exec(benchmark_q).all()

        # If no items collected today yet, also check recent inbox items from past 48h
        # or auto-trigger a quick initial inspection cycle if completely empty
        if not trending_materials and not benchmark_materials:
            recent_cutoff = now - timedelta(days=2)
            trending_materials = sess.exec(
                select(Material)
                .where(
                    Material.user_id == target_uid,
                    Material.material_type == "trending",
                    Material.status == "inbox",
                    Material.created_at >= recent_cutoff,
                )
                .order_by(Material.created_at.desc())
                .limit(10)
            ).all()

            benchmark_materials = sess.exec(
                select(Material)
                .where(
                    Material.user_id == target_uid,
                    Material.material_type == "benchmark",
                    Material.status == "inbox",
                    Material.created_at >= recent_cutoff,
                )
                .order_by(Material.created_at.desc())
                .limit(5)
            ).all()

        # If still completely empty, trigger an initial harvest so user never faces an empty briefing
        if not trending_materials and not benchmark_materials:
            _wheels.run_wheel_1(self, sess, user_id=target_uid)
            _wheels.run_wheel_2(self, sess, user_id=target_uid)
            trending_materials = sess.exec(
                select(Material)
                .where(
                    Material.user_id == target_uid,
                    Material.material_type == "trending",
                    Material.status == "inbox",
                )
                .order_by(Material.created_at.desc())
                .limit(10)
            ).all()
            benchmark_materials = sess.exec(
                select(Material)
                .where(
                    Material.user_id == target_uid,
                    Material.material_type == "benchmark",
                    Material.status == "inbox",
                )
                .order_by(Material.created_at.desc())
                .limit(5)
            ).all()

        total = len(trending_materials) + len(benchmark_materials)
        dismissed = _state._read_dismissed_date(self, sess, target_uid, self._dismissed_date)
        is_unread = total > 0 and dismissed != today_str

        return {
            "date": today_str,
            "generated_at": now.isoformat(),
            "unread": is_unread,
            "total_items": total,
            "trending_count": len(trending_materials),
            "benchmark_count": len(benchmark_materials),
            "trending_topics": [_serialize_material(m) for m in trending_materials],
            "benchmark_blueprints": [_serialize_material(m) for m in benchmark_materials],
        }

    if session:
        return _execute(session)
    with Session(_facade_engine()) as s:
        return _execute(s)


def confirm_briefing_into_vault(
    self,
    session: Optional[Session] = None,
    user_id: Optional[str | uuid.UUID] = None,
) -> Dict[str, Any]:
    """Confirms all today's briefing materials into the vault, stamps them as vault confirmed,
    and marks today's briefing as read.
    """
    target_uid = _parse_uid(user_id)

    def _execute(sess: Session) -> Dict[str, Any]:
        nonlocal target_uid
        if not target_uid:
            user = CognitiveService.get_or_create_default_user(sess)
            target_uid = user.id

        now = datetime.now(timezone.utc)
        today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        today_str = today_start.strftime("%Y-%m-%d")

        # 1. Query today's materials
        mats = sess.exec(
            select(Material).where(
                Material.user_id == target_uid,
                Material.material_type.in_(["trending", "benchmark"]),
                Material.created_at >= today_start,
            )
        ).all()

        # Fallback if no items created today yet (check past 48h)
        if not mats:
            recent_cutoff = now - timedelta(days=2)
            mats = sess.exec(
                select(Material).where(
                    Material.user_id == target_uid,
                    Material.material_type.in_(["trending", "benchmark"]),
                    Material.status == "inbox",
                    Material.created_at >= recent_cutoff,
                )
            ).all()

        for m in mats:
            current_meta = dict(m.meta_info or {})
            current_meta["vault_confirmed"] = True
            current_meta["confirmed_at"] = now.isoformat()
            m.meta_info = current_meta
            sess.add(m)

        sess.commit()
        row = _state._get_or_create_user_state(self, sess, target_uid)
        row.dismissed_date = today_str
        row.updated_at = datetime.now(timezone.utc)
        sess.add(row)
        sess.commit()
        self._dismissed_by_user[str(target_uid)] = today_str

        return {
            "success": True,
            "count": len(mats),
            "message": f"已成功将 {len(mats)} 条巡检素材确认留存在素材库",
            "confirmed_date": today_str,
        }

    if session:
        return _execute(session)
    with Session(_facade_engine()) as s:
        return _execute(s)


def mark_briefing_read(
    self,
    date_str: Optional[str] = None,
    user_id: Optional[str | uuid.UUID] = None,
    session: Optional[Session] = None,
) -> Dict[str, Any]:
    """Marks the briefing for the given date (default today) as read, per user."""
    today_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    uid = _parse_uid(user_id)
    if uid is None:
        scope = DEFAULT_SCOPE
        self._dismissed_by_user[scope] = today_str
        self._dismissed_date = today_str
        return {"success": True, "marked_date": today_str}

    def _execute(sess: Session) -> Dict[str, Any]:
        row = _state._get_or_create_user_state(self, sess, uid)
        row.dismissed_date = today_str
        row.updated_at = datetime.now(timezone.utc)
        sess.add(row)
        sess.commit()
        self._dismissed_by_user[str(uid)] = today_str
        return {"success": True, "marked_date": today_str}

    if session is not None:
        return _execute(session)
    with Session(_facade_engine()) as s:
        return _execute(s)
