from app.api.materials_common import *  # noqa: F401,F403
from app.api.materials_common import (  # noqa: F401
    MATERIAL_NOT_FOUND_MESSAGE,
    _get_owned_material,
    _parse_uid,
    _serialize_material,
    get_current_user,
    get_session,
    get_skill_manager,
    logger,
)

@router.post("/collect-url", response_model=Dict[str, Any])
async def collect_url(
    payload: CollectUrlRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    skill_manager: SkillManager = Depends(get_skill_manager),
) -> Dict[str, Any]:
    """Executes the content-collector skill via WindowsSandboxRunner to extract content
    and structural blueprint from any web URL, saving it into the Material Vault as a benchmark.
    """
    url_target = payload.url.strip()
    if not url_target:
        raise AppError(VALIDATION_ERROR, "URL parameter cannot be empty.")

    # Execute sandboxed skill
    result = skill_manager.execute_skill_sync(
        "content-collector",
        {
            "url": url_target,
            "extract_blueprint": payload.extract_blueprint,
        },
    )

    if not result.success or not isinstance(result.output, dict):
        logger.error(
            "content-collector failed: mode=%s error=%s",
            getattr(result, "runner_mode", None),
            result.error,
        )
        raise AppError(DEPENDENCY_FAILURE, "Content collection failed.")

    output = result.output
    if not output.get("success", False):
        raise AppError(DEPENDENCY_FAILURE, "Unable to extract content from the target URL.")

    if payload.user_id:
        logger.debug("Ignoring client-supplied user_id on collect-url.")
    target_uid = current_user.id

    final_title = payload.title or output.get("title") or "采集素材"
    merged_tags = list(set((output.get("tags") or []) + (payload.tags or [])))
    cleaned_content = output.get("cleaned_content") or ""
    blueprint_data = output.get("blueprint_data")

    if payload.save:
        material = Material(
            id=uuid.uuid4(),
            user_id=target_uid,
            material_type="benchmark",
            source_platform=output.get("source_platform", "web"),
            source_url=url_target,
            source_author=output.get("source_author") or "网络创作者",
            title=final_title,
            raw_content=output.get("raw_content"),
            cleaned_content=cleaned_content,
            blueprint_data=blueprint_data,
            tags=merged_tags,
            status="inbox",
            meta_info={
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "word_count": len(cleaned_content),
                "extractor": "content-collector",
            },
        )
        session.add(material)
        session.commit()
        session.refresh(material)
        return {
            "success": True,
            "material": _serialize_material(material),
            "blueprint": blueprint_data,
        }

    return {
        "success": True,
        "preview": {
            "title": final_title,
            "cleaned_content": cleaned_content,
            "source_platform": output.get("source_platform"),
            "source_author": output.get("source_author"),
            "source_url": url_target,
            "blueprint_data": blueprint_data,
            "tags": merged_tags,
        },
    }


@router.post("/fetch-trending", response_model=Dict[str, Any])
async def fetch_trending(
    payload: FetchTrendingRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    skill_manager: SkillManager = Depends(get_skill_manager),
) -> Dict[str, Any]:
    """Executes the trending-radar skill to fetch real-time viral topics and batch save to vault."""
    result = skill_manager.execute_skill_sync(
        "trending-radar",
        {
            "platform": payload.platform or "all",
            "limit": payload.limit,
        },
    )

    if not result.success:
        logger.error(
            "trending-radar failed: mode=%s error=%s",
            getattr(result, "runner_mode", None),
            result.error,
        )
        raise AppError(DEPENDENCY_FAILURE, "Trending radar execution failed.")

    # Normalize output: trending_radar outputs either a list of topics or a dict with "items"
    if isinstance(result.output, list):
        raw_items = result.output
    elif isinstance(result.output, dict):
        raw_items = result.output.get("items", [])
    else:
        logger.error("trending-radar returned unexpected output type: %s", type(result.output).__name__)
        raise AppError(INTERNAL_ERROR, "Trending radar returned an unexpected result.")

    if payload.user_id:
        logger.debug("Ignoring client-supplied user_id on fetch-trending.")
    target_uid = current_user.id

    saved_items: List[Dict[str, Any]] = []

    if payload.batch_save:
        for item in raw_items:
            t = item.get("title", "").strip()
            if not t:
                continue
            p = item.get("platform") or item.get("source_platform") or "web"
            url = item.get("url") or item.get("source_url")
            summary = item.get("summary") or item.get("cleaned_content") or item.get("raw_content") or t
            author = item.get("author") or item.get("source_author") or f"{p.capitalize()}热榜"
            category = item.get("category")
            tags = list(item.get("tags") or [])
            if "全网热点" not in tags:
                tags.append("全网热点")
            if category and category not in tags:
                tags.append(category)

            meta = dict(item.get("meta_info") or {})
            if "hot_value" in item and "hot_score" not in meta:
                meta["hot_score"] = item["hot_value"]
                meta["hot_value"] = item["hot_value"]
            if "score" in item:
                meta["score"] = item["score"]

            # De-duplicate: check if already exists
            existing = session.exec(
                select(Material).where(
                    Material.user_id == target_uid,
                    Material.title == t,
                    Material.material_type == "trending",
                )
            ).first()

            if existing:
                saved_items.append(_serialize_material(existing))
                continue

            mat = Material(
                id=uuid.uuid4(),
                user_id=target_uid,
                material_type="trending",
                source_platform=p,
                source_url=url,
                source_author=author,
                title=t,
                raw_content=summary,
                cleaned_content=summary,
                tags=tags,
                status="inbox",
                meta_info=meta,
            )
            session.add(mat)
            session.commit()
            session.refresh(mat)
            saved_items.append(_serialize_material(mat))

        return {
            "success": True,
            "platform": payload.platform or "all",
            "count": len(saved_items),
            "items": saved_items,
        }

    return {
        "success": True,
        "platform": payload.platform or "all",
        "count": len(raw_items),
        "items": raw_items,
    }


