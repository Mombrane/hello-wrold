# Supermemory：Agent 记忆实现方案深度调研

> 调研日期：2026-06-05
> 调研人：Hermes Agent
> 系列：Agent 记忆实现方案对比（方案 A）

---

## 1. 项目概览

| 项目 | 说明 |
|------|------|
| 名称 | Supermemory |
| GitHub | [supermemoryai/supermemory](https://github.com/supermemoryai/supermemory) |
| Star | 25.5k |
| 协议 | MIT（开源） |
| 技术栈 | TypeScript monorepo（apps/ + packages/） |
| 官网 | [supermemory.ai](https://supermemory.ai) |
| 基准排名 | LongMemEval、LoCoMo、ConvoMem **#1** |

Supermemory 定位为 **AI Agent 的记忆与上下文引擎**（memory & context engine），由研究实验室开发。它同时提供 RAG 文档检索和记忆事实追踪两个维度的能力，默认以混合模式运行。

---

## 2. 核心架构

```
┌─────────────────────────────────────────────────┐
│              Your App / AI Agent                 │
└────────────────────┬────────────────────────────┘
                     │
          ┌──────────▼──────────┐
          │    Supermemory      │
          ├─────────────────────┤
          │ Memory Engine       │  提取事实、追踪更新、解决矛盾、自动遗忘
          │ User Profiles       │  静态事实 + 动态上下文（~50ms 检索）
          │ Hybrid Search       │  RAG + Memory 双路并行检索
          │ Connectors          │  Google Drive / Gmail / Notion / GitHub / Web Crawler
          │ File Processing     │  PDF / 图片(OCR) / 视频(转录) / 代码(AST-aware分块)
          └─────────────────────┘
```

### 2.1 Memory vs RAG

| 维度 | RAG（文档检索） | Memory（事实记忆） |
|------|----------------|-------------------|
| 状态 | 无状态——同一文档所有人检索结果相同 | 有状态——追踪用户个人事实 |
| 时序 | 不处理更新 | 自动处理时序更新和矛盾 |
| 遗忘 | 无 | 自动遗忘过期临时事实 |
| 检索方式 | 向量相似度 | 向量 + 结构化事实匹配 |

Supermemory 默认将两者**混合运行**，一次查询同时返回文档片段和记忆事实。

---

## 3. 多容器（Multi-Container）机制：containerTags

### 3.1 核心概念

Supermemory **不使用"multi-container"术语**，其隔离机制名为 **`containerTags`** —— 一个字符串数组标签，作为记忆空间的硬隔离边界。

```typescript
// 用户级隔离
await client.add({
  content: "用户偏好深色主题",
  containerTags: ["user_123"]
});

// 项目级隔离
await client.add({
  content: "项目使用 React + TypeScript",
  containerTags: ["project_alpha"]
});

// 多级层次隔离
await client.add({
  content: "团队决策：采用 monorepo 架构",
  containerTags: ["org_456", "team_789"]
});
```

### 3.2 匹配规则：精确数组匹配

**关键设计决策**：containerTags 使用**精确数组匹配**，而非模糊/子集匹配。

```
已存储记忆: containerTags = ["user_123", "project_a"]

✅ 搜索 containerTags: ["user_123", "project_a"]  → 命中（完全匹配）
❌ 搜索 containerTags: ["user_123"]                → 未命中（子集不匹配）
❌ 搜索 containerTags: ["project_a"]               → 未命中（子集不匹配）
```

这意味着需要**预先设计好标签层次**，搜索时必须传入完整的标签组合。

### 3.3 天然映射到记忆范围

| 记忆范围 | containerTags 方案 | 说明 |
|----------|-------------------|------|
| 全局记忆 | `["global"]` | 所有 Agent 共享的知识 |
| 用户个人记忆 | `["user_{id}"]` | 用户偏好、历史对话事实 |
| 项目上下文记忆 | `["project_{id}"]` | 项目文档、技术栈、约定 |
| 组织/团队记忆 | `["org_{id}", "team_{id}"]` | 团队决策、规范 |
| Agent 实例记忆 | `["agent_{id}"]` | 单个 Agent 的运行时学习 |
| 跨用户共享记忆 | `["shared_{topic}"]` | 特定主题的公共知识 |

这正是 Supermemory 的天然优势：**不需要额外构建隔离层**，containerTags 数组本身就是作用域定义，精确匹配保证了隔离性。

### 3.4 Metadata 过滤增强

在 containerTags 硬隔离之上，还支持 metadata 软过滤：

```typescript
await client.search.memories({
  containerTags: ["user_123"],
  filters: {
    AND: [
      { property: "category", operator: "eq", value: "preference" },
      { property: "confidence", operator: "gte", value: 0.8 }
    ]
  }
});
```

支持的操作符：字符串相等、子串匹配、数值比较、数组成员、取反。可与 containerTags 组合 AND/OR 查询。

---

## 4. 核心 API

| API 方法 | 用途 |
|----------|------|
| `client.add()` | 存储内容（文本、对话、URL、HTML） |
| `client.profile()` | 获取用户画像 + 可选搜索，一步到位 |
| `client.search.memories()` | 混合搜索（RAG + Memory） |
| `client.search.documents()` | 纯文档搜索 + metadata 过滤 |
| `client.documents.uploadFile()` | 上传 PDF/图片/视频/代码 |
| `client.settings.update()` | 配置记忆提取和分块策略 |

---

## 5. 生态集成

### 5.1 SDK

| 语言 | 包名 |
|------|------|
| TypeScript/JS | `npm install supermemory` |
| Python | `pip install supermemory` |

### 5.2 框架集成

Vercel AI SDK、LangChain、LangGraph、OpenAI Agents SDK、Mastra、Agno、n8n

### 5.3 MCP 支持

```bash
npx -y install-mcp@latest https://mcp.supermemory.ai/mcp --client claude --oauth=yes
```

支持客户端：Claude Desktop、Cursor、Windsurf、VS Code、Claude Code、OpenCode、OpenClaw、Hermes

### 5.4 数据连接器

Google Drive、Gmail、Notion、OneDrive、GitHub、Web Crawler（实时 webhook 同步）

---

## 6. 定价

| 套餐 | 月费 | 包含额度 | 适用场景 |
|------|------|----------|----------|
| Free | $0 | $5/月用量 | 个人开发/评估 |
| Pro | $19 | ~$20 | 小型项目 |
| Max | $100 | ~$130 | 中型生产 |
| Scale | $399 | ~$600 | 大规模部署 |
| Enterprise | 自定义 | 专属基础设施 | 企业/自托管 |

**按量计费单价**：

| 类型 | 单价 |
|------|------|
| Memory（纯文本） | $0.005 / 1K SM tokens |
| Memory（富内容） | $0.010 / 1K SM tokens |
| SuperRAG（纯文本） | $0.001 / 1K SM tokens |
| SuperRAG（富内容） | $0.002 / 1K SM tokens |
| 搜索 & 遍历 | $0.005 / 1K queries |
| 操作 | $0.10 / 1K operations |

> SM tokens = 去重后的唯一内容 token（字节级去重），重复内容不额外计费。

**创业/研究计划**：$1,000 免费额度，6 个月，全功能解锁。

---

## 7. 优劣势分析

### ✅ 优势

1. **containerTags 天然映射记忆范围** —— 不需要额外构建隔离层，数组标签即作用域
2. **Memory + RAG 混合** —— 一次查询同时获得事实记忆和文档检索
3. **自动遗忘机制** —— 临时事实自动过期，矛盾自动解决
4. **基准测试 #1** —— LongMemEval、LoCoMo、ConvoMem 三项第一
5. **生态丰富** —— MCP 支持、主流框架集成、数据连接器
6. **开源 MIT** —— 可自托管

### ⚠️ 潜在风险

1. **精确匹配的灵活性限制** —— containerTags 必须完整匹配，不能按子集查询，设计标签层次需要提前规划
2. **云端依赖** —— 默认 SaaS 模式，自托管需要 Enterprise 套餐
3. **成本可控性** —— 按量计费，高频 Agent 场景下费用需要预估
4. **相对年轻** —— 25.5k star 但社区生态尚在发展中

---

## 8. 与其他方案对比（预览）

| 维度 | Supermemory | Mem0 | Hermes 内置 | OpenClaw QMD |
|------|-------------|------|------------|-------------|
| 隔离机制 | containerTags（数组精确匹配） | 基于 user_id | Holographic HRR | QMD embedding |
| 开源 | ✅ MIT | ✅ Apache 2.0 | ✅ | ✅ |
| RAG + Memory | ✅ 混合默认 | Memory 为主 | 分层架构 | Embedding 检索 |
| 自动遗忘 | ✅ | 部分 | ✅ | ❌ |
| MCP 支持 | ✅ | ❌ | ✅ | ✅ |
| 自托管 | Enterprise | ✅ | ✅ | ✅ |

> 详细对比将在系列报告后续篇目中展开。

---

## 9. 结论

Supermemory 的 **containerTags 机制**是其最大差异化优势——用一个字符串数组就能定义记忆的作用域边界，天然适配 Agent 系统中常见的「全局 / 用户 / 项目 / 团队」多层记忆需求。配合 Memory + RAG 混合检索和自动遗忘机制，它在技术完整度上处于领先位置。

对于需要**多租户记忆隔离**的 Agent 系统，Supermemory 的 containerTags 是目前最简洁的原生方案之一。
