---
title: "Best Simple System for Now"
source: "https://dannorth.net/blog/best-simple-system-for-now/"
published: "2025-02-03"
created: "2026-07-07"
description: "You can have your cake and eat it, as long as you bake it carefully. 'We can do this the quick way and pay later, or the thorough way and pay now.' This seems to be a fundamental dichotomy in software development, between 'perfectionism' and 'pragmatism', but I do not think it has to be a trade-off at all."
author:
  - "[[Daniel Terhorst-North]]"
topics:
  - tech
---

# [Best Simple System for Now](https://dannorth.net/blog/best-simple-system-for-now/)

## Core View
- Proposes a middle path between 'perfectionism' and 'pragmatism' in software development through the concept of the 'Best Simple System for Now' (BSSN).
- The BSSN is defined as the simplest system that meets current product needs, written to an appropriate standard with no extraneous or over-engineered code.
- Emphasizes designing for the present, not anticipating the future, to avoid speculative complexity and technical debt.
- Highlights the importance of simplicity, quality, and maintainability—especially in early development stages—without sacrificing long-term flexibility.
- Cites John Gall’s law: 'A complex system that works is invariably found to have evolved from a simple system that worked.'

## Key Principles of BSSN
- For Now: The system should not anticipate future needs. Designing for the current context prevents over-engineering and reduces risk of technical debt.
- Simple: The system should be as minimal as possible while still meeting current requirements. Complexity should be directly tied to current needs.
- Best: Code should be intention-revealing, composable, and domain-based, following CUPID principles (Composable, Unix, Predictable, Idiomatic, Domain-based).
- Iterative and Evolvable: The BSSN is not a one-time solution but a foundation that can evolve as requirements change.

## Case Studies
- JSON Library Example: A trading client needed a JSON library for Java. Instead of choosing a full-featured library, a lightweight interface was implemented for nine entity types, resulting in zero dependencies, high performance, and easy extensibility.
- XML Streamer Example: A Java-based XML streamer was built for a simple object-to-XML conversion. Though initially rejected as 'too simple', it evolved into XStream—a widely adopted, production-grade tool used even on the International Space Station.

## Why BSSN Matters
- Reduces risk by avoiding large, complex systems that are hard to maintain and debug.
- Lowers cost by reducing the need for extensive testing, documentation, and long-term maintenance.
- Improves developer velocity through early feedback and small, testable increments.
- Aligns with agile and iterative development principles, reducing 'cost of delay' and opportunity cost.
- Supports a culture of 'joyful code'—code that is readable, maintainable, and enjoyable to work with.

## Challenges and Counterarguments
- Criticism: BSSN may be seen as 'overkill' for prototypes or 'incomplete' for early-stage products.
- Counter: Early delivery of a partial product with high quality leads to faster customer adoption and better feedback loops.
- Counter: BSSN reduces long-term risk by avoiding large, untested systems and enables faster iteration and learning.

## Cultural and Philosophical Underpinnings
- Rooted in the idea of 'seeing what is really there'—a shift from pattern-matching to conscious observation.
- Influenced by thinkers like Richard Gabriel (worse is better), Kent Beck (make the change easy), and Alan Kay (objects as communicating cells).
- Encourages a shift from scarcity mindset to abundance mindset—where both quality and speed can coexist.

## Key Takeaways
- The 'Best Simple System for Now' is a pragmatic, high-quality approach to software development that balances speed and reliability.
- Simplicity is context-dependent and should be defined by current requirements, not future speculation.
- Early, iterative delivery with high-quality, minimal systems reduces risk and improves long-term maintainability.
- The BSSN approach fosters a culture of joyful, maintainable code that evolves with user needs.

---
**Topics**: [[tech/best-simple-system-for-now|Best Simple System for Now]]  
**Tags**: #tech #software-design #agile #code-quality #pragmatic-development
