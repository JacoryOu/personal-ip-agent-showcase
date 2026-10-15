# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import re

from _markdown_links import REF_DEF_PATTERN, parse_markdown_links

def extract_footnotes(content: str, sections: list = None):
    """
    Extracts markdown hyperlinks and reference links into structured footnotes.
    Converts inline links [Text](URL) and reference links [Text][ref] into footnotes [index] Text: URL.
    Returns:
        footnotes: list of dicts [{'index': int, 'title': str, 'text': str, 'url': str, 'formatted': str}]
        link_map: dict of {url: (index, title)}
    """
    footnotes = []
    seen_urls = {}

    full_texts = [content] if content else []
    if sections:
        for s in sections:
            full_texts.extend(s.get('paragraphs', []))
    combined_search_space = '\n'.join(full_texts)

    # 1. Parse reference definitions
    ref_defs = {}
    for match in REF_DEF_PATTERN.finditer(combined_search_space):
        ref_id = match.group(1).strip()
        url = match.group(2).strip()
        title = (match.group(3) or '').strip()
        ref_defs[ref_id.lower()] = {
            'ref_id': ref_id,
            'url': url,
            'title': title,
        }

    # 2. Extract in-text links in order
    links = parse_markdown_links(combined_search_space, ref_defs)
    for link in links:
        url = link['url']
        title = link['title'] or link['text']
        norm_url = url.rstrip('/')
        if url not in seen_urls and norm_url not in seen_urls:
            idx = len(footnotes) + 1
            seen_urls[url] = (idx, title)
            seen_urls[norm_url] = (idx, title)
            seen_urls[norm_url + '/'] = (idx, title)
            footnotes.append({
                'index': idx,
                'title': title,
                'text': title,
                'url': url,
                'formatted': f'[{idx}] {title}\uff1a{url}'
            })

    # 3. Add any reference definitions that weren't cited in text
    for ref_key, rdef in ref_defs.items():
        url = rdef['url']
        norm_url = url.rstrip('/')
        if url not in seen_urls and norm_url not in seen_urls:
            idx = len(footnotes) + 1
            title = rdef['title'] or rdef['ref_id']
            seen_urls[url] = (idx, title)
            seen_urls[norm_url] = (idx, title)
            seen_urls[norm_url + '/'] = (idx, title)
            footnotes.append({
                'index': idx,
                'title': title,
                'text': title,
                'url': url,
                'formatted': f'[{idx}] {title}\uff1a{url}'
            })

    # Also store ref_defs mapping in seen_urls for reference link lookup
    for ref_key, rdef in ref_defs.items():
        url = rdef['url']
        norm_url = url.rstrip('/')
        if url in seen_urls:
            idx_info = seen_urls[url]
            seen_urls[f'ref:{ref_key}'] = (idx_info[0], idx_info[1], url)

    return footnotes, seen_urls


def replace_links_with_footnotes(text: str, seen_urls: dict) -> str:
    """
    Replaces inline markdown links [Title](URL) and reference links [Title][ref]
    with WeChat-compliant superscript footnote references:
    'Title [1]' so external links don't trigger platform sanitization.
    """
    if not seen_urls or not text:
        return text

    # Reconstruct ref_defs lookup if stored
    ref_defs = {}
    for k, v in seen_urls.items():
        if k.startswith('ref:'):
            ref_id = k[4:]
            u = v[2] if isinstance(v, (list, tuple)) and len(v) > 2 else ''
            t = v[1] if isinstance(v, (list, tuple)) and len(v) > 1 else ''
            ref_defs[ref_id] = {'url': u, 'title': t}

    # Also extract any local reference definitions in the text chunk
    for match in REF_DEF_PATTERN.finditer(text):
        ref_id = match.group(1).strip()
        url = match.group(2).strip()
        title = (match.group(3) or '').strip()
        ref_defs[ref_id.lower()] = {'ref_id': ref_id, 'url': url, 'title': title}

    links = parse_markdown_links(text, ref_defs)
    if not links:
        cleaned = re.sub(r'^[ \t]*\[[^\]]+\]:[ \t]*<?https?://\S+.*$', '', text, flags=re.MULTILINE)
        return cleaned.strip()

    result_parts = []
    last_idx = 0
    for link in links:
        result_parts.append(text[last_idx:link['start']])
        url = link.get('url', '')
        idx = None
        if url in seen_urls:
            idx = seen_urls[url][0]
        else:
            norm = url.rstrip('/')
            if norm in seen_urls:
                idx = seen_urls[norm][0]
            elif (norm + '/') in seen_urls:
                idx = seen_urls[norm + '/'][0]

        if idx is None and link.get('ref'):
            rk = link['ref'].lower()
            if f'ref:{rk}' in seen_urls:
                idx = seen_urls[f'ref:{rk}'][0]

        if idx is not None:
            result_parts.append(f"{link['text']} [{idx}]")
        else:
            result_parts.append(text[link['start']:link['end']])
        last_idx = link['end']

    result_parts.append(text[last_idx:])
    output = ''.join(result_parts)
    # Strip any standalone reference definition lines
    output = re.sub(r'^[ \t]*\[[^\]]+\]:[ \t]*<?https?://\S+.*$', '', output, flags=re.MULTILINE)
    return output.strip()

__all__ = [
    "REF_DEF_PATTERN",
    "parse_markdown_links",
    "extract_footnotes",
    "replace_links_with_footnotes",
]
