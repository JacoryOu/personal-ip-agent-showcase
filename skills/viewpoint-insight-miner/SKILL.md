---
name: viewpoint_insight_miner
description: "Deeply analyzes article text or conversational transcripts to mine Thinking DNA (vocabulary habits, logic preferences, core values), benchmark blueprints (structural skeletons, emotional arcs), or debate clash points."
entrypoint: scripts/mine.py
runner_mode: restricted_token
permissions:
  - filesystem:isolated
parameters:
  type: object
  properties:
    content:
      type: string
      description: "Article text or conversation transcript to analyze."
    analysis_type:
      type: string
      enum: [own_work, benchmark, dialogue]
      default: own_work
      description: "Analysis focus: own_work for thinking DNA, benchmark for skeleton & clash points, dialogue for conversational insights."
  required:
    - content
---

# Viewpoint & Insight Miner

An analytical skill running in the Windows Native Sandboxed environment. It extracts semantic patterns, argumentative logic, and narrative structures from long-form content.
