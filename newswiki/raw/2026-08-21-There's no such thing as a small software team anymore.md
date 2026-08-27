---
title: "There's no such thing as a small software team anymore"
source: "https://jacob.gold/posts/theres-no-such-thing-as-a-small-software-team/"
author:
  - "[[Jake Gold]]"
published: 2026-08-20
created: 2026-08-21
description: "Uber infamously runs thousands of microservices. They ended up with so many services because hundreds of engineers wanted to deploy on their own schedule, with clear ownership of their code, instead of waiting in one giant merge queue.For decades a small team with 5 or 10 people writing code at the same time didn’t even need to consider doing this. On a busy day a small team might generate 50 commits/20 pushes/10 PRs. A small team today, running 20-100 agents in parallel, might generate 500 commits/200 pushes/100 PRs."
---
Uber infamously runs [thousands of microservices](https://www.uber.com/us/en/blog/up-portable-microservices-ready-for-the-cloud/). They ended up with so many services because hundreds of engineers wanted to deploy on their own schedule, with clear ownership of their code, instead of waiting in one giant merge queue.

For decades a small team with 5 or 10 people writing code at the same time didn’t even need to consider doing this. On a busy day a small team might generate 50 commits/20 pushes/10 PRs. A small team today, running 20-100 agents in parallel, might generate 500 commits/200 pushes/100 PRs.

So Uber’s approach to modularity may have seemed extreme at the time, but it could become the new normal.

**One developer coding in a “single-threaded” way, editing one file at a time:** [![[_resources/2026-08-21-There's no such thing as a small software team anymore/6b763fa0686e6a4d55aaa34aa319fc48_MD5.webp]]](https://jacob.gold/images/theres-no-such-thing-as-a-small-software-team-vscode.webp)

**One developer coding in a “multi-threaded” way, using coding agents in parallel:**## The more modular your code, the more agents you can run

If you have a large monolithic service where every change has to be coordinated carefully, there’s a good chance two pieces of significant work will trample on each other and force you to resolve merge conflicts and refactor.

If you have thousands of microservices like Uber, you’ve got an “embarrassingly parallel” way of working on code. Fire up a coding agent for each one, tell it to “improve performance”, and there’s a good chance you ship significant improvements across all of them.

100+ coding agents running in parallel have to work well independently. If they spend all their time resolving merge conflicts, fixing broken builds, and creating deployment nightmares, you can end up with net-negative productivity.

## Modularity got cheap

Splitting things up used to be very expensive, since every service meant more boilerplate, plumbing, and CI config. Agents write all of that now, so the overhead matters a lot less.

Agents are also extremely context-limited. A module (whether it’s a service or a library) that’s small enough to fit in the context window dramatically improves coding agent performance.

The modularity of your codebase determines how many coding agents you can run in parallel effectively, so now it’s worth designing for it from the beginning.

[Hacker News](https://news.ycombinator.com/submitlink?t=There%27s%20no%20such%20thing%20as%20a%20small%20software%20team%20anymore&u=https%3A%2F%2Fjacob.gold%2Fposts%2Ftheres-no-such-thing-as-a-small-software-team%2F) [Discuss on Bluesky](https://bsky.app/profile/jacob.gold/post/3mtjir6vqhs2a)