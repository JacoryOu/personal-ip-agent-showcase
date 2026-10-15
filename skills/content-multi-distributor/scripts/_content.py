# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import re

def clean_title_text(title: str) -> str:
    t = re.sub(r'^[#*_\s]+|[#*_\s]+$', '', title.strip())
    t = re.sub(r'[\u3002\uff01\uff1f!?\uff1b;:：，,]+$', '', t).strip()
    return t


def extract_title_and_clean_content(content: str, explicit_title: str = None):
    if explicit_title and explicit_title.strip():
        title = clean_title_text(explicit_title)
        return title, content.strip()

    lines = content.strip().splitlines()
    found_title = None
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()
        if not found_title:
            if stripped.startswith('# '):
                found_title = re.sub(r'^#+\s*', '', stripped).strip()
                continue
            elif stripped.startswith('## '):
                found_title = re.sub(r'^#+\s*', '', stripped).strip()
                continue
            elif stripped and not stripped.startswith('#') and not stripped.startswith('>') and len(stripped) <= 60 and len(lines) > 1:
                found_title = stripped
                continue
        cleaned_lines.append(line)

    if not found_title:
        first_non_empty = [l.strip() for l in lines if l.strip()]
        if first_non_empty:
            candidate = re.split(r'[\u3002\uff01\uff1f!?\n]', first_non_empty[0])[0].strip()
            found_title = candidate[:35] if candidate else first_non_empty[0][:35]
        else:
            found_title = "\u6838\u5fc3\u6df1\u5ea6\u601d\u8003"

    found_title = clean_title_text(found_title)
    cleaned_body = '\n'.join(cleaned_lines).strip()

    if not cleaned_body:
        cleaned_body = content.strip()

    return found_title, cleaned_body


def parse_content_blocks(content: str):
    lines = content.splitlines()
    sections = []
    current_section = {'title': '\u6838\u5fc3\u80cc\u666f\u4e0e\u75db\u70b9', 'paragraphs': []}
    current_paras = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('# ') or stripped.startswith('## ') or stripped.startswith('### '):
            if current_paras:
                current_section['paragraphs'] = current_paras
                sections.append(current_section)
                current_paras = []
            heading = re.sub(r'^#+\s*', '', stripped).strip()
            current_section = {'title': clean_title_text(heading), 'paragraphs': []}
        else:
            clean_p = re.sub(r'^[>\-*+]\s*', '', stripped).strip()
            if clean_p:
                if re.match(r'^\s*\[[^\]]+\]:\s*<?https?://\S+', clean_p):
                    continue
                current_paras.append(clean_p)

    if current_paras:
        current_section['paragraphs'] = current_paras
        sections.append(current_section)

    sections = [s for s in sections if s['paragraphs']]

    if not sections:
        sections = [
            {'title': '\u6838\u5fc3\u75db\u70b9\u4e0e\u73b0\u8c61\u6d1e\u5bdf', 'paragraphs': [content.strip()]},
            {'title': '\u5e95\u5c42\u903b\u8f91\u4e0e\u56e0\u679c\u5256\u6790', 'paragraphs': ['\u770b\u6e05\u8868\u8c61\u80cc\u540e\u7684\u771f\u5b9e\u673a\u5236\uff0c\u907f\u514d\u9677\u5165\u4f4e\u6548\u5185\u8017\u4e0e\u76f2\u76ee\u8bd5\u9519\u3002']},
            {'title': '\u5b9e\u6218\u7b56\u7565\u4e0e\u7834\u5c40\u8def\u5f84', 'paragraphs': ['\u6293\u4f4f\u6838\u5fc3\u6760\u6746\u652f\u70b9\uff0c\u5efa\u7acb\u6700\u5c0f\u9a8c\u8bc1\u95ed\u73af\uff0c\u6301\u7eed\u5c0f\u6b65\u5feb\u8dd1\u8fed\u4ee3\u3002']},
        ]
    elif len(sections) == 1 and sections[0]['title'] in ('\u6838\u5fc3\u80cc\u666f\u4e0e\u75db\u70b9', '\u6838\u5fc3\u89c2\u70b9', '\u6838\u5fc3\u80cc\u666f\u4e0e\u6d1e\u5bdf'):
        all_paras = sections[0]['paragraphs']
        default_stage_names = ['\u6838\u5fc3\u75db\u70b9\u4e0e\u73b0\u8c61\u6d1e\u5bdf', '\u5e95\u5c42\u903b\u8f91\u4e0e\u56e0\u679c\u5256\u6790', '\u5b9e\u6218\u7b56\u7565\u4e0e\u7834\u5c40\u8def\u5f84']
        if len(all_paras) >= 3:
            chunk_size = max(1, len(all_paras) // 3)
            p1 = all_paras[:chunk_size]
            p2 = all_paras[chunk_size: chunk_size * 2]
            p3 = all_paras[chunk_size * 2:]
            sections = [
                {'title': default_stage_names[0], 'paragraphs': p1 or [all_paras[0]]},
                {'title': default_stage_names[1], 'paragraphs': p2 or [all_paras[min(1, len(all_paras)-1)]]},
                {'title': default_stage_names[2], 'paragraphs': p3 or [all_paras[-1]]},
            ]
        else:
            full_text = ' '.join(all_paras)
            sentences = [s.strip() for s in re.split(r'[\u3002\uff01\uff1f!?\n]+', full_text) if s.strip()]
            if len(sentences) >= 3:
                s_chunk = max(1, len(sentences) // 3)
                sections = [
                    {'title': default_stage_names[0], 'paragraphs': ['\u3002'.join(sentences[:s_chunk]) + '\u3002']},
                    {'title': default_stage_names[1], 'paragraphs': ['\u3002'.join(sentences[s_chunk:s_chunk*2]) + '\u3002']},
                    {'title': default_stage_names[2], 'paragraphs': ['\u3002'.join(sentences[s_chunk*2:]) + '\u3002']},
                ]
            else:
                sections = [
                    {'title': default_stage_names[0], 'paragraphs': [full_text]},
                    {'title': default_stage_names[1], 'paragraphs': ['\u770b\u6e05\u8868\u8c61\u80cc\u540e\u7684\u771f\u5b9e\u673a\u5236\uff0c\u907f\u514d\u9677\u5165\u4f4e\u6548\u5185\u8017\u4e0e\u76f2\u76ee\u8bd5\u9519\u3002']},
                    {'title': default_stage_names[2], 'paragraphs': ['\u6293\u4f4f\u6838\u5fc3\u6760\u6746\u652f\u70b9\uff0c\u5efa\u7acb\u6700\u5c0f\u9a8c\u8bc1\u95ed\u73af\uff0c\u6301\u7eed\u5c0f\u6b65\u5feb\u8dd1\u8fed\u4ee3\u3002']},
                ]
    elif len(sections) < 3:
        default_stage_names = ['\u6838\u5fc3\u8ba4\u77e5\u6df1\u5316', '\u843d\u5730\u884c\u52a8\u6307\u5357']
        idx = 0
        while len(sections) < 3:
            name = default_stage_names[idx % len(default_stage_names)]
            sections.append({
                'title': name,
                'paragraphs': ['\u57fa\u4e8e\u4e0a\u8ff0\u903b\u8f91\uff0c\u805a\u7126\u6838\u5fc3\u6760\u6746\u652f\u70b9\uff0c\u5efa\u7acb\u6301\u7eed\u8fed\u4ee3\u7684\u6b63\u5411\u53cd\u9988\u95ed\u73af\u3002']
            })
            idx += 1

    return sections


def extract_key_sentences(content: str, max_count: int = 5):
    lines = [
        line.strip() for line in content.splitlines()
        if line.strip()
        and not re.match(r'^\s*\[[^\]]+\]:\s*\S+', line.strip())
        and not re.match(r'^\s*!\[.*?\]\(.*?\)', line.strip())
    ]
    cleaned_content = '\n'.join(lines)
    sentences = re.split(r'[\u3002\uff01\uff1f!?\n]+', cleaned_content)
    cleaned = [s.strip() for s in sentences if 10 <= len(s.strip()) <= 120]
    
    keywords = ['\u672c\u8d28', '\u6838\u5fc3', '\u5173\u952e', '\u5e95\u5c42', '\u771f\u6b63', '\u5fc5\u987b', '\u75db\u70b9', '\u4ef7\u503c', '\u903b\u8f91', '\u89c4\u5f8b', '\u9677\u9631', '\u91cd\u6784', '\u6760\u6746']
    prioritized = [s for s in cleaned if any(k in s for k in keywords)]
    
    candidates = prioritized + [s for s in cleaned if s not in prioritized]
    if not candidates and cleaned:
        candidates = cleaned
    if not candidates:
        candidates = ['\u770b\u6e05\u5e95\u5c42\u903b\u8f91\uff0c\u624d\u80fd\u5728\u4e0d\u786e\u5b9a\u6027\u4e2d\u5efa\u7acb\u7b03\u5b9a\u7684\u884c\u52a8\u7b56\u7565\u3002']
    return candidates[:max_count]


def derive_hashtags(title: str, content: str) -> list[str]:
    standard_tags = ['#\u6df1\u5ea6\u601d\u8003', '#\u8ba4\u77e5\u5347\u7ea7', '#\u4e2a\u4eba\u6210\u957f', '#\u5e95\u5c42\u903b\u8f91', '#\u5e72\u8d27\u5206\u4eab']
    candidates = []

    keyword_map = [
        (['AI', '\u5927\u6a21\u578b', 'Prompt', '\u4eba\u5de5\u667a\u80fd'], '#AI\u751f\u4ea7\u529b'),
        (['\u5546\u4e1a', '\u8d5a\u94b1', '\u53d8\u73b0', '\u4ea7\u54c1', '\u95ed\u73af'], '#\u5546\u4e1a\u8ba4\u77e5'),
        (['\u6280\u672f', '\u67b6\u6784', '\u7cfb\u7edf', '\u5f00\u53d1', '\u4ee3\u7801'], '#\u6280\u672f\u601d\u8003'),
        (['\u804c\u573a', '\u56e2\u961f', '\u7ba1\u7406', '\u664b\u5347'], '#\u804c\u573a\u8fdb\u9636'),
        (['\u4e2a\u4f53', '\u72ec\u7acb', '\u521b\u4f5c\u8005', 'IP'], '#\u8d85\u7ea7\u4e2a\u4f53'),
        (['\u6548\u7387', '\u5de5\u5177', '\u5de5\u4f5c\u6d41', '\u751f\u4ea7\u529b'], '#\u9ad8\u6548\u5de5\u4f5c\u6d41'),
    ]

    combined = f'{title} {content}'
    for words, tag in keyword_map:
        if any(w in combined for w in words):
            if tag not in candidates:
                candidates.append(tag)

    clean_title_words = re.sub(r'[^\w\u4e00-\u9fa5]', '', title)
    if 2 <= len(clean_title_words) <= 8:
        tag = f'#{clean_title_words}'
        if tag not in candidates:
            candidates.insert(0, tag)

    for st in standard_tags:
        if len(candidates) >= 5:
            break
        if st not in candidates:
            candidates.append(st)

    return candidates[:5]
