from app.api.private_domain_common import *  # noqa: F401,F403
from app.api.private_domain_common import (  # noqa: F401
    _load_owned_persona,
    _load_owned_product,
    router,
    public_router,
)
from app.api.private_domain_schemas import *  # noqa: F401,F403
from app.api.private_domain_text import (  # noqa: F401
    calculate_moments_lines,
    clean_mechanical_dates,
    enforce_anti_fold_formatting,
)
from app.api.private_domain_fallback import (  # noqa: F401
    DEFAULT_CATEGORY_DATA,
    _build_rule_based_moment,
)
from app.api.private_domain_fallback import _build_rule_based_moment  # noqa: F401

# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.post("/generate-moment", response_model=GenerateMomentResponse)
async def generate_moment(
    body: GenerateMomentRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> GenerateMomentResponse:
    uid = current_user.id

    # 1. Load active IPPersona (ownership enforced)
    persona: Optional[IPPersona] = _load_owned_persona(session, body.persona_id, uid)

    if not persona:
        persona = session.exec(
            select(IPPersona).where(IPPersona.user_id == uid, IPPersona.is_active == True)
        ).first()

    if not persona:
        persona = PERSONA_PRESETS[0]

    salutation = persona.reader_salutation if persona and persona.reader_salutation else "姐妹们"
    tone_style = persona.tone_style if persona and persona.tone_style else "温暖、专业、接地气"

    # 2. Retrieve Thinking DNA
    dna_context = MemoryService.retrieve_contextual_dna(
        topic=body.raw_experience or body.topic or body.category,
        user_id=uid,
        session=session,
    )
    dna_summary = dna_context.summary if dna_context else "遵循温和调养与生命节律"

    # 3. Load Product Vault item if product_id provided
    product: Optional[ProductVault] = _load_owned_product(session, body.product_id, uid)

    if not product and body.category == "好物自用":
        product = session.exec(
            select(ProductVault).where(ProductVault.user_id == uid, ProductVault.is_active == True)
        ).first()
        if not product and PRODUCT_PRESETS:
            product = PRODUCT_PRESETS[0]

    # 4. Apply time narrative mode
    now = datetime.now(timezone.utc)
    if body.time_narrative_mode == "anniversary":
        ref_date = now - timedelta(days=730)
    elif body.time_narrative_mode == "solar_term":
        ref_date = datetime(now.year, 10, 23, tzinfo=timezone.utc)
    elif body.time_narrative_mode == "fuzzy":
        ref_date = now - timedelta(days=120)
    else:
        ref_date = now

    natural_time = naturalize_time_expression(ref_date, mode=body.time_narrative_mode or "invisible")

    # If product exists and topic is generic, enrich topic with product context
    if product and (not body.topic or body.topic.strip() in ["", "好物自用", "自用好物", "日常温和调养", "内养之道"]):
        topic = f"我日常自用的「{product.product_name}」真实体验"
    else:
        topic = body.topic.strip() if body.topic and body.topic.strip() else DEFAULT_CATEGORY_DATA.get(body.category, {}).get("topic", "内养之道")

    # 5. Try calling LLM via ModelGateway
    text = ""
    pinned_comment = ""
    visual_card_prompt = ""
    tags: List[str] = []

    length_tier = body.length_tier or "standard"
    tier_instructions = {
        "short": "【篇幅与排版：🍃 精炼短篇 (80-150字，3-5行以内，不折叠)】：全文简短有力，言简意赅，不要在第5行加👇，不要强制写满6行，确保在微信朋友圈直接完整展示无需点开全文。",
        "standard": "【篇幅与排版：🎯 经典折叠篇 (200-350字，6-9行)】：第5行必须以👇结尾制造强悬念钩子，第6行及以后展开关键干货，必须触发朋友圈折叠。",
        "deep": "【篇幅与排版：📜 深度长文/微散文 (400-600字，10-15行)】：深度叙事表达，逻辑层层递进，第5行保留👇悬念钩子，后面充分展开具体论证、心路历程与细节心法。",
    }
    tier_desc = tier_instructions.get(length_tier, tier_instructions["standard"])

    trigger_labels = {
        "study_insight": "🌿 中医/专业学习心得与顿悟",
        "reading_notes": "📖 读书/古籍金句深度笔记",
        "case_experience": "👥 身边人/学员案例与踩坑经历",
        "daily_thought": "☕ 日常随想与生活切片",
    }
    trigger_label = trigger_labels.get(body.trigger_type or "daily_thought", "生活切片与思考")

    try:
        gateway = get_model_gateway()
        client = gateway.get_client_for_role(ModelRole.DRAFT)
        model = gateway.get_model_for_role(ModelRole.DRAFT)

        product_prompt_section = ""
        if product:
            product_prompt_section = f"""
【核心绑定交付好物 (必须自然融入文案与评论，严禁遗漏)】：
- 推荐品名：{product.product_name} (品类：{product.category})
- 核心成分/亮点：{product.core_ingredients}
- 适合体质/人群：{product.suitable_conditions}
- 禁忌与劝退人群（体现真诚与信任）：{product.taboos}
- 第一人称真实自用体验：{product.personal_usage_experience}
- 转化引流钩子：{product.conversion_hooks}

【好物融入执行标准】：
1. 必须在正文展开部分，明确自然地带出该好物「{product.product_name}」，以“我一直在喝/在用”的第一人称生活化口吻，讲述其成分和带给你的真实体感，拒绝干瘪叫卖！
2. 必须提及适合谁、不建议谁用（如适用{product.suitable_conditions}，而{product.taboos}则劝退不宜多食），树立超高信任度的专业自用人设。
3. 生成的【置顶评论】必须紧扣该好物转化钩子（如：私信或评论区扣数字，送冲泡指南、自调节气配方或好物品鉴装）！
"""

        experience_section = ""
        if body.raw_experience:
            experience_section += f"\n【触发事件/所学内容/案例切片】：\n{body.raw_experience}"
        if body.my_takeaway:
            experience_section += f"\n【创作者真实观点/感悟态度】：\n{body.my_takeaway}"

        system_prompt = f"""你是一名资深私域朋友圈内容主理人。
人设调性：{persona.name}（称谓：{salutation}，风格：{tone_style}）
认知底色：{dna_summary}
触发源类型：{trigger_label}
{product_prompt_section}
要求：
1. 编写一条适合微信朋友圈的文案，五维分类：【{body.category}】，话题：【{topic}】。
2. {tier_desc}
3. 朋友圈结构规范：
   - 第一行使用称谓【{salutation}】温馨开场
   - 时间修辞：{'禁止出现具体年月日机械日期，使用自然口语：' + natural_time if natural_time else '抹去一切生硬日期'}
   - 如有【触发事件/所学内容】，开篇先陈述该具体事件、读书段落或中医知识点；再自然升华至【创作者真实观点/感悟态度】。
   - 真实有烟火气，有态度有体温，严禁'综上所述'、'总而言之'等AI腔调。
4. 同时生成一条作者置顶的截流评论话术（引导私信或评论区扣数字领专属资料/配方/福利）。
5. 生成1:1方图的设计Prompt与3-4个标签。

输出格式（纯文本，按标记分割）：
---TEXT---
(朋友圈正文)
---PINNED---
(置顶评论话术)
---VISUAL---
(1:1方图提示词)
---TAGS---
(逗号分隔标签)"""

        user_content = f"话题：{topic}\n分类：{body.category}\n触发源类型：{trigger_label}{experience_section}"
        if product:
            user_content += f"\n绑定产品档案：【{product.product_name}】\n成分与亮点：{product.core_ingredients}\n自用感受：{product.personal_usage_experience}\n适用人群：{product.suitable_conditions}\n禁忌人群：{product.taboos}\n转化引子：{product.conversion_hooks}"

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_tokens=1000,
        )
        content = (response.choices[0].message.content or "").strip()

        if "---TEXT---" in content:
            parts = content.split("---TEXT---")[1]
            t_part, rest = parts.split("---PINNED---", 1) if "---PINNED---" in parts else (parts, "")
            text = t_part.strip()
            if "---VISUAL---" in rest:
                p_part, rest2 = rest.split("---VISUAL---", 1)
                pinned_comment = p_part.strip()
                if "---TAGS---" in rest2:
                    v_part, tag_part = rest2.split("---TAGS---", 1)
                    visual_card_prompt = v_part.strip()
                    tags = [t.strip() for t in tag_part.replace("#", "").split(",") if t.strip()]
                else:
                    visual_card_prompt = rest2.strip()
            else:
                pinned_comment = rest.strip()
    except Exception:
        # Fallback to high quality rule-based generator
        pass

    if not text:
        text, pinned_comment, visual_card_prompt, tags = _build_rule_based_moment(
            category=body.category,
            topic=topic,
            salutation=salutation,
            natural_time=natural_time,
            product=product,
            persona=persona,
            dna_summary=dna_summary,
            trigger_type=body.trigger_type,
            raw_experience=body.raw_experience,
            my_takeaway=body.my_takeaway,
            length_tier=length_tier,
        )

    defaults = DEFAULT_CATEGORY_DATA.get(body.category, DEFAULT_CATEGORY_DATA["专业沉淀"])
    if not tags:
        tags = list(defaults["tags"])
    if not pinned_comment:
        pinned_comment = defaults["pin"]
    if not visual_card_prompt:
        visual_card_prompt = defaults["prompt"]

    # Enforce Anti-Fold formatting:
    # 1. reader_salutation in opening
    # 2. Line 5 curiosity cliffhanger hook (for standard/deep)
    # 3. Mechanical dates stripped/replaced
    # 4. Short length preservation
    text = enforce_anti_fold_formatting(
        text=text,
        salutation=salutation,
        category=body.category,
        natural_time=natural_time,
        length_tier=length_tier,
    )

    # Calculate lines & anti-fold metrics
    total_lines, will_fold, fold_preview = calculate_moments_lines(text)
    char_count = len(text.replace("\n", "").replace(" ", "").replace("\r", ""))

    return GenerateMomentResponse(
        text=text,
        estimated_lines=total_lines,
        will_fold=will_fold,
        fold_preview=fold_preview,
        pinned_comment=pinned_comment,
        visual_card_prompt=visual_card_prompt,
        tags=tags,
        character_count=char_count,
    )


