---
title: "A Road to Lisp: Which Lisp"
source: "https://scotto.me/blog/2026-07-17-which-lisp/"
published: "2026-07-17"
created: "2026-07-18"
description: "Comparison of modern Lisp dialects"
author:
  - "[[Elia Scotto (hello@scotto.me)]]"
topics:
  - tech
---

# [A Road to Lisp: Which Lisp](https://scotto.me/blog/2026-07-17-which-lisp/)

## Core View
- Lisp is a family of programming languages, not a single language, with over 20 dialects due to shared syntax and divergent semantics.
- [AI Synthesis] Common Lisp (CL) is the most mature and standardized dialect, with ANSI specification from 1994; supports native compilation, powerful REPL, and advanced features like condition and restart system.
- [AI Synthesis] Clojure runs on the JVM, offers functional programming with immutable data, and provides seamless integration with Java ecosystems; used by Nubank, Walmart, Netflix, and Apple.
- [AI Synthesis] Racket is language-oriented, enabling creation of new programming languages and DSLs; ideal for education, research, and prototyping with built-in GUI and development tools.
- [AI Synthesis] Elisp is used for customizing Emacs, offering real-time editor extension without reload.

## Dialect Highlights
- [[tech/common-lisp|Common Lisp]] excels in performance and long-running processes, with native compilation and powerful debugging via live REPL.
- [[tech/clojure|Clojure]] shines in data-intensive systems and large-scale software, with immutable data, lazy sequences, and seamless JVM integration.
- [[tech/racket|Racket]] is ideal for language design, compiler development, and educational tools, with a rich ecosystem of libraries and a beginner-friendly IDE.
- [[tech/elisp|Elisp]] enables deep customization of Emacs, making it a practical tool for developers who rely on the editor for daily workflows.

## Syntax and Use Cases
- Common Lisp uses `LOOP` and `CASE` for iteration and control flow; Clojure uses `reduce` and keywords for functional programming; Racket uses `for/fold` and `match` for pattern matching and iteration.
- Clojure's syntax is more modern and concise, with vectors and keywords, while Common Lisp retains older Lisp idioms.
- Racket's `#lang` system allows creation of new language variants, making it a powerful tool for language designers and researchers.

## Key Takeaways
- Clojure is recommended for most developers due to its modern syntax, strong tooling, and production use in major tech companies.
- Common Lisp offers superior performance and a powerful interactive development environment, ideal for research and prototyping.
- Racket is best suited for language design, education, and building DSLs with built-in GUI and development support.
- Elisp is a practical tool for Emacs users who want to extend the editor's functionality.

## Related Articles

- [[tech/a-road-to-lisp-why-lisp|A road to Lisp: Why Lisp]]

---
**Topics**: [[tech/_index|Tech]]  
**Tags**: #lisp #programming-languages #functional-programming #ai-tooling
