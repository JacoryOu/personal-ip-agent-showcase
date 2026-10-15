# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import argparse
import json
from pathlib import Path
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

from _data import FALLBACK_TOPICS, USER_AGENT
from _fetchers import (
    fetch_36kr,
    fetch_bilibili,
    fetch_douyin,
    fetch_weibo,
    fetch_zhihu,
)
from _core import PLATFORM_FETCHERS, calculate_relevance_score, run_radar

__all__ = [
    'USER_AGENT',
    'FALLBACK_TOPICS',
    'fetch_weibo',
    'fetch_zhihu',
    'fetch_bilibili',
    'fetch_36kr',
    'fetch_douyin',
    'PLATFORM_FETCHERS',
    'calculate_relevance_score',
    'run_radar',
    'main',
]



def main():
    parser = argparse.ArgumentParser(description="Multi-platform Trending Radar")
    parser.add_argument("--platforms", help="Comma-separated platforms: weibo,zhihu,bilibili,36kr,douyin")
    parser.add_argument("--keywords", help="Comma-separated keywords, e.g. AI,商业,独立开发,效率")
    parser.add_argument("--limit", type=int, default=20, help="Max items to return")
    parser.add_argument("--min-score", type=float, default=0.0, help="Min relevance score threshold (0.0 - 1.0)")
    parser.add_argument("--json", help="JSON payload string")
    parser.add_argument("--file", help="Path to JSON file containing parameters")
    args = parser.parse_args()

    platforms = None
    keywords = None
    limit = args.limit
    min_score = args.min_score

    payload = {}
    if args.file and Path(args.file).exists():
        try:
            payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
        except Exception:
            pass
    elif args.json:
        try:
            payload = json.loads(args.json)
        except Exception:
            pass
    elif not (args.platforms or args.keywords) and not sys.stdin.isatty():
        try:
            stdin_data = sys.stdin.read().strip()
            if stdin_data:
                payload = json.loads(stdin_data)
        except Exception:
            pass

    if payload:
        if "platforms" in payload:
            platforms = payload["platforms"]
        if "keywords" in payload:
            keywords = payload["keywords"]
        if "limit" in payload:
            limit = int(payload["limit"])
        if "min_score" in payload:
            min_score = float(payload["min_score"])

    if platforms is None and args.platforms:
        platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    if keywords is None and args.keywords:
        keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]

    results = run_radar(
        platforms=platforms,
        keywords=keywords,
        limit=limit,
        min_score=min_score
    )

    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
