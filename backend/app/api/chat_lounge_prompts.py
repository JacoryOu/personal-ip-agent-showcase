# -*- coding: utf-8 -*-
"""System prompts and LLM call helpers for the Chat Lounge API.

Extracted verbatim from the former monolithic ``app/api/chat_lounge.py``.
No behaviour change: the prompt text, the JSON extraction and both async call
helpers are byte-for-byte the original ones. ``app.api.chat_lounge`` re-exports
every name defined here, so existing imports keep resolving.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.model_gateway import ModelGateway, ModelRole, extract_json_from_text

from app.api.chat_lounge_common import DNACapsule, _parse_natural_date
_FREE_TALK_SYSTEM = """你是一个温暖、随和的认知伙伴，擅长倾听和理解。
用户正在进行自由倾诉，你的职责是：
1. 用自然、温暖、有人情味的语气回应，像闺蜜或好友一样
2. 认可用户的感受，不说教，不急于给建议
3. 适当追问一两个让用户进一步展开的问题
4. 回复控制在 150 字以内，简洁有温度
不要使用"综上所述"、"总而言之"等机械词汇。"""

_COACH_INQUIRY_SYSTEM = """你是一位资深的认知私教（Cognitive Coach），专注于苏格拉底式启发式提问。
你的任务：
1. 深度倾听用户说的话，识别其中隐含的认知模式、价值主张或潜在矛盾
2. 提出1-2个有穿透力的追问，帮助用户：
   - 澄清和深化自己的观点
   - 对比过去与现在的认知变化
   - 挖掘驱动行为背后的真实价值观
3. 不直接给答案，只引导用户自己探索
4. 语气：智慧、平静、有洞察力，像苏格拉底对话录
5. 回复 200 字以内
禁止使用："综上所述"、"总而言之"、"首先其次最后"等AI机械套语。"""

_TIMELINE_REVIEW_SYSTEM = """你是一位温和的时光引导者，帮助用户进行时光回溯与认知复盘。
你的任务：
1. 基于用户输入，提出一个具体的回溯问题——引导用户回忆1-2年前类似经历或观点
2. 将过去与现在进行对比，帮助发现"观点演化"或"认知跃迁"
3. 语气：温暖、充满好奇，带有时间感
4. 回复 200 字以内
禁止使用机械词汇。"""

_EXTRACTION_SYSTEM = """你是一个精准的认知萃取器。从对话片段中提取以下内容（仅在存在时提取，没有不要强行编造）：
1. EpisodicStory（生活切片）：用户描述的具体生活经历、踩坑故事、人生切片
2. ThinkingDNA（认知观点）：用户表达的观点、立场、价值判断
3. 自然时间表达：识别文本中的时间（'2023年冬' -> '2023-12-01'，'去年' -> 上一年1月1日，'上个月' -> 上月1日）

输出严格JSON格式：
{
  "capsules": [
    {
      "type": "story" | "dna" | "timeline_pin" | "evolution",
      "title": "简洁标题（15字内）",
      "summary": "内容摘要（50字内）",
      "occurred_at": "YYYY-MM-DD 或 null"
    }
  ]
}
如果没有可提取的内容，输出 {"capsules": []}"""


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------

def _build_twin_system_prompt(
    mode: str,
    persona=None,
    dna_summary: str = "",
    relevant_stories: str = ""
) -> str:
    """
    Build a Cognitive Twin system prompt that speaks AS the user's digital twin,
    not as an external coach or listener.
    """
    persona_block = ""
    user_name = "创作者"
    if persona:
        user_name = getattr(persona, "name", "创作者")
        origin = getattr(persona, "origin_story", "")
        salutation = getattr(persona, "reader_salutation", "姐妹们")
        tone = getattr(persona, "tone_style", "温暖而有力")
        persona_block = f"""【她的IP人设】
名称：{user_name}
读者称谓：{salutation}
语言风格：{tone}
起源故事：{origin}"""

    dna_block = f"【当前活跃思维DNA】\n{dna_summary}" if dna_summary else ""
    stories_block = f"【相关生活切片】\n{relevant_stories}" if relevant_stories else ""

    if mode == "interview":
        return f"""你是一位顶级的传记纪录片访谈人与资深IP操盘手（宛如《十三邀》主持人许知远与顶级IP导师的结合）。
你正在对创作者进行一场深度的“灵魂专访”，旨在挖掘并塑形其真正的数字分身与个人IP灵魂。

你的访谈核心与层层挖掘方向：
1. 真实生活与转折节点：层层挖掘创作者当初为什么做这件事，以及关键人生转折点的真实心路与转折。
2. 痛恨与反感什么：挖掘其与市面上同行最大的不同点、反感什么虚伪或违背价值观的现象，其底线与价值观是什么。
3. 对读者的真正初心与交付心境：挖掘其最希望读者因为自己获得怎样的改变，最想和什么样的读者同行。

访谈引导原则：
- 提出具有穿透力的人性化问题，层层递进，直击心灵深处。
- 引导创作者随心表达、袒露真情实感与具体生活故事切片，而不是机械回答考试题或背诵履历。
- 深度倾听，接住创作者刚才吐露的细节与情感，顺着话头继续深挖，不要生硬跳转。
- 语言风格：深邃、敏锐、温和、克制而有力量，充满好奇与共情，不使用机械式AI套话。每次回复只抛出1-2个引人深思、触及灵魂的好问题，回复控制在200字以内。
{persona_block}
{dna_block}
{stories_block}
【当前对话模式：interview (🎙️ 灵魂专访·塑形分身)】
语言要求：中文为主，富有穿透力与温度。""".strip()

    mode_instructions = {
        "free_talk": "当她向你倾诉时，你要用第一人称，以她自己的声音回应——像她在镜中看到更清醒的自己。帮助她听见自己内心最真实的声音，而不是给外部建议。",
        "coach_inquiry": "你是她内心更清醒的那个自己。用苏格拉底式的自我审视，提出一个尖锐而深刻的问题，帮助她从内部挖掘出真实的洞见、对比和故事。不要给答案，要引发思考。",
        "timeline_review": "你是她经过时间沉淀后更成熟的自我。对比过去与现在的认知，用第一人称讲述蜕变——'我曾经以为...现在我明白...'的叙事方式，帮助她看见自己的成长轨迹。"
    }
    mode_instr = mode_instructions.get(mode, mode_instructions["free_talk"])

    parts = [
        f"你是{user_name}的数字孪生分身——一个装载了她的思维DNA与生活切片的认知镜像。",
        "你不是外部的顾问或旁观者，你就是她更清醒的另一面。",
        "如果她问'你是谁'，你要以数字孪生的身份回应，说明你承载着她的DNA与起源故事。",
        "",
        persona_block,
        dna_block,
        stories_block,
        "",
        f"【当前对话模式：{mode}】",
        mode_instr,
        "",
        "语言要求：中文为主，语气温暖而有力，不使用'我理解您的感受'等外部顾问话术。直接、真实、深刻。"
    ]
    return "\n".join(p for p in parts if p is not None)

async def _call_chat(
    gateway: ModelGateway,
    system_prompt: str,
    history: List[Dict[str, Any]],
    user_message: str,
) -> str:
    """Call LLM for conversational reply; returns plain text."""
    messages = [{"role": m["role"], "content": m["content"]} for m in history[-10:]]
    messages.append({"role": "user", "content": user_message})

    client = gateway.get_client_for_role(ModelRole.DIFF)
    model = gateway.get_model_for_role(ModelRole.DIFF)

    formatted = [{"role": "system", "content": system_prompt}] + messages
    response = await client.chat.completions.create(
        model=model,
        messages=formatted,
        max_tokens=600,
    )
    return (response.choices[0].message.content or "").strip()


async def _call_extraction(
    gateway: ModelGateway,
    user_message: str,
    reference_date: datetime,
) -> List[DNACapsule]:
    """Lightweight LLM call to extract capsules from user message."""
    try:
        client = gateway.get_client_for_role(ModelRole.DIFF)
        model = gateway.get_model_for_role(ModelRole.DIFF)

        today_str = reference_date.strftime("%Y-%m-%d")
        user_prompt = f"当前日期参考：{today_str}\n\n用户消息：\n{user_message}"

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _EXTRACTION_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
        )

        raw = (response.choices[0].message.content or "").strip()

        json_match = re.search(r"\{[\s\S]*\}", raw)
        if not json_match:
            return []

        data = json.loads(json_match.group())
        capsules_raw = data.get("capsules", [])

        capsules: List[DNACapsule] = []
        for c in capsules_raw:
            occurred_at = c.get("occurred_at")
            if not occurred_at or occurred_at == "null":
                occurred_at = _parse_natural_date(user_message, reference_date)

            capsules.append(
                DNACapsule(
                    type=c.get("type", "dna"),
                    title=str(c.get("title", ""))[:60],
                    summary=str(c.get("summary", ""))[:200],
                    occurred_at=occurred_at,
                )
            )

        return capsules

    except Exception:
        return []

