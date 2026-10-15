# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import json
import sys
from pathlib import Path

from _content import (
    clean_title_text,
    derive_hashtags,
    extract_key_sentences,
    extract_title_and_clean_content,
    parse_content_blocks,
)
from _formatters import (
    format_video,
    format_wechat,
    format_twitter,
    format_xiaohongshu,
    generate_section_illustrations,
)
from _references import (
    REF_DEF_PATTERN,
    extract_footnotes,
    parse_markdown_links,
    replace_links_with_footnotes,
)

__all__ = [
    "clean_title_text",
    "extract_title_and_clean_content",
    "parse_content_blocks",
    "extract_key_sentences",
    "derive_hashtags",
    "format_xiaohongshu",
    "REF_DEF_PATTERN",
    "parse_markdown_links",
    "extract_footnotes",
    "replace_links_with_footnotes",
    "generate_section_illustrations",
    "format_wechat",
    "format_twitter",
    "format_video",
    "distribute_content",
    "main",
]

def distribute_content(content: str, explicit_title: str = None, platforms=None):
    if not content or not content.strip():
        return {'success': False, 'error': 'No content provided for distribution.'}

    target_platforms = platforms or ['xiaohongshu', 'wechat', 'twitter', 'video']
    if isinstance(target_platforms, str):
        target_platforms = [p.strip() for p in target_platforms.split(',') if p.strip()]

    title, cleaned_content = extract_title_and_clean_content(content, explicit_title)
    sections = parse_content_blocks(cleaned_content)
    golden_sentences = extract_key_sentences(cleaned_content)

    results = {}
    if 'xiaohongshu' in target_platforms:
        results['xiaohongshu'] = format_xiaohongshu(title, sections, golden_sentences)
    if 'wechat' in target_platforms:
        results['wechat'] = format_wechat(title, sections, golden_sentences, raw_content=cleaned_content)
    if 'twitter' in target_platforms:
        results['twitter'] = format_twitter(title, sections, golden_sentences)
    if 'video' in target_platforms:
        results['video'] = format_video(title, sections, golden_sentences)

    return {
        'success': True,
        'title': title,
        'platforms': results,
    }


def main():
    parser = argparse.ArgumentParser(description='Multi-platform content distribution formatter.')
    parser.add_argument('--content', help='Article text content')
    parser.add_argument('--title', help='Article title')
    parser.add_argument('--platforms', nargs='*', help='Platforms to format for')
    parser.add_argument('--json', help='JSON payload string')
    parser.add_argument('--file', help='Path to JSON payload file')
    args = parser.parse_args()

    content = args.content or ''
    title = args.title
    platforms = args.platforms

    if args.file and Path(args.file).exists():
        try:
            p = json.loads(Path(args.file).read_text(encoding='utf-8'))
            content = p.get('content', content)
            title = p.get('title', title)
            platforms = p.get('platforms', platforms)
        except Exception:
            pass

    if args.json:
        try:
            p = json.loads(args.json)
            content = p.get('content', content)
            title = p.get('title', title)
            platforms = p.get('platforms', platforms)
        except Exception:
            pass

    if not content and not sys.stdin.isatty():
        try:
            stdin_data = sys.stdin.read().strip()
            if stdin_data:
                try:
                    p = json.loads(stdin_data)
                    content = p.get('content', content)
                    title = p.get('title', title)
                    platforms = p.get('platforms', platforms)
                except Exception:
                    content = stdin_data
        except Exception:
            pass

    res = distribute_content(content=content, explicit_title=title, platforms=platforms)
    print(json.dumps(res, ensure_ascii=True))


if __name__ == '__main__':
    main()
