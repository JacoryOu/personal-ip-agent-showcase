"""Batch collection and deconstruction pipeline.

Split out of ``platform_crawler_service``; behaviour is unchanged and the
original module re-exposes this method through the ``PlatformCrawlerService``
facade.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlmodel import Session, select

from app.core.db import engine
from app.core.skill_engine import get_skill_manager
from app.models.material import Material
from app.models.user import User
from app.schemas.platform_schemas import FeedItem
from app.services.cognitive_service import CognitiveService
from app.services.platform_crawler_support_service import (
    _parse_uid,
    extract_fallback_blueprint,
)



class PlatformCrawlerCollectMixin:

    @classmethod
    def batch_collect_and_deconstruct(
        cls,
        items: List[FeedItem],
        extract_blueprint: bool = True,
        category: str = "benchmark",
        tags: Optional[List[str]] = None,
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Batch imports selected articles into MaterialVault and performs structural blueprint deconstruction."""
        if not items:
            return {"success": True, "count": 0, "material_ids": [], "materials": []}

        skill_mgr = get_skill_manager()

        def _execute(sess: Session) -> Dict[str, Any]:
            uid = _parse_uid(user_id)
            if not uid:
                user = CognitiveService.get_or_create_default_user(sess)
                uid = user.id
            else:
                user = sess.get(User, uid)
                if not user:
                    user = User(id=uid, username=f"user_{str(uid)[:8]}")
                    sess.add(user)
                    sess.commit()
                    sess.refresh(user)

            saved_materials = []
            material_ids = []

            for item in items:
                title = item.title.strip()
                source_url = item.url
                author = item.author
                platform = item.platform
                content = item.content.strip()
                summary = item.summary or content[:200]
                merged_tags = list(set((item.tags or []) + (tags or []) + [platform, "对标拆解"]))

                # 1. Blueprint Extraction
                blueprint_data = None
                if extract_blueprint:
                    try:
                        # Try sandboxed content_collector skill first
                        skill_res = skill_mgr.execute_skill_sync(
                            "content_collector",
                            {
                                "content": content,
                                "title": title,
                                "url": source_url,
                            },
                        )
                        if skill_res.success and isinstance(skill_res.output, dict):
                            blueprint_data = skill_res.output.get("blueprint")
                    except Exception:
                        pass

                    if not blueprint_data:
                        blueprint_data = extract_fallback_blueprint(title, content)

                # 2. De-duplicate or upsert in Material
                existing = None
                if source_url:
                    existing = sess.exec(
                        select(Material).where(
                            Material.user_id == uid,
                            Material.source_url == source_url,
                        )
                    ).first()
                if not existing:
                    existing = sess.exec(
                        select(Material).where(
                            Material.user_id == uid,
                            Material.title == title,
                            Material.material_type == "benchmark",
                        )
                    ).first()

                meta = {
                    "likes": item.likes,
                    "collects": item.collects,
                    "comments": item.comments,
                    "shares": item.shares,
                    "hot_score": item.hot_score,
                    "publish_time": item.publish_time,
                    "cover_url": item.cover_url,
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                }

                if existing:
                    existing.title = title
                    existing.cleaned_content = content
                    existing.raw_content = content
                    existing.source_author = author
                    existing.source_platform = platform
                    existing.blueprint_data = blueprint_data
                    existing.tags = list(set((existing.tags or []) + merged_tags))
                    existing.meta_info = {**(existing.meta_info or {}), **meta}
                    existing.updated_at = datetime.now(timezone.utc)
                    sess.add(existing)
                    mat_rec = existing
                else:
                    mat_rec = Material(
                        id=uuid.uuid4(),
                        user_id=uid,
                        material_type="benchmark",
                        source_platform=platform,
                        source_url=source_url,
                        source_author=author,
                        title=title,
                        raw_content=content,
                        cleaned_content=content,
                        blueprint_data=blueprint_data,
                        tags=merged_tags,
                        status="inbox",
                        meta_info=meta,
                    )
                    sess.add(mat_rec)

                sess.commit()
                sess.refresh(mat_rec)
                saved_materials.append({
                    "id": str(mat_rec.id),
                    "title": mat_rec.title,
                    "source_platform": mat_rec.source_platform,
                    "source_author": mat_rec.source_author,
                    "source_url": mat_rec.source_url,
                    "blueprint_data": mat_rec.blueprint_data,
                })
                material_ids.append(str(mat_rec.id))

                # 3. Register blueprint in user profile for instant reskinning
                if blueprint_data:
                    current_profile = dict(user.profile_data or {})
                    bps = list(current_profile.get("benchmark_blueprints", []))
                    created_at_str = (
                        mat_rec.created_at.isoformat()
                        if hasattr(mat_rec.created_at, "isoformat")
                        else str(mat_rec.created_at or datetime.now(timezone.utc).isoformat())
                    )
                    bp_record = {
                        "id": str(mat_rec.id),
                        "material_id": str(mat_rec.id),
                        "title": title,
                        "source_url": source_url,
                        "author": author,
                        "platform": platform,
                        "hook_style": blueprint_data.get("hook_style") or blueprint_data.get("opening_hook", "痛点悬念破题"),
                        "opening_hook": blueprint_data.get("opening_hook") or blueprint_data.get("hook_style", "痛点悬念破题"),
                        "structural_stages": blueprint_data.get("structural_stages") or blueprint_data.get("key_stages", []),
                        "key_stages": blueprint_data.get("key_stages") or blueprint_data.get("structural_stages", []),
                        "emotional_arc": blueprint_data.get("emotional_arc", "认知刺痛 ➔ 逻辑反转 ➔ 框架推演 ➔ 价值落地"),
                        "golden_quotes": blueprint_data.get("golden_quotes", []),
                        "pacing": blueprint_data.get("pacing", "前段悬念破题，中段递进论证，尾段升华心法"),
                        "word_count": len(content),
                        "created_at": created_at_str,
                    }
                    bps = [b for b in bps if b.get("id") != str(mat_rec.id)]
                    bps.insert(0, bp_record)
                    current_profile["benchmark_blueprints"] = bps[:50]
                    user.profile_data = current_profile
                    sess.add(user)
                    sess.commit()

            return {
                "success": True,
                "count": len(saved_materials),
                "material_ids": material_ids,
                "materials": saved_materials,
            }

        if session:
            return _execute(session)
        with Session(engine) as s:
            return _execute(s)


