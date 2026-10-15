# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import re

from _content import derive_hashtags, extract_key_sentences, parse_content_blocks
from _references import replace_links_with_footnotes

def format_xiaohongshu(title: str, sections: list, golden_sentences: list):
    clean_title = clean_title_text(title)
    short_title = clean_title[:20]
    xhs_title = f'\U0001F525 \u5efa\u8bae\u6536\u85cf\uff01\u3010{short_title}\u3011\u6df1\u5ea6\u5e72\u8d27\u2728'
    
    body_parts = [
        f'\U0001F4CC \u5f88\u591a\u670b\u53cb\u5728\u3010{short_title}\u3011\u4e0a\u8e29\u8fc7\u4e0d\u5c11\u5751\uff0c\u4eca\u5929\u7528\u6700\u901a\u4fd7\u6613\u61c2\u7684\u903b\u8f91\u628a\u6838\u5fc3\u8981\u70b9\u8bb2\u900f\uff0c\u5efa\u8bae\u3010\u8d5e\u85cf\u9632\u8d70\u4e22\u3011\U0001F31F\n'
    ]

    # 智能识别末尾章节是否为“总结/复盘/行动”类章节
    is_last_sec_summary = False
    if len(sections) >= 2:
        last_sec = sections[-1]
        last_sec_title = last_sec.get('title', '')
        if any(k in last_sec_title for k in ['复盘', '总结', '行动', '清单', '结语', '闭环', '建议', '思考']):
            is_last_sec_summary = True

    if is_last_sec_summary:
        content_sections = sections[:-1][:6]
        summary_source = sections[-1]
    else:
        content_sections = sections[:6]
        summary_source = None

    for idx, sec in enumerate(content_sections, 1):
        body_parts.append(f'▪️ 阶段 0{idx}｜{sec["title"]}')
        for p in sec.get('paragraphs', [])[:3]:
            clean_p = p.strip()
            if clean_p:
                short_p = clean_p[:95] + ('...' if len(clean_p) > 95 else '')
                body_parts.append(f'  ▫️ {short_p}')
        body_parts.append('')

    if golden_sentences:
        body_parts.append('💡 破局认知金句：')
        body_parts.append(f'“{golden_sentences[0]}”\n')

    body_parts.append('⚡️ 关键避坑与行动清单：')
    body_parts.append('  ✅ 先破除思维定势，抓住关键认知杠杆')
    body_parts.append('  ✅ 减少低效内耗，建立正向反馈闭环')
    body_parts.append('  ✅ 持续小步快跑，在实战中敏捷迭代\n')

    body_parts.append('💬 你在日常中也遇到过类似瓶颈吗？欢迎在评论区交流探讨～ 记得点赞收藏🌟不迷路！')

    all_content = ' '.join([' '.join(s.get('paragraphs', [])) for s in sections])
    tags = derive_hashtags(clean_title, all_content)
    tags_str = ' '.join(tags)
    full_content = '\n'.join(body_parts) + '\n\n' + tags_str

    # 构造小红书专属视觉与结构化数据
    # 1. 封面数据（高视觉冲击标题、黄金钩子、副标题、标签及 AI 生图提示词）
    cover_card = {
        'card_type': 'cover',
        'index': '01',
        'badge': '🔥 建议收藏',
        'title': short_title,
        'hook': f'很多人在【{short_title}】上反复踩坑内耗，看懂底层逻辑少走半年弯路',
        'subtitle': '底层逻辑与破局指南 · 深度干货',
        'tags': tags[:3],
        'author': '个人认知 IP 引擎',
        'image_prompt': f'Aesthetic vertical 3:4 editorial photo about {short_title}, minimalist composition with ample central negative space for typography overlay, cinematic ambient lighting, hyper-detailed 8k',
        'suggested_prompt': f'高端商业概念摄影，关于【{short_title}】，极简留白构图，深色光影质感，适合大字报排版，8k',
    }

    # 2. 章节要点卡片（02, 03, 04... 结构化痛点剖析与破局论点，保留充实文本）
    body_cards = []
    for idx, sec in enumerate(content_sections, 1):
        raw_pars = [p.strip() for p in sec.get('paragraphs', []) if p.strip()]
        
        # 杜绝痛点与要点内容重复：首段若作为痛点引言，后续段落作为独立破局要点
        if len(raw_pars) >= 2:
            pain = raw_pars[0][:75]
            points = [p[:70] for p in raw_pars[1:4]]
        elif len(raw_pars) == 1:
            pain = ''
            points = [raw_pars[0][:70]]
        else:
            pain = ''
            points = []

        card_idx_str = f'{idx + 1:02d}'
        body_cards.append({
            'card_type': 'point',
            'index': card_idx_str,
            'step_number': f'{idx:02d}',
            'title': sec['title'],
            'key_points': points,
            'pain_point_analysis': pain,
            'highlight': (golden_sentences[idx - 1][:50]) if idx - 1 < len(golden_sentences) else '',
        })

    # 3. 终结复盘与行动清单卡片（金句总结 + 行动 checklist + 互动引导）
    summary_title = '破局认知与行动复盘'
    summary_quote = (golden_sentences[0].strip()[:50]) if (golden_sentences and golden_sentences[0] and golden_sentences[0].strip()) else '看清底层逻辑，执行才不会变形。'
    summary_checklist = [
        '破除思维定势，抓住关键认知杠杆',
        '减少低效内耗，建立正向反馈闭环',
        '持续小步快跑，在实战中敏捷迭代',
    ]

    if summary_source:
        summary_title = summary_source.get('title', summary_title)
        sum_pars = [p.strip() for p in summary_source.get('paragraphs', []) if p.strip()]
        if sum_pars:
            if len(sum_pars) >= 1:
                summary_quote = sum_pars[0][:60]
            if len(sum_pars) >= 2:
                summary_checklist = [p[:40] for p in sum_pars[1:4]]

    summary_card_idx_str = f'{len(body_cards) + 2:02d}'
    summary_card = {
        'card_type': 'summary',
        'index': summary_card_idx_str,
        'badge': f'PAGE {summary_card_idx_str}',
        'title': summary_title,
        'golden_quote': summary_quote,
        'checklist': [item[:40] for item in summary_checklist],
        'interaction_prompt': '你在日常中遇到过类似瓶颈吗？欢迎在评论区交流探讨，点赞收藏不迷路 🌟',
        'cta': '点赞 + 收藏，持续沉淀你的 Thinking DNA 🧠',
    }

    cards = [cover_card] + body_cards + [summary_card]

    return {
        'title': xhs_title,
        'content': full_content,
        'tags': tags,
        'cover': cover_card,
        'body_cards': body_cards,
        'summary_card': summary_card,
        'cards': cards,
    }
def generate_section_illustrations(title: str, sections: list) -> list:
    """
    Generates structured 16:9 commercial concept illustration prompts and metadata for article sections.
    Optimized for Agnes Image 2.5 Flash / Wanx / DALL-E image models.
    """
    clean_title = clean_title_text(title)
    illustrations = []

    for idx, sec in enumerate(sections, 1):
        sec_title = sec.get('title', f'\u5c0f\u8282 0{idx}').strip()
        paras = sec.get('paragraphs', [])
        
        # Select first meaningful text paragraph (skip image tags and reference definitions)
        anchor_para = ''
        for p in paras:
            cp = p.strip()
            if not cp:
                continue
            if re.match(r'^!\[.*?\]\(.*?\)', cp):
                continue
            if re.match(r'^\s*\[.*?\]:\s*\S+', cp):
                continue
            anchor_para = cp
            break
        if not anchor_para and paras:
            anchor_para = paras[0].strip()

        concept_summary = ''
        if anchor_para:
            clean_anchor = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', anchor_para)
            clean_anchor = re.sub(r'\[([^\]]+)\]\[[^\]]*\]', r'\1', clean_anchor)
            clean_anchor = re.sub(r'[#*`_>~!\(\)\[\]]', '', clean_anchor)
            clean_anchor = re.sub(r'[^\w\s\uFF0C\u3002\u3001\uff01\uff1f]', '', clean_anchor).strip()
            concept_summary = clean_anchor[:35]
        if not concept_summary:
            concept_summary = f'{clean_title}\u7684{sec_title}'

        prompt_zh = (
            f"\u73b0\u4ee3\u5546\u4e1a\u79d1\u6280\u6982\u5ff5\u63d2\u753b\uff0c\u5173\u4e8e\u3010{sec_title}\u3011\uff0c\u6838\u5fc3\u9690\u55bb\u3010{concept_summary}\u3011\u3002"
            f"\u6781\u7b80\u73b0\u4ee3\u8bbe\u8ba1\u98ce\u683c\uff0c\u6df1\u8272\u79d1\u6280\u80cc\u666f\uff0c\u7535\u5f71\u7ea7\u7acb\u4f53\u5149\u5f71\u4e0e\u67d4\u548c\u5fae\u5149\uff0c\u62bd\u8c61\u8ba4\u77e5\u56fe\u8c31\u4e0e\u7cfb\u7edf\u67b6\u6784\u6d41\u52a8\u611f\uff0c"
            f"\u9ad8\u7aef\u5546\u4e1a\u6742\u5fd7\u914d\u56fe\u8d28\u611f\uff0c8k\u8d85\u6e05\u5206\u8fa8\u7387\uff0c16:9\u6784\u56fe --ar 16:9"
        )
        prompt_en = (
            f"Editorial business concept illustration about '{sec_title}', conceptual metaphor for {concept_summary or sec_title}. "
            f"Modern minimalist aesthetics, deep atmospheric dark background, volumetric cinematic lighting, 3D abstract diagram, "
            f"high-end magazine editorial quality, 8k resolution, wallpaper aesthetics --ar 16:9"
        )
        caption = f"\u56fe 0{idx}\uff1a{sec_title} \u6838\u5fc3\u903b\u8f91\u793a\u610f" if idx < 10 else f"\u56fe {idx}\uff1a{sec_title} \u6838\u5fc3\u903b\u8f91\u793a\u610f"

        illustrations.append({
            'section_index': idx,
            'section_title': sec_title,
            'image_prompt': prompt_zh,
            'prompt_zh': prompt_zh,
            'prompt_en': prompt_en,
            'caption': caption,
            'anchor_paragraph': anchor_para,
            'aspect_ratio': '16:9',
        })

    return illustrations

__all__ = [
    "format_xiaohongshu",
    "generate_section_illustrations",
]
