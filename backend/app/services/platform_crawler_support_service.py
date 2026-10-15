"""Shared helpers for the platform crawler service split modules.

Holds the module-level helpers that were historically defined in
``platform_crawler_service`` so that both the facade and the split mixin
modules can import them without a circular import. Behaviour is unchanged.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional


def _parse_uid(uid_raw: Optional[str | uuid.UUID]) -> Optional[uuid.UUID]:
    if not uid_raw:
        return None
    if isinstance(uid_raw, uuid.UUID):
        return uid_raw
    try:
        return uuid.UUID(str(uid_raw))
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(uid_raw))


def extract_fallback_blueprint(title: str, content: str) -> Dict[str, Any]:
    """Deterministic structural blueprint extractor when skill engine sandbox is bypassed or fallback is needed."""
    paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
    first_para = paragraphs[0] if paragraphs else "开门见山提出问题与痛点"
    
    # Identify headings
    headings = [p.lstrip("#").strip() for p in paragraphs if p.startswith("#")]
    if not headings:
        # Segment into 3 parts
        if len(paragraphs) >= 3:
            headings = [
                paragraphs[0][:20] + "...",
                paragraphs[len(paragraphs) // 2][:20] + "...",
                paragraphs[-1][:20] + "...",
            ]
        else:
            headings = ["核心痛点破题", "底层逻辑拆解", "行动跃迁建议"]

    # Extract quotes (sentences with punctuation or emphasis)
    quotes = []
    for p in paragraphs:
        if any(kw in p for kw in ["本质上", "真正的壁垒", "核心在于", "必须", "永远不要", "反直觉"]):
            quotes.append(p[:80])
            if len(quotes) >= 3:
                break
    if not quotes and paragraphs:
        quotes = [paragraphs[0][:60]]

    # Detect title formula
    if "为什么" in title or "真相" in title:
        formula = "反直觉颠覆型（打破思维定势）"
    elif "如何" in title or "从零到" in title or "指南" in title:
        formula = "实战方法论型（阶段跃迁解法）"
    elif "深度" in title or "复盘" in title:
        formula = "实盘硬核复盘型（内幕经验沉淀）"
    else:
        formula = "痛点唤醒与认知重构型"

    return {
        "title_formula": formula,
        "opening_hook": first_para[:120],
        "hook_style": first_para[:100],
        "key_stages": headings[:6],
        "structural_stages": headings[:6],
        "emotional_arc": "认知刺痛 ➔ 逻辑反转 ➔ 框架推演 ➔ 价值落地",
        "golden_quotes": quotes,
        "pacing": "前 15% 建立高感知悬念，中段 70% 递进展开认知框架与实操避坑，后 15% 升华行动心法",
    }



