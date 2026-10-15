# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import concurrent.futures

from _data import FALLBACK_TOPICS
from _fetchers import (
    fetch_36kr,
    fetch_bilibili,
    fetch_douyin,
    fetch_weibo,
    fetch_zhihu,
)



PLATFORM_FETCHERS = {
    "weibo": fetch_weibo,
    "zhihu": fetch_zhihu,
    "bilibili": fetch_bilibili,
    "36kr": fetch_36kr,
    "douyin": fetch_douyin,
}

def calculate_relevance_score(item, keywords):
    hot_value = item.get("hot_value", 0)
    hot_factor = min(1.0, hot_value / 10000000.0)

    if not keywords:
        return round(min(1.0, 0.5 + 0.5 * hot_factor), 3)

    title = item.get("title", "").lower()
    summary = item.get("summary", "").lower()
    category = item.get("category", "").lower()

    title_matches = 0
    cat_matches = 0
    sum_matches = 0

    for kw in keywords:
        kw_lower = kw.strip().lower()
        if not kw_lower:
            continue
        if kw_lower in title:
            title_matches += 1
        if kw_lower in category:
            cat_matches += 1
        if kw_lower in summary:
            sum_matches += 1

    total_hits = title_matches + cat_matches + sum_matches
    if total_hits == 0:
        return 0.0

    raw_score = (
        min(0.65, title_matches * 0.40) +
        min(0.20, cat_matches * 0.20) +
        min(0.15, sum_matches * 0.10) +
        (hot_factor * 0.10)
    )
    return round(min(1.0, max(0.1, raw_score)), 3)

def run_radar(platforms=None, keywords=None, limit=20, min_score=0.0):
    if not platforms:
        selected_platforms = list(PLATFORM_FETCHERS.keys())
    else:
        selected_platforms = [p.lower().strip() for p in platforms if p.lower().strip() in PLATFORM_FETCHERS]
        if not selected_platforms:
            selected_platforms = list(PLATFORM_FETCHERS.keys())

    all_items = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(selected_platforms)) as executor:
        future_to_platform = {executor.submit(PLATFORM_FETCHERS[p]): p for p in selected_platforms}
        for future in concurrent.futures.as_completed(future_to_platform):
            p = future_to_platform[future]
            try:
                items = future.result()
            except Exception:
                items = FALLBACK_TOPICS.get(p, [])
            for item in items:
                score = calculate_relevance_score(item, keywords)
                item_with_score = dict(item)
                item_with_score["score"] = score
                if keywords:
                    if score > 0.0 and score >= min_score:
                        all_items.append(item_with_score)
                else:
                    if score >= min_score:
                        all_items.append(item_with_score)

    # Distribute topics across platforms so one platform (e.g. Douyin with 10M+ values) doesn't crowd out others
    by_platform = {}
    for item in all_items:
        p = item.get("platform", "unknown")
        by_platform.setdefault(p, []).append(item)

    for p in by_platform:
        by_platform[p].sort(key=lambda x: (x.get("score", 0.0), x.get("hot_value", 0)), reverse=True)

    balanced_items = []
    max_len = max((len(lst) for lst in by_platform.values()), default=0)
    for idx in range(max_len):
        for p in selected_platforms:
            lst = by_platform.get(p, [])
            if idx < len(lst):
                balanced_items.append(lst[idx])
                if len(balanced_items) >= limit:
                    break
    if keywords:
        balanced_items.sort(key=lambda x: (x.get("score", 0.0), x.get("hot_value", 0)), reverse=True)

    return balanced_items[:limit]

