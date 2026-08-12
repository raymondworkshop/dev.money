---
title: "Building Food Metadata with LLM Juries, Context Optimization & Multimodal AI"
source: "https://careersatdoordash.com/blog/building-food-metadata-with-llm-juries-context-optimization-multimodal-ai/"
published: "2026-07-03"
created: "2026-07-14"
description: "How DoorDash built reliable food metadata at scale using AI, LLM jury, context-optimization agents, and distributed inference."
author:
  - "[[David Lindsay]]"
  - "[[Shuang Liu]]"
  - "[[Ying Yang]]"
topics:
  - tech
---

# [Building Food Metadata with LLM Juries, Context Optimization & Multimodal AI](https://careersatdoordash.com/blog/building-food-metadata-with-llm-juries-context-optimization-multimodal-ai/)

## Core View
- DoorDash uses a multimodal AI platform to infer item- and store-level attributes from text, images, and web search signals.
- An LLM jury system improves annotation accuracy by ~20% compared to human reviewers by enabling consensus-based evaluation of tags.
- Context-optimization agents iteratively improve prompts using failure signals, increasing model precision by over 20% and accelerating development tenfold.
- Distributed computing reduces backfill time from over a month to just days, enabling real-time metadata updates at scale.
- AI-led annotation generates training data with 90% lower inference cost and zero human effort, accelerating fine-tuning of specialized models.

## Technical Innovations
- LLM jury system: Multiple LLM evaluators independently judge tags and vote on consensus, improving accuracy and reducing human dependency.
- Context optimization loop: Failure signals from high-quality evaluation datasets are used to propose and test prompt improvements, mimicking reinforcement learning.
- Deduplication, Spark distribution, batch processing, and result remapping enable efficient, scalable inference across millions of items.
- AI-generated training data accelerates fine-tuning without requiring human annotation, reducing development cycle time significantly.

## Impact on Customer Experience
- Structured metadata enables powerful downstream features: customer search, personalization, filtering, and analytics.
- Enhanced search and discovery allow users to find relevant dishes based on cuisine, dietary needs, and preferences.
- Metadata serves as a foundational layer for personalization and analytics across the DoorDash platform.

## Key Takeaways
- Multimodal AI systems can achieve high accuracy and scalability when built with automated evaluation and iterative context optimization.
- LLM juries and failure-driven prompt tuning reduce human labor and improve model precision in large-scale production environments.
- Distributed inference pipelines are essential for handling millions of items with low latency and cost efficiency.

## Related Articles

- [[tech/2x-not-10x-coding-llms-2026|2x, not 10x: coding with LLMs in 2026]]
- [[tech/local-llm-question-categorization|Fine Tuning a Local LLM to Categorize Questions]]
- [[tech/how-i-use-llms-to-learn|How I use LLMs to learn complex topics]]
- [[tech/llm-critics-right-use-anyway|The LLM Critics Are Right. I Use LLMs Anyway.]]

---
**Topics**: [[tech/_index|Tech]]  
**Tags**: #tech #multimodal-ai #llm
