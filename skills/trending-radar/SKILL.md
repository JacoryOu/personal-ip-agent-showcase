---
name: trending_radar
description: 'Fetches and aggregates real-time trending topics across major platforms (Weibo, Zhihu, Bilibili, 36Kr, Douyin) with keyword filtering, relevance scoring, and offline fallback.'
entrypoint: scripts/radar.py
runner_mode: restricted_token
permissions:
  - network:read
  - filesystem:isolated
parameters:
  type: object
  properties:
    platforms:
      type: array
      items:
        type: string
      description: 'Target platforms to aggregate (e.g. [weibo, zhihu, bilibili, 36kr, douyin]). Defaults to all.'
    keywords:
      type: array
      items:
        type: string
      description: 'Keywords to filter and score topics (e.g. [AI, 商业, 独立开发, 效率]). If empty, returns top trending.'
    limit:
      type: integer
      description: 'Maximum number of topics to return. Defaults to 20.'
      default: 20
    min_score:
      type: number
      description: 'Minimum relevance score threshold between 0.0 and 1.0. Defaults to 0.0.'
      default: 0.0
  required: []
---

# Trending Radar Skill

Automated multi-platform trending radar running inside the Windows Native Sandboxed environment (unner_mode: restricted_token).

## Capabilities
1. **Multi-Source Aggregation**: Fetches hot search lists and trending articles across Weibo, Zhihu, Bilibili, 36Kr, and Douyin.
2. **Offline Fallback Guarantee**: If external networks are inaccessible, rate-limited, or blocked, seamlessly supplies rich, realistic domain-specific trending topics.
3. **Keyword Filtering & Relevance Scoring**: Evaluates topic relevance against user-specified cognitive domains (AI, 商业, 独立开发, 效率) and computes normalized relevance scores.
4. **Structured Output**: Produces standardized topic objects with title, hot value, platform, category, summary, URL, and score.

## Internal Module Layout (2026-10 refactor)

The Skill Engine still invokes exactly one entrypoint: scripts/radar.py.
The script was split by responsibility; the CLI contract is unchanged.

| File | Responsibility |
| --- | --- |
| scripts/radar.py | CLI entrypoint + compatibility re-exports (USER_AGENT, FALLBACK_TOPICS, PLATFORM_FETCHERS, 
un_radar, main, per-platform fetchers) |
| scripts/_data.py | Static constants: user agent, fallback topic pool, platform score weights |
| scripts/_fetchers.py | Per-platform HTTP fetchers (Weibo, Zhihu, Bilibili, 36Kr, Douyin) and the platform dispatch map |
| scripts/_core.py | Relevance scoring, aggregation and result shaping |

Guarantees:
- CLI flags, stdout JSON schema and exit codes are unchanged.
- Offline fallback behaviour and network access pattern are unchanged.
- No new sandbox capability is claimed: execution still happens under the
  Skill Engine runner mode declared in the frontmatter
  (
estricted_token), with the guarantees/limits documented in
  docs/architecture/10_Sandbox_and_Permission_Model.md.
