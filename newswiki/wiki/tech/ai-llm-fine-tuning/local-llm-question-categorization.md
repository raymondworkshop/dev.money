---
title: "Fine Tuning a Local LLM to Categorize Questions"
source: "https://www.teachmecoolstuff.com/viewarticle/fine-tuning-a-local-llm-to-categorize-questions"
created: "2026-06-22"
description: "A personal project detailing the use of a chatbot powered by RAG, where a small local LLM is fine-tuned to preprocess and categorize household maintenance questions into specific metadata tags (e.g., pool, hvac, gutters) before vector search."
topics:
  - tech
---

# [Fine Tuning a Local LLM to Categorize Questions](https://www.teachmecoolstuff.com/viewarticle/fine-tuning-a-local-llm-to-categorize-questions)

## Project Overview
- The goal is to build a chatbot for household maintenance queries using RAG against a vector database.
- A preprocessing step uses a small local LLM to categorize incoming questions into known metadata tags (e.g., pool, car, hvac, cooking) to narrow the vector search space.
- The experiment tests the hypothesis that a very small local LLM can be reliably fine-tuned for this classification task.

## LLM & Finetuning Details
- Models used: Qwen 3:4B (general QA) and Qwen 3:0.6B (classifier).
- Finetuning framework: Unsloth, using QLoRA.
- Initial dataset size: ~850 entries, split 70/15/15 (Train/Eval/Test).

## Baseline Performance (Zero-Shot Prompting)
- Initial testing of Qwen 0.6B without fine-tuning showed poor performance.
- Accuracy on 131 tests was only ~10% correct.
- Failure modes included overuse of broad labels (e.g., 'electric') and inventing categories not in the allowed list.

## Finetuning Attempts & Results
- **1st Attempt:** Fine-tuning improved accuracy to ~79% (104/131 correct). Issues persisted with category fragmentation (e.g., 'ac' instead of 'hvac').
- **2nd Attempt (Code Mapping):** Switching the output requirement from a variable category string to a fixed, two-character opaque code significantly boosted performance.
- **Final Result:** Accuracy reached ~92% (120/131 correct) by enforcing a fixed-format code output, demonstrating the critical role of output constraints in small model reliability.

## Key Takeaways
- Small, specialized LLMs can be effectively fine-tuned for specific classification tasks like question routing.
- The success of fine-tuning heavily depends on constraining the output format (e.g., using fixed codes) to minimize ambiguity and improve reliability.
- The transition from 10% to 92% accuracy highlights the power of targeted fine-tuning over zero-shot prompting for constrained tasks.

---
**Topics**: [[tech/ai-llm-fine-tuning/_index|AI/ML Model Fine-Tuning for Question Categorization]]  
**Tags**: #LLM #RAG #FineTuning
