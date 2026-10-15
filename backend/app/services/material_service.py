import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlmodel import Session, select

from app.core.db import engine
from app.core.skill_engine import get_skill_manager
from app.models.draft import Draft
from app.models.material import Material
from app.models.user import User
from app.services.cognitive_service import CognitiveService


def _parse_user_id(user_id: Optional[str | uuid.UUID]) -> Optional[uuid.UUID]:
    if not user_id:
        return None
    if isinstance(user_id, uuid.UUID):
        return user_id
    try:
        return uuid.UUID(str(user_id))
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(user_id))


class MaterialService:
    @classmethod
    def ingest_trending_topics(
        cls,
        topics: List[Dict[str, Any]],
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None,
    ) -> List[Material]:
        """Bulk ingests trending radar topics into the user Material Library."""
        if not topics:
            return []

        def _execute(sess: Session) -> List[Material]:
            parsed_uid = _parse_user_id(user_id)
            if parsed_uid:
                user = sess.get(User, parsed_uid)
                if not user:
                    user = User(id=parsed_uid, username=f"user_{str(parsed_uid)[:8]}")
                    sess.add(user)
                    sess.commit()
                    sess.refresh(user)
            else:
                user = CognitiveService.get_or_create_default_user(sess)

            saved_materials = []
            for topic in topics:
                title = topic.get("title", "").strip()
                if not title:
                    continue
                source_url = topic.get("url")
                platform = topic.get("platform")
                category = topic.get("category")
                summary = topic.get("summary")
                hot_value = topic.get("hot_value")
                score = topic.get("score")

                # De-duplicate if same url or title+platform already exists for this user
                existing_query = select(Material).where(
                    Material.user_id == user.id,
                    Material.type == "trend_topic",
                )
                if source_url:
                    existing_query = existing_query.where(Material.source_url == source_url)
                else:
                    existing_query = existing_query.where(Material.title == title, Material.platform == platform)

                existing = sess.exec(existing_query).first()
                if existing:
                    if hot_value is not None:
                        existing.hot_value = int(hot_value)
                    if score is not None:
                        existing.relevance_score = float(score)
                    existing.updated_at = datetime.now(timezone.utc)
                    sess.add(existing)
                    saved_materials.append(existing)
                else:
                    mat = Material(
                        user_id=user.id,
                        type="trend_topic",
                        title=title,
                        summary=summary,
                        content=None,
                        source_url=source_url,
                        platform=platform,
                        category=category,
                        hot_value=int(hot_value) if hot_value is not None else None,
                        relevance_score=float(score) if score is not None else None,
                        tags=[t for t in [category, platform] if t],
                        metadata_={"raw_topic": topic},
                    )
                    sess.add(mat)
                    saved_materials.append(mat)

            sess.commit()
            for m in saved_materials:
                sess.refresh(m)
            return saved_materials

        if session:
            return _execute(session)
        with Session(engine) as s:
            return _execute(s)

    @classmethod
    def collect_and_save_article(
        cls,
        url: Optional[str] = None,
        html_content: Optional[str] = None,
        content: Optional[str] = None,
        title: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Executes content_collector skill, persists clean article + BenchmarkBlueprint
        into the Material Library, and registers the blueprint for creative re-skinning.
        """
        skill_manager = get_skill_manager()
        res = skill_manager.execute_skill_sync(
            "content_collector",
            {
                "url": url,
                "html_content": html_content,
                "content": content,
                "title": title,
            },
        )
        if not res.success or not isinstance(res.output, dict):
            raise RuntimeError(f"Content collection failed: {res.error or res.stderr or 'Unknown error'}")

        collected = res.output
        art_title = collected.get("title") or title or "未命名收集素材"
        cleaned_md = collected.get("cleaned_markdown") or content or ""
        author = collected.get("author")
        publish_time = collected.get("publish_time")
        cover_image_url = collected.get("cover_image_url")
        source_url = collected.get("source_url") or url
        blueprint_data = collected.get("blueprint") or {}

        platform = "web"
        if source_url:
            if "weixin.qq.com" in source_url:
                platform = "wechat"
            elif "zhihu.com" in source_url:
                platform = "zhihu"
            elif "36kr.com" in source_url:
                platform = "36kr"
            elif "bilibili.com" in source_url:
                platform = "bilibili"
            elif "douyin.com" in source_url:
                platform = "douyin"

        def _execute(sess: Session) -> Dict[str, Any]:
            parsed_uid = _parse_user_id(user_id)
            if parsed_uid:
                user = sess.get(User, parsed_uid)
                if not user:
                    user = User(id=parsed_uid, username=f"user_{str(parsed_uid)[:8]}")
                    sess.add(user)
                    sess.commit()
                    sess.refresh(user)
            else:
                user = CognitiveService.get_or_create_default_user(sess)

            existing = None
            if source_url:
                existing = sess.exec(
                    select(Material).where(
                        Material.user_id == user.id,
                        Material.source_url == source_url,
                    )
                ).first()

            tag_list = list(tags or [])
            if category and category not in tag_list:
                tag_list.append(category)
            if platform and platform not in tag_list:
                tag_list.append(platform)

            if existing:
                existing.title = art_title
                existing.content = cleaned_md
                existing.author = author
                existing.publish_time = publish_time
                existing.cover_image_url = cover_image_url
                existing.blueprint = blueprint_data
                existing.tags = list(set(existing.tags + tag_list))
                existing.updated_at = datetime.now(timezone.utc)
                sess.add(existing)
                material_rec = existing
            else:
                material_rec = Material(
                    user_id=user.id,
                    type="benchmark_article",
                    title=art_title,
                    summary=(cleaned_md[:200] + "...") if len(cleaned_md) > 200 else cleaned_md,
                    content=cleaned_md,
                    source_url=source_url,
                    author=author,
                    platform=platform,
                    category=category,
                    cover_image_url=cover_image_url,
                    publish_time=publish_time,
                    blueprint=blueprint_data,
                    tags=tag_list,
                    metadata_={
                        "word_count": collected.get("word_count", len(cleaned_md)),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                sess.add(material_rec)

            sess.commit()
            sess.refresh(material_rec)

            if blueprint_data:
                current_profile = dict(user.profile_data or {})
                blueprints = list(current_profile.get("benchmark_blueprints", []))
                bp_record = {
                    "id": str(material_rec.id),
                    "material_id": str(material_rec.id),
                    "title": art_title,
                    "source_url": source_url,
                    "author": author,
                    "hook_style": blueprint_data.get("hook_style") or blueprint_data.get("opening_hook", "开门见山提出问题或悬念"),
                    "opening_hook": blueprint_data.get("opening_hook") or blueprint_data.get("hook_style", "开门见山提出问题或悬念"),
                    "structural_stages": blueprint_data.get("structural_stages") or blueprint_data.get("key_stages", []),
                    "key_stages": blueprint_data.get("key_stages") or blueprint_data.get("structural_stages", []),
                    "emotional_arc": blueprint_data.get("emotional_arc", "痛点唤醒 ➔ 认知颠覆 ➔ 框架推演 ➔ 价值升华"),
                    "golden_quotes": blueprint_data.get("golden_quotes", []),
                    "pacing": blueprint_data.get("pacing", "前 15% 悬念破题，中段 70% 递进式框架论证，后 15% 认知升华"),
                    "word_count": len(cleaned_md),
                    "created_at": material_rec.created_at.isoformat(),
                }
                blueprints = [bp for bp in blueprints if bp.get("id") != str(material_rec.id)]
                blueprints.insert(0, bp_record)
                current_profile["benchmark_blueprints"] = blueprints[:50]
                user.profile_data = current_profile
                sess.add(user)
                sess.commit()

            return {
                "success": True,
                "material": {
                    "id": str(material_rec.id),
                    "user_id": str(material_rec.user_id),
                    "type": material_rec.type,
                    "title": material_rec.title,
                    "summary": material_rec.summary,
                    "content": material_rec.content,
                    "source_url": material_rec.source_url,
                    "author": material_rec.author,
                    "platform": material_rec.platform,
                    "category": material_rec.category,
                    "cover_image_url": material_rec.cover_image_url,
                    "publish_time": material_rec.publish_time,
                    "blueprint": material_rec.blueprint,
                    "tags": material_rec.tags,
                    "created_at": material_rec.created_at.isoformat(),
                    "updated_at": material_rec.updated_at.isoformat(),
                },
                "blueprint": blueprint_data,
            }

        if session:
            return _execute(session)
        with Session(engine) as s:
            return _execute(s)

    @classmethod
    def list_materials(
        cls,
        user_id: Optional[str | uuid.UUID] = None,
        type: Optional[str] = None,
        category: Optional[str] = None,
        platform: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        session: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """List materials with search, category, and platform filtering."""
        def _execute(sess: Session) -> List[Dict[str, Any]]:
            query = select(Material)
            if user_id:
                parsed_uid = _parse_user_id(user_id)
                if parsed_uid:
                    query = query.where(Material.user_id == parsed_uid)
            if type:
                query = query.where(Material.type == type)
            if category:
                query = query.where(Material.category == category)
            if platform:
                query = query.where(Material.platform == platform)
            if keyword:
                kw = f"%{keyword.strip()}%"
                query = query.where(
                    (Material.title.ilike(kw))
                    | (Material.summary.ilike(kw))
                    | (Material.content.ilike(kw))
                )

            query = query.order_by(Material.created_at.desc()).offset(offset).limit(limit)
            materials = sess.exec(query).all()

            return [
                {
                    "id": str(m.id),
                    "user_id": str(m.user_id),
                    "type": m.type,
                    "title": m.title,
                    "summary": m.summary,
                    "content": m.content,
                    "source_url": m.source_url,
                    "author": m.author,
                    "platform": m.platform,
                    "category": m.category,
                    "hot_value": m.hot_value,
                    "relevance_score": m.relevance_score,
                    "cover_image_url": m.cover_image_url,
                    "publish_time": m.publish_time,
                    "blueprint": m.blueprint,
                    "tags": m.tags or [],
                    "metadata": m.metadata_ or {},
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "updated_at": m.updated_at.isoformat() if m.updated_at else None,
                }
                for m in materials
            ]

        if session:
            return _execute(session)
        with Session(engine) as s:
            return _execute(s)

    @classmethod
    def get_material(
        cls,
        material_id: str | uuid.UUID,
        session: Optional[Session] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve material by ID."""
        def _execute(sess: Session) -> Optional[Dict[str, Any]]:
            m_id = _parse_user_id(material_id)
            if not m_id:
                return None
            m = sess.get(Material, m_id)
            if not m:
                return None
            return {
                "id": str(m.id),
                "user_id": str(m.user_id),
                "type": m.type,
                "title": m.title,
                "summary": m.summary,
                "content": m.content,
                "source_url": m.source_url,
                "author": m.author,
                "platform": m.platform,
                "category": m.category,
                "hot_value": m.hot_value,
                "relevance_score": m.relevance_score,
                "cover_image_url": m.cover_image_url,
                "publish_time": m.publish_time,
                "blueprint": m.blueprint,
                "tags": m.tags or [],
                "metadata": m.metadata_ or {},
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            }

        if session:
            return _execute(session)
        with Session(engine) as s:
            return _execute(s)

    @classmethod
    def get_material_derived_drafts(
        cls,
        material_id: str | uuid.UUID,
        session: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """Find all drafts created with reference to this material (forward lineage)."""
        def _execute(sess: Session) -> List[Dict[str, Any]]:
            m_id = _parse_user_id(material_id)
            if not m_id:
                return []
            material = sess.get(Material, m_id)
            source_url = material.source_url if material else None

            all_drafts = sess.exec(select(Draft)).all()
            matched = []
            seen_ids = set()
            for d in all_drafts:
                if d.id in seen_ids:
                    continue
                is_match = False
                if d.material_id == m_id:
                    is_match = True
                elif d.metadata_ and isinstance(d.metadata_, dict):
                    m_meta = d.metadata_
                    l_src = (m_meta.get("lineage") or {}).get("source_material_id") if isinstance(m_meta.get("lineage"), dict) else None
                    if l_src and str(l_src) == str(m_id):
                        is_match = True
                    elif str(m_meta.get("material_id") or "") == str(m_id):
                        is_match = True

                if is_match:
                    seen_ids.add(d.id)
                    matched.append(d)

            return [
                {
                    "id": str(d.id),
                    "user_id": str(d.user_id),
                    "topic": d.topic,
                    "title": (d.metadata_ or {}).get("title") or d.topic,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                    "word_count": (d.metadata_ or {}).get("word_count") or len((d.user_final_draft or d.original_ai_draft or "").strip()),
                }
                for d in matched
            ]

        if session:
            return _execute(session)
        with Session(engine) as s:
            return _execute(s)

    @classmethod
    def get_draft_lineage(
        cls,
        draft_id: str | uuid.UUID,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Retrieves comprehensive historical reference & provenance lineage for a draft article."""
        def _execute(sess: Session) -> Dict[str, Any]:
            d_id = _parse_user_id(draft_id)
            if not d_id:
                raise ValueError("Invalid draft ID")
            draft = sess.get(Draft, d_id)
            if not draft:
                raise ValueError(f"Draft '{draft_id}' not found")

            # 1. Source Material
            material_info = None
            material = None
            mat_id = draft.material_id
            meta = dict(draft.metadata_ or {})
            existing_lineage = meta.get("lineage") or {}

            if not mat_id:
                raw_mat = meta.get("material_id") or (existing_lineage.get("source_material_id") if isinstance(existing_lineage, dict) else None)
                if raw_mat:
                    mat_id = _parse_user_id(raw_mat)

            if mat_id:
                material = sess.get(Material, mat_id)
                if material:
                    material_info = {
                        "id": str(material.id),
                        "type": material.type,
                        "title": material.title,
                        "source_url": material.source_url,
                        "platform": material.platform,
                        "author": material.author,
                        "category": material.category,
                        "collected_at": material.created_at.isoformat() if material.created_at else None,
                    }

            meta = dict(draft.metadata_ or {})
            existing_lineage = meta.get("lineage") or {}

            # 2. Structural Blueprint
            blueprint_info = (
                meta.get("blueprint")
                or (existing_lineage.get("blueprint") if isinstance(existing_lineage, dict) else None)
            )
            if not blueprint_info and material and material.blueprint:
                blueprint_info = material.blueprint

            # 3. Injected DNA
            injected_dna = meta.get("injected_dna")

            # 4. Timeline
            timeline = []
            if material_info and material_info.get("collected_at"):
                timeline.append({
                    "stage": "material_collected",
                    "timestamp": material_info.get("collected_at"),
                    "details": f"Material collected from {material_info.get('platform') or 'web'}: {material_info.get('title')}",
                })

            if blueprint_info:
                timeline.append({
                    "stage": "blueprint_deconstructed",
                    "timestamp": (material_info.get("collected_at") if material_info else None) or (draft.created_at.isoformat() if draft.created_at else None),
                    "details": f"Deconstructed BenchmarkBlueprint skeleton: {blueprint_info.get('title') or (material_info.get('title') if material_info else 'Benchmark')}",
                })

            timeline.append({
                "stage": "ai_draft_generated",
                "timestamp": draft.created_at.isoformat() if draft.created_at else None,
                "details": f"Generated draft on topic '{draft.topic}' (Word count: {meta.get('word_count') or len(draft.original_ai_draft or '')})",
            })

            if draft.user_final_draft and draft.user_final_draft != draft.original_ai_draft:
                timeline.append({
                    "stage": "user_edited_final",
                    "timestamp": draft.updated_at.isoformat() if draft.updated_at else None,
                    "details": f"User revised final draft (Final word count: {len(draft.user_final_draft.strip())})",
                })

            return {
                "draft_id": str(draft.id),
                "topic": draft.topic,
                "title": meta.get("title") or draft.topic,
                "source_url": draft.source_url or (material_info.get("source_url") if material_info else None),
                "material": material_info,
                "blueprint": blueprint_info,
                "injected_dna": injected_dna,
                "timeline": timeline,
                "created_at": draft.created_at.isoformat() if draft.created_at else None,
                "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
            }

        if session:
            return _execute(session)
        with Session(engine) as s:
            return _execute(s)