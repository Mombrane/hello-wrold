# Memex 生态调研报告：AI Agent 的长期记忆方案

## 概述

"Memex" 这个词源自 Vannevar Bush 在 1945 年发表的《As We May Think》中提出的概念——一种可以扩展人类记忆的个人知识设备。2025-2026 年，随着 AI Coding Agent（Claude Code、Codex CLI、Cursor 等）的广泛使用，"Agent 的记忆问题" 成为新的瓶颈：会话结束后知识丢失、历史对话难以检索、跨会话经验无法积累。

围绕这个问题，GitHub 上涌现了多个以 "memex" 命名的开源项目，它们从不同角度尝试解决 Agent 的长期记忆问题。本报告对五个核心项目进行了源码级分析，涵盖架构设计、技术栈、适用场景和工程落地可行性。

---

## 项目全景对比

| 项目 | Stars | 语言 | 核心定位 | 数据格式 | 许可 |
|------|-------|------|----------|----------|------|
| [zelixag/ai-memex-cli](https://github.com/zelixag/ai-memex-cli) | 7 | TypeScript | Karpathy LLM Wiki 模式的工程化实现 | Markdown + Git | MIT |
| [nicosuave/memex](https://github.com/nicosuave/memex) | 76 | Rust | 本地历史对话快速检索 | Tantivy(BM25) + ONNX | MIT |
| [vimo-ai/memex](https://github.com/vimo-ai/memex) | 28 | Rust+Vue | Claude Code 会话全生命周期管理 | SQLite + LanceDB | MIT |
| [labazhou2024/memexa](https://github.com/labazhou2024/memexa) | 53 | Python | 中文多源数据个人记忆图谱 | Proprietary | Apache-2.0 |
| [chriskd/memex-kb](https://github.com/chriskd/memex-kb) | 15 | Python | 可搜索 Markdown 知识库 | Markdown + SQLite | MIT |

**四个项目，四种哲学**：ai-memex-cli 是 "wiki 派"——用 Markdown 构建结构化知识库；nicosuave/memex 是 "检索派"——只管搜得快搜得准；vimo-ai/memex 是 "压缩派"——用 LLM 做多层摘要压缩；memexa 是 "图谱派"——构建实体关系网络。

---

## 1. ai-memex-cli — Karpathy 思想的工程化落地

### 设计理念

ai-memex-cli 是 Karpathy 2025 年提出的 [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 概念的最忠实实现，核心思路是"LLM 是程序员，Obsidian 是 IDE，Wiki 是代码库"。它把知识沉淀为一个由 Git 管理的 Markdown 知识库（称为 Vault），结构如下：

```text
~/.llmwiki/
├── raw/          # 不可变原始数据（网页、文档、会话记录）
├── wiki/         # Agent 维护的结构化知识页
├── AGENTS.md     # Schema 定义
├── index.md      # Wiki 目录
└── log.md        # 操作日志
```

### 三层架构

项目的架构分层非常清晰——这是我最欣赏的设计决策之一。三层严格分离，边界明确：

| 层 | 职责 | 核心约束 |
|----|------|----------|
| **Agent Interface（L3）** | ai-memex skill + `/memex:*` 工作流 | 决定何时 capture/ingest/query，写语义内容 |
| **CLI Toolbox（L2）** | fetch/search/lint/link-check 等命令 | 纯机械操作，**永不调用 LLM API** |
| **Vault Protocol（L1）** | 文件系统 + Git | raw 不可变、wiki 可写，Markdown 格式 |

这种"机械层永不调 LLM"的红线设计是个很聪明的约束——它保证了 CLI 对所有 Agent（Claude Code、Codex、Cursor、Gemini CLI、Aider 等 8+ 个）的中立性，避免了 MCP 这类特定生态绑定。

### 工作流闭环

项目的核心闭环设计完整：
```
SessionStart hook → glob → 本地 wiki 投影
                         → inject (@include) → 上下文注入
                                          ↓
                                  对话中 agent 读/写 wiki
                                          ↓
SessionEnd hook   → distill → raw/sessions/
                                          ↓
                        用户/定时  ingest → agent 更新 wiki
                                          ↓
                        定期     lint → JSON 报告 → agent 修正
                                          ↓
                                  下次新会话（回到起点）
```

### 我的评价

**优点**：(1) 三层架构边界清晰，"CLI 不调 LLM" 是正确且有远见的架构决策；(2) 8+ Agent 支持覆盖广泛，不绑定单一生态；(3) `memex watch --daemon --heal` 实现了自主自愈循环，这在同类项目中是独一份；(4) 交互式 onboard 向导降低上手门槛。

**缺点**：(1) 项目知名度低（仅 7 star），社区生态薄弱，长期维护存疑；(2) 依赖 Agent 自身的语义能力——如果 Agent 的 ingest 质量差，知识库就会"垃圾进垃圾出"，没有内置质量保障机制；(3) 双层 vault（global + local）对用户认知负担较高；`@include` 的 glob 匹配语法在边界情况的行为不够透明。

**适用场景**: 如果你认同 Karpathy 的 "Wiki 作为知识载体" 哲学，且愿意手动 curate Agent 的输出质量，这是最对齐的方案。

---

## 2. nicosuave/memex — 极致检索性能

### 设计理念

nicosuave/memex 的哲学很简单：**搜得快、搜得准**。它不做知识提取、不做语义压缩，只管把 Claude Code / Codex CLI / OpenCode 的会话记录索引起来，让 Agent 能跨会话快速找到"上次我们怎么解决那个 bug 的"。

### 技术选型

- **检索引擎**: Tantivy（Rust 生态的 Lucene 等价物），BM25 全文搜索
- **向量搜索（可选）**: ONNX Runtime 本地推理，支持 MiniLM / BGE / Nomic / Gemma / Potion 五种模型
- **数据源**: Claude Code (`~/.claude/projects/`)、Codex CLI (`~/.codex/`)、OpenCode (`~/.local/share/opencode/`)
- **UI**: 终端 TUI（基于 ratatui）

### 特色的 Agent Skill 集成

项目内置了 Claude Code 和 Codex CLI 的 skill 文件，通过 `memex setup` 一键安装。Agent 在对话中可以直接调用 `memex search` 检索历史会话。

### 我的评价

**优点**：(1) Rust 实现，性能极致，索引速度远超 Python 方案；(2) 支持 GPU 加速（CUDA / CoreML），大索引库也能秒级响应；(3) 本地推理，数据不离开本机，隐私友好；(4) 对 Claude Code subagent 会话也支持索引（`--include-agents`）。

**缺点**：(1) 只做检索不做知识沉淀——查到的是原始对话片段，需要 Agent 在每次查询时重新理解上下文；(2) 没有跨会话的知识积累机制，本质上是一个"更快的 grep"；(3) 依赖 ONNX 模型文件下载，首次使用需要网络且模型较大。

**适用场景**: 如果你想要的是一个"搜索引擎"而不是"知识库"，这是最好的选择。作为其他记忆方案的底层检索引擎也非常合适。

---

## 3. vimo-ai/memex — 多层级智能压缩

### 设计理念

vimo-ai/memex 是目前 memex 生态中**工程最重**的项目，Rust 后端 + Vue Web UI + MCP Server，定位是 Claude Code 会话历史的**全生命周期管理**。核心创新是多层级摘要压缩（L0-L4）和读写分离的 V2 架构。

### L0-L4 压缩层级

| 层级 | 内容 | 模型 | 说明 |
|------|------|------|------|
| L0 | 原始消息（messages 表） | 无 | 始终保留，不可删除 |
| L1 | Observations | Qwen3 0.6B | 每个工具调用一个观测 |
| L2 | Talk Summary | Qwen3 0.6B | 每轮对话摘要 |
| L3 | Session Summary | Qwen3 0.6B | 整个会话摘要（依赖 L2） |
| L4 | Knowledge | 强模型 | 结构化知识提取（独立管线） |

### V2 架构：读写分离

项目从 V1 的单体架构演进到 V2 的读写分离：文件监听和写入由 `vimo-agent` 负责，`memex-rs` 通过 HTTP API 被动触发 compact 和向量索引。这个设计让两部分可以独立扩缩。

### 混合检索栈

检索层面比较完善：SQLite FTS5（全文）+ LanceDB（向量，BGE-M3 1024维）+ RRF（Reciprocal Rank Fusion）融合排序。比 nicosuave/memex 的 Tantivy 方案更重但更灵活。

### 我的评价

**优点**：(1) L0-L4 压缩层级设计精细，"原文始终保留、压缩可选重做"的架构确保信息不丢失；(2) compact 用 0.6B 小模型控制成本，knowledge 用强模型保证质量——这个"分级用模"的策略很务实；(3) V2 的读写分离架构为部署提供了灵活性——可以把 memex 跑在服务器上，多个 client 共享；(4) MCP 工具设计遵循"精简输出、渐进披露"原则，对 Agent token 预算友好。

**缺点**：(1) 重——需要 Ollama 跑本地模型（至少 0.6B + BGE-M3），对机器资源要求高；(2) compact 质量依赖 Qwen3 小模型，在中文场景下的摘要质量存疑；(3) Web UI 文档不完善，README 几乎是空的；(4) 项目似乎仍在快速迭代中，API 稳定性不确定。

**适用场景**: 如果你有 GPU 机器、愿意跑本地模型、需要"全自动"的会话记忆管理（不仅是搜索，还包括自动摘要和知识提取），这是当前功能最全的选择。

---

## 4. memexa — 中文原生个人记忆图谱

### 设计理念

memexa 的目标用户非常明确：需要用中文处理微信、QQ、邮件、AI 对话等多源数据的个人用户。它的核心价值主张是"每条消息逐字保存，抽取成结构化记忆卡，每个答案都能引用回原句"。

### 需要注意的开源/专有分离

memexa 的 GitHub 仓库**仅是开源 demo**——包含一份小型合成数据集和一个 stub 抽取器，用于在 30 秒内展示项目形态。完整的 memexa 引擎是**专有产品**，包含：
- 跨多源实时增量摄入
- 双 LLM 抽取流水线（带逐条引用、跨别名归一）
- 多通道召回 + cross-encoder 精排（专为杂乱中文聊天设计）
- MCP Server + CLI
- 本地桌面应用

### 我的评价

**优点**：(1) 中文原生——专为微信/QQ 等中文聊天场景设计，不是英文工具的翻译版；(2) 多数据源统一入口（微信/QQ/邮件/浏览器/AI 对话/录音），这是其他 memex 工具都不具备的能力；(3) 逐字溯源的设计保证了可信度。

**缺点**：(1) 核心引擎闭源——开源 demo 无法用于实际场景，这极大地限制了社区的参与度和信任度。如果你在评估是否能 "跑起来"，答案是：demo 可以，生产不行。(2) 专有产品的定价和获取方式不透明，增加了采用风险；(3) 自托管方案看起来需要较多系统资源，双 LLM 管线的资源消耗 vs. 实际产出价值需要验证。

**适用场景**: 如果你对中文个人记忆图谱有刚需，且愿意承担闭源工具的 vendor lock-in 风险，可以联系作者获取完整引擎的试用。

---

## 5. chriskd/memex-kb — Markdown 知识库 + 图

### 设计理念

chriskd/memex-kb 提供了另一种思路：以 Markdown 为核心的知识库，加上混合检索、类型化关系、wiki 链接和图视图。Token-efficient 的 CLI 给 Agent 用，静态发布给人看。

这个项目风格上介于 ai-memex-cli 和 Obsidian 之间——比 ai-memex-cli 多了图视图和类型化关系，但少了 agent skill 集成和自动化蒸馏管线。

---

## 综合评价与选型建议

### 选型决策矩阵

| 需求场景 | 推荐项目 | 理由 |
|----------|----------|------|
| 追求 Karpathy 理念，手动 curate 知识 | ai-memex-cli | 最忠实于 LLM Wiki 模式 |
| 只要快速搜索历史对话 | nicosuave/memex | 性能最优，最轻量 |
| 全自动记忆管理，有 GPU | vimo-ai/memex | 功能最全，自动化程度最高 |
| 中文多源数据（微信/QQ） | memexa | 唯一的中文原生方案 |
| 轻量 Markdown KB | memex-kb | 最简洁 |

### 整体趋势判断

2025-2026 年的 memex 生态呈现三个趋势：

1. **从"检索"到"积累"的范式转移**：早期方案（nicosuave）关注搜索历史对话，新方案（ai-memex-cli、vimo-ai）关注把对话"转化"为可积累的知识。这个方向更接近 Bush 1945 年的原始 vision。

2. **Agent 中立成为共识**：ai-memex-cli 和 nicosuave/memex 都选择了"不绑定特定 Agent"的架构。vimo-ai/memex 目前偏向 Claude Code，但 MCP 协议也提供了跨 Agent 的可能性。

3. **本地优先 vs 云托管**：目前所有 memex 项目都是本地优先的，数据不出机器。这对隐私敏感的用户是刚需。

### 批判性思考：memex 真的解决记忆问题了吗？

尽管这些项目各有千秋，我需要指出几个尚未被充分解决的深层问题：

1. **知识腐烂**：Markdown wiki 里的内容会过时——一个技术决策在三个月后可能已经不适用了。所有项目都缺少"时间衰减"或"老知识标记"的机制。vimo-ai 的分层归档（daily→weekly→monthly→yearly）是唯一的例外，但它归档的是原始数据而非知识。

2. **假阳性风险**：当 Agent 检索到历史中的"类似问题"时，它可能错误地套用旧方案。当前的混合检索（BM25+向量+RRF）都只优化"相关性"而非"适用性"——这还是需要人来判断的灰色地带，而"人来判断"恰恰违背了自动化的初衷。

3. **跨项目知识迁移**：绝大多数 memex 工具按项目组织知识，但真实的知识是跨项目的——一个在项目 A 中学到的架构模式，可能对项目 B 同样有价值。ai-memex-cli 的 local vault 投影机制是目前唯一尝试解决这个问题的设计，但实现相对粗糙。

4. **与 Hermes 的对比**：Hermes Agent 本身的记忆系统（memory 工具 + session DB + FTS5 搜索）已经实现了大部分 memex 工具的功能：跨会话记忆存储、历史检索、上下文注入。ai-memex-cli 的独特价值在于把知识"结构化"为 Markdown wiki（人可读、可 diff），而 Hermes 的记忆是 Agent 专用的。如果你同时使用 Hermes 和其他 Agent，ai-memex-cli 作为跨 Agent 的"知识中间层"可能最有价值。

---

*调研日期：2026-07-01。项目数据来自 GitHub 当日快照，star 数等指标可能已变化。*
