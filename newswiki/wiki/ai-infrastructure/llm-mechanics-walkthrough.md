---
title: "How LLMs Actually Work"
source: "https://www.0xkato.xyz/how-llms-actually-work/"
published: "2026-06-01"
created: "2026-06-07"
description: "A from-the-ground-up walkthrough of how modern LLMs work, from tokens to transformer blocks to the next-token loop"
author:
  - "[[0xkato]]"
---

# How LLMs Actually Work: A Technical Walkthrough

## Core LLM Pipeline Stages
- The process involves nine key stages: Tokenization $\rightarrow$ Embeddings $\rightarrow$ Positional Encoding $\rightarrow$ Attention $\rightarrow$ Multi-head Attention $\rightarrow$ Feed-forward Network $\rightarrow$ Residual Stream/Layer Normalization $\rightarrow$ Next Token Prediction.
- The model operates on a sequence of integers (token IDs) rather than raw text.

## Tokenization
- Converts input text into a sequence of integer IDs using a fixed vocabulary.
- Modern models use subword tokenization (e.g., Byte Pair Encoding) for efficiency and generalization.
- The choice of tokenizer impacts compute cost and multilingual coverage.

## Embeddings & Positional Encoding
- Token IDs are mapped to dense vectors (embeddings) representing semantic meaning.
- Positional encoding injects sequence order information. Modern models often use Rotary Position Embeddings (RoPE) for better generalization to longer contexts.
- The combination of embedding and positional encoding gives the model both meaning and sequence context.

## Attention Mechanism (The Core)
- Attention allows each token to weigh the importance of all other tokens in the sequence.
- Tokens are transformed into Query (Q), Key (K), and Value (V) vectors.
- Match scores are calculated via scaled dot product between Q and K, followed by Softmax to derive weights.
- The output is a weighted average of the Value vectors, allowing information flow across distances.

## Multi-Head Attention & Parallelism
- Running attention in parallel across multiple 'heads' allows the model to learn diverse relationships (e.g., grammar, coreference, positional tracking).
- Different heads specialize in different roles, leading to emergent capabilities like 'induction heads' that track patterns.
- Modern optimizations like Grouped-Query Attention (GQA) reduce memory overhead (KV cache) while maintaining performance.

## Feed-Forward Network (FFN) & Memory
- The FFN processes each token vector independently, performing non-linear transformations (e.g., using SwiGLU) to encode deeper structure.
- A significant portion of the model's factual and semantic knowledge is stored within the FFN weights.
- Advanced scaling techniques like Mixture of Experts (MoE) use parallel FFNs (experts) to increase parameter count while keeping per-token compute cost manageable.

## Training & Inference Loop
- The Residual Stream accumulates contributions from each layer, while Layer Normalization keeps the vector magnitudes stable during training.
- Next-token prediction is the objective: the model predicts the next token based on the final layer's vector, using logits and a temperature/sampling strategy.
- Inference relies on the KV cache to avoid recomputing past tokens, making generation sequential.

## Key Takeaways
- LLMs are highly complex, deep stacks of transformer blocks, each layer refining the token's vector through attention and FFNs.
- The convergence on specific components (RoPE, RMSNorm, SwiGLU) reflects a mature, optimized design pattern for modern frontier models.
- The model's function is fundamentally next-token prediction, which enables emergent capabilities like reasoning and coding.

---
**Topic**: [[ai-infrastructure/_index|AI Infrastructure]]  
**Tags**: #LLM #Transformer #DeepLearning #ML
