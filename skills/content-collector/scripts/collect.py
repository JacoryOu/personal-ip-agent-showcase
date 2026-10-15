# -*- coding: utf-8 -*-
import argparse
import html
import json
import os
from pathlib import Path
import re
import sys
import urllib.request
import urllib.parse

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def clean_title_string(raw_title: str) -> str:
    if not raw_title:
        return ""
    t = html.unescape(raw_title).strip()
    t = re.sub(r"<[^>]+>", "", t).strip()
    # Strip site suffixes
    t = re.sub(r"[\s\-_\|]+(微信公众平台|知乎|36氪|知乎专栏|Bilibili|简书|掘金|博客园|CSDN).*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"[\s\-_\|]+$", "", t).strip()
    return t


def extract_metadata_from_html(html_str: str, url: str = ""):
    title = ""
    author = ""
    publish_time = ""
    cover_image_url = ""

    # 1. WeChat specific extraction
    if "mp.weixin.qq.com" in url or 'id="js_content"' in html_str or 'class="rich_media_title"' in html_str:
        # WeChat title
        t_match = re.search(r'<h1[^>]*id="activity-name"[^>]*>(.*?)</h1>', html_str, re.DOTALL | re.IGNORECASE)
        if not t_match:
            t_match = re.search(r'<h2[^>]*class="[^"]*rich_media_title[^"]*"[^>]*>(.*?)</h2>', html_str, re.DOTALL | re.IGNORECASE)
        if t_match:
            title = clean_title_string(t_match.group(1))

        # WeChat author
        a_match = re.search(r'<span[^>]*class="[^"]*rich_media_meta_text[^"]*"[^>]*>(.*?)</span>', html_str, re.DOTALL | re.IGNORECASE)
        if not a_match:
            a_match = re.search(r'id="js_name"[^>]*>(.*?)</a>', html_str, re.DOTALL | re.IGNORECASE)
        if not a_match:
            a_match = re.search(r'var\s+nickname\s*=\s*["\']([^"\']+)["\']', html_str)
        if a_match:
            author = re.sub(r"<[^>]+>", "", html.unescape(a_match.group(1))).strip()

        # WeChat publish time
        pt_match = re.search(r'var\s+publish_time\s*=\s*["\']([^"\']+)["\']', html_str)
        if not pt_match:
            pt_match = re.search(r'var\s+ct\s*=\s*["\']?(\d{10})["\']?', html_str)
        if pt_match:
            publish_time = pt_match.group(1).strip()

        # WeChat cover
        c_match = re.search(r'var\s+msg_cdn_url\s*=\s*["\']([^"\']+)["\']', html_str)
        if c_match:
            cover_image_url = c_match.group(1).strip()

    # 2. Zhihu specific extraction
    if "zhihu.com" in url or 'class="Post-Title"' in html_str or 'class="Post-RichText"' in html_str:
        if not title:
            zt_match = re.search(r'<h1[^>]*class="[^"]*Post-Title[^"]*"[^>]*>(.*?)</h1>', html_str, re.DOTALL | re.IGNORECASE)
            if zt_match:
                title = clean_title_string(zt_match.group(1))

        if not author:
            za_match = re.search(r'<span[^>]*class="[^"]*AuthorInfo-name[^"]*"[^>]*>(.*?)</span>', html_str, re.DOTALL | re.IGNORECASE)
            if za_match:
                author = re.sub(r"<[^>]+>", "", html.unescape(za_match.group(1))).strip()

    # 3. OpenGraph & Meta Tags Fallback
    if not title:
        og_t = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', html_str, re.IGNORECASE)
        if not og_t:
            og_t = re.search(r'<meta[^>]*name=["\']twitter:title["\'][^>]*content=["\']([^"\']+)["\']', html_str, re.IGNORECASE)
        if og_t:
            title = clean_title_string(og_t.group(1))

    if not title:
        head_t = re.search(r'<title[^>]*>(.*?)</title>', html_str, re.DOTALL | re.IGNORECASE)
        if head_t:
            title = clean_title_string(head_t.group(1))

    if not title:
        h1_m = re.search(r'<h1[^>]*>(.*?)</h1>', html_str, re.DOTALL | re.IGNORECASE)
        if h1_m:
            title = clean_title_string(h1_m.group(1))

    if not author:
        meta_a = re.search(r'<meta[^>]*name=["\']author["\'][^>]*content=["\']([^"\']+)["\']', html_str, re.IGNORECASE)
        if not meta_a:
            meta_a = re.search(r'<meta[^>]*property=["\']article:author["\'][^>]*content=["\']([^"\']+)["\']', html_str, re.IGNORECASE)
        if meta_a:
            author = html.unescape(meta_a.group(1)).strip()

    if not publish_time:
        meta_pt = re.search(r'<meta[^>]*property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)["\']', html_str, re.IGNORECASE)
        if not meta_pt:
            meta_pt = re.search(r'<meta[^>]*name=["\'](?:pubdate|publishdate|date)["\'][^>]*content=["\']([^"\']+)["\']', html_str, re.IGNORECASE)
        if not meta_pt:
            meta_pt = re.search(r'<time[^>]*datetime=["\']([^"\']+)["\']', html_str, re.IGNORECASE)
        if meta_pt:
            publish_time = meta_pt.group(1).strip()

    if not cover_image_url:
        og_img = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html_str, re.IGNORECASE)
        if not og_img:
            og_img = re.search(r'<meta[^>]*name=["\']twitter:image["\'][^>]*content=["\']([^"\']+)["\']', html_str, re.IGNORECASE)
        if og_img:
            cover_image_url = html.unescape(og_img.group(1)).strip()

    # Fallback first img in body
    if not cover_image_url:
        img_m = re.search(r'<img[^>]*(?:data-src|src)=["\'](https?://[^"\']+)["\']', html_str, re.IGNORECASE)
        if img_m:
            cover_image_url = img_m.group(1).strip()

    return {
        "title": title or "Untitled Extracted Article",
        "author": author or "Unknown Author",
        "publish_time": publish_time,
        "cover_image_url": cover_image_url,
    }


def html_to_clean_markdown(html_str: str, url: str = "") -> str:
    # 1. Extract target article container
    body_content = html_str

    # WeChat container
    if 'id="js_content"' in html_str:
        m = re.search(r'<div[^>]*id="js_content"[^>]*>(.*?)</div>\s*(?:<div|<script|<footer|$)', html_str, re.DOTALL | re.IGNORECASE)
        if m:
            body_content = m.group(1)

    # Zhihu container
    elif 'class="Post-RichText"' in html_str or 'class="RichContent-inner"' in html_str:
        m = re.search(r'<div[^>]*class="[^"]*(?:Post-RichText|RichContent-inner)[^"]*"[^>]*>(.*?)</div>', html_str, re.DOTALL | re.IGNORECASE)
        if m:
            body_content = m.group(1)

    # Generic article/main container
    else:
        m = re.search(r'<article[^>]*>(.*?)</article>', html_str, re.DOTALL | re.IGNORECASE)
        if not m:
            m = re.search(r'<main[^>]*>(.*?)</main>', html_str, re.DOTALL | re.IGNORECASE)
        if not m:
            m = re.search(r'<div[^>]*class="[^"]*(?:article-body|article-content|entry-content|post-content)[^"]*"[^>]*>(.*?)</div>', html_str, re.DOTALL | re.IGNORECASE)
        if m:
            body_content = m.group(1)

    # 2. Strip scripts, styles, iframes, svgs, forms, navs, headers, footers
    strip_tags = ["script", "style", "noscript", "header", "footer", "nav", "aside", "form", "iframe", "svg", "button", "select"]
    for tag in strip_tags:
        body_content = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", "", body_content, flags=re.DOTALL | re.IGNORECASE)

    # Strip elements with ad / banner / social / share / comment / copyright class/id
    body_content = re.sub(r'<div[^>]*(?:class|id)=["\'][^"\']*(?:advert|banner|sidebar|share|social|comment|footer|copyright)[^"\']*["\'][^>]*>.*?</div>', '', body_content, flags=re.DOTALL | re.IGNORECASE)

    # 3. Convert HTML elements to Markdown
    # Headings
    for i in range(6, 0, -1):
        def _h_repl(match):
            h_text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
            return f"\n\n{'#' * i} {h_text}\n\n"
        body_content = re.sub(rf"<h{i}[^>]*>(.*?)</h{i}>", _h_repl, body_content, flags=re.DOTALL | re.IGNORECASE)

    # Blockquotes
    def _bq_repl(match):
        bq_text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        lines = [f"> {line}" for line in bq_text.splitlines() if line.strip()]
        return "\n\n" + "\n".join(lines) + "\n\n"
    body_content = re.sub(r"<blockquote[^>]*>(.*?)</blockquote>", _bq_repl, body_content, flags=re.DOTALL | re.IGNORECASE)

    # Pre/Code blocks
    def _code_repl(match):
        c_text = html.unescape(re.sub(r"<[^>]+>", "", match.group(1)).strip())
        return f"\n\n```\n{c_text}\n```\n\n"
    body_content = re.sub(r"<pre[^>]*><code[^>]*>(.*?)</code></pre>", _code_repl, body_content, flags=re.DOTALL | re.IGNORECASE)
    body_content = re.sub(r"<pre[^>]*>(.*?)</pre>", _code_repl, body_content, flags=re.DOTALL | re.IGNORECASE)
    body_content = re.sub(r"<code[^>]*>(.*?)</code>", lambda m: f"`{re.sub(r'<[^>]+>', '', m.group(1)).strip()}`", body_content, flags=re.DOTALL | re.IGNORECASE)

    # Bold and Italic
    body_content = re.sub(r"<(?:strong|b)[^>]*>(.*?)</(?:strong|b)>", lambda m: f"**{re.sub(r'<[^>]+>', '', m.group(1)).strip()}**", body_content, flags=re.DOTALL | re.IGNORECASE)
    body_content = re.sub(r"<(?:em|i)[^>]*>(.*?)</(?:em|i)>", lambda m: f"*{re.sub(r'<[^>]+>', '', m.group(1)).strip()}*", body_content, flags=re.DOTALL | re.IGNORECASE)

    # Images (handling data-src for WeChat)
    def _img_repl(match):
        tag_str = match.group(0)
        src_m = re.search(r'(?:data-src|src)=["\']([^"\']+)["\']', tag_str, re.IGNORECASE)
        alt_m = re.search(r'alt=["\']([^"\']*)["\']', tag_str, re.IGNORECASE)
        src = src_m.group(1) if src_m else ""
        alt = alt_m.group(1) if alt_m else "图片"
        if src and not src.startswith("data:image"):
            return f"\n\n![{alt}]({src})\n\n"
        return ""
    body_content = re.sub(r"<img[^>]*>", _img_repl, body_content, flags=re.IGNORECASE)

    # Links
    def _link_repl(match):
        href_m = re.search(r'href=["\']([^"\']+)["\']', match.group(0), re.IGNORECASE)
        l_text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        href = href_m.group(1) if href_m else ""
        if href and l_text and not href.startswith("javascript:"):
            return f"[{l_text}]({href})"
        return l_text
    body_content = re.sub(r"<a\b[^>]*>(.*?)</a>", _link_repl, body_content, flags=re.DOTALL | re.IGNORECASE)

    # List items
    body_content = re.sub(r"<li[^>]*>(.*?)</li>", lambda m: f"\n- {re.sub(r'<[^>]+>', '', m.group(1)).strip()}", body_content, flags=re.DOTALL | re.IGNORECASE)
    body_content = re.sub(r"</?(?:ul|ol)[^>]*>", "\n", body_content, flags=re.IGNORECASE)

    # Paragraphs & Line breaks
    body_content = re.sub(r"<br\s*/?>", "\n", body_content, flags=re.IGNORECASE)
    body_content = re.sub(r"<p[^>]*>(.*?)</p>", lambda m: f"\n\n{m.group(1)}\n\n", body_content, flags=re.DOTALL | re.IGNORECASE)

    # Strip remaining HTML tags
    clean_text = re.sub(r"<[^>]+>", " ", body_content)
    clean_text = html.unescape(clean_text)

    # Normalize whitespace & multiple empty lines
    lines = [line.strip() for line in clean_text.splitlines()]
    non_empty_lines = []
    prev_empty = False
    for line in lines:
        if line:
            non_empty_lines.append(line)
            prev_empty = False
        elif not prev_empty:
            non_empty_lines.append("")
            prev_empty = True

    return "\n".join(non_empty_lines).strip()


def deconstruct_benchmark_blueprint(title: str, markdown_content: str):
    """Deconstructs article into BenchmarkBlueprint:
    - title_formula
    - opening_hook
    - key_stages
    - emotional_arc
    - golden_quotes
    - pacing
    """
    # 1. Title Formula
    title_formula = "痛点聚焦 + 认知解法型"
    if any(k in title for k in ["别再", "为什么说", "其实并不", "真相", "谎言", "并不是", "反常识", "认知差"]):
        title_formula = "反直觉/颠覆认知型（以颠覆既有偏见制造强烈反差）"
    elif re.search(r"\d+[\u4e2a\u6b65\u62db\u5927\u6761\u9879]", title) or any(k in title for k in ["指南", "全流程", "实战", "复盘", "清单", "SOP", "手把手", "教程"]):
        title_formula = "数字盘点/实战指南型（高可信度量化拆解与落地路径）"
    elif any(k in title for k in ["终局", "未来", "重塑", "趋势", "危机", "颠覆", "洗牌", "爆发", "演进"]):
        title_formula = "终局推演/趋势预警型（基于底层变量推演宏大未来）"
    elif any(k in title for k in ["我如何", "从零到", "一人", "年入", "普通人", "逆袭", "跃迁", "翻盘"]):
        title_formula = "故事痛点/个人跃迁型（以真实经历唤起强烈代入与渴望）"

    # Split lines and sentences
    lines = [l.strip() for l in markdown_content.splitlines() if l.strip()]
    sentences = []
    for line in lines:
        if line.startswith("#"):
            continue
        parts = re.split(r"[。！？!?\n]+", line)
        for p in parts:
            p_strip = p.strip()
            if len(p_strip) >= 8:
                sentences.append(p_strip)

    # 2. Opening Hook
    opening_hook = "开门见山提出问题或悬念"
    for s in sentences[:4]:
        if any(c in s for c in ["？", "?", "为什么", "然而", "如果", "很多人", "事实上", "真相"]):
            opening_hook = s
            break
    if opening_hook == "开门见山提出问题或悬念" and sentences:
        opening_hook = sentences[0]

    # 3. Key Stages (Structural Headings or Synthesized Logical Progression)
    headings = []
    for line in lines:
        if line.startswith("## ") or line.startswith("### ") or line.startswith("# "):
            h_text = re.sub(r"^#+\s*", "", line).strip()
            if h_text and len(h_text) <= 50:
                headings.append(h_text)

    if len(headings) >= 2:
        key_stages = headings[:6]
    else:
        key_stages = [
            "阶段一：悬念切入与痛点唤醒",
            "阶段二：核心根因与认知冲突",
            "阶段三：方法论与破局路径",
            "阶段四：终局推演与价值升华",
        ]

    # 4. Emotional Arc
    if any(k in markdown_content for k in ["危机", "风险", "陷阱", "警惕", "代价"]):
        emotional_arc = "危机警示 ➔ 深度排查 ➔ 避坑指南 ➔ 从容破局"
    elif any(k in markdown_content for k in ["困惑", "痛苦", "迷茫", "难题", "瓶颈"]):
        emotional_arc = "困惑/痛点共鸣 ➔ 认知重构 ➔ 理性剖析 ➔ 笃定/行动赋能"
    elif any(k in markdown_content for k in ["从零", "逆袭", "突破", "增长", "跃迁"]):
        emotional_arc = "逆境困境 ➔ 顿悟转折 ➔ 实践复盘 ➔ 愿景召唤"
    else:
        emotional_arc = "痛点唤醒 ➔ 认知颠覆 ➔ 框架推演 ➔ 价值升华"

    # 5. Golden Quotes
    quote_triggers = ["不是", "而是", "真正的", "在于", "核心逻辑", "本质上", "永远不要", "必须", "唯一的", "关键是", "核心在于", "第一性原理"]
    golden_quotes = []
    for s in sentences:
        if any(t in s for t in quote_triggers) and 12 <= len(s) <= 75:
            if s not in golden_quotes:
                golden_quotes.append(s)
        if len(golden_quotes) >= 4:
            break

    if len(golden_quotes) < 2:
        # Fallback to punchy declarative sentences
        for s in sentences:
            if 15 <= len(s) <= 60 and s not in golden_quotes:
                golden_quotes.append(s)
            if len(golden_quotes) >= 3:
                break

    # 6. Pacing
    pacing = "前 15% 悬念破题与痛点共鸣，中段 70% 递进式框架论证，后 15% 认知升华与行动指引"

    return {
        "title": title,
        "title_formula": title_formula,
        "opening_hook": opening_hook,
        "hook_style": opening_hook,
        "key_stages": key_stages,
        "structural_stages": key_stages,
        "emotional_arc": emotional_arc,
        "golden_quotes": golden_quotes,
        "pacing": pacing,
    }


def collect_article(url=None, html_content=None, content=None, title=None):
    effective_url = url or ""
    effective_html = html_content or ""
    effective_content = content or ""
    override_title = title or ""

    # 1. If URL given but no html, fetch it
    if effective_url and not effective_html and not effective_content:
        req = urllib.request.Request(
            effective_url,
            headers={"User-Agent": USER_AGENT}
        )
        try:
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                effective_html = resp.read().decode(charset, errors="replace")
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to fetch URL: {str(e)}",
                "source_url": effective_url,
            }

    # 2. Extract metadata and convert HTML -> Markdown
    if effective_html:
        meta = extract_metadata_from_html(effective_html, url=effective_url)
        cleaned_markdown = html_to_clean_markdown(effective_html, url=effective_url)
        art_title = override_title or meta["title"]
        author = meta["author"]
        publish_time = meta["publish_time"]
        cover_image_url = meta["cover_image_url"]
    elif effective_content:
        # Check if content itself is HTML
        if "<p>" in effective_content or "<div>" in effective_content or "<html>" in effective_content:
            meta = extract_metadata_from_html(effective_content, url=effective_url)
            cleaned_markdown = html_to_clean_markdown(effective_content, url=effective_url)
            art_title = override_title or meta["title"]
            author = meta["author"]
            publish_time = meta["publish_time"]
            cover_image_url = meta["cover_image_url"]
        else:
            cleaned_markdown = effective_content.strip()
            # Extract first line as title if not provided
            lines = [l.strip() for l in cleaned_markdown.splitlines() if l.strip()]
            if override_title:
                art_title = override_title
            elif lines and lines[0].startswith("# "):
                art_title = lines[0][2:].strip()
            elif lines:
                art_title = lines[0][:40].strip()
            else:
                art_title = "Raw Text Document"
            author = "Original Author"
            publish_time = ""
            cover_image_url = ""
    else:
        return {
            "success": False,
            "error": "No url, html_content, or content provided.",
        }

    # 3. BenchmarkBlueprint deconstruction
    blueprint = deconstruct_benchmark_blueprint(art_title, cleaned_markdown)

    return {
        "success": True,
        "title": art_title,
        "author": author,
        "publish_time": publish_time,
        "word_count": len(cleaned_markdown),
        "source_url": effective_url,
        "cover_image_url": cover_image_url,
        "cleaned_markdown": cleaned_markdown,
        "blueprint": blueprint,
    }


def main():
    parser = argparse.ArgumentParser(description="Content Collector & Benchmark Blueprint Extractor")
    parser.add_argument("--url", help="Article URL")
    parser.add_argument("--html", help="Raw HTML content")
    parser.add_argument("--content", help="Raw text or markdown content")
    parser.add_argument("--text", help="Alias for content")
    parser.add_argument("--title", help="Optional title override")
    parser.add_argument("--json", help="JSON payload string")
    parser.add_argument("--file", help="Path to JSON file containing parameters")
    args = parser.parse_args()

    url = args.url
    html_content = args.html
    content = args.content or args.text
    title = args.title

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
    elif not (url or html_content or content) and not sys.stdin.isatty():
        try:
            stdin_data = sys.stdin.read().strip()
            if stdin_data:
                try:
                    payload = json.loads(stdin_data)
                except Exception:
                    content = stdin_data
        except Exception:
            pass

    if payload:
        url = payload.get("url", url)
        html_content = payload.get("html_content") or payload.get("html", html_content)
        content = payload.get("content") or payload.get("text", content)
        title = payload.get("title", title)

    result = collect_article(
        url=url,
        html_content=html_content,
        content=content,
        title=title
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()