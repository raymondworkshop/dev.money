---
title: "Coding Agent Harness"
source: "https://x.com/dongxi_nlp/article/2071729771126346093"
author:
  - "[[马东锡 NLP (@dongxi_nlp)]]"
published: 2026-06-30
created: 2026-07-11
description: "七篇文章合集。01. The Harness Is The Product为什么 coding agent 最重要的部分，常常是最不显眼的那部分。每次讨论 coding agent，大家最后都会从 model 开始。“ 用哪个 model？context 多大? 写代码能力怎么样..."
---
![[_resources/2026-07-11-Coding Agent Harness/4538321c099a92c88470e5066480de67_MD5.jpg]]

七篇文章合集。

## 01\. The Harness Is The Product

![[_resources/2026-07-11-Coding Agent Harness/136dd5d757545b238ecf87ac76f9f4ec_MD5.jpg]]

为什么 coding agent 最重要的部分，常常是最不显眼的那部分。

每次讨论 coding agent，大家最后都会从 model 开始。

“ 用哪个 model？context 多大? 写代码能力怎么样？”

这些问题重要，但它们已经不再是我们应该最先问的问题，我们应该问的第一个问题应该是：

> Harness 到底负责什么？

当我们回顾基础的 LLM 预测文本任务，reasoning model 可以跟随结构，输出 tool call，并在 protocol 里工作。

coding agent 则更进一步：它把 model 放进一套 runtime。这个 runtime 能检查真实 repo，请求 tool，编辑文件，跑检查，记住发生过什么，并在多轮中继续推进。

> 这层 runtime 就是 harness。

对 coding agent 来说，harness 本身就是 product。

![[_resources/2026-07-11-Coding Agent Harness/cbe8b5c389adec4bcdd61e5c2066b4fe_MD5.jpg]]

## The Naive Version

一个 mini 版本的coding agent 通常长得像这样：

Naive agent loop:

> user request -> big prompt -> model response -> run whatever tool it asked for -> paste result back into prompt -> repeat

这个 loop 看起来很简单，因为 validation、permission、result limits 和 state updates 都被藏起来了。

这是一张有用的草图，但这样的mini agent 很快会出问题。比如：

- 当 model 要编辑一个它从没读过的文件，会发生什么？
- 当 shell command 触碰 workspace 外的文件，会发生什么？
- 当 tool 返回 50,000 行输出，会发生什么？
- 当文件已经在磁盘上变化，transcript 里仍然保留旧 file read，会发生什么？
- 当 tool result 和产生它的 tool call 对不上，会发生什么？

这个 system 还没有成为 coding agent。

## What The Harness Owns

Model 可以提出 proposal，Harness 负责做决定。

从 architecture 的角度去看，关键 surface 超出这一行：

Interface is not the agent:

> model(prompt) -> answer

这只是一层 interface。真正的 agent 还需要 tool lifecycle、permission decision、transcript、file truth 和 next-turn state。

它更接近：

What the harness actually owns:

> input routing -> message design -> prompt assembly -> model output -> parser -> tool validation -> permission policy -> execution -> bounded result -> transcript + state update -> next turn

每一个 arrow 都是 boundary。model proposes，harness controls the path to real-world effect。

每一个箭头，都是 harness 可以保护用户的位置；也可能是它悄悄失控的位置。

![[_resources/2026-07-11-Coding Agent Harness/09e4a192c5822c25cbacab5022286492_MD5.jpg]]

## Six Things A Coding-Agent Harness Must Do

这里，我们把 Coding Agent 压缩成六个核心组件：

1. Live repo context

Agent 不该从空 prompt 开始。它需要知道 workspace、当前文件、相关 project docs，以及哪些 repo state 可以安全暴露。

1. Prompt shape

Context quality 经常看起来像 model quality。稳定的 prefix、清晰的 tool contract、当前 request、受控的 history，带来的行为差异可能比换 model 更大。

1. Structured tools

Tools 不应被当作 helper functions。它们是 model proposal 和真实 side effects 之间的 contract。

Harness 解析 arguments，验证 paths，检查 policy，执行操作，裁剪 output，并记录发生了什么。

1. Context reduction

如果 harness 盲目追加所有东西，model 最后会看到太多、太少，或者看到错误的东西。

好的 context 是一个 projection，而非不断膨胀的 blob。

1. Transcripts and memory

Transcript 回答：“发生过什么？”

Working state 回答：“现在什么重要？”

这是两份不同的任务，当然需要区别对待。

1. Delegation

Subagents 也不等于 magic parallelism。它们应该是有边界的 workers：scoped tools、isolated state、distilled results。

当 delegation 充当 context firewall 时，它才真正有用。

## The Main Loop

coding agent 是一个 observe-act loop，但真正有价值的部分，发生在 observe 和 act 之间。

The model is inside the loop:

> while tool\_steps < max\_steps: prompt = build\_prompt( workspace=workspace\_state, tools=tool\_schemas, memory=session\_memory, file\_state=file\_state, history=projected\_history, ) output = model.complete(prompt) action = parse\_model\_output(output) if action.kind == "final": return action.text result = validate\_authorize\_execute\_record(action) projected\_history = update\_context(result)

model 在 loop 里面, harness 拥有 loop。

这个区别很关键。

## A Concrete Example

假设 model 发出一个 tool call：

A tool call is a proposal:

> write\_file( path="src/config.py", content="..." )

write 变成真实副作用之前，harness 还要检查 path safety、baseline freshness、approval 和 state update。

model 做出了一个 proposal。harness 接下来要回答一串问题：

- src/config.py 是否在 workspace 内？
- 这个 path 是否会通过 symlink 逃逸？
- 这是新文件，还是 overwrite？
- model 最近是否读过现有文件？
- 已知的 file baseline 是否过期？
- 这次 write 是否需要 human approval？
- edit result 是否应该包含 diff summary？
- 后面是否应该跑 validation command？
- 有多少 output 应该进入下一轮 prompt？
- 需要更新哪些 state，避免下一轮 stale？

这些判断不该交给 model 的随机处理。

Prompt 可以描述期望行为。Harness 负责落实边界。

## The Product Lesson

一旦你开始看见 harness，很多 coding-agent 行为都会更容易诊断。

- 如果 agent 不断重复，去检查 loop 和 retry policy。
- 如果它编辑 stale code，去检查 file-state baselines。
- 如果它越跑越差，去检查 context projection。
- 如果它运行了意外的东西，去检查 permission policy。
- 如果它无法从 tool errors 中恢复，去检查 tool result objects。
- 如果它解释不清发生了什么，去检查 traces、audit、doctor surfaces。

model 当然重要，只是 model quality 只占其中一层。

真正的 agent experience 来自 model 周围的整套 harness：

The agent experience is a stack:

- model
- repo context
- prompt structure
- tool contracts
- validation
- permissions
- transcript
- file state
- diagnostics

Anything that must be reliable belongs in the harness.

这就是为什么 “the harness is the product” 不只是一句 slogan。

它是一条工程规则：

> Anything that must be reliable belongs in the harness.

好了，至此，希望你更加理解 harness。

下一篇，会 **The Stale Read Trap**.

## 02\. The Stale Read Trap 旧读陷阱

![[_resources/2026-07-11-Coding Agent Harness/d41bcfc256d8513f39011da60adddc84_MD5.jpg]]

Harness 系列文章之二，The Stale Read Trap

模型记住的是 transcript，但 Harness 必须要记住 truth。

> 什么是 Stale Read Trap？

Coding Agent 最危险的 bug，常常看起来很普通。

Agent 读了一个文件。用户改了这个文件。

Model 记得 transcript 里的文件内容，但磁盘上的文件已经变了。

Agent 继续编辑旧版本。

没有夸张的报错，没有明显的 hallucination，只是 model 很自信地基于过期证据工作，落入了 “旧读陷阱” （我造的词 ：））。

这就是 stale read trap。

请记住：

> Transcript text 不等于 file truth。

如果一个 coding agent 分不清 model 记住的文件内容是否还匹配磁盘，它迟早会 patch 昨天的代码。

![[_resources/2026-07-11-Coding Agent Harness/1b0d3e8574ee1732f5934ff95bc954b5_MD5.jpg]]

## The Failure

想象这个 sequence：

Failure sequence:

> turn 1 read\_file("src/config.py") -> transcript now contains the file content outside the agent formatter / user / git checkout changes src/config.py turn 2 model uses the old transcript text patch\_file( path="src/config.py", old="TIMEOUT = 30", new="TIMEOUT = 60")

问题不是 read\_file。问题是磁盘变了以后，agent 仍然相信旧 read。

Model 在用心做事，从它的视角看，文件内容就在 conversation 里。

问题在于，conversation 只是历史。workspace 才是当前事实。

## The Naive Design

一个小型 agent 往往把 tool output 当成普通 transcript text：

Naive transcript:

> User: change the timeout Tool: here is src/config.py Assistant: I will patch line 12 Tool: patch succeeded

Plain transcript text cannot detect external file changes.

只要 transcript 外没有变化，这样能跑。但 transcript 和 磁盘并非同一状态。

Transcript versus disk:

> transcript says: 12: TIMEOUT = 30 disk now says: 12: REQUEST\_TIMEOUT = 45 13: RETRY\_TIMEOUT = 30

If transcript and disk disagree, the harness should believe disk.

如果 harness 只会追加文本，model 就可能在一个已经消失的世界里行动。

## What The Harness Needs To Know

harness 需要单独记录 file truth，不能只记录 “model 读过东西”。

它需要知道 File State Records，简而言之，时刻记录 file state：

What file state records:

> path: src/config.py read range: whole file or lines 1-80 baseline hash: abc123... mtime / size: last known disk fingerprint content baseline: bounded text the model saw source: read\_file, agent\_change, external\_change status: fresh, changed, stale, partial, truncated

> Transcript is chronological, File content is stateful

> Transcript is chronological. File content is stateful.

transcript 回答：conversation 里发生过什么？

file state 回答：model 现在可以相信哪些文件内容？

## The Harness Contract

成熟的 harness 会把 read\_file 看成一份 contract。

The harness contract:

> read\_file(path) -> record baseline -> attach bounded content to transcript -> remember what the model saw before edit(path) -> compare baseline with disk -> reject stale / partial / missing / changed -> require fresh read or inject current changed lines after successful edit(path) -> record post-edit baseline -> mark the agent's own write as fresh

这样，file read 从一个方便的工具，变成了 safety mechanism。

Model 依然可以提出 edit proposal。Harness 负责判断这个 proposal 是否基于最新的 file truth。

![[_resources/2026-07-11-Coding Agent Harness/558e2a16e2ce3fbbef0e28f980e96ab6_MD5.jpg]]

## Partial Reads Are Partial

Stale read trap 里面还要注意一点， 即 partial reads。

Model 只读了 lines 100-140，然后尝试重写整个文件。Harness 应该立刻格外关注这样的 partial reads。Range read 可以帮助回答问题，但它不应自动授权高风险 edit。

Partial reads are partial:

> read\_file("[server.py](https://server.py/)", start=100, end=140) -> useful context -> partial baseline -> not enough for whole-file overwrite

A local slice can answer a question without authorizing a risky edit.

一个简单规则很有用：

> Existing-file edits should require a fresh full-file baseline, unless the edit tool has a stricter exact-context contract.

这样可以避免 model 只理解局部片段，却要猜完整个文件。

## What should Harness track

当 read\_file 运行时，要记录：

- workspace-relative path
- line range 和 total line count
- 这次 read 是否覆盖完整文件
- modification time、file size、SHA-256 fingerprint
- bounded baseline text
- state 的来源

当 write\_file 或 patch\_file 成功后，要把 post-edit content 记录成新的 known baseline。当下一轮 prompt 构建时，让 Agent 去 lazy refresh tracked files：

- unchanged content 保持 fresh
- timestamp-only change 且内容相同，安静刷新
- external disk edit 会产生当前 changed-line snippet
- deleted 或 oversized changed file 会变成 stale warning
- fresh read\_file 会清除 stale 或 external-change state

## Why This Changes Agent Behavior

一旦有 file state，agent 的行为会明显不同。

文件没变时，重复 read 可以被压缩成 summary，避免 context flooding。

文件在 agent 外部变化时，下一轮 prompt 可以显示当前 changed lines，而非旧 transcript content。

文件只被部分读取时，edit 可以在造成破坏前被拒绝。

agent 自己写入文件后，post-edit content 可以成为 fresh baseline。

session resume 之后，harness 可以恢复的不只是文本，还包括 agent 可以信任什么。

这会改变真实产品体验。

用这句话，结束这篇：

> The model can remember text. The harness must remember truth.

## 03\. Tools Are Contracts, Not Functions

![[_resources/2026-07-11-Coding Agent Harness/7eea78e2e53d598723145521bc443880_MD5.jpg]]

Harness 系列文章之 3，Tools Are Contracts。

如果 Coding Agent 拥有一个世界，那么每次 tool call，就是用 generated text 请求改变其世界的状态。

Tool call 很容易显得过于简单，model 输出 JSON，Harness parse 它，某个本地 function 被执行，result 被放回下一轮 prompt。

这是 tiny agent 版本。

但 coding agent 的 tool call，并非简单的 function。

Tool call 来自 generated text，它正在请求访问 workspace，shell，network，transcript，或者另一个 Agent。

这个差异会改变整个 Coding Agent 的状态和所处的环境。

> The model can ask. The harness decides.

![[_resources/2026-07-11-Coding Agent Harness/02d4f798d48529f6bf0eb5de72bdda72_MD5.jpg]]

## The Proposal and Contract

想象 model 输出：

The model proposal:

> \<tool>{ "name": "write\_file", "args": { "path": "src/config.py", "content": "..." } }\</tool>

Valid-looking JSON is still only a request for power.

它看起来很 structured，它依然只是一份 proposal。

Model 产出了看似合法的 JSON，并不自动获得 write access。

Harness 仍然需要回答：

- 这个 tool 是否存在？
- args 是否匹配 schema？
- path 是否在 workspace 内？
- 这是 create、overwrite，还是 patch？
- model 最近是否读过现有文件？
- file-state baseline 是否 fresh？
- 这个 action 是否需要 approval？
- approval 前应该给 human 看什么？
- 多少 result output 可以安全进入 context？
- 执行之后需要更新哪些 transcript 和 state？

**这一串问题，就是 tool contract。**

## The Naive Design

naive design 会把 tools 当作一个 function map：

The naive function map:

> tool = tools\[model\_json\["name"\]\] result = tool(\*\*model\_json\["args"\]) history.append(result)

One short line can hide parsing, policy, limits, and state updates.

这段代码很短，所以看起来干净， 但它同时把很多责任压进了一行。

Parsing，schema validation，path safety，permission policy，sandbox choice，execution，output clipping，transcript recording，state updates，全都被塞进 tool(...)

Demo 可以这样写。但能够修改真实 repo 的 coding agent，需要更强的边界。问题不在 function 本身，问题在于 tool boundary 有不同的 trust rules。

Function call vs Tool call

> 普通程序里，function call 是 implementation detail。

> coding agent 里，tool call 是 generated text 请求改变真实世界的位置。

## What A Tool Contract Contains

有用的 tool contract 不能只有 name 和 handler。它应该描述：

What the contract contains:

> name: write\_file args schema: path, content risk: workspace\_write path policy: must stay inside workspace state requirement: existing file needs fresh baseline approval: required for writes approval summary: path + operation + size execution: atomic write or exact patch result budget: bounded diff / chars / lines state update: record post-edit baseline transcript record: paired call and result

有些字段面向 model。有些字段只属于 harness。

Model 需要足够的信息来正确发起请求，Harness 需要足够的 metadata 来正确裁决。

## The Lifecycle

一个最小可用 lifecycle：

![[_resources/2026-07-11-Coding Agent Harness/ed68c9a006df25281017e119c780931c_MD5.jpg]]

每一步拦截不同类型的问题。

- parse 处理 malformed output
- schema validation 处理 missing fields 和 wrong types
- path validation 处理 workspace escape
- policy 处理 risky action、approval、sandbox、denial
- execution 运行真实 handler
- bounding 避免一次 command 或 file read 淹没下一轮 prompt
- recording 让下一轮可以恢复和审计

所以，“just call the function” 这个 mental model 不够用，function 只是 lifecycle 中的很小片段。

## Validate Before Approval

validation 应该发生在 approval 之前。

- 如果 patch\_file 指向 workspace 外，先 reject
- 如果 old\_text 缺失或有歧义，先 reject
- 如果 tool call 立刻重复上一轮失败请求，先 reject 或 retry
- 如果 write 目标是现有文件，但缺少 fresh baseline，先 reject
- approval 是 product surface

用户不应该被要求判断一个本来就无效的请求。，需要 approval 时，summary 应该保持 bounded。

Validate before approval:

> tool: write\_file path: src/config.py operation: update existing file content: 84 lines, 2410 chars risk: workspace\_write requires: human approval

Invalid requests should fail before a human is asked to decide.

文件编辑的 approval prompt 应该展示 affected path 和 change shape，避免倾倒 unbounded raw content。

Harness 可以之后展示 diff，count，preview。Approval boundary 要小而清楚。

## Bounded Results Are Part Of Safety

Tool output 会变成 context，Context 会影响 Agent 行为。

- 如果 search 返回 10,000 条结果，model 并没有更清楚
- 如果 run\_shell 打出巨大 log，下一轮可能丢掉真正的 user request
- 如果 read\_file 每一轮重复同一个未变化文件，有用 context 会被 duplicate text 挤走

所以 tool contract 需要 result limits：

Bounded result:

> stdout: clipped stderr: clipped large files: offset + limit search: max matches diff: compact preview binary data: metadata, not raw bytes

Tool output becomes the model’s next working set, so result limits protect both token budget and reasoning quality.

这不只是 token cost，它关系到 model working set 是否准确。

Harness 应该决定哪些 result evidence 进入 transcript，哪些成为 durable state，哪些保留为 external artifact reference。

评估一个 coding-agent tool 时，不要先问：

> model 能不能 call 它？

更应该问：

- argument schema 精确吗？
- 这个 tool 能 read 或 mutate 什么？
- 哪些 paths、commands、resources 被允许？
- 运行前需要哪种 fresh state？
- allow、ask、sandbox、deny 由什么 policy 决定？
- 什么 result evidence 会回到 model？
- success 或 failure 之后，哪些 durable state 会变化？
- 之后如何把这个 call 和 result 配对？

Model 可以请求，Harness 负责裁决。

Tool Call 只在 Harness 裁决批准后执行。

这个过程，就是契约。

简而言之，工具即契约。

## 04\. The Agent's Toolkit: "/"

![[_resources/2026-07-11-Coding Agent Harness/b49b4f092b12497b47fbff803311afb9_MD5.jpg]]

Harness 系列文章之 4，斜杠让 coding agent 超出单纯 prompt box。

> 不是所有的 input，都可以成为 prompt。

每个 coding-agent UI 都从一个简单想法开始：

输入请求，发给 model，拿回结果。这是 prompt-box 视角下的 agent。

普通请求很适合这样处理：

Ordinary work requests:

> fix the failing tests explain this module add a config option

These are work requests. They can become a prompt.

但产品级的 coding agent 还有另一类 input：

> /status、/tools、/reset、/goal pause、/audit

这些 input 不该交给 model 当普通请求理解。

它们是用户用来控制 agent runtime 的 tools。

> Do not send control-plane intent to the model as ordinary chat.

![[_resources/2026-07-11-Coding Agent Harness/b62aa380de8d382373ac0ee7750d200d_MD5.jpg]]

## The Naive Prompt Box

tiny agent 往往把所有 text 都用同一条路径处理：

The naive prompt box:

> raw user input -> append to transcript -> build prompt -> call model -> parse model output

All text becomes model input, including commands that should control the runtime.

这样很简单，也会让产品陷入困境。

- 用户输入 /status，model 可能编一个 status
- 用户输入 /reset，model 可能讨论 reset，却没有清理 session state
- 用户输入 /goal pause，model 可能把它当成当前 task 里的 instruction
- 用户把 /status 打成 /statsu，model 可能试图帮忙猜，而非返回 command help

**问题发生在 model quality 之前。harness 没有正确 route input。**

## Slash Commands Are User Tools

Article 03 说，model tools 是 contracts。

slash commands 属于另一类 tool，它们属于用户和 harness。

它们可以在 model call 出现之前 inspect，steer，reset，pause，diagnose，configure runtime。

一个简单的 command families 如下：

Slash command families:

> session: /status /memory /session /reset /help tools: /tools goal: /goal /goal pause /goal resume /goal clear capability: /skills /mcp /hooks policy + diagnostics: /permissions /audit /doctor future context: /compact

- 有些 command 产生 local output
- 有些 command 修改 session state
- 有些 command 展示 harness metadata
- 有些 command 为下一轮 model turn 准备 context

**它们都需要在 prompt construction 之前被 route。**

此时的关键词已经出来了，那就是

> Input Router

## The Input Router

有用的 coding-agent harness 有两个 parser boundary。

第一层处理 user input，后一层处理 model output。

input router 应该判断：

The input router:

> raw user input -> empty? ignore -> known slash command? handle locally -> unknown slash command? return command help -> local query? answer locally -> normal request? prepare message and call model

只有最后一条路径应该进入 agent.ask()

Prompt box 不再是唯一入口，Harness 拥有自己的 control surface。

> Not Every Input Becomes A prompt

![[_resources/2026-07-11-Coding Agent Harness/a3ad435addced2dc2092df1b17c1caf1_MD5.jpg]]

## The Special Case: /goal

/goal 是最有意思的 slash command，因为它夹在 user control 和 model work 之间。

> goal 是显式 session state

Goal control state:

> session\["goal"\] = { "objective": "...", "status": "active", "created\_at": "...", "updated\_at": "...", "events": \[\] } user controls: /goal pause /goal resume /goal clear model tools: get\_goal() update\_goal(status="complete")

Goal state is control-plane state, not fuzzy chat memory.

user-facing command 控制 lifecycle：

/goal \<objective> / /goal pause / /goal resume / /goal complete / /goal clear

> /goal \<objective> /goal pause /goal resume /goal complete /goal clear

Model 可以在 prompt 里看到 goal context。

但 model 不能随意 create，pause，resume，clear goals。

> get\_goal() / update\_goal(status="complete")

goal 可以引导 model，用户仍然拥有 control state。

completion 应该依赖 evidence，而非 model 觉得已经完成。

## Diagnostics Should Stay Local

有些 command 应该直接 inspect harness。

/audit 和 /doctor 是很好的例子。

它们不应该问 model：

> does my session look healthy?

它们应该检查 deterministic state，例如使用 /audit 或者 /doctor

Diagnostics stay local:

> /audit /doctor inspect: session history roles tool call / result pairing file-state freshness tool registry metadata goal state context projection permission state MCP + hook configuration

第一步检查应该在 local 完成。

diagnostics 作为 local command 时，harness 可以报告真实 invariants。

## Why This Changes The Product

一旦有 slash commands，用户拥有的不只是 prompt box。

用户可以问：

- 当前 workspace 是哪里？
- 有哪些 tools 可用？
- 当前 active goal 是什么？
- 哪些 state 会进入下一轮？
- 上次 edit 之后发生了什么？
- harness 内部是否一致？
- 这个 session 应该 reset、pause、resume，还是 compact？

**这些是 runtime questions，它们需要 runtime answers。**

**slash 后面的 text 属于 harness，而非 model。**

所以 coding-agent harness 应该有：

Control plane rule:

> A coding-agent harness needs: typed input router known local command handlers unknown command help session-state commands diagnostic commands narrow model mutation rules tests proving local commands do not call the model

Prompt box 是用户请求工作的地方。

Slash 是用户控制 worker 的地方。

这就是 agent toolkit 从 / 开始的原因。

## 05\. Markdown Is A Context Interface

![[_resources/2026-07-11-Coding Agent Harness/e79e6d5ed84d84f96c9f301103860177_MD5.jpg]]

Harness 系列文章之 5，小小的 markdown 文件，却可以改变 Coding Agent 的世界状态。

> .md file works when the harness knows what kind of context it is.

![[_resources/2026-07-11-Coding Agent Harness/3d3d4d0df32b40e2adae6cbf991e7834_MD5.jpg]]

现代 coding agent 里，一个很有意思的现象是：普通 markdown 文件可以改变 agent behavior。

加一个 AGENTS.md，Agent 开始遵守 repo-specific rules。

加一个 SKILL.md，Agent 在某类 task 上突然更稳定。

Markdown file 只是可见部分。

真正有趣的是 Harness 对这种机制的设计：

The mechanism:

> discover the file -> classify its role -> decide when it loads -> project it into model context -> apply tool and workflow constraints -> record what happened

Markdown changes behavior only when the runtime gives it a role.

## The Naive Markdown Dump

按照习惯，如果我们从一个从 tiny agent 看 markdown：

The naive markdown dump:

> find every useful .md file -> paste it into the prompt -> hope the model follows it

.md should be routed, not poured.

这看起来合理，因为 rules，docs，plans，procedures 都经常写在 markdown 里。

但 raw markdown dumping 有代价：

- 旧 notes 会和当前 instructions 竞争
- 长 docs 会挤掉最近的 tool result
- drafts 可能被误当成 rules
- general project guidance 可能盖过 narrow task procedure

Model 得到了更多 text，但 task 得到的有用的 instruction 更少。

所以，

> .md 应该通过 Harness route 进入 context，不能直接倒进 prompt。

## Two Files, Two Jobs

这里，我们可以一起看两个常用 markdown files，AGENTS.md 以及 SKILLS.md

Two files, two jobs:

> AGENTS.md -> workspace rules -> loaded early -> applies broadly -> shapes default behavior SKILL.md -> task procedure -> discovered as metadata -> loaded on invoke -> shapes one workflow

Same markdown format, different harness contract.

它们都是 markdown, 但进入 prompt 的方式不一样。

> AGENTS.md ：In this workspace, behave like this.

> SKILL.md ：For this kind of task, use this procedure.

## Why AGENTS.md Works

AGENTS.md 有效，是因为 Harness 把它当成 workspace instruction context。

它是 project guidance，应该在 model 开始操作 repo 前可见。

例如我自己的 Dongxi Agent 主要任务是要根据每天与 coding agent的交互中，总结学习经验。

那么，在 DongXi 这个 workspace 里，AGENTS.md 要求：做 DongXi Agent 或 coding-agent harness learning 时，要保持 learning artifact current。

这一个文件会改变整个 session 的行为：

Why AGENTS.md works:

> task mentions DongXi Agent -> harness loads AGENTS.md as workspace guidance -> note-capture protocol becomes active -> session notes and concept map stay current

Model 仍然负责 writing 和 reasoning。

但 Harness 在 turn 开始前插入了稳定的 project rule。

这就是 AGENTS.md 强的地方：

- 它从 workspace 被发现
- 它被 project 或 directory scope 限定
- 它进入 stable instruction layer
- 它跨多个 tasks 持续生效
- 它让用户不必在每个 prompt 里重复 local conventions

## How AGENTS.md Works

How AGENTS.md works:

> start agent in cwd -> resolve workspace root -> find applicable AGENTS.md files -> read scoped instructions -> add them to stable context -> rebuild prompt with current task

AGENTS.md is loaded early and scoped by workspace or directory.

- Harness 应该知道每条 rule 适用于哪个 directory。
- nested workspace 可能有更窄的 rules。
- 这些 rules 应该被当成 instruction context，同时仍然低于 system 和 developer policy。
- 文件内容不应该被盲目复制进每条 visible transcript message。
- 它属于 stable context layer。

这样 prompt 可以保持一致，又不会把 project rules 变成 noisy chat history。

## Where Agents.md Enters The Agent Turn

![[_resources/2026-07-11-Coding Agent Harness/6058a20ce91cb621b5fba4e591ea86f0_MD5.jpg]]

AGENTS.md 在 model turn 组装前加载。

它进入 stable workspace instruction context，和 project rules、local operating constraints 放在一起。transcript 记录发生了什么；AGENTS.md 约束接下来该怎么做。

## Why SKILL.md Works

SKILL.md 有效，原因不同。

它能提升某类 task 的表现，是因为它在正确时机给 model 一个聚焦的 procedure。

没有 skill 时，model 可能懂一般领域，但会漏掉 local workflow。

有 skill 时，Harness 可以提供：

- 什么时候使用这个 workflow
- 哪些 files 或 artifacts 重要
- 哪些 tools 被允许或期待使用
- 应该按什么步骤做
- 什么 checks 证明工作完成
- 用户期待什么 output format

这比一句 vague prompt 强得多：

Why SKILL.md works:

> \--- name: review-notes description: Review learning notes for missing evidence. allowed-tools: read\_file, search model-invocable: true user-invocable: true --- # Review Notes 1. Read the note-capture protocol. 2. Search the relevant notes. 3. Check evidence, decisions, and next steps. 4. Return missing pieces with file references.

这个文件会提升 performance，因为它把 fuzzy ability 变成 repeatable procedure。

## How SKILL.md Works

好的 Harness 不会把所有 skills 都塞进 default prompt。

它使用 progressive disclosure。

在 startup 或 capability refresh 时，Harness 扫描 skill folders：

How SKILL.md works:

> scan skill folders: .dongxi/skills/\*/SKILL.md .agents/skills/\*/SKILL.md default prompt sees metadata: name, description, path, allowed tools when relevant: load\_skill(name="review-notes") -> read SKILL.md body -> continue with skill active

The full procedure body stays out until the task needs it.

Model 可以看到这个 skill 存在。

用户也可以通过 /skills 之类的 local command 看到它。

完整 body 在 task 需要时才进入 context。

## Where Skills.md Enters The Agent Turn

![[_resources/2026-07-11-Coding Agent Harness/031e111aa40500f7c55c1eb77d219dee_MD5.jpg]]

SKILL.md 先以 capability metadata 出现，task invoke 之后才加载 body。

它进入 task procedure context：steps、tool expectations、checks、output shape。这个 context 只服务当前 workflow，不扩散成 always-on workspace policy。

小小的 markdown，没有改变 model weights。

却改变了该 task 里的 harness-managed context、tools 和 workflow。

合适使用这些 markdown，是 coding agent 最关心的问题。

而：

> 在恰当的时机，把不同的 markdown 文件加载进context，就是 harness 应该做的事情。

## 06\. Context Is A Projection

![[_resources/2026-07-11-Coding Agent Harness/ee785e2b3c610eb9b71b7c333e7936a1_MD5.jpg]]

Harness 系列文章之 6，关于 context management。

在 coding agent的世界里，昨日的重现，就是将昨日重要的事情映射到今天。

> A transcript records what happened. Context decides what matters now.

![[_resources/2026-07-11-Coding Agent Harness/22e5d65d7ff02ad0612652698685d4d8_MD5.jpg]]

每个 coding agent 最后都会遇到同一个问题： session 会越来会长。

Model 读过文件，跑过命令，搜过日志，改过代码，收到过 validation output，也回答过旧问题。

这些 context 如何管理？

## The Naive Append Loop

The naive append loop:

> take the previous prompt -> append the next user request -> append every assistant message -> append every tool result -> repeat

This feels like memory until it becomes context flooding.

最直觉的做法很简单，append transcript。但其实这是 context flooding。

一开始，model 似乎更聪明，因为它能看到更多。

很快就会遇到问题：

- 旧 tool output 会和当前 evidence 竞争
- 巨大的 shell log 会淹没下一条 instruction
- retry message，partial read，旧 plan，stale summary 全部挤在一个不断变大的 blob 里

## The Multi-Turn Loop

Five-phase loop:

> Phase 1: receive app input Phase 2: project working context Phase 3: ask the model Phase 4: execute tools and collect evidence Phase 5: commit transcript + app state

比 Naive Append Loop 更成熟一点的是 5 phase loop，这部分放在文章的末尾。

## The Core Split

成熟的 Harness 会把三件事分开：

Three memory surfaces:

> durable log -> complete record of what happened model-visible context -> bounded working set for the next call app state -> file baselines, goals, validation, tools, tasks

- Durable log 应该完整和简洁，它服务 resume，audit，evals 和 debugging。
- Model-visible context 应该被选择，是 model 为下一步行动需要看到的视图。
- app state 应该结构化。它不能依赖旧 transcript text 是否还在 prompt 里。

在此，我们定义出了projection：

> Projection means to turn the full history into the small, relevant view the model needs for the next step.

这对应了这篇文章的标题：

> Context Is A Projection

## Projection Happens Before The Model Call

Context management 应该发生在 model call 之前。

Harness projection pipeline：

![[_resources/2026-07-11-Coding Agent Harness/06ef4f01526e3459f1c7d33f968edc36_MD5.jpg]]

- 先从完整 session log 开始，这是 source of truth
- 再看 context pressure：下一轮回答，tool use，evidence 还需要多少 context 空间
- 保留最近几轮 verbatim，因为这里通常放着当前任务
- 大的 output 变成 preview，完整内容留在 prompt 外
- 已完成的旧片段做显式 summary
- 注入当前 app state：changed files，validation，goal，tasks 和 fresh evidence

## Four Projection Moves

Four projection moves:

> 1\. Large-result preview 2. Idle-gap microcompact 3. Old-span collapse 4. Auto-compact near the limit

每个动作解决 context management 中面临的不同问题

## Large-Result Preview

有些 tool result 太大，不适合在每个 turn 原样放进 context。

例如：

- test logs，grep output
- generated files， web fetches
- dependency trees

弱 Harness 会随机截断，更强的 Harness 则会把完整结果放到别处，然后在 model-visible context 里放一个稳定 preview。

Large-result preview:

> tool result: 80k chars -> persist full output -> keep preview + content\_ref -> record replacement metadata -> show compact evidence to model

Model 得到足够继续工作的 evidence。

Harness 保留足够的 metadata，用来 resume，inspect，或者重新加载完整结果。

## Idle-Gap Microcompact

有些 context 因为时间过去而变得不那么重要。

比如用户吃完午饭回来，或者 session 空闲了一夜。

最新 goal 仍然重要，最近几次 edit 仍然重要。

很久以前的重复 read 和 command output，未必重要。

microcompact 是一个小动作：

Idle-gap microcompact:

> long idle gap -> keep recent N compactable results -> clear or preview older tool output -> preserve current task and state blocks

## Old-Span Collapse

有时一整段 messages 已经完成使命，Harness 可以把这段折叠成 summary。但 summary 应该显式存在：

Compact boundary:

> compact boundary: replaced turns 12-29 user asked for config refactor files touched: src/config.py tests/test\_config.py key result: validation passed open issue: retry timeout still hard-coded

Model 知道 collapse 发生过，用户可以检查保留下来的内容。

resume 可以围绕 compact boundary 重建 conversation，而不会把 summary 当成一条随机的新 user message。

## Auto-Compact Near The Limit

当 context pressure 很高时，Harness 应该在 model call 失败前 compact。

好的实现不能只写一句 "if too long, summarize"。

![[_resources/2026-07-11-Coding Agent Harness/1e9a74570913999e8e1fa1b83fb9ee3c_MD5.jpg]]

它需要：

- warning thresholds：提示用户 context 还剩余多少百分比
- hard blocking thresholds：超过限制前需要block model call，要求 compact 后再继续
- recursion guards：防止 compact 又触发新的 compact
- restored attachments or state blocks：compact 后重新加入attachments、file state、validation、goal 和 tasks。

auto-compact 要保护下一轮，同时保留继续工作所需的 evidence。

## The Multi-Turn Loop

> You should not be prompting coding agents anymore. You should be designing loops that prompt your agents.

context 的管理，在 Multi-turn Loop 中尤其重要。

一个 Multi-turn Loop 大概如下，分为 5 个 phase：

The multi-turn loop:

> Phase 1: app input Phase 2: context projection Phase 3: model call Phase 4: tools and evidence Phase 5: next-state commit

Projection prepares the turn. Commit makes the next turn possible.

在 loop 中，The next turn 从 committed runtime state 开始。

Phase 2 context projection 负责生成 model-visible view。

Phase 5 负责提交变化，让下一轮从真实的 runtime state 开始。

从 model call 开始，coding agent 的世界状态发生了变化，划分成了昨天和今天。

Model 不需要整个过去，它需要正确的过去、当前 state，以及足够支持下一步的 evidence。

> Harness Context management 就是管理和决定 model call 看到的 selected view。

## 07\. A Subagent Opens A New Context

![[_resources/2026-07-11-Coding Agent Harness/c23c74ee03ae92eb8fec5ccc1e55e790_MD5.jpg]]

Harness 系列文章之 7，关于 subagent。

> Subagent 是一次 tool call，为 coding agent会打开一个新的 work context。

![[_resources/2026-07-11-Coding Agent Harness/a53a586daf389e02c429e96262a10dc2_MD5.jpg]]

在启动一次 subagent 的过程中，发生了什么？

简要回答：Tool call outside, runtime inside.

## 先看 tool call

为什么说，subagent 的启动其实是一次 tool call。

Invocation example:

> user: Use a verifier agent for webhook retries. parent tool: spawn\_agent({ task\_name: "verify\_retries", agent\_type: "verifier", fork\_turns: "3", message: "Audit billing/webhook.ts..." }) tool result: /root/verify\_retries

比如，用户说：“Use a verifier subagent to audit webhook retries.”

如果 Harness 支持，可以直接使用 slash command /delegate 完成 spawn\_agent 的 tool call。

From user request to child handle:

> User request -> prompt builder -> parent model -> harness -> child handle -> follow-up -> result

Slash commands are user-to-harness; spawn\_agent is model-to-harness.

tool 跑完以后，parent 会拿到 child handle。

## 再看 run time

> Tools Are Contracts. A subagent is another contract: a small interface backed by runtime state.

在 harness 文章 3中，提到，每次 tool call，都改变了 coding agent 的世界状态。

那么 subagent 这次启动的 tool call 之后，发生了什么？来看 runtime inside。

Tool call outside, runtime inside:

> model sees: spawn\_agent(...) harness creates: child thread context policy role / model tools / permissions mailbox / status transcript

Tool call 是入口 ，深入一层，Harness 会打开一个新的 work context。

> subagent 的 context 与 coding agent 的 context 有什么关系？

## Session, Context, Subagent

这三个词容易混在一起。

- session 是 runtime container：thread、transcript、tools、permissions、resources、status、artifacts。
- context 是某次 model call 能看到的 projection：instructions、skills、AGENTS.md、recent turns、summaries、tool results、file state。
- subagent 是 parent session 下面新开的 child session。它可以继承 resources，也会拿到一段被选择过的 context slice。

Session, context, subagent:

> Session -> durable transcript -> tools + permissions -> cost + resources -> mailbox + artifacts Context -> instructions + AGENTS.md -> skills + summaries -> recent turn -> tool results + file state Subagent -> child session -> fresh / fork / partial context -> own turns -> projected result

Tool Call Outside, Runtime Inside

Tool call outside, runtime inside:

> Parent model -> spawn\_agent(...) -> control plane -> parent context Child runtime carries: model context role tools mailbox transcript

- Subagent 这个词有点容易误导，它听起来像一个小一点的智能体。
- 在 harness 里，它更像一个 managed child runtime。subagent 可以使用很多 parent 也能使用的 Harness resources。例如 tools、skills、AGENTS.md，MCP servers、cwd、sandbox、permissions。
- 但 shared resources 不代表 shared transcript。child 有自己的 work context。parent 选择投影多少 context 给它。

Shared resources, separate context:

> Shared resource layer: tools, files, docs, memories, subagent metadata Child work context: task role fork / partial fork recent tools Result projection: child final findings evidence parent integration

## Fresh Agent, Forked Agent or Partial Fork?

Fresh, forked, partial:

> fresh child -> only task prompt -> needs full briefing full fork -> inherits parent history -> needs a directive partial fork -> last N turns or selected slice -> needs a tight boundary

Context sharing is a projection choice.

parent 选择投射多少 context 给 sub agent，由 subagent的类型决定， 常见的 subagent 有三种 pattern：

- fresh child 它需要收到 goal、relevant files、已尝试过什么、exact output，以及回答深度。
- forked child 已经继承了 surrounding context，prompt 应该直接给下一步 directive。
- partial fork 是最实用的中间方案。它给 child 足够的 local memory 去工作，同时避免 parent history 变成 inherited noise。

这里给出一些列子，我们可以想想，什么样的 subagent 适合对应的task？

1. Parallelism Agent, 一个 subagent 查 database migration, 一个 subagent 看 frontend state, 一个 subagent 跑 verification
2. Role Specialization: Explorer, Planner, Verifier, Worker, reviewer ...
3. Background Work, 例如多个 subgent 完成大型重构，长测试

## Subagent workflow

一个实用的 subagent workflow ：

![[_resources/2026-07-11-Coding Agent Harness/29b1a6eeefd3f4d0faf5264297491d2c_MD5.jpg]]

如何组织好多个 subagent 完成工作，其实非常具有挑战性，越清晰的地定义 subagent 的 role，context， tool 越好。

最后：

更多 agents 不保证更好的工作，更多 agents 会制造更多 runtime state。

Harness 必须知道谁在工作、它知道什么、改了什么、什么时候完成、结果如何变成 evidence。

subagent 会为 coding agent 拓展世界，而 harness 则关于新世界是否更好还是更混沌，