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
  - career
---

# [There's no such thing as a small software team anymore](https://jacob.gold/posts/theres-no-such-thing-as-a-small-software-team/)

## Core View
- Small software teams running 20–100 AI coding agents in parallel can generate 10× the commit/PR volume of traditional teams (500 commits, 200 pushes, 100 PRs per busy day vs. 50/20/10).
- Uber's thousands-of-microservices model — once seen as extreme — becomes the new normal because high modularity enables "embarrassingly parallel" agent work across services.
- Modularity used to be expensive (boilerplate, plumbing, CI config); AI agents now write that overhead, making fine-grained splitting cheap.
- Coding agents are context-limited: modules small enough to fit in a context window dramatically improve agent performance.
- The modularity of your codebase now directly determines how many agents you can run effectively — design for it from the start.

## Key Takeaways
- AI agents turn modularity from a cost into a leverage point: more/smaller modules = more parallel agents = higher throughput.
- Teams that don't design for modularity will hit merge-conflict and context-window bottlenecks as agent counts scale.
- Uber's microservice architecture prefigured the agent-era workflow; its "extreme" approach is now a practical template.

---
**Topics**: [[tech/_index|科技]], [[career/_index|职场]]  
**Tags**: #tech #career
