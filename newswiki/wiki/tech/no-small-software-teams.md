---
title: "There's no such thing as a small software team anymore"
source: "https://jacob.gold/posts/theres-no-such-thing-as-a-small-software-team/"
published: "2026-08-20"
created: "2026-08-21"
description: "Uber infamously runs thousands of microservices. They ended up with so many services because hundreds of engineers wanted to deploy on their own schedule, with clear ownership of their code, instead of waiting in one giant merge queue.For decades a small team with 5 or 10 people writing code at the same time didn’t even need to consider doing this. On a busy day a small team might generate 50 commits/20 pushes/10 PRs. A small team today, running 20-100 agents in parallel, might generate 500 commits/200 pushes/100 PRs."
author:
  - "[[Jake Gold]]"
topics:
  - tech
---

# [There's no such thing as a small software team anymore](https://jacob.gold/posts/theres-no-such-thing-as-a-small-software-team/)

## Core View
- AI coding agents have fundamentally changed the scale of software production; a small team utilizing 20-100 agents can generate commit and PR volumes previously seen only in massive organizations like [[hubs/Uber|Uber]].
- High modularity (e.g., microservices) is now a necessity for small teams to enable 'embarrassingly parallel' workflows and prevent agents from creating net-negative productivity through merge conflicts and broken builds.
- The traditional overhead of modularity—such as boilerplate and CI configuration—has been neutralized because [[hubs/ai-agents|AI Agents]] can now automate these tasks.
- Modular design is critical for agent performance because smaller modules fit more effectively within the limited context windows of current LLMs.

## Key Takeaways
- Software architecture must now be designed for agent-parallelism, not just human-parallelism.
- Modularity is the primary lever for scaling the effective use of coding agents.

## Related Articles

- [[tech/why-write-code-in-2026|Why write code in 2026]]
- [[tech/stripe-kai-deep-agents|How Stripe Built Kai on Deep Agents in 1 Week]]
- [[business/ai-software-company-moats|How does AI affect software company moats?]]
- [[tech/rogue-ai-agents-guide|失控AI机器人世界的用户指南]]

---
**Topics**: [[tech/_index|Tech]]  
**Tags**: #ai-agents #software-architecture #modularity
