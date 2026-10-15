---
name: content_multi_distributor
description: "Formats any article or draft into 4 distinct distribution formats: Xiaohongshu card format with emojis and 5 hashtags, WeChat Official account format with bold golden quotes and interactive engagement CTA, Twitter/X 5~8 tweet cascade thread with retweet prompt, and a 3-minute Video Monologue script with 3-second golden hook and visual/pacing cues."
entrypoint: scripts/distribute.py
runner_mode: restricted_token
permissions:
  - filesystem:isolated
parameters:
  type: object
  properties:
    content:
      type: string
      description: "The full article or draft text to adapt into multi-platform distribution formats."
    title:
      type: string
      description: "Optional article headline or topic."
    platforms:
      type: array
      items:
        type: string
      description: "Optional list of platforms to generate (xiaohongshu, wechat, twitter, video). Defaults to all four."
  required:
    - content
---

# Multi-Platform Content Distribution Formatter Skill

This skill runs inside the Windows Native Sandboxed Runner with credentials stripped and directory isolation. It deterministically adapts long-form articles into four platform-native distribution formats:
1. **Xiaohongshu (小红书)**: Catchy title with emojis, structured card paragraphs, pain points, call to action, and 5 hashtags (#话题).
2. **WeChat Official (微信公众号)**: Clean Markdown, bold golden quotes, section takeaways, interactive engagement CTA, structured section illustrations (section_illustrations) with 16:9 prompts for Agnes Image 2.5 Flash/Wanx/DALL-E, and automated markdown footnote references (footnotes).
3. **Twitter / X Thread**: 5~8 connected tweets labeled (1/N, 2/N...), strong opening hook, key takeaways, closing retweet prompt.
4. **Video Monologue Script (短视频口播脚本)**: 3-second golden hook, spoken conversational dialogue, clear visual/pacing cues like `[镜头切换/特写]`, `[停顿思考]`.


## Internal Module Layout (2026-10 refactor)

The Skill Engine still invokes exactly one entrypoint: scripts/distribute.py.
The 1000-line script was split by responsibility; the CLI contract is unchanged.

| File | Responsibility |
| --- | --- |
| scripts/distribute.py | CLI entrypoint, distribute_content, main, and compatibility re-exports of every public helper |
| scripts/_content.py | Title cleaning, content parsing, key-sentence extraction, hashtag derivation |
| scripts/_markdown_links.py | Markdown inline-link parsing and reference-definition pattern |
| scripts/_references.py | Footnote extraction and link-to-footnote replacement (re-exports the link parser for compatibility) |
| scripts/_formatters_xhs.py | Xiaohongshu card formatter and section illustration prompts |
| scripts/_formatters.py | WeChat / Twitter / video formatters, plus compatibility re-exports of the Xiaohongshu formatters |

Guarantees:
- CLI flags, stdout JSON schema and exit codes are unchanged.
- Formatter output is byte-for-byte identical for the same input: this was a
  structural split only, no formatting logic was altered.
- No new sandbox capability is claimed; execution still uses the runner mode
  declared in the frontmatter and the guarantees/limits documented in
  docs/architecture/10_Sandbox_and_Permission_Model.md.
