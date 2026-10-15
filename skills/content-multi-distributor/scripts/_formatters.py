# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import re

from _content import derive_hashtags, extract_key_sentences, parse_content_blocks
from _formatters_xhs import format_xiaohongshu, generate_section_illustrations
from _references import replace_links_with_footnotes

def format_wechat(title: str, sections: list, golden_sentences: list, raw_content: str = ""):
    clean_title = clean_title_text(title)
    wechat_title = f'{clean_title}\uff1a\u5e95\u5c42\u903b\u8f91\u4e0e\u7834\u5c40\u6307\u5357'
    
    # Extract footnotes
    footnotes, link_map = extract_footnotes(raw_content, sections)

    # Generate section illustrations
    target_sections = sections[:5]
    section_illustrations = generate_section_illustrations(clean_title, target_sections)

    parts = [
        f'# {wechat_title}\n',
        f'> **\u5bfc\u8bfb**\uff1a\u5728\u590d\u6742\u7684\u4fe1\u606f\u6d6a\u6f6e\u4e2d\uff0c\u6293\u4f4f\u5e95\u5c42\u903b\u8f91\u5f80\u5f80\u6bd4\u86ee\u529b\u6267\u884c\u66f4\u6709\u6548\u3002\u672c\u6587\u56f4\u7ed5\u3010{clean_title}\u3011\u5c55\u5f00\u6df1\u5ea6\u62c6\u89e3\uff0c\u68b3\u7406\u5173\u952e\u77db\u76fe\u4e0e\u7834\u5c40\u7b56\u7565\uff0c\u5e0c\u671b\u80fd\u7ed9\u4f60\u5e26\u6765\u5207\u5b9e\u542f发\u3002\n',
    ]

    for idx, sec in enumerate(target_sections, 1):
        parts.append(f'### 0{idx} / {sec["title"]}\n')
        for p in sec['paragraphs'][:3]:
            clean_p = p.strip()
            if not clean_p:
                continue
            if re.match(r'^\s*\[[^\]]+\]:\s*\S+', clean_p):
                continue
            clean_p = replace_links_with_footnotes(clean_p, link_map)
            if not clean_p:
                continue
            if clean_p.startswith('!['):
                parts.append(f'{clean_p}\n')
            elif len(clean_p) > 40 and ('\uff1a' in clean_p or '\uff0c' in clean_p or ':' in clean_p or ',' in clean_p):
                parts.append(f'{clean_p}\n')
            else:
                parts.append(f'**{clean_p}**\n')
        parts.append('')

    if golden_sentences:
        clean_gold = replace_links_with_footnotes(golden_sentences[0], link_map)
        parts.append(f'> \U0001f4a1 **\u6838\u5fc3\u8ba4\u77e5**\uff1a{clean_gold}\n')

    parts.append('#### \U0001f4dd \u5173\u952e\u8981\u70b9\u590d\u76d8\uff1a')
    for i, s in enumerate(golden_sentences[:3], 1):
        clean_s = replace_links_with_footnotes(s, link_map)
        parts.append(f'- **\u8981\u70b9 0{i}**\uff1a{clean_s}')
    parts.append('')

    if footnotes:
        parts.append('#### \U0001f4da \u53c2\u8003\u8d44\u6599\u4e0e\u5f15\u7528\uff1a')
        for fn in footnotes:
            parts.append(f"- {fn['formatted']}")
        parts.append('')

    parts.append('---')
    parts.append('')
    parts.append('**\u4e92\u52a8\u65f6\u523b\uff1a**')
    parts.append('\u611f\u8c22\u6df1\u5ea6\u9605\u8bfb\uff01\u5982\u679c\u4f60\u89c9\u5f97\u672c\u6587\u5bf9\u4f60\u6240有\u542f\u53d1\uff0c\u8bf7\u4e0d\u541d\u300c\u70b9\u8d5e + \u5728\u770b + \u8f6c\u53d1\u300d\u652f\u6301\u4f5c\u8005\u3002')
    parts.append('\u5173\u6ce8\u516c\u4f17\u53f7\uff0c\u6301\u7eed\u4e3a\u4f60\u62c6\u89e3\u8ba4\u77e5\u601d\u7ef4\u4e0e\u6df1\u5ea6\u751f\u4ea7\u529b\u5e72\u8d27\u3002\u4f60\u5bf9\u8fd9\u4e2a\u8bae\u9898\u6709\u4f55\u89c1\u89e3\uff1f\u6b22\u8fce\u5728\u7559\u8a00\u533a\u4ea4\u6d41\u63a2\u8ba8\u3002')

    cover_image = {
        'title': clean_title,
        'subtitle': '\u5e95\u5c42\u903b\u8f91\u4e0e\u7834\u5c40\u6307\u5357 \u00b7 \u6df1\u5ea6\u6d1e\u5bdf',
        'badge': '\u6df1\u5ea6\u957f\u6587',
        'author': '\u4e2a\u4eba\u8ba4\u77e5 IP \u64ce\u673f',
        'ratio': '900 \u00d7 383 (\u5b98\u65b9\u6807\u51c6\u5c01\u9762\u6bd4\u4f8b)',
    }
    quote_card = {
        'quote': golden_sentences[0] if golden_sentences else '\u770b\u6e05\u5e95\u5c42\u903b\u8f91\uff0c\u624d\u80fd\u5728\u590d\u6742\u4e16\u754c\u4e2d\u4fdd\u6301\u6218\u7565\u6e05\u9192\u3002',
        'source': clean_title,
        'author': 'Cognitive IP',
        'ratio': '16 : 9 (\u6b63\u6587\u9ad8\u5149\u91d1\u53e5\u914d\u56fe)',
    }
    image_prompts = [
        {
            'role': '\u5fae\u4fe1\u516c\u4f17\u53f7\u5b98\u65b9\u5927\u56fe\u5c01\u9762 (900 \u00d7 383 / 16:9)',
            'prompt_zh': f'\u73b0\u4ee3\u79d1\u6280\u6982\u5ff5\u5546\u4e1a\u63d2\u753b\uff0c\u5173\u4e8e\u3010{clean_title}\u3011\uff0c\u6781\u7b80\u73b0\u4ee3\u98ce\u683c\uff0c\u6df1\u8272\u5149\u5f71\uff0c8k\u9ad8\u5206\u8fa8\u7387\uff0c\u7535\u5f71\u7ea7\u8d28\u611f\uff0c\u9ad8\u7aef\u6742\u5fd7\u98ce\u683c',
            'prompt_en': f'Editorial tech business illustration about {clean_title}, minimalist modern aesthetics, volumetric lighting, hyper-detailed, 8k wallpaper --ar 16:9',
        },
        {
            'role': '\u6b63\u6587\u903b\u8f91\u67b6\u6784\u6982\u5ff5\u914d\u56fe',
            'prompt_zh': '\u62bd\u8c61\u8ba4\u77e5\u6a21\u578b\u56fe\u8c31\uff0c\u7acb\u4f53\u7f51\u72b6\u7ed3\u6784\uff0c\u601d\u8003\u4e0e\u7075\u611f\u706b\u82b1\uff0c\u6df1\u8272\u9ad8\u7aef\u80cc\u666f\uff0c\u4e13\u4e1a\u4fe1\u606f\u56fe\u8868\u8d28\u611f',
            'prompt_en': 'Abstract cognitive architecture diagram, 3D isometric network, glowing nodes, clean dark background, professional infographic style --ar 16:9',
        },
    ]

    return {
        'title': wechat_title,
        'content': '\n'.join(parts),
        'cover_image': cover_image,
        'quote_card': quote_card,
        'image_prompts': image_prompts,
        'section_illustrations': section_illustrations,
        'footnotes': footnotes,
    }


def format_twitter(title: str, sections: list, golden_sentences: list):
    clean_title = clean_title_text(title)
    
    tweets = []

    tweet_1_template = (
        f'\u5173\u4e8e\u3010{clean_title}\u3011\uff0c\u5f88\u591a\u4eba\u82b1\u8d39\u4e86\u5927\u91cf\u7cbe\u529b\u5374\u6536\u6548\u751a\u5fae\u3002\n\n'
        f'\u6839\u672c\u539f\u56e0\u5f80\u5f80\u4e0d\u662f\u4e0d\u591f\u52aa\u529b\uff0c\u800c\u662f\u9677\u5165\u4e86\u8ba4\u77e5\u7684\u201c\u76f2\u533a\u9677\u9631\u201d\u3002\n\n'
        f'\u82b1 2 \u5206\u949f\u8bfb\u5b8c\u8fd9\u4e2a\u63a8\u6587\u4e32\uff0c\u4e3a\u4f60\u62c6\u89e3\u6700\u5173\u952e\u7684\u7834\u5c40\u903b\u8f91 \U0001F9F5\U0001F447'
    )
    tweets.append(tweet_1_template)

    for sec in sections[:4]:
        p_text = ' '.join(sec['paragraphs'][:2]).strip()
        if not p_text:
            continue
        if len(p_text) > 160:
            p_text = p_text[:155] + '...'
        tw = f'\u3010{sec["title"]}\u3011\n\n{p_text}'
        tweets.append(tw)

    for g in golden_sentences[:2]:
        if len(tweets) >= 7:
            break
        tw = (
            f'\U0001F4A1 \u6838\u5fc3\u8ba4\u77e5\u7a7f\u900f\uff1a\n\n'
            f'\u201c{g}\u201d\n\n'
            f'\u770b\u6e05\u8868\u8c61\u80cc\u540e\u7684\u56e0\u679c\u5f8b\uff0c\u6267\u884c\u624d\u4e0d\u4f1a\u53d8\u5f62\u3002'
        )
        tweets.append(tw)

    filler_pool = [
        '\u26a0\ufe0f \u81f4\u547d\u76f2\u533a\u8b66\u793a\uff1a\n\n\u7edd\u5927\u591a\u6570\u4eba\u7684\u74f6\u9888\u4e0d\u5728\u4e8e\u6267\u884c\u529b\u5ea6\uff0c\u800c\u5728\u4e8e\u628a\u624b\u6bb5\u5f53\u6210\u4e86\u76ee\u7684\uff0c\u5728\u4f4e\u7ef4\u5ea6\u7684\u7ec6\u8282\u4e0a\u53cd\u590d\u5185\u8017\u3002',
        '\U0001F511 \u7834\u5c40\u5173\u952e\u52a8\u4f5c\uff1a\n\n\u5148\u805a\u7126\u5355\u4e00\u6838\u5fc3\u652f\u70b9\uff0c\u5efa\u7acb\u6700\u5c0f\u9a8c\u8bc1\u95ed\u73af\uff0c\u7528\u771f\u5b9e\u7684\u53cd\u9988\u6821\u51c6\u8ba4\u77e5\u504f\u5dee\u3002',
        '\u26a1\ufe0f \u6760\u6746\u6548\u5e94\u601d\u8003\uff1a\n\n\u8ba4\u77e5\u51b3\u5b9a\u4e0a\u9650\uff0c\u8282\u594f\u51b3\u5b9a\u6210\u8d25\u3002\u627e\u5230\u5c5e\u4e8e\u81ea\u5df1\u7684\u590d\u5229\u6a21\u578b\uff0c\u624d\u80fd\u771f\u6b63\u62c9\u5f00\u5dee\u8ddd\u3002',
    ]
    filler_idx = 0
    while len(tweets) < 4 and filler_idx < len(filler_pool):
        tweets.append(filler_pool[filler_idx])
        filler_idx += 1

    tweets = tweets[:7]

    final_tweet_template = (
        '\U0001F4CC \u6838\u5fc3\u8981\u70b9\u590d\u76d8\uff1a\n'
        '\u2022 \u8ba4\u77e5\u5148\u884c\uff0c\u5148\u770b\u6e05\u5168\u5c40\u518d\u52a8\u624b\n'
        '\u2022 \u6293\u4f4f\u5173\u952e\u6760\u6746\u70b9\uff0c\u62d2\u7edd\u4f4e\u6c34\u5e73\u91cd\u590d\n'
        '\u2022 \u4fdd\u6301\u8282\u594f\uff0c\u5728\u53cd\u9988\u4e2d\u5feb\u901f\u8fed\u4ee3\n\n'
        '\u5982\u679c\u4f60\u89c9\u5f97\u8fd9\u4e2a\u63a8\u6587\u4e32\u5bf9\u4f60\u6240\u6709\u542f\u53d1\uff1a\n'
        '1. \U0001F501 \u8f6c\u53d1\u7b2c\u4e00\u6761\u63a8\u6587\uff08Retweet\uff09\uff0c\u5206\u4eab\u7ed9\u66f4\u591a\u540c\u884c\u8005\n'
        '2. \U0001F516 Bookmark \u6536\u85cf\u968f\u65f6\u5bf9\u7167\u590d\u76d8\n'
        '3. \u5173\u6ce8\u6211\u83b7\u53d6\u66f4\u591a\u6df1\u5ea6\u6d1e\u5bdf\uff01'
    )
    tweets.append(final_tweet_template)

    total_count = len(tweets)
    numbered_tweets = [f'{i}/{total_count}\n\n{tw}' for i, tw in enumerate(tweets, 1)]

    return {
        'thread': numbered_tweets,
        'content': '\n\n---\n\n'.join(numbered_tweets),
    }


def format_video(title: str, sections: list, golden_sentences: list):
    clean_title = clean_title_text(title)
    short_title = clean_title[:18]

    hook_cue = (
        '\u3010\u524d3\u79d2\u9ec4\u91d1\u94a9\u5b50\u3011\n'
        '[\u773c\u795e\u76f4\u89c6\u955c\u5934\uff0c\u8eab\u4f53\u5411\u524d\u5fae\u503e\uff0c\u8bed\u901f\u7d27\u51d1\u575a\u5b9a]\n'
        f'\u201c\u542c\u6211\u8bf4\uff0c\u5982\u679c\u4f60\u8fd8\u5728\u3010{short_title}\u3011\u91cc\u6b7b\u78d5\uff0c\u8d76\u7d27\u505c\u4e0b\u6765\uff01\u4eca\u5929\u8fd9\u6761\u89c6\u9891\uff0c\u53ef\u80fd\u76f4\u63a5\u7701\u4e0b\u4f60\u534a\u5e74\u7684\u8bd5\u9519\u6210\u672c\u3002\u201d'
    )

    body_parts = [
        hook_cue,
        '\n[\u955c\u5934\u5207\u6362/\u7279\u5199]',
        '\u201c\u8bf4\u767d\u4e86\uff0c\u5f88\u591a\u4eba\u4e4b\u6240\u4ee5\u5361\u5728\u8fd9\u4e2a\u5730\u65b9\uff0c\u672c\u8d28\u4e0a\u5c31\u662f\u628a\u8868\u8c61\u5f53\u6210\u4e86\u539f\u56e0\u2026\u2026\u201d\n',
        '[\u505c\u987f\u601d\u8003 1\u79d2]',
        '\u201c\u5176\u5b9e\u771f\u6b63\u7684\u9ad8\u624b\u505a\u8fd9\u4ef6\u4e8b\u60c5\uff0c\u53ea\u6293\u51e0\u4e2a\u5173\u952e\u52a8\u4f5c\uff1a\u201d\n',
    ]

    cues = [
        '[\u624b\u52bf\u6bd4\u51fa 1]',
        '[\u624b\u52bf\u6bd4\u51fa 2]',
        '[\u624b\u52bf\u6bd4\u51fa 3]',
    ]

    target_sections = sections[:3]
    while len(target_sections) < 3:
        if len(target_sections) == 1:
            target_sections.append({'title': '\u6293\u51c6\u5e95\u5c42\u903b\u8f91', 'paragraphs': ['\u770b\u6e05\u8868\u8c61\u80cc\u540e\u7684\u771f\u5b9e\u8fd0\u884c\u673a\u5236\uff0c\u4e0d\u76f2\u4ece\u4e0d\u7126\u8651\u3002']})
        elif len(target_sections) == 2:
            target_sections.append({'title': '\u5efa\u7acb\u6b63\u5411\u95ed\u73af', 'paragraphs': ['\u7528\u6700\u5c0f\u963b\u529b\u8def\u5f84\u6301\u7eed\u62ff\u5230\u6b63\u5411\u53cd\u9988\uff0c\u62c9\u5f00\u5dee\u8ddd\u3002']})

    for idx in range(3):
        sec = target_sections[idx]
        cue = cues[idx]
        summary = ' '.join(sec['paragraphs'][:1]).strip()[:80]
        if not summary:
            summary = '\u627e\u5230\u7cfb\u7edf\u6760\u6746\u89e3\uff0c\u7834\u5c40\u8def\u5f84\u4f9d\u8d56'
        summary = re.sub(r'[\u3002\uff01\uff1f!?]+$', '', summary)
        body_parts.append(cue)
        body_parts.append(f'\u201c\u7b2c{idx+1}\u70b9\uff0c\u5173\u4e8e\u3010{sec["title"]}\u3011\u2014\u2014{summary}\u3002\u201d\n')

    if golden_sentences:
        clean_golden = re.sub(r'[\u3002\uff01\uff1f!?]+$', '', golden_sentences[0])
        body_parts.append('[\u773c\u795e\u575a\u5b9a\uff0c\u76f4\u9762\u955c\u5934]')
        body_parts.append(f'\u201c\u8bb0\u4f4f\u8fd9\u53e5\u8bdd\uff1a{clean_golden}\u3002\u201d\n')

    body_parts.append('[\u6587\u672b\u4e92\u52a8\uff1a\u9762\u5bf9\u955c\u5934\u5fae\u7b11\uff0c\u4f38\u624b\u793a\u610f]')
    body_parts.append('\u201c\u8ba4\u77e5\u51b3\u5b9a\u4e0a\u9650\uff0c\u8282\u594f\u51b3\u5b9a\u6210\u8d25\u3002\u89c9\u5f97\u6709\u542f\u53d1\uff0c\u70b9\u4e2a\u8d5e\uff0c\u5173\u6ce8\u6211\uff0c\u4e0b\u671f\u5e26\u4f60\u770b\u4e0d\u4e00\u6837\u7684\u5b9e\u6218\u5e72\u8d27\uff01\u201d')

    full_script = '\n'.join(body_parts)
    script_chars = len(re.sub(r'\[.*?\]', '', full_script))
    est_seconds = max(45, min(180, int(script_chars / 3.5)))

    return {
        'hook': hook_cue,
        'content': full_script,
        'estimated_duration_seconds': est_seconds,
    }

__all__ = [
    "format_xiaohongshu",
    "generate_section_illustrations",
    "format_wechat",
    "format_twitter",
    "format_video",
]
