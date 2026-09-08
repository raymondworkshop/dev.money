---
title: "美国企业观念突变，不再为AI大肆烧钱"
source: "https://cn.wsj.com/articles/china-us-ai-model-costs-8eed553e?mod=cn_hp_biz_pos1"
published: "2026-07-27"
created: "2026-07-27"
description: "美国企业界掀起模型“混搭”潮，AI行业经济模式与竞争格局迎来重构。"
author:
  - "[[Angel Au-Yeung]]"
  - "[[Katherine Bindley]]"
  - "[[Tina Li]]"
topics:
  - tech
  - business
---

# [美国企业观念突变，不再为AI大肆烧钱](https://cn.wsj.com/articles/china-us-ai-model-costs-8eed553e?mod=cn_hp_biz_pos1)

## 核心观点
- 美国企业正从追求“词元消耗量”转向追求“词元经济效益”，不再盲目为最高端、最昂贵的AI模型支付溢价。
- 企业开始采用“模型混搭”策略，将 [[tech/openai|OpenAI]] 和 [[tech/anthropic|Anthropic]] 的高端模型与更便宜的开放权重模型（包括中国模型）搭配使用。
- AI模型正逐渐被视为普通商品（Commodity），企业忠诚度降低，倾向于根据任务复杂度选择最具性价比的方案。
- 出现了一种典型的分层架构：由顶级模型（如 Anthropic Fable 或 OpenAI Sol）负责规划和审查，由低成本模型（如 [[tech/deepseek|DeepSeek]] 或 [[tech/moonshot-ai|月之暗面]] 的 Kimi）负责执行。

## 行业影响与竞争格局
- 开放权重模型（如 Meta 的 [[tech/llama|Llama]]）通过微调为企业带来显著成本削减，例如 Zoom 通过微调 Llama 节省大量资金。
- 中国 AI 初创公司（如 DeepSeek、MiniMax、月之暗面）的模型在美国企业中被广泛使用，尽管面临地缘政治风险和安全警告。
- 高端模型厂商（OpenAI, Anthropic）面临估值威胁，因为基础模型能力的普及降低了高端模型的绝对垄断地位，迫使它们通过补贴和激励措施锁定客户。
- [[business/cursor|Cursor]] 等模型无关（Model-agnostic）的工具获益，允许用户在不同供应商之间自由切换。

## 企业实践案例
- Telnyx：采用混合架构，使用 Z.AI 模型驱动 1,400 个智能体执行，由 Anthropic Fable 规划，OpenAI Sol 审查，大幅降低每日运营成本。
- Harvey：训练 GLM-5.2 模型处理常规任务，仅在判定为“艰巨任务”时才调用 Anthropic Fable 5。
- Cursor 实验：通过结合 Composer 编程模型与 Anthropic Opus 4.8，将构建浏览器的成本从 1 万美元降低至 1,339 美元。

## 核心要点
- AI 行业进入“词元经济学”时代，成本控制成为企业部署 AI 的核心考量。
- 模型混合策略（Hybrid Strategy）成为主流，打破了单一顶级模型的垄断。
- 开放权重模型和中国低成本模型正在侵蚀美国封闭模型的高端市场份额。
- AI 能力的商品化使得模型供应商之间的竞争演变为价格战和生态锁定之战。

---
**主题**: [[tech/_index|Tech]], [[business/_index|Business]]  
**标签**: #tech #ai-economics #model-mixing

## 相关文章

- [[business/openai-q2-revenue-slowdown|OpenAI第二季度收入增长乏力，增速逊于Anthropic]]
