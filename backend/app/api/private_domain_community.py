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

@router.post("/generate-community", response_model=GenerateCommunityResponse)
async def generate_community(
    body: GenerateCommunityRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> GenerateCommunityResponse:
    uid = current_user.id
    topic = body.topic.strip() if body.topic and body.topic.strip() else "日常体质健康调养"

    # Ownership is enforced even when the persona does not feed the script
    # body directly, so a cross-user or malformed id can never be accepted.
    _load_owned_persona(session, body.persona_id, uid)
    product: Optional[ProductVault] = _load_owned_product(session, body.product_id, uid)

    script_type = body.script_type or "discussion_starter"

    if script_type == "sale_theater":
        content = (
            f"【社群轻剧场·自用种草】\n\n"
            f"主理人（发真实茶席照片）：姐妹们，今天下午煮了这壶「{product.product_name if product else '新会陈皮老白茶'}」，"
            f"满屋子都是陈香。最近降温，好多朋友说胃口胀、嗓子发紧，这种天气最适合用陈皮理气温中。\n\n"
            f"助教/老客户小A：我也一直在喝这个！上周脾胃不适喝了两天，明显感觉舒服多了。\n\n"
            f"主理人：是的，选对地道原料比什么都强。今天给咱们群里争取了20份自用同款尝鲜装，需要的老友直接在群里扣【老白茶】登记，先到先得~"
        )
        roles = ["社群主理人", "老群友/助教", "潜水咨询读者"]
        timing = "工作日下午 15:00 - 16:30 (下午茶休闲时刻)"
        cta = "群内扣【老白茶】登记领取专属礼盒"
    elif script_type == "qa_spark":
        content = (
            f"【晨间认知破壁·常见误区答疑】\n\n"
            f"关于「{topic}」，最近很多群友私聊问我：为什么天天喝祛湿茶，反而觉得浑身乏力、大便更稀？\n\n"
            f"今天在群里统一解答：很多人盲目喝生薏米和寒凉凉茶，把原本就虚弱的脾阳给伤了！\n"
            f"真正的调养讲究「温阳健脾」，而不是一味清热泄火。\n"
            f"群友们对照一下自己的晨起舌苔：舌边有齿痕吗？有的话在群里回个【1】，稍后我分享三个居家温养小动作。"
        )
        roles = ["专业主理人", "求助学员"]
        timing = "工作日上午 08:30 - 09:30"
        cta = "回复【1】领取居家温养舌象对照指南"
    else:
        content = (
            f"【今日话题·围炉夜话】\n\n"
            f"诸位姐妹们好！今晚想和大家探讨一个很有意思的话题：【{topic}】。\n"
            f"大家在日常生活中，是否也常有那种「明明睡够了8小时，但醒来还是觉得沉重疲乏」的感觉？\n\n"
            f"欢迎大家在群里分享你尝试过最有效的恢复精力方法，今晚点赞最多的分享者将获得我们定制的节气养生手册一份！"
        )
        roles = ["社群掌柜", "全员群友"]
        timing = "晚间 20:00 - 21:30"
        cta = "在群里分享你的自用养生心得参与抽奖"

    return GenerateCommunityResponse(
        content=content,
        script_type=script_type,
        roles=roles,
        recommended_timing=timing,
        call_to_action=cta,
    )


@public_router.get("/templates", response_model=List[TemplateItem])
def list_templates() -> List[TemplateItem]:
    """Returns the 5-dimensional WeChat Moments matrix templates."""
    return [
        TemplateItem(
            category="专业沉淀",
            name="🏛️ 专业沉淀圈",
            description="输出高价值专业认知与体质调养干货，确立专业权威与信任背书",
            example_topic="脾虚湿热与虚寒体质的晨起辨识指南",
            sample_hook="很多人以为是单纯上火，其实关键只在第三点👇",
            recommended_timing="工作日早上 07:30 - 08:30 (晨读黄金期)",
            target_goal="建立专业信任度，吸引同频高认知读者",
        ),
        TemplateItem(
            category="生活切片",
            name="☕ 生活切片圈",
            description="展现真实的烟火气日常与自律内养习惯，拉近读者心理距离",
            example_topic="阴雨天煮一壶老白茶的治愈下午",
            sample_hook="后来我才发现，真正能让人放松下来的细节往往是这个👇",
            recommended_timing="下午 14:30 - 16:00 (茶歇放松期)",
            target_goal="营造有温度、接地气、真实可感的真实人物形象",
        ),
        TemplateItem(
            category="好物自用",
            name="📦 好物自用圈",
            description="以严苛挑剔的真实自用视角分享养生好物，不推销但极具种草力",
            example_topic="翻出喝了三年的陈皮老白茶私藏配方",
            sample_hook="试过市面上不下十款，直到喝到这批才算彻底惊艳👇",
            recommended_timing="中午 12:00 - 13:00 或 晚上 20:30 - 21:30",
            target_goal="高转化自用种草，配合评论区置顶一键截流",
        ),
        TemplateItem(
            category="互动截流",
            name="💬 互动截流圈",
            description="抛出体质痛点与高共鸣话题，引导读者对号入座在评论区扣数字",
            example_topic="经常吃完饭就犯困、大便粘马桶的姐妹有多少？",
            sample_hook="自测身体信号很简单，其实关键只要看这一点👇",
            recommended_timing="晚间 21:00 - 22:30 (睡前刷圈高峰)",
            target_goal="激发评论区高频互动，批量转化为私域1对1咨询",
        ),
        TemplateItem(
            category="岁月反思",
            name="⏳ 岁月反思圈",
            description="对比两三年前的迷茫/踩坑与当下的通透自洽，体现认知演化与生命韧性",
            example_topic="从盲目追求高强度生酮到顺应节气内养",
            sample_hook="以前我也总以为越猛越快，直到身体亮起红灯才彻底醒悟👇",
            recommended_timing="周末深夜 22:00 - 23:30 (深度情绪共鸣期)",
            target_goal="塑造有深度、有历练、有成长弧光的超级IP魅力",
        ),
    ]
