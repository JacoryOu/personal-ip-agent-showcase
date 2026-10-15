from app.api.private_domain_common import *  # noqa: F401,F403
from app.api.private_domain_common import router, public_router  # noqa: F401
from app.api.private_domain_schemas import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# Fallback / Deterministic Generation Logic
# ---------------------------------------------------------------------------

DEFAULT_CATEGORY_DATA = {
    "专业沉淀": {
        "topic": "脾虚湿阻体质调养底层逻辑",
        "hook": "很多人以为喝红豆薏米水就够了，其实关键只在第三点👇",
        "pin": "【自测指南】常年舌苔厚白、齿痕明显的姐妹，私信扣【1】领《节气脾胃自测排湿对照表》，今天先发前30位姐妹🌿",
        "prompt": "1:1 方形极简中式调养方卡，米白亚麻质感，优雅宋体排版，核心观点与体质辨识图谱",
        "tags": ["#中医食疗", "#脾胃调养", "#内养日常", "#女性健康"],
    },
    "生活切片": {
        "topic": "慢煮一壶老白茶的松弛感时刻",
        "hook": "后来我才发现，真正能让你戒掉内耗的其实只是一件小事👇",
        "pin": "【生活碎念】评论区聊聊你们最近最放松的瞬间，抽3位同频姐妹送我自存的私房老白茶小样品鉴装🍵",
        "prompt": "1:1 方形暖调生活切片方图，柔和自然光，茶席与温润茶汤，极简治愈美学排版",
        "tags": ["#慢生活", "#老白茶", "#治愈日常", "#生活美学"],
    },
    "好物自用": {
        "topic": "自喝三年的五年陈皮老白茶实测",
        "hook": "试过市面上不下十款，直到喝到它才算彻底对味👇",
        "pin": "【自用置顶】问陈皮产地和煮泡配比的姐妹太多了，我整理了一份《四季陈皮老白茶冲泡配方》，私信发我【1】免费发你，仅发前20位姐妹~",
        "prompt": "1:1 方形典雅好物方图，米白背景，老树白茶与陈皮原料细节微距，匠心品质卡片",
        "tags": ["#好物分享", "#新会陈皮", "#自用推荐", "#老白茶调养"],
    },
    "互动截流": {
        "topic": "饭后总犯困是气血不足还是湿气重？",
        "hook": "想知道自己属于哪种，其实对照镜子看这一个信号就全懂了👇",
        "pin": "【读者互动】有以上情况的姐妹在评论区扣【2】，我一一帮大家看看舌象和体质归属，给对症调理建议🌿",
        "prompt": "1:1 方形痛点问答方图，醒目优雅标题，体质信号对照清单，清晰易读排版",
        "tags": ["#体质自测", "#女性气血", "#健康打卡", "#互动探讨"],
    },
    "岁月反思": {
        "topic": "从盲目追求高强度生酮到顺应节气内养",
        "hook": "以前我也总以为越猛越快，直到身体亮起红灯才彻底醒悟👇",
        "pin": "【岁月复盘】走过弯路才懂得倾听身体的声音。私信扣【1】领取我的《温和内养三年避坑笔记》，与你同行。",
        "prompt": "1:1 方形岁月长河反思方图，墨色与米白对比，时间印章，深刻金句卡片",
        "tags": ["#认知迭代", "#身体觉醒", "#岁月沉淀", "#女性成长"],
    },
}


def _build_rule_based_moment(
    category: MomentCategory,
    topic: str,
    salutation: str,
    natural_time: str,
    product: Optional[ProductVault],
    persona: Optional[IPPersona],
    dna_summary: str,
    trigger_type: Optional[TriggerType] = "daily_thought",
    raw_experience: Optional[str] = None,
    my_takeaway: Optional[str] = None,
    length_tier: Optional[LengthTier] = "standard",
) -> Tuple[str, str, str, List[str]]:
    defaults = DEFAULT_CATEGORY_DATA.get(category, DEFAULT_CATEGORY_DATA["专业沉淀"])
    hook_line = defaults["hook"]
    pin = defaults["pin"]
    visual_prompt = defaults["prompt"]
    tags = list(defaults["tags"])

    # Incorporate trigger intro
    time_prefix = f"{natural_time}，" if natural_time else ""
    core_subject = raw_experience.strip() if raw_experience and raw_experience.strip() else topic

    if trigger_type == "study_insight":
        opening = f"{salutation}，{time_prefix}今天温习医案与经典，关于「{core_subject}」有了很深的触动。"
        tags = ["#中医心得", "#辨证思考", "#医案体悟"] + tags[:1]
    elif trigger_type == "reading_notes":
        opening = f"{salutation}，{time_prefix}翻到书中关于「{core_subject}」的一段论述，瞬间击中了我。"
        tags = ["#读书笔记", "#古籍金句", "#思维顿悟"] + tags[:1]
    elif trigger_type == "case_experience":
        opening = f"{salutation}，{time_prefix}最近一位学员朋友聊到「{core_subject}」，特别有代表性。"
        tags = ["#真实案例", "#调养经验", "#避坑指南"] + tags[:1]
    else:
        opening = f"{salutation}，{time_prefix}今天聊聊「{core_subject}」。"

    takeaway_text = my_takeaway.strip() if my_takeaway and my_takeaway.strip() else "调养从来不是一场冲刺，而是一场水滴石穿的生活修养。"

    # Short Tier (80-150 chars, 3-4 lines, no fold)
    if length_tier == "short":
        lines = [
            opening,
            f"在这个快节奏的时代里，我的切身体悟是：{takeaway_text}",
        ]
        if product and product.product_name:
            lines.append(f"平时常喝的「{product.product_name}」，入口温润，特别适合调养身心。放慢步子，让气血和心神真正归位🌿")
            pin = f"【好物置顶】私信发我【1】领取自用「{product.product_name}」冲泡心得，仅发前20位姐妹~"
        else:
            lines.append("把步子放慢一点，顺应天时，让气血和心神自然归位。")
        text = "\n".join(lines)
        return text, pin, visual_prompt, tags

    # Standard & Deep Tiers
    lines = [
        opening,
        "在这个快节奏的时代里，我们总习惯了催促自己走得更快、更猛。",
        "但身体的信号往往很诚实，每一次疲惫与不适，都是它在向我们发出温柔的提醒。",
        "很多人在调养和认知路上反复踩坑，甚至越用力越觉得心力交瘁。",
        hook_line,
    ]

    if product and product.product_name:
        lines.append(f"其实核心在于原材的性味配伍与真实体质适配。就拿我平时自用的「{product.product_name}」来说：")
        lines.append(f"核心选用{product.core_ingredients or '地道食材'}，温和润燥，专针对{product.suitable_conditions or '体虚湿滞'}。")
        if product.taboos:
            lines.append(f"不过要特别劝退一句：{product.taboos}，调养一定要遵循身体底色，不盲跟风。")
        lines.append(f"我的真实自用体会：{product.personal_usage_experience or '入口温润甘甜，调理一段时间后整个人神清气爽。'}")
        if product.conversion_hooks:
            pin = f"【自用好物置顶】总有姐妹问我同款「{product.product_name}」怎么喝：{product.conversion_hooks}。评论区或私信扣【1】免费发你一份冲泡指南🌿"
        else:
            pin = f"【自用好物置顶】私信发我【1】领取自用「{product.product_name}」调理心得与配方明细，仅发前20位有缘姐妹~"
    else:
        lines.append(f"第一是顺应天时与身体节律；第二是重视：{takeaway_text}。")
        lines.append("第三也是最关键的：倾听自己的身体反应，不盲从任何绝对化的调理教条。")
        lines.append("调养从来不是一场冲刺，而是一场水滴石穿的生活修养。")

    if length_tier == "deep":
        lines.append("很多人问我坚持的动力是什么，其实根本谈不上坚持，当你真正体会到身心通透带来的充实感，健康就变成了一种水到渠成的生活本能。")
        lines.append("认知是一步步走出来的，体质是一天一天养出来的。")

    lines.append("把步子放慢一点，让气血和心神真正归位。")

    text = "\n".join(lines)
    return text, pin, visual_prompt, tags


