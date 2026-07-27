---
title: "Kimi K3, and what we can still learn from the pelican benchmark"
source: "https://simonwillison.net/2026/Jul/16/kimi-k3/"
created: "2026-07-25"
description: "Chinese AI lab Moonshot AI announced Kimi K3 this morning, describing it as their “most capable model to date, with 2.8 trillion parameters”. It’s currently available via their website and …"
author:
  - "[[Simon Willison]]"
topics:
  - tech
---

# [Kimi K3, and what we can still learn from the pelican benchmark](https://simonwillison.net/2026/Jul/16/kimi-k3/)

## Core View
- Moonshot AI released Kimi K3, a 2.8 trillion parameter model, described as the first "open 3T-class model" with an open weight release promised by July 27, 2026.
- Benchmarks indicate K3 generally outperforms [[tech/claude-opus-4.8|Claude Opus 4.8]] and [[tech/gpt-5.5|GPT-5.5]], but trails [[tech/claude-fable-5|Claude Fable 5]] and [[tech/gpt-5.6|GPT-5.6]].
- Kimi K3 is currently the leading model on Arena.ai’s Frontend Code arena, surpassing [[tech/claude-fable-5|Claude Fable 5]].
- Pricing has increased significantly to $3/million input and $15/million output tokens, aligning it with the [[tech/claude-sonnet|Claude Sonnet]] series and making it the most expensive model from a Chinese AI lab to date.
- The "pelican benchmark" (generating an SVG of a pelican on a bicycle) reveals high reasoning overhead, with K3 consuming 13,241 reasoning tokens for a single task.
- Analysis of token counts suggests Kimi K3 may utilize a hidden system prompt of approximately 85 tokens.
- [AI Synthesis] The shift toward premium pricing suggests Moonshot AI is pivoting from a growth-at-all-costs user acquisition strategy to a value-capture model targeting high-end enterprise and developer workloads.

## Key Takeaways
- Kimi K3 represents a massive scale-up in parameters (2.8T), competing directly with the top-tier frontier models.
- The 'pelican benchmark' is no longer a reliable proxy for general intelligence but remains a useful 'hello world' for estimating cost, reasoning effort, and spatial awareness.
- K3 demonstrates strong vision capabilities and a high proficiency in frontend code generation.

---
**Topics**: [[tech/_index|Tech]]  
**Tags**: #tech
