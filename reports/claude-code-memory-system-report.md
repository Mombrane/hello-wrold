# Claude Code 记忆系统源码解析：四层模型、写入与召回机制

> 基于 Claude Code 源码（`memdir/`、`services/extractMemories/`）的完整逆向分析。
> 源码版本：2026-03-31。

---

## 摘要

Claude Code 的记忆系统采用**四层固定类型分类**（user / feedback / project / reference），每层记忆均可压缩为一个核心追问：user 回答“这个用户是谁？”，feedback 回答“我以后该怎么做？”，project 回答“这个项目当前处在什么现实语境里？”，reference 回答“如果要查外部信息，我该去哪？”。系统通过**双路径写入**（主代理直写 + 后台提取代理）和**双层召回**（MEMORY.md 索引 + Sonnet 关联选择）实现对记忆的全生命周期管理。

---

## 1. 设计哲学

### 1.1 核心约束：不存可推导信息

源码 `memoryTypes.ts` 头部注释明确定义了记忆系统的边界：

> *"Memories are constrained to four types capturing context NOT derivable from the current project state. Code patterns, architecture, git history, and file structure are derivable (via grep/git/CLAUDE.md) and should NOT be saved as memories."*

这意味着记忆系统只存储**无法从代码、git 历史或项目文件中推导出来的信息**。凡是可以通过 `grep`、`git log`、`CLAUDE.md` 获取的内容，都不属于记忆的范畴。

### 1.2 四类固定类型

```typescript
// memoryTypes.ts 第 14-19 行
export const MEMORY_TYPES = [
  'user',
  'feedback',
  'project',
  'reference',
] as const
```

四种类型是硬编码常量，不可扩展。每种类型有独立的 `description`、`when_to_save`（写入时机）、`how_to_use`（召回时机）和 `scope`（私有/团队）语义。

---

## 2. 四层记忆模型详解

### 2.1 user —— “这个用户是谁？”

| 维度 | 说明 |
|------|------|
| **存储内容** | 用户的角色、目标、职责、知识背景 |
| **设计目标** | 构建对用户的完整画像，使模型能够针对不同用户调整协作方式 |
| **scope** | `always private`——永远私有，不进入团队目录 |
| **body 结构** | 自由格式 |

**源码定义**（第 46-55 行）：

> *"Your goal in reading and writing these memories is to build up an understanding of who the user is and how you can be most helpful to them specifically. For example, you should collaborate with a senior software engineer differently than a student who is coding for the very first time."*

**典型示例**：
- “用户是一名数据科学家，当前聚焦于日志/可观测性”
- “用户有十年 Go 经验，但第一次接触 React 前端——从前端解释时应类比后端概念”

---

### 2.2 feedback —— “我以后该怎么做？”

| 维度 | 说明 |
|------|------|
| **存储内容** | 用户关于工作方法的指导——既包括要避免的，也包括应坚持的 |
| **设计目标** | 使模型保持一致的行为方式，用户无需重复相同的指导 |
| **scope** | 默认 private；仅当指导是明确的项目级约定时存为 team |
| **body 结构** | 规则 → **Why:** → **How to apply:**（三段式） |

**源码定义**（第 60-73 行）：

> *"Record from failure AND success: if you only save corrections, you will avoid past mistakes but drift away from approaches the user has already validated, and may grow overly cautious."*

feedback 的核心设计原则是**双向记录**：既记录纠正（“不要这样做”），也记录确认（“这样做是对的”）。如果只记纠正不记确认，模型会变得越来越保守，最终失去已验证的正确做法。

**body 结构的设计意图**（第 63 行）：

> *"Knowing why lets you judge edge cases instead of blindly following the rule."*

三段式中的 `Why` 不是可有可无的注释——它是模型在边缘情况下判断是否仍应遵循规则的关键依据。

**典型示例**：
- 纠正：“不要在测试中 mock 数据库——上次 mock 通过的测试在生产迁移中失败了。**Why:** mock 与生产环境的差异掩盖了迁移错误。”
- 确认：“这次重构打包成一个 PR 是正确的选择。**Why:** 拆分成多个小 PR 只会增加无效的变更轮次。”

**scope 规则**（第 59 行）：

> *"Save as team only when the guidance is clearly a project-wide convention that every contributor should follow (e.g., a testing policy, a build invariant), not a personal style preference."*

测试策略、构建规范等属于团队级 feedback；个人沟通偏好（如“不要在每个回复末尾总结”）属于私有 feedback。

---

### 2.3 project —— “这个项目当前处在什么现实语境里？”

| 维度 | 说明 |
|------|------|
| **存储内容** | 代码和 git 历史推导不出的现实语境——谁在做什么、为什么、何时 |
| **设计目标** | 理解工作的更广泛语境和动机，预判协调问题 |
| **scope** | `strongly bias toward team`——强烈倾向团队共享 |
| **body 结构** | 事实 → **Why:** → **How to apply:**（三段式） |

**源码定义**（第 78-88 行）：

> *"Information that you learn about ongoing work, goals, initiatives, bugs, or incidents within the project that is not otherwise derivable from the code or git history."*

project 记忆存的是项目的“活语境”——截止日期、合规驱动的重构动机、线上事故原因、团队并行工作等。

**关键规则一：绝对时间**（第 79 行末尾）：

> *"Always convert relative dates in user messages to absolute dates when saving (e.g., 'Thursday' → '2026-03-05'), so the memory remains interpretable after time passes."*

用户说的“周四”必须在存储时转化为绝对日期。否则三周后读到“周四”无法判断具体是哪一天。

**关键规则二：快速衰减**（第 82 行）：

> *"Project memories decay fast, so the why helps future-you judge whether the memory is still load-bearing."*

project 记忆的时效性最强——截止日期过了、发布完成了，记忆就过时了。因此 `Why` 字段对于判断记忆是否仍然有效至关重要。

**典型示例**：
- “2026-03-05 起非关键合并冻结，移动端团队正在切发布分支。**Why:** 发布分支需要稳定基线。**How to apply:** 标记该日期之后的所有非关键 PR 工作。”
- “认证中间件重写是法律/合规要求驱动的，不是技术债清理。**Why:** 会话令牌存储方式不符合新合规要求。**How to apply:** 作用域决策应优先考虑合规性而非工效学。”

---

### 2.4 reference —— “如果要查外部信息，我该去哪？”

| 维度 | 说明 |
|------|------|
| **存储内容** | 外部系统中信息位置的指针 |
| **设计目标** | 记住在项目目录之外哪里可以找到最新信息 |
| **scope** | `usually team`——通常是团队共享 |
| **body 结构** | 自由格式 |

**源码定义**（第 93-103 行）：

> *"Stores pointers to where information can be found in external systems. These memories allow you to remember where to look to find up-to-date information outside of the project directory."*

reference 存的是**指针**，不是内容本身。外部系统的数据是动态的——存 URL/项目名/频道名，实际数据去源头实时查询。

**典型示例**：
- “pipeline bug 在 Linear 项目 'INGEST' 中跟踪”
- “grafana.internal/d/api-latency 是值班延迟仪表盘——修改请求路径代码时应先检查此面板”

---

## 3. 写入机制

记忆写入采用**双路径 + 互斥**架构。

### 3.1 路径一：主代理直写

**实现位置**：`buildMemoryPrompt()` 函数（`memdir/memdir.ts` 第 272-316 行）。

主代理的 system prompt 中包含完整的记忆类型定义（通过 `TYPES_SECTION_INDIVIDUAL` 或 `TYPES_SECTION_COMBINED` 注入）、保存方法指引、以及现有的 `MEMORY.md` 索引内容。模型在对话过程中自行判断是否应保存记忆，并直接调用 Write 工具写入文件。

保存流程（两步）：
1. **Step 1**：将记忆内容写入独立文件（如 `user_role.md`），使用 YAML frontmatter 声明 `name`、`description`、`type`
2. **Step 2**：在 `MEMORY.md` 中添加一行索引：`- [Title](file.md) — one-line hook`（限 ~150 字符）

### 3.2 路径二：后台提取代理

**实现位置**：`services/extractMemories/extractMemories.ts`（615 行）。

后台提取代理是一个独立的异步子进程，fork 自主对话。其工作机制如下：

1. **触发时机**：每次用户 query 完成后（`handleStopHooks`），由 `executeExtractMemories()` 调用
2. **频率控制**：通过 feature flag `tengu_bramble_lintel` 控制每 N 轮触发一次（默认每轮）
3. **光标机制**：通过 `lastMemoryMessageUuid` 追踪已处理的消息，每次只分析新增的消息
4. **子代理限制**：
   - 最多 5 个 turn（`maxTurns: 5`）
   - 只允许 Read/Grep/Glob/read-only Bash，Write/Edit 仅限于记忆目录内
   - 不允许 MCP、Agent 等外部工具
5. **优化策略**（prompts.ts 第 39 行）：*"turn 1 — issue all Read calls in parallel for every file you might update; turn 2 — issue all Write/Edit calls in parallel. Do not interleave reads and writes across multiple turns."*

提取代理的 prompt 中注入了现有记忆文件的 manifest（通过 `scanMemoryFiles` 扫描所有 `.md` 的 frontmatter），避免子代理浪费一个 turn 执行 `ls`。

### 3.3 双路径互斥

**实现位置**：`extractMemories.ts` 第 121-148 行。

```typescript
function hasMemoryWritesSince(messages, sinceUuid): boolean {
  // 检查主代理的 assistant 消息中是否包含对记忆目录的 Write/Edit
  // 如果主代理已写入 → 返回 true → 后台代理跳过此轮
}
```

两条路径互斥的逻辑：如果主代理在响应中已经写了记忆文件，后台代理直接跳过此轮并推进光标。这确保了同一轮对话不会产生重复记忆。

### 3.4 写入时机总览

| 类型 | 主代理写入触发 | 后台代理提取触发 |
|------|---------------|-----------------|
| **user** | 用户自曝身份/技能/偏好 | 从对话中推断出的用户画像 |
| **feedback** | 纠正词（"no not that"）+ 确认词（"yes exactly"） | 从对话中识别的纠正/确认信号 |
| **project** | 用户透露计划/截止日期/动机 | 从对话中提取的项目语境信息 |
| **reference** | 用户提及外部系统/资源 | 从对话中识别外部系统引用 |

---

## 4. 召回机制

### 4.1 索引加载

**实现位置**：`memdir/memdir.ts` 第 295-313 行。

`MEMORY.md` 的内容始终作为 system prompt 的一部分注入。当记忆目录中没有 `MEMORY.md` 时，注入提示信息；当文件超过 200 行或 25KB 时，截断并追加警告。

### 4.2 自动关联选择

**实现位置**：`memdir/findRelevantMemories.ts`（141 行）。

这是记忆召回的核心引擎，采用**二阶段选择**机制：

**阶段一：扫描**（`scanMemoryFiles`，`memoryScan.ts` 第 35-77 行）

```typescript
export async function scanMemoryFiles(memoryDir, signal): Promise<MemoryHeader[]> {
  const entries = await readdir(memoryDir, { recursive: true })
  const mdFiles = entries.filter(f => f.endsWith('.md') && basename(f) !== 'MEMORY.md')
  // 并行读取每个 .md 的前 30 行，解析 frontmatter
  // 按 mtime 降序排列，截取前 200 个
}
```

每个记忆文件只需读取 frontmatter（前 30 行），提取 `filename`、`description`、`type`、`mtimeMs` 四个字段。`MEMORY.md` 自身被排除在外（它已通过索引加载）。

**阶段二：选择**（`selectRelevantMemories`，第 77-141 行）

```typescript
async function selectRelevantMemories(query, memories, signal, recentTools): Promise<string[]> {
  const manifest = formatMemoryManifest(memories) // 格式化为文本列表
  const result = await sideQuery({
    model: getDefaultSonnetModel(),
    system: SELECT_MEMORIES_SYSTEM_PROMPT,  // Sonnet 选择器 prompt
    messages: [{ role: 'user', content: `Query: ${query}\n\nAvailable memories:\n${manifest}` }],
    max_tokens: 256,
    output_format: { type: 'json_schema', ... }  // 强制 JSON 输出
  })
  // 返回 selected_memories 数组（最多 5 个文件名）
}
```

选择器使用一个独立的 Sonnet 调用（`sideQuery`），输入为：
- **用户原始 query**
- **所有记忆文件的 manifest**：`[type] filename (ISO时间): description`
- **最近使用的工具列表**（用于过滤策略，见下文）

输出为 JSON：`{ "selected_memories": ["user_role.md", "feedback_testing.md"] }`，最多 5 个。

**选择器的特殊过滤规则**（`SELECT_MEMORIES_SYSTEM_PROMPT` 第 23 行）：

> *"If a list of recently-used tools is provided, do not select memories that are usage reference or API documentation for those tools (Claude Code is already exercising them). DO still select memories containing warnings, gotchas, or known issues about those tools — active use is exactly when those matter."*

当模型正在活跃使用某工具时：
- ❌ 不召回该工具的 API 使用文档（已是噪声）
- ✅ 仍召回该工具的 warnings/gotchas/已知问题（活跃使用恰是需要这些信息的时候）

**已浮现去重**（第 44 行参数 `alreadySurfaced`）：
- 前几轮已经展示过的记忆文件会被过滤掉，确保 5 个槽位用于新的候选记忆而非重复推荐

### 4.3 漂移验证

**实现位置**：`memoryTypes.ts` 第 201-202 行。

> *"Before answering the user or building assumptions based solely on information in memory records, verify that the memory is still correct and up-to-date by reading the current state of the files or resources. If a recalled memory conflicts with current information, trust what you observe now — and update or remove the stale memory rather than acting on it."*

召回后的记忆并非无条件信任。系统要求模型在使用记忆前执行验证：
1. 记忆提到文件路径 → `ls` 确认文件存在
2. 记忆提到函数/flag → `grep` 确认仍在代码中
3. 记忆与当前状态冲突 → **信任当前观察**，更新或删除过时记忆

`TRUSTING_RECALL_SECTION`（第 240-256 行）进一步强调：

> *"A memory that names a specific function, file, or flag is a claim that it existed when the memory was written. It may have been renamed, removed, or never merged."*

### 4.4 召回时机总览

| 层 | 机制 | 触发时机 |
|----|------|---------|
| **索引层** | `MEMORY.md` 内容注入 system prompt | 每次对话开始 |
| **关联选择层** | `findRelevantMemories` side query | 每次用户发消息时并行执行 |
| **手动搜索层** | `grep -rn "<term>" <memdir> --include="*.md"` | 模型主动搜索时 |
| **验证层** | `TRUSTING_RECALL_SECTION` 规则 | 使用召回的记忆前 |

---

## 5. 存储结构

### 5.1 目录布局

记忆文件存放在 `~/.claude/projects/<sanitized-git-root>/memory/` 目录下（通过 `paths.ts` 中的 `getAutoMemPath()` 解析）。

```
~/.claude/projects/<sanitized-repo-path>/memory/
├── MEMORY.md              # 索引文件（始终加载到 system prompt）
├── user_role.md           # 带 frontmatter 的记忆文件
├── feedback_testing.md
├── project_merge_freeze.md
└── reference_linear_ingest.md
```

### 5.2 记忆文件格式

每个记忆文件使用 YAML frontmatter 声明元数据：

```markdown
---
name: {{memory name}}
description: {{one-line description — used to decide relevance in future conversations, so be specific}}
type: {{user, feedback, project, reference}}
---

{{memory content}}
```

### 5.3 索引文件格式

`MEMORY.md` 是纯文本索引，不含 frontmatter：

```markdown
- [User Role](user_role.md) — senior Go engineer, new to React frontend
- [Integration Tests No Mocks](feedback_testing.md) — tests must use real database
- [Merge Freeze March 2026](project_merge_freeze.md) — non-critical merges frozen after 2026-03-05
- [Linear INGEST Project](reference_linear_ingest.md) — pipeline bugs tracked here
```

索引条目限制：
- 每行 ~150 字符
- 总行数 ≤ 200（超出截断）
- 总字节数 ≤ 25KB（超出截断）

### 5.4 容量限制

| 限制项 | 值 | 定义位置 |
|--------|-----|---------|
| 索引行数上限 | 200 行 | `MAX_ENTRYPOINT_LINES` |
| 索引字节上限 | 25 KB | `MAX_ENTRYPOINT_BYTES` |
| 记忆文件数上限 | 200 个 | `MAX_MEMORY_FILES` |
| Frontmatter 读取行数 | 30 行 | `FRONTMATTER_MAX_LINES` |
| 选择器最多返回 | 5 个文件 | `findRelevantMemories` |

---

## 6. 记忆范围（Scope）

系统支持两种范围模式：

### 6.1 单目录模式（Individual-only）

默认模式。所有记忆存储在同一目录下，无私有/团队区分。使用 `TYPES_SECTION_INDIVIDUAL` prompt。

### 6.2 双目录模式（Combined）

通过 feature flag `TEAMMEM` 启用。两个目录：

- **私有目录**：`~/.claude/projects/<repo>/memory/`
- **团队目录**：`~/.claude/projects/<repo>/memory/team/`

各类型的 scope 指引：

| 类型 | scope | 说明 |
|------|-------|------|
| user | always private | 用户画像是个人隐私 |
| feedback | 默认 private | 仅项目级约定存为 team |
| project | strongly team | 项目语境应团队共享 |
| reference | usually team | 外部资源指针团队共享 |

---

## 7. 不应存入记忆的内容

`WHAT_NOT_TO_SAVE_SECTION`（第 183-195 行）明确列出了排除项：

| 类别 | 原因 |
|------|------|
| 代码模式/规范/架构/文件路径 | 可通过阅读当前项目状态推导 |
| Git 历史/最近变更/谁改了什么 | `git log` / `git blame` 是权威来源 |
| 调试方案/fix 配方 | 修复本身已在代码中；commit message 包含上下文 |
| CLAUDE.md 中已有的内容 | 避免重复 |
| 临时任务细节：进行中的工作、临时状态、当前对话上下文 | 这些属于 plan/task 的范畴 |

此外，以下内容即使用户明确要求也不应存入：

> *"These exclusions apply even when the user explicitly asks you to save. If they ask you to save a PR list or activity summary, ask what was surprising or non-obvious about it — that is the part worth keeping."*

---

## 8. 与其他持久化机制的边界

`buildMemoryLines` 函数（`memdir.ts` 第 254-258 行）明确了记忆与 plan/task 的边界：

| 机制 | 用途 | 生命周期 |
|------|------|---------|
| **Memory** | 跨对话持久化的信息 | 长期 |
| **Plan** | 非平凡实现任务的方法对齐 | 单次对话 |
| **Task** | 当前对话中的分步工作跟踪 | 单次对话 |

---

## 9. 辅助模式（KAIROS）

通过 feature flag `KAIROS` 启用的特殊模式（`memdir.ts` 第 327-370 行）：

在长期运行的 assistant 会话中，记忆不直接写入 topic 文件，而是**追加到按日期命名的日志文件**：

```
~/.claude/projects/<repo>/memory/logs/2026/06/2026-06-10.md
```

每晚由独立的 `/dream` skill 将日志提炼为 topic 文件并更新 `MEMORY.md` 索引。此模式下，`MEMORY.md` 仍加载到上下文中，但模型只读不写。

---

## 10. 总结

Claude Code 的记忆系统是一个精密的**四层固定类型分类 + 双路径写入 + 双层召回 + 漂移验证**架构：

- **四层记忆**覆盖了 AI 辅助编程所需的全部跨对话持久化信息：用户画像（user）、行为指导（feedback）、项目语境（project）、外部指针（reference）
- **双路径写入**通过主代理直写和后台提取代理的互斥协作，确保记忆既能在模型主动判断时即时写入，也能在被动场景下自动补全
- **双层召回**通过 MEMORY.md 索引和 Sonnet 侧查询并行选择，在保证覆盖率的同时控制上下文消耗（最多 5 个文件）
- **漂移验证**要求模型在使用记忆前验证其时效性，防止过时信息产生错误建议
- **严格的“不存可推导信息”原则**确保记忆系统保持低噪声，不与 `grep`/`git log`/`CLAUDE.md` 等实时工具产生冗余

该设计的核心洞察是：**代码可以被工具实时检索，但人的意图、偏好、决策动机和外部知识的“位置”无法从代码中推导**——这正是记忆系统存在的根本原因。
