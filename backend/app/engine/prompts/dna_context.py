"""Helper utility to format ThinkingDNA, IP Persona, Episodic Stories, and Product Vault
into structured prompt context for agent generation (四位一体深度锁合).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from app.schemas.diff_schemas import ThinkingDNA


def _extract_val(obj: Any, key: str, default: str = "") -> str:
    if obj is None:
        return default
    if isinstance(obj, dict):
        val = obj.get(key)
    else:
        val = getattr(obj, key, None)
    if val is None:
        return default
    s = str(val).strip()
    return s if s else default


def format_full_ip_context_prompt(
    thinking_dna: Optional[ThinkingDNA] = None,
    persona: Optional[Any] = None,
    stories: Optional[List[Any]] = None,
    product: Optional[Any] = None,
    dna_evolution_notes: Optional[List[str]] = None,
    time_narrative_mode: str = "fuzzy",
) -> str:
    """
    Assembles a comprehensive, four-in-one IP context prompt block:
    1. === 👤 创作者 IP 人设与灵魂定位 (IP PERSONA) ===
    2. === 🧠 认知底色与演进树 (THINKING DNA 2.0) ===
    3. === 📖 真实个人经历与案例背书 (EPISODIC STORIES) ===
    4. === 📦 交付方案与产品心智 (PRODUCT VAULT) ===
    """
    from app.services.memory_service import naturalize_time_expression

    sections: List[str] = []

    # 1. IP Persona
    if persona:
        p_name = _extract_val(persona, "name")
        p_aud = _extract_val(persona, "target_audience")
        p_tone = _extract_val(persona, "tone_style")
        p_salut = _extract_val(persona, "reader_salutation")
        p_origin = _extract_val(persona, "origin_story")

        persona_lines = [
            "=== 👤 创作者 IP 人设与灵魂定位 (IP PERSONA) ===",
            "你必须以该创作者的真实人设立场与口吻进行创作，保持人设的一致性与辨识度：",
        ]
        if p_name:
            persona_lines.append(f"- 创作者定位 / IP 名称: {p_name}")
        if p_aud:
            persona_lines.append(f"- 目标受众群体: {p_aud}")
        if p_tone:
            persona_lines.append(f"- 语言风格与调性: {p_tone}")
        if p_salut:
            persona_lines.append(f"- 读者核心称谓: {p_salut}（请在文章开篇引入或行文互动中自然使用此称谓，拉近与读者的心理距离）")
        if p_origin:
            persona_lines.append(f"- 立身起点 / 原点故事: {p_origin}")
        persona_lines.append(
            "【人设执行指令】严禁以第三方旁观者或生硬AI助手口吻写作，全程代入上述创作者灵魂与语调，传递真实人情味与立身信仰。"
        )
        sections.append("\n".join(persona_lines))

    # 2. Thinking DNA 2.0
    dna_subsections: List[str] = []
    if thinking_dna:
        if thinking_dna.vocabulary_habits:
            vocab_items = [f"「{v.strip()}」" for v in thinking_dna.vocabulary_habits if v.strip()]
            if vocab_items:
                dna_subsections.append(
                    "- Characteristic Phrasing & Preferred Lexicon (Actively weave these terms into output):\n  "
                    + ", ".join(vocab_items[:12])
                )
        if thinking_dna.logic_preferences:
            logic_items = [l.strip() for l in thinking_dna.logic_preferences if l.strip()]
            if logic_items:
                dna_subsections.append(
                    "- Logic Flow & Reasoning Preferences (Structure arguments following these patterns):\n  "
                    + "\n  ".join([f"• {item}" for item in logic_items[:6]])
                )
        if thinking_dna.core_values:
            value_items = [c.strip() for c in thinking_dna.core_values if c.strip()]
            if value_items:
                dna_subsections.append(
                    "- Core Values & Contrarian Stances (Uncompromising worldviews & positions to uphold):\n  "
                    + "\n  ".join([f"★ {val}" for val in value_items[:8]])
                )
        if thinking_dna.summary:
            dna_subsections.append(
                f"- Holistic Cognitive Persona Summary:\n  {thinking_dna.summary.strip()}"
            )

    if dna_evolution_notes:
        notes_cleaned = [n.strip() for n in dna_evolution_notes if n.strip()]
        if notes_cleaned:
            dna_subsections.append(
                "- Cognitive Evolution Notes & Active Versions (认知演进历程与活跃版本):\n  "
                + "\n  ".join([f"🔄 {item}" for item in notes_cleaned[:5]])
            )

    if dna_subsections:
        dna_block = (
            "=== 🧠 认知底色与演进树 (THINKING DNA 2.0) ===\n"
            "=== USER'S COGNITIVE PROFILE & THINKING DNA (CRITICAL HARNESS INJECTION) ===\n"
            "The following thinking DNA has been extracted from the user's authentic writing history.\n"
            "You MUST deeply integrate and reflect these specific linguistic choices, logical structures, and stance principles into the generated result:\n"
            + "\n\n".join(dna_subsections)
        )
        sections.append(dna_block)

    # 3. Episodic Stories
    if stories:
        story_lines = [
            "=== 📖 真实个人经历与案例背书 (EPISODIC STORIES) ===",
            "以下是创作者亲历的真实事件与案例切片。在长文论证与叙事过程中，必须以第一人称（「我」）将这些经历自然穿插融入，作为观点的第一手证据与信任背书。",
            "【叙事与时间修辞要求】：必须使用口语化、生活化的自然时间表达（严禁生硬罗列具体年月日或机械数字），保持真实人情味与烟火气：",
        ]
        for idx, story in enumerate(stories, 1):
            s_title = _extract_val(story, "title", "亲历故事")
            s_content = _extract_val(story, "story_content")
            if not s_content:
                continue
            s_type = _extract_val(story, "story_type", "daily_life")
            s_tags_raw = story.get("tags") if isinstance(story, dict) else getattr(story, "tags", None)
            s_tags = [str(t).strip() for t in (s_tags_raw or []) if str(t).strip()]
            s_occurred = story.get("occurred_at") if isinstance(story, dict) else getattr(story, "occurred_at", None)

            if isinstance(s_occurred, str):
                try:
                    s_occurred = datetime.fromisoformat(s_occurred)
                except Exception:
                    s_occurred = None

            if time_narrative_mode == "invisible":
                time_part = ""
            else:
                natural_time = naturalize_time_expression(s_occurred, mode=time_narrative_mode) if s_occurred else "之前有段时间"
                if not natural_time:
                    natural_time = "之前"
                time_part = f"时间修辞：{natural_time} | "

            tags_str = f" [标签：{', '.join(['#' + t for t in s_tags])}]" if s_tags else ""
            story_desc = f"• 【案例切片 {idx}】「{s_title}」（{time_part}类型：{s_type}）{tags_str}:\n  经历详实：{s_content}"
            story_lines.append(story_desc)
        if len(story_lines) > 3:
            sections.append("\n".join(story_lines))

    # 4. Product Vault
    if product:
        p_name = _extract_val(product, "product_name")
        p_cat = _extract_val(product, "category")
        p_ing = _extract_val(product, "core_ingredients")
        p_cond = _extract_val(product, "suitable_conditions")
        p_taboos = _extract_val(product, "taboos")
        p_exp = _extract_val(product, "personal_usage_experience")
        p_hooks = _extract_val(product, "conversion_hooks")

        prod_lines = [
            "=== 📦 交付方案与产品心智 (PRODUCT VAULT) ===",
            "若长文中涉及商业交付、产品推荐、调理/实践方案或结尾行动建议，请自然融入以下专属产品心智。以创作者自身真实自用体验为背书，温和引导转化，严禁生硬突兀的广告推销：",
        ]
        if p_name:
            cat_suffix = f" (品类：{p_cat})" if p_cat else ""
            prod_lines.append(f"- 推荐产品 / 交付方案: {p_name}{cat_suffix}")
        if p_ing:
            prod_lines.append(f"- 核心用料与配方成分: {p_ing}")
        if p_cond:
            prod_lines.append(f"- 适用体质与核心场景: {p_cond}")
        if p_taboos:
            prod_lines.append(f"- 禁忌与适用注意: {p_taboos}")
        if p_exp:
            prod_lines.append(f"- 创作者自用体会与细节体感: {p_exp}")
        if p_hooks:
            prod_lines.append(f"- 转化心智与价值钩子: {p_hooks}")
        prod_lines.append(
            "【交付植入指令】将产品作为水到渠成的解决方案呈现，着重突出自身使用后的真实体感改善，强化真诚度。"
        )
        sections.append("\n".join(prod_lines))

    if not sections:
        return ""

    return (
        "\n\n==================== 🌟 创作者 IP 四位一体深度锁合上下文 (FULL IP CONTEXT) ====================\n"
        + "\n\n".join(sections)
        + "\n==============================================================================================\n"
    )


def format_dna_prompt_section(
    thinking_dna: Optional[ThinkingDNA] = None,
    persona: Optional[Any] = None,
    stories: Optional[List[Any]] = None,
    product: Optional[Any] = None,
    dna_evolution_notes: Optional[List[str]] = None,
    time_narrative_mode: str = "fuzzy",
) -> str:
    """
    Backwards-compatible wrapper that formats Thinking DNA or full IP context.
    """
    return format_full_ip_context_prompt(
        thinking_dna=thinking_dna,
        persona=persona,
        stories=stories,
        product=product,
        dna_evolution_notes=dna_evolution_notes,
        time_narrative_mode=time_narrative_mode,
    )


__all__ = ["format_dna_prompt_section", "format_full_ip_context_prompt"]
