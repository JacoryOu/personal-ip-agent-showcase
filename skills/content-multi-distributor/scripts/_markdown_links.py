# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import re

REF_DEF_PATTERN = re.compile(
    r'^[ \t]*\[([^\]]+)\]:[ \t]*<?(https?://[^\s>]+)>?(?:[ \t]+["\'\(](.*?)[\"\'\)])?[ \t]*$',
    re.MULTILINE
)

def parse_markdown_links(text: str, ref_defs: dict = None) -> list:
    """
    Finds all Markdown inline links [text](dest) and reference links [text][ref] in text.
    Handles angle brackets <URL>, balanced parens in URLs, and optional titles.
    """
    if ref_defs is None:
        ref_defs = {}
    links = []
    i = 0
    n = len(text)
    while i < n:
        idx = text.find('[', i)
        if idx == -1:
            break
        # Skip markdown images ![alt](url)
        if idx > 0 and text[idx - 1] == '!':
            i = idx + 1
            continue
        close_bracket = text.find(']', idx + 1)
        if close_bracket == -1:
            break
        inner_bracket = text.find('[', idx + 1)
        if inner_bracket != -1 and inner_bracket < close_bracket:
            idx = inner_bracket
            continue

        link_text = text[idx + 1:close_bracket]
        after_bracket = close_bracket + 1

        # Check inline link: `](`
        if after_bracket < n and text[after_bracket] == '(':
            paren_start = after_bracket
            p = paren_start + 1
            paren_depth = 1
            url = ''
            title = ''
            
            # Check angle bracket URL: <https://...>
            p_stripped = p
            while p_stripped < n and text[p_stripped] in ' \t':
                p_stripped += 1
            if p_stripped < n and text[p_stripped] == '<':
                angle_end = text.find('>', p_stripped + 1)
                if angle_end != -1:
                    url = text[p_stripped + 1:angle_end].strip()
                    p = angle_end + 1
                    while p < n and text[p] in ' \t':
                        p += 1
                    if p < n and text[p] in ('"', "'"):
                        quote = text[p]
                        quote_end = text.find(quote, p + 1)
                        if quote_end != -1:
                            title = text[p + 1:quote_end]
                            p = quote_end + 1
                    close_paren = text.find(')', p)
                    if close_paren != -1:
                        match_end = close_paren + 1
                        if url.startswith(('http://', 'https://', 'www.')):
                            links.append({
                                'start': idx,
                                'end': match_end,
                                'text': link_text,
                                'url': url,
                                'title': title or link_text,
                                'type': 'inline'
                            })
                            i = match_end
                            continue

            # Standard URL parsing with balanced parenthesis tracking
            url_chars = []
            in_quotes = False
            quote_char = None
            title_chars = []
            matched = False

            while p < n:
                ch = text[p]
                if not in_quotes:
                    if ch in ('"', "'") and (p > paren_start + 1 and text[p - 1] in ' \t'):
                        in_quotes = True
                        quote_char = ch
                    elif ch == '(':
                        paren_depth += 1
                        url_chars.append(ch)
                    elif ch == ')':
                        paren_depth -= 1
                        if paren_depth == 0:
                            matched = True
                            match_end = p + 1
                            break
                        else:
                            url_chars.append(ch)
                    else:
                        url_chars.append(ch)
                else:
                    if ch == quote_char:
                        in_quotes = False
                    else:
                        title_chars.append(ch)
                p += 1

            if matched:
                raw_url = ''.join(url_chars).strip()
                raw_url = raw_url.split()[0] if raw_url else ''
                title_str = ''.join(title_chars).strip()
                if raw_url.startswith(('http://', 'https://', 'www.')):
                    links.append({
                        'start': idx,
                        'end': match_end,
                        'text': link_text,
                        'url': raw_url,
                        'title': title_str or link_text,
                        'type': 'inline'
                    })
                    i = match_end
                    continue

        # Check reference link: `][ref]` or `][]`
        elif after_bracket < n and text[after_bracket] == '[':
            ref_close = text.find(']', after_bracket + 1)
            if ref_close != -1:
                ref_id = text[after_bracket + 1:ref_close].strip()
                ref_key = ref_id.lower() if ref_id else link_text.strip().lower()
                match_end = ref_close + 1
                if ref_key in ref_defs:
                    url = ref_defs[ref_key]['url']
                    title = ref_defs[ref_key]['title'] or link_text
                    links.append({
                        'start': idx,
                        'end': match_end,
                        'text': link_text,
                        'url': url,
                        'ref': ref_key,
                        'title': title,
                        'type': 'ref_link'
                    })
                    i = match_end
                    continue

        # Check shortcut reference link: `[ref_id]`
        ref_key = link_text.strip().lower()
        if ref_key in ref_defs:
            match_end = close_bracket + 1
            url = ref_defs[ref_key]['url']
            title = ref_defs[ref_key]['title'] or link_text
            links.append({
                'start': idx,
                'end': match_end,
                'text': link_text,
                'url': url,
                'ref': ref_key,
                'title': title,
                'type': 'ref_shortcut'
            })
            i = match_end
            continue

        i = idx + 1

    return links
