# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
import re
import urllib.parse
import urllib.request

from _data import FALLBACK_TOPICS, USER_AGENT



def fetch_weibo():
    try:
        req = urllib.request.Request(
            "https://weibo.com/ajax/side/hotSearch",
            headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = []
            realtime = data.get("data", {}).get("realtime", [])
            for entry in realtime[:20]:
                word = entry.get("word") or entry.get("note") or ""
                if not word:
                    continue
                hot = entry.get("num") or entry.get("raw_hot") or 100000
                items.append({
                    "title": word,
                    "hot_value": int(hot),
                    "platform": "weibo",
                    "category": entry.get("category", "综合"),
                    "summary": f"微博热搜：{word}",
                    "url": f"https://s.weibo.com/weibo?q={urllib.parse.quote(word)}"
                })
            if items:
                return items
    except Exception:
        pass
    return FALLBACK_TOPICS["weibo"]

def fetch_zhihu():
    try:
        req = urllib.request.Request(
            "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=25",
            headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = []
            for entry in data.get("data", []):
                target = entry.get("target", {})
                title = target.get("title", "")
                if not title:
                    continue
                detail_text = entry.get("detail_text", "0")
                match = re.search(r"(\d+(\.\d+)?)", detail_text)
                hot = int(float(match.group(1)) * 10000) if match else 500000
                url = target.get("url", "")
                if url.startswith("//"):
                    url = "https:" + url
                elif not url.startswith("http"):
                    url = f"https://www.zhihu.com/question/{target.get('id', '')}"
                items.append({
                    "title": title,
                    "hot_value": hot,
                    "platform": "zhihu",
                    "category": "问答",
                    "summary": target.get("excerpt", f"知乎热榜：{title}"),
                    "url": url
                })
            if items:
                return items
    except Exception:
        pass
    return FALLBACK_TOPICS["zhihu"]

def fetch_bilibili():
    try:
        req = urllib.request.Request(
            "https://api.bilibili.com/x/web-interface/popular?ps=25&pn=1",
            headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = []
            for entry in data.get("data", {}).get("list", []):
                title = entry.get("title", "")
                if not title:
                    continue
                hot = entry.get("stat", {}).get("view", 100000)
                bvid = entry.get("bvid", "")
                items.append({
                    "title": title,
                    "hot_value": int(hot),
                    "platform": "bilibili",
                    "category": entry.get("tname", "视频"),
                    "summary": entry.get("desc", f"B站热门：{title}"),
                    "url": entry.get("short_link_v2") or f"https://www.bilibili.com/video/{bvid}"
                })
            if items:
                return items
    except Exception:
        pass
    return FALLBACK_TOPICS["bilibili"]

def fetch_36kr():
    try:
        req = urllib.request.Request(
            "https://gateway.36kr.com/api/mis/nav/home/nav/realtime",
            headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
            data=b'{"partner_id":"web","pageEvent":0,"pageSize":25}'
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = []
            for entry in data.get("data", {}).get("itemList", []):
                mat = entry.get("templateMaterial", {})
                title = mat.get("widgetTitle") or mat.get("title", "")
                if not title:
                    continue
                item_id = mat.get("itemId", "")
                items.append({
                    "title": title,
                    "hot_value": int(mat.get("statRead", 80000)),
                    "platform": "36kr",
                    "category": "创投/商业",
                    "summary": mat.get("summary", f"36氪快讯：{title}"),
                    "url": f"https://36kr.com/p/{item_id}" if item_id else "https://36kr.com"
                })
            if items:
                return items
    except Exception:
        pass
    return FALLBACK_TOPICS["36kr"]

def fetch_douyin():
    try:
        req = urllib.request.Request(
            "https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/",
            headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = []
            for entry in data.get("word_list", [])[:20]:
                word = entry.get("word", "")
                if not word:
                    continue
                hot = entry.get("hot_value", 200000)
                items.append({
                    "title": word,
                    "hot_value": int(hot),
                    "platform": "douyin",
                    "category": "短视频",
                    "summary": f"抖音热点：{word}",
                    "url": f"https://www.douyin.com/search/{urllib.parse.quote(word)}"
                })
            if items:
                return items
    except Exception:
        pass
    return FALLBACK_TOPICS["douyin"]

