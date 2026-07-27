---
title: "How I use LLMs as a staff engineer in 2026"
source: "https://www.seangoedecke.com/how-i-use-llms-in-2026/"
created: "2026-07-16"
topics:
  - career
---

# [How I use LLMs as a staff engineer in 2026](https://www.seangoedecke.com/how-i-use-llms-in-2026/)

## Core View
- Use LLMs for smart autocomplete with Copilot and for short tactical changes in unfamiliar domains, always reviewed by a SME.
- Write use-once-and-throwaway research code and ask targeted questions to learn about new topics like Unity game engine.
- Use LLMs for last-resort bugfixes and for big-picture proofreading of long-form English communication.
- [AI Synthesis] LLMs are now used to produce entire PRs in areas the engineer is familiar with, reducing manual typing and enabling faster iteration.
- [AI Synthesis] LLMs are used to investigate and diagnose 80% of bugs independently, especially when given cross-repo context.
- [AI Synthesis] The engineer performs extensive evaluation of agent-generated changes, rejecting most due to misalignment with intent, and only accepting changes after thorough review.
- [AI Synthesis] LLMs are used to generate test scripts and perform local setup tasks (e.g., Node version issues), replacing manual Googling with faster, automated troubleshooting.
- [AI Synthesis] The engineer still manually writes PR descriptions to ensure clarity and human oversight, as LLMs over-communicate and lack nuance.

## Tasks I Don’t Use AI For
- Do not use LLMs to write full PRs, ADRs, or technical communications — prefer human-written content to signal personal review and intent.
- Do not use LLMs to write blog posts, though drafts are reviewed for feedback.
- Do not use LLMs for UI testing or for changes requiring high-level design judgment.

## Key Shifts in 2025–2026
- Shifted from using LLMs in isolated, low-risk tasks to using them for full PRs and bug investigation with minimal supervision.
- [AI Synthesis] Agents now operate with greater autonomy and recover from errors more effectively than early versions, though human oversight remains critical for complex or ambiguous cases.
- [AI Synthesis] Human expertise is still essential in narrowing down bug search space — the engineer actively provides context, builds mental models, and guides agent sessions to improve accuracy.

## Key Takeaways
- LLMs are now trusted for full PR generation in familiar domains, reducing manual effort and accelerating development cycles.
- Bug diagnosis has improved dramatically, with 80% of issues resolved autonomously by agents when given sufficient context.
- Human review remains essential — even with powerful agents, rejection rates are high due to misaligned intent or over-optimization.
- Testing and local setup tasks are now efficiently delegated to agents, reducing time spent on trivial debugging.
- The core balance is shifting toward AI automation, but human judgment and oversight are still required for quality and trust.

## Related Articles

- [[tech/ai-password-handover-experiment|把密码交给AI是一种什么体验？我做了一次实测]]

---
**Topics**: [[career/ai-impact|AI and Employment Trends]], [[career/ai-in-the-workplace|AI in Professional Practice]], [[tech/ai-agent-tools|AI Agents and Development Tools]]  
**Tags**: #ai-in-career #staff-engineering #ai-automation
