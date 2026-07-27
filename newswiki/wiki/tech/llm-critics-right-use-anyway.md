---
title: "The LLM Critics Are Right. I Use LLMs Anyway."
source: "https://www.theocharis.dev/blog/llm-critics-are-right-i-use-llms-anyway/"
published: "2026-07-15"
created: "2026-07-25"
description: "I almost agree with all of the LLM critics, yet I still use LLMs a lot. I know this sounds like I am delusional, but I don't think I am alone with it."
author:
  - "[[Jeremy Theocharis]]"
topics:
  - tech
  - career
  - design
---

# [The LLM Critics Are Right. I Use LLMs Anyway.](https://www.theocharis.dev/blog/llm-critics-are-right-i-use-llms-anyway/)

## Core View
- The 'dissonance' of LLM usage: many senior engineers agree with critics regarding 'AI slop' and ethical concerns but continue to use tools like [[tech/claude-code|Claude Code]] to amplify their own thinking.
- Risks to [[tech/open-source-software|OSS]]: The flood of low-effort LLM PRs erodes trust, leading some projects (e.g., Zig, Gentoo) to refuse AI-generated contributions.
- Impact on [[career/junior-engineers|Junior Engineers]]: LLMs automate mundane tasks, potentially removing the incentive for seniors to teach juniors and making it harder to gauge a junior's actual effort and growth.
- Geopolitical and Corporate Risk: Dependence on frontier models (e.g., [[hubs/anthropic|Anthropic]]) exposes users to abrupt export controls and corporate pricing shifts; local-weights models are the primary hedge.
- The 'Amplification' Principle: LLMs do not replace thinking; they amplify existing opinions, structures, and frameworks. High-quality output requires a human to put thought behind the prompt.
- Practical Workflow Patterns: Using the '/grill-me' technique (relentless interviewing) and 'Ralph Wiggum loops' (sub-agents ripping apart plans) to force human rigor and eliminate hallucinations.

## Technical Strategies for Quality
- Intuition Probing: Letting an LLM hallucinate an expected API or UX before showing it the real design to test if the design matches common human expectations.
- The 3-Sentence Problem Statement: Forcing a concise 'Problem', 'Shipping', and 'Not Shipping' statement to ensure human readability and factual accuracy.
- Expertise Requirement: LLMs are most dangerous when used in fields where the user cannot distinguish 'good' from 'dogshit'; they are best used as learning tools when a clear feedback loop (e.g., code compiling) exists.

## Key Takeaways
- LLMs should be used to make fewer things of higher quality, rather than more things of lower quality.
- Trust is the primary currency in the AI era; credibility is maintained by only publishing work the author would be willing to read aloud in front of an audience.
- Local models are essential for independence from geopolitical instability and corporate volatility.

## Related Articles

- [[tech/ai-food-metadata|Building Food Metadata with LLM Juries, Context Optimization & Multimodal AI]]
- [[tech/local-llm-question-categorization|Fine Tuning a Local LLM to Categorize Questions]]
- [[tech/best-books-for-software-engineers|The Best Books I ever read: Suggestions for a software engineer.]]

---
**Topics**: [[tech/_index|Tech]], [[career/_index|Career]], [[design/_index|Design]]  
**Tags**: #tech #llm #software-engineering
