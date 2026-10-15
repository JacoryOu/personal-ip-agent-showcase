---
name: media_article_extractor
description: Cleanly extracts article title, author, publish date, and main body text from WeChat, Zhihu, and web URLs or HTML using Trafilatura, stripping advertisements and boilerplates.
entrypoint: scripts/extract.py
runner_mode: restricted_token
permissions:
  - network:read
  - filesystem:isolated
parameters:
  type: object
  properties:
    url:
      type: string
      description: The HTTP/HTTPS web address of the article (e.g. WeChat, Zhihu, medium, blog post).
    html_content:
      type: string
      description: Optional raw HTML string to extract without network requests.
  required: []
---

# Media Article Extractor

This skill wraps the industrial-grade Trafilatura engine inside a Windows Native Sandboxed Runner. It extracts clean, structured content while filtering out junk elements, sidebars, cookie notices, and advertisements.
