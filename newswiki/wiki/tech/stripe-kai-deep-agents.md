---
title: "How Stripe Built Kai on Deep Agents in 1 Week"
source: "https://www.langchain.com/blog/how-stripe-built-their-knowledge-ai-platform-on-deep-agents"
published: "2026-08-03"
created: "2026-08-07"
description: "Learn how Stripe built Kai, a company-wide AI agent on LangChain, LangGraph, and Deep Agents, reaching 5,000 users in roughly 4 weeks."
author:
  - "[[Sofia Sulikowski]]"
topics:
  - tech
---

# [How Stripe Built Kai on Deep Agents in 1 Week](https://www.langchain.com/blog/how-stripe-built-their-knowledge-ai-platform-on-deep-agents)

## Core View
- Stripe developed 'Kai', a company-wide productivity agent, utilizing the [[tech/langchain|LangChain]] and [[tech/langgraph|LangGraph]] stack, specifically leveraging the 'Deep Agents' open-source harness.
- The architecture is layered: Deep Agents (base primitives) $\rightarrow$ Stripe-specific harness (security/infra) $\rightarrow$ Configuration layer (custom personas/skills) $\rightarrow$ Kai UI.
- Production-readiness was achieved through three key middleware components: a virtual filesystem (S3-backed) for persistent session context, a sandboxed environment for secure code execution (analytics/PDF processing), and summarization middleware to manage long-turn context limits.
- Kai employs a federated 'skills' model with over 1,000 skills from 100+ teams, using a two-pass dynamic tool loading system to prevent model quality degradation caused by oversized system prompts.
- The project validated Stripe's investment in a Python-native stack, as a single engineer built the initial version in one week using Deep Agents' primitives.
- Adoption grew from ~300 to 5,000+ users in four weeks, with particularly high penetration in non-engineering functions like Marketing (95%) and GTM (87%).

## Key Takeaways
- Deep Agents abstracts the 'non-domain' agent infrastructure, allowing engineers to focus on specific business workflows.
- Virtual filesystems and sandboxing are critical for transforming generic LLMs into reliable, production-ready company agents.
- Dynamic skill selection is essential when scaling to hundreds of internal tools to maintain frontier model performance.

## Related Articles

- [[tech/no-small-software-teams|There's no such thing as a small software team anymore]]
- [[tech/why-write-code-in-2026|Why write code in 2026]]
- [[business/ai-software-company-moats|How does AI affect software company moats?]]
- [[tech/rogue-ai-agents-guide|失控AI机器人世界的用户指南]]

---
**Topics**: [[tech/_index|Tech]]  
**Tags**: #tech #ai-agents #stripe
