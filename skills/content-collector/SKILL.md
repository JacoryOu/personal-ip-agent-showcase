---
name: content_collector
description: "Scrapes and parses articles from WeChat Official Accounts, Zhihu, and generic web pages or raw text. Cleans HTML into pure Markdown without ads/navbars, extracts rich metadata, and automatically deconstructs content skeletons in BenchmarkBlueprint format (title formula, opening hook, key stages/headings, emotional arc, golden quotes, pacing) ready for '拆骨换皮' creative restructuring."
entrypoint: scripts/collect.py
runner_mode: restricted_token
permissions:
  - network:read
  - filesystem:isolated
parameters:
  type: object
  properties:
    url:
      type: string
      description: "Target article HTTP/HTTPS URL (WeChat, Zhihu, 36Kr, blog post, generic web page)."
    html_content:
      type: string
      description: "Optional raw HTML string to clean and deconstruct without network requests."
    content:
      type: string
      description: "Optional raw article text or Markdown string to analyze and deconstruct."
    title:
      type: string
      description: "Optional custom title to override extracted title."
  required: []
---

# Content Collector & Benchmark Blueprint Deconstruction Skill

Automated article ingestion and structural skeleton extractor running inside the Windows Native Sandboxed environment (`runner_mode: restricted_token`).

## Capabilities
1. **Multi-Source Scraping & Parsing**: Supports WeChat Official Accounts (`mp.weixin.qq.com`), Zhihu (`zhihu.com`), and general web articles.
2. **Readability Cleaning**: Strips advertisements, navigation bars, cookie banners, scripts, and sidebar clutter, converting rich HTML into clean Markdown.
3. **Metadata Extraction**: Extracts article title, author, publish timestamp/date, word count, source URL, and cover image.
4. **Benchmark Blueprint ("拆骨换皮")**:
   - **Title Formula**: Classifies headline archetype (e.g. 反直觉/颠覆认知型, 数字盘点/实战指南型, 终局推演/趋势预警型, 故事痛点/个人跃迁型).
   - **Opening Hook**: Extracts the opening suspenseful hook / question.
   - **Key Stages**: Identifies 3-5 structural progression phases / section headings.
   - **Emotional Arc**: Traces the reader's psychological journey (e.g. 痛点唤醒 ➔ 认知颠覆 ➔ 框架推演 ➔ 价值升华).
   - **Golden Quotes**: Curates 3-5 punchy, memorable, quote-worthy statements.
   - **Pacing**: Analyzes paragraph and narrative pacing.