"""Inspection wheel implementations (trending harvest and benchmark sampling)."""

from __future__ import annotations

from typing import Any
from app.models.benchmark_account import BenchmarkAccount
from app.services.cognitive_service import CognitiveService
from typing import Dict
from app.core.skill_engine import ExecutionContext
from app.schemas.platform_schemas import FeedItem
from typing import List
from app.models.material import Material
from typing import Optional
from app.services.platform_crawler_service import PlatformCrawlerService
from app.schemas.scheduler_schemas import SchedulerSettings
from sqlmodel import Session
from datetime import datetime
import logging
from app.core.workflow_permissions import (
    ACTION_SCHEDULER_UNATTENDED,
    WorkflowDenied,
    WorkflowMode,
    require_authorization,
)
from app.services.inspection_quota_service import (
    check_and_consume as quota_check_and_consume,
)
from app.services.inspection_quota_service import (
    record_error as quota_record_error,
)
from sqlmodel import select
from datetime import timezone
import uuid
from app.services.inspection_scheduler_helpers import (
    _facade_engine,
    _facade_skill_manager,
    _parse_uid,
)
import app.services.inspection_scheduler_state as _state

logger = logging.getLogger(__name__)

def run_wheel_1(
    self,
    session: Session,
    user_id: Optional[str | uuid.UUID] = None,
    custom_settings: Optional[SchedulerSettings] = None,
) -> List[Material]:
    """Wheel 1: Trending Radar Automated Harvest.
    Periodically executes trending_radar to harvest trending topics from Weibo, Zhihu, 36Kr, Douyin,
    filters by user IP interest tags, and auto-saves new topics into Material with status='inbox'.
    """
    cfg = custom_settings or _state.get_settings(self, user_id, session=session)
    if not cfg.wheel1_enabled:
        return []

    target_uid = _parse_uid(user_id)
    if not target_uid:
        user = CognitiveService.get_or_create_default_user(session)
        target_uid = user.id

    # 1. Execute trending_radar skill via SkillManager
    skill_mgr = _facade_skill_manager()()
    keywords = cfg.interest_tags or ["AI", "商业", "独立开发", "超级个体", "效率", "技术变现"]
    limit = cfg.max_trending_per_run or 10

    raw_topics: List[Dict[str, Any]] = []

    # Pre-authorization + quota gate. Unattended runs must not prompt, so the
    # persisted grant and remaining budget are the whole decision.
    decision = quota_check_and_consume(session, target_uid, runs=1)
    self._last_quota_decision = decision
    try:
        _state._write_state_field(self, session, target_uid, "quota_decision", decision)
    except Exception:
        logger.exception("Failed to persist quota decision for user=%s", target_uid)
    if not decision["allowed"]:
        logger.warning(
            "Wheel1 external harvest skipped (user=%s reason=%s)",
            target_uid,
            decision["reason"],
        )
        return []

    try:
        require_authorization(
            ACTION_SCHEDULER_UNATTENDED,
            actor_id=str(target_uid),
            mode=WorkflowMode.UNATTENDED,
            detail={
                "skill": "trending-radar",
                "trigger": "inspection_scheduler",
            },
        )
    except WorkflowDenied as exc:
        logger.warning(
            "Wheel1 external harvest denied by workflow policy "
            "(user=%s reason=%s)",
            target_uid,
            exc.reason,
        )
        return []

    try:
        res = skill_mgr.execute_skill_sync(
            "trending-radar",
            {
                "keywords": keywords,
                "limit": limit * 2,
                "platforms": ["weibo", "zhihu", "36kr", "douyin", "bilibili"],
            },
            # A scheduled inspection has nobody to answer an approval prompt,
            # so declare UNATTENDED explicitly instead of relying on the
            # COG_SKILL_EXECUTION_CONTEXT env var. Policy then honours only
            # the pre-authorised unattended scope and denies the rest.
            execution_context=ExecutionContext.UNATTENDED,
        )
        if res.success and res.output:
            if isinstance(res.output, list):
                raw_topics = res.output
            elif isinstance(res.output, dict):
                raw_topics = res.output.get("items", [])
        else:
            logger.warning(
                "trending-radar skill returned failure for user=%s: %s",
                target_uid,
                getattr(res, "error", "unknown"),
            )
    except Exception as exc:
        # Previously this was silently swallowed and replaced with fake data.
        logger.exception("trending-radar skill execution failed for user=%s", target_uid)
        quota_record_error(session, target_uid, f"trending-radar failed: {exc}")
        return []

    if not raw_topics:
        logger.info("trending-radar returned no items for user=%s", target_uid)
        raw_topics = []

    # 2. Filter & Deduplicate & Ingest into Material (status: inbox, material_type: trending)
    saved_materials: List[Material] = []
    now = datetime.now(timezone.utc)

    # Existing titles and urls for de-duplication
    existing_titles = set(
        session.exec(
            select(Material.title).where(
                Material.user_id == target_uid,
                Material.material_type == "trending",
            )
        ).all()
    )
    existing_urls = set(
        session.exec(
            select(Material.source_url).where(
                Material.user_id == target_uid,
                Material.source_url.is_not(None),
            )
        ).all()
    )

    for item in raw_topics:
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        url = item.get("url")
        if title in existing_titles or (url and url in existing_urls):
            continue

        platform = item.get("platform") or "web"
        category = item.get("category") or "全网热点"
        summary = item.get("summary") or title
        hot_value = item.get("hot_value", 0)
        score = item.get("score", 0.0)

        tags = list(set([category, platform, "全网热点"]))
        meta = {
            "hot_value": hot_value,
            "score": score,
            "harvested_by": "wheel1_radar",
            "inspected_at": now.isoformat(),
        }

        mat = Material(
            id=uuid.uuid4(),
            user_id=target_uid,
            material_type="trending",
            source_platform=platform,
            source_url=url,
            source_author=f"{platform.capitalize()}热榜",
            title=title,
            raw_content=summary,
            cleaned_content=summary,
            blueprint_data=None,
            tags=tags,
            status="inbox",
            meta_info=meta,
            created_at=now,
            updated_at=now,
        )
        session.add(mat)
        saved_materials.append(mat)
        existing_titles.add(title)
        if url:
            existing_urls.add(url)

        if len(saved_materials) >= limit:
            break

    if saved_materials:
        session.commit()
        for m in saved_materials:
            session.refresh(m)

    return saved_materials


def run_wheel_2(
    self,
    session: Session,
    user_id: Optional[str | uuid.UUID] = None,
    custom_settings: Optional[SchedulerSettings] = None,
) -> List[Material]:
    """Wheel 2: Monitored Benchmark Accounts Inspection & Silent Deconstruct.
    Periodically inspects active benchmark accounts across WeChat MP, Xiaohongshu, Zhihu,
    identifies viral posts, and automatically extracts structural blueprints into MaterialVault with status='inbox'.
    """
    cfg = custom_settings or _state.get_settings(self, user_id, session=session)
    if not cfg.wheel2_enabled:
        return []

    target_uid = _parse_uid(user_id)
    if not target_uid:
        user = CognitiveService.get_or_create_default_user(session)
        target_uid = user.id

    # 1. Fetch active benchmark accounts
    accounts = session.exec(
        select(BenchmarkAccount).where(
            BenchmarkAccount.user_id == target_uid,
            BenchmarkAccount.status == "active",
        )
    ).all()

    # If user has no monitored accounts yet, seed default high-quality benchmark accounts
    if not accounts:
        default_seeds = [
            ("wechat", "极客商业认知", "mp_geek_biz"),
            ("xhs", "超级个体小叶", "xhs_super_ye"),
            ("zhihu", "架构师思维实验室", "zhihu_arch_lab"),
        ]
        for plat, name, acc_id in default_seeds:
            PlatformCrawlerService.create_benchmark_account(
                platform=plat,
                account_name=name,
                account_id=acc_id,
                user_id=target_uid,
                session=session,
            )
        accounts = session.exec(
            select(BenchmarkAccount).where(
                BenchmarkAccount.user_id == target_uid,
                BenchmarkAccount.status == "active",
            )
        ).all()

    viral_threshold = cfg.viral_threshold_likes or 3000
    max_posts = cfg.max_posts_per_account or 5
    deconstructed_materials: List[Material] = []

    # 2. Inspect each account
    for acc in accounts:
        try:
            feed_data = PlatformCrawlerService.fetch_account_posts(
                account_id=acc.id,
                sort_by="hot",
                limit=max_posts,
                user_id=target_uid,
                session=session,
            )
            items: List[FeedItem] = feed_data.get("items", [])

            # Filter viral posts (high interaction/likes or top hot items not yet ingested)
            viral_candidates = [
                item for item in items
                if not item.is_ingested and (item.likes >= viral_threshold or item.hot_score >= viral_threshold)
            ]

            # Fallback to top hottest uningested post if threshold wasn't met
            if not viral_candidates and items:
                uningested = [it for it in items if not it.is_ingested]
                if uningested:
                    viral_candidates = [uningested[0]]

            if not viral_candidates:
                continue

            # Batch collect and deconstruct into Material with blueprint
            res = PlatformCrawlerService.batch_collect_and_deconstruct(
                items=viral_candidates[:2],
                extract_blueprint=True,
                category="benchmark",
                tags=["自动巡检", "爆款拆骨"],
                user_id=target_uid,
                session=session,
            )

            mat_ids = res.get("material_ids", [])
            for mid_str in mat_ids:
                mid = _parse_uid(mid_str)
                if mid:
                    mat = session.get(Material, mid)
                    if mat:
                        deconstructed_materials.append(mat)
        except Exception:
            continue

    return deconstructed_materials
