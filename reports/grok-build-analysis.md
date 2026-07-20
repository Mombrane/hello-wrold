# Grok Build (grok) 源码分析报告

> 仓库: https://github.com/xai-org/grok-build  
> 语言: Rust (edition 2024, ~60+ crates)  
> 许可证: Apache 2.0  
> 定位: xAI 的终端 AI 编码 agent（对标 Claude Code / Codex CLI）  
> 分析日期: 2026-07-20

---

## 1. 项目概览

Grok Build 是 SpaceXAI 的终端 AI 编码 agent，运行在全屏 TUI 中。它可以理解代码库、编辑文件、执行 shell 命令、搜索网页、管理长运行任务——交互式使用、headless 脚本/CI、或通过 ACP 嵌入编辑器。

**关键信息：**
- 从 SpaceXAI monorepo 定期同步出来，`SOURCE_REV` 记录 monorepo commit SHA
- 不接受外部贡献
- 二进制产物叫 `xai-grok-pager`，发布时重命名为 `grok`
- 预编译二进制支持 macOS / Linux / Windows

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                     Leader Process                           │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                   MvpAgent (agent 核心)                   ││
│  │   - 共享状态 (所有 client 共享)                           ││
│  │   - 持久化到 ~/.grok/                                    ││
│  └─────────────────────────────────────────────────────────┘│
│                           ▲                                  │
│                           │ ACP (JSON-RPC)                   │
│  ┌────────────────────────┴────────────────────────────────┐│
│  │               IPC Server (Unix Socket)                   ││
│  └────────────────────────┬────────────────────────────────┘│
└───────────────────────────┼──────────────────────────────────┘
                            │ Unix socket (~/.grok/leader.sock)
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│   TUI Client  │   │  IDE Extension │   │ Headless CLI  │
│   (ratatui)   │   │   (stdio)      │   │  (websocket)  │
└───────────────┘   └───────────────┘   └───────────────┘
```

**关键设计决策：**

| 决策 | 说明 |
|------|------|
| Leader-follower 架构 | 一个 Leader 进程管理 agent 状态，多个 client（TUI/IDE/headless）通过 Unix socket 通信 |
| ACP 协议 | 使用 Agent Client Protocol（agentclientprotocol.com）作为标准通信协议 |
| LocalSet 单线程 | MvpAgent 跑在 tokio `LocalSet` 上，用 `LocalRef<T>` 原始指针绕过 borrow checker |
| 持久化到 ~/.grok/ | session 存在磁盘，可恢复 |

---

## 3. Agent 核心架构

### 3.1 Agent Turn 三层嵌套架构 ⭐

**文件:** `crates/codegen/xai-grok-shell/src/session/acp_session_impl/turn.rs`

agent 的 turn 处理有**三层嵌套循环**，这是 grok 最精巧的设计之一：

```
外层 handle_prompt()         ← 生命周期钩子、goal continuation、stop gate
  ├── on_turn_start 钩子
  ├── 解析 slash commands / skills / 图片
  ├── 内层 loop（支持 goal continuation + stop gate）:
  │    loop {
  │        round = process_conversation_turn_with_recovery()
  │        if goal_active: run_goal_round_end() → inject continuation → continue
  │        match run_stop_gate():
  │            AllowStop → break
  │            KeepWorking → push feedback → continue
  │    }
  └── on_turn_done / on_turn_abort / on_turn_error 钩子

中层 process_conversation_turn_with_recovery()   ← Completion Requirement 自动恢复
  ├── 如果 agent 定义了必须调用某个 tool，失败后自动重试
  ├── loop for 1..=max_retries:
  │    sleep(指数退避)
  │    push auto_recovery_prompt
  │    if required_tool_was_called { break }
  └── 耗尽 → 通知 AutoRecoveryExhausted

内层 process_conversation_turn()                  ← LLM 交互 loop
  ├── drain pending interjections / skill reminders / monitor events
  ├── check_auto_compact_needed()
  ├── run_turn_via_sampler(request)  ← 流式 LLM 调用
  ├── if no tool_calls: TodoGate + StructuredOutput validation → return
  ├── execute_tool_calls():
  │    ├── PermissionReject → Cancelled
  │    ├── HookDenied → continue
  │    ├── FollowupMessage → push + continue
  │    └── Cancelled → return
  ├── MaxTurns check → return if exceeded
  └── continue（下一轮 tool-use 迭代）
```

**核心设计哲学：completion-driven 链式推进**——每个 turn 的完成回调自动驱动下一个 pending prompt，形成自驱动的事件循环。

### 3.2 MvpAgent

**文件:** `crates/codegen/xai-grok-shell/src/agent/mvp_agent/mod.rs` (2630 行)

MvpAgent 是 agent 的中央调度器，管理：
- **Session 生命周期** (`session_lifecycle.rs`)：创建、加载、fork、恢复、sweep dead actors
- **Subagent 协调** (`subagent_coordinator.rs`)：spawn、查询、取消
- **ACP 代理** (`acp_agent.rs`)：处理 ACP 协议消息
- **Prompt 处理**：解析、采样、流式输出

### 3.2 Session 管理

**文件:** `crates/codegen/xai-grok-shell/src/session/handle.rs`

Session 是一个 actor 模型：
- `SessionHandle` — `Clone + Send` 代理，通过 `mpsc::UnboundedSender<SessionCommand>` 与 actor 通信
- `SessionLiveState` 枚举：`Working` / `IdleResident` / `Dormant` / `Completed` / `DeadFailed`
- Session 没有"终结"状态——它是磁盘上的可恢复日志

**PromptOrigin** (提示词来源) 枚举很有意思：

| 来源 | 说明 |
|------|------|
| `User` | 用户发起的提示词 |
| `TaskCompleted` | 后台 terminal 任务完成后的自动唤醒 |
| `SubagentCompleted` | 子代理完成后的自动唤醒 |
| `NotificationDrain` | 空闲时的通知批量处理 |
| `GoalSummary` | Goal orchestrator 注入的进度更新 |
| `VerificationNudge` | 验证阶段的推进 |

### 3.4 子代理 (Subagent) 系统

**文件:** `crates/codegen/xai-grok-shell/src/agent/mvp_agent/subagent_coordinator.rs` (644 行), `agent/subagent/handle_request.rs:77`

- 子代理是**独立的 child session**，有自己的 context window
- SubagentCoordinator 事件驱动：`Spawn` / `Query` / `Cancel` / `ListActive` / `Completions`
- `MAX_SUBAGENT_DEPTH` 深度限制——到达最大深度时移除 task tool
- 隔离模式：None / Worktree（copy-on-write 文件系统）
- **Block-wait**：父代理可阻塞等待（200ms 轮询 + 30s 超时）
- **工具快照继承**：子代理继承 MCP pool、client hooks、tool definitions
- **Session 重归属**：子 session spawn 可被重归属到 root session
- **Agent vs Persona 两层抽象**：
  - Agent 决定 session 本身（模型、工具、系统提示）
  - Persona 是行为覆盖层，只影响子代理（语调、输出格式、任务聚焦）

### 3.5 Goal 系统（内置的 multi-step planner）

**文件:** `crates/codegen/xai-grok-shell/src/session/templates/goal_*.md`

Grok 有一套内置的 goal 系统模板：
- `goal_task_discipline.md` — 任务纪律规则（"先调用工具再叙述"、"不要问不必要的权限"、"不要停下有简单工作未完成"）
- `goal_planner_prompt.md` — 规划器提示
- `goal_strategist_prompt.md` — 策略师提示
- `goal_verifier_prompt.md` — 验证器提示
- `goal_summarizer_prompt.md` — 总结器提示
- `goal_rules.md` — 规则

这说明 grok 内部有一个 **planner → strategist → verifier → summarizer** 的多阶段 goal 流水线。

---

## 4. 上下文压缩 (Compaction) ⭐ 重点

这是 grok-build 最有价值的部分，因为我们之前在调研 Codex CLI 和 OpenCode 的压缩机制。

### 4.1 总体设计

**文件:** `crates/common/xai-grok-compaction/src/lib.rs`

grok 的 compaction 是**传输无关、策略共享**的独立 crate。它通过 trait seam 与 grok-build 和 Grok chat 两个宿主解耦：

- `CompactionItem` / `CompactionRole` — 抽象一个 turn
- `ItemTokenCounter` — token 计数
- `CompactionSampler` — LLM 调用
- `CompactionStreamProc` — 状态提交

### 4.2 LLM 交互与失败恢复

**文件:** `crates/codegen/xai-grok-shell/src/session/acp_session_impl/sampler_turn.rs:860`

LLM 交互通过 `SamplerHandle.submit_and_collect()` 进行流式 SSE 调用：

| 失败类型 | 恢复策略 | 位置 |
|----------|----------|------|
| Context window overflow | Compaction → 重试 | sampler_turn.rs:903-905 |
| HTTP 401 (auth) | Token refresh → 指数退避 (最多 N 次) | sampler_turn.rs:908-909 |
| Content filter refusal | 返回 refusal notice，不重试 | turn.rs:2125-2143 |
| Tool 401 | `OnceCell` 去重 → `AuthManager.recover` → 一次重试 | sampler_turn.rs:66-109 |
| JWT 临近过期 | 主动 refresh（5min 阈值） | sampler_turn.rs:924-1050 |
| Completion requirement fail | 指数退避 + recovery prompt, max `recovery.max_retries` 次 | turn.rs:1419-1510 |
| Structured output validation fail | 最多 3 次 retry → error message → re-sample | turn.rs:1597-1648 |
| Doom loop (死循环检测) | `DoomLoopTally` 统计 → 自动恢复 | turn.rs:1008-1019 |
| Max turns exceeded | 立即返回 `TurnOutcome::MaxTurnsReached` | turn.rs:2322-2326 |

### 4.3 三种压缩策略

| 策略 | 模块 | 用途 | 算法 |
|------|------|------|------|
| **code_compaction** | `code_compaction/` | grok-build (coding agent) | **full-replace**：总结整个对话，重建全新 history |
| **intra_compaction** | `intra_compaction/` | Grok chat | **tail-keep**：保留尾部，逐步压缩 |
| **inter_compaction** | `inter_compaction/` | Grok chat | **chunked between-turn**：分块，在 turn 之间压缩 |

### 4.4 Full-Replace 压缩（coding agent 的核心策略）

**文件:** `crates/common/xai-grok-compaction/src/code_compaction/`

grok-build 不使用"保留尾部"策略。它**总结整个对话**，然后**从零重建 history**。

**触发条件：**
- 默认阈值：**85%** 上下文窗口 (`DEFAULT_AUTO_COMPACT_THRESHOLD_PERCENT`)
- 可通过环境变量、用户配置、remote per-model/global flags 覆盖

**压缩流程：**
```
build prompt → sample (retry + classify) → clean → assemble
```

**FullReplaceConfig 默认值：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_attempts` | 3 | 最多 LLM 调用尝试次数 |
| `retry_delay_secs` | 3 | 重试间隔 |
| `sampling_timeout_secs` | 120 | 每次 LLM 调用超时 |
| `MIN_SUMMARY_SEED_CHARS` | 500 | 最短有效摘要字符数（短于此则重试） |

**失败分类 (`failure.rs`)：**
- `deterministic` — 重发相同输入无济于事 → 抑制 auto-compaction
- `context_overflow` — 上下文溢出 → 用更小的输入重试（verbatim→fitted→lossy 阶梯）

### 4.5 IntraCompaction 的 4 种模式变体

**文件:** `crates/common/xai-grok-compaction/src/intra_compaction/compact.rs:74-139`

IntraCompaction（Grok chat 用）有 4 种模式变体，通过 `mode` 参数切换：

| 模式 | 算法 | 使用场景 |
|------|------|----------|
| **FullReplace** | 整对话总结 → 重建（由 `code_compaction` 核心驱动） | 默认 |
| **StepsOnly** | 只压缩当前循环的步骤轮次（尾部保留） | 活跃对话，只需压缩当前任务 |
| **HistoryOnly** | 只压缩历史轮次 | 长对话，历史可压缩 |
| **HistoryThenSteps** | 先历史后步骤（如果步骤 token 占比 > `steps_trigger_ratio` 的 30%） | 混合场景 |

**配置参数** (`intra_compaction/config.rs:84-201`)：

| 参数 | 值 | 说明 |
|------|-----|------|
| `trigger_threshold_percent` | 85% | 触发阈值 |
| `target_threshold_percent` | 50% | 压缩后目标 |
| `min_compactable_tokens` | 5000 | 最小可压缩 token 数 |
| `max_reduction_ratio` | 0.8 | 至少减少 20% |
| `compaction_model_name` | `grok-4.20` | 压缩专用模型 |
| `min_steps_before_compact` | 3 | FullReplace 忽略此值 |

### 4.6 SplitPlan 分割算法（关键安全机制）

**文件:** `crates/common/xai-grok-compaction/src/select.rs:60-119`

`select_turns_to_compact()` 决定在对话的哪个位置切割"保留"和"压缩"两部分：

1. 从最新项向后遍历，累计"保留"端的 token
2. 当添加下一项会超出 `target_tokens` 时设置分割点
3. **安全边界修正**：如果分割点落在 tool-result 项上，前移越过所有 tool-result 项——**避免孤立 tool 结果导致 API 400 错误**
4. 如果可压缩 token 低于 `min_compactable`（默认 5000），返回 `None`（不值得压缩）

### 4.7 摘要 Prompt

**文件:** `crates/common/xai-grok-compaction/src/code_compaction/templates/full_replace_summary_prompt.txt`

这是一个**结构化的 9 段摘要模板**（与 Claude Code 的 compaction prompt 非常相似）：

1. **Primary Request and Intent** — 用户的显式请求和意图
2. **Key Technical Concepts** — 涉及的技术栈
3. **Files and Code Sections** — 检查/创建/修改的文件（要求完整代码片段）
4. **Errors and Fixes** — 错误和修复
5. **Problem Solving** — 已解决问题和进行中的诊断
6. **All User Messages** — 所有用户消息（不含系统生成的 compaction 指令）
7. **Pending Tasks** — 未完成的任务
8. **Current Work** — 压缩前正在做什么（足够具体以便恢复）
9. **Optional Next Step** — 下一步建议

还有一个**简化版** `SELF_SUMMARIZATION_PROMPT`（约 10 行），用于 harness 的 self-summary 场景。

### 4.8 与其他 agent 的压缩对比

| 特性 | Grok Build | Claude Code | Codex CLI | OpenCode |
|------|-----------|-------------|-----------|----------|
| 压缩策略 | **full-replace** (全量替换) | 结构化摘要 + 尾部保留 | Memento 本地压缩 + remote v2 加密 token | 结构化摘要 + 增量更新 |
| 触发阈值 | 85% 上下文窗口 | ~70-85% 可配置 | 基于 token 预算 | 基于溢出检测 |
| 压缩粒度 | 整个 session | 可选择保留最近 N 轮 | 基于 turn 的 compact | 增量摘要 |
| 失败处理 | 三级阶梯重试 + transient/deterministic 分类 | 降级策略 | 失败回退 | — |
| **摘要 prompt** | **9 段结构化模板**（最详细） | 结构化摘要 | Memento 特定格式 | 结构化摘要 |

**我的判断：** Grok 的 full-replace 策略是最大胆的——它丢弃了所有历史细节，完全依赖摘要。这节省了最多的 token，但风险也最高（摘要质量决定了后续工作的质量）。相比之下，Claude Code 和 OpenCode 的"结构化摘要 + 尾部保留"是更保守但更安全的做法。

---

## 5. 工具系统

### 5.1 Tool Taxonomy

**文件:** `crates/codegen/xai-grok-tools/src/tool_taxonomy.rs`

Grok 有 30+ 种工具类型 (`ToolKind`)：

| 类别 | 工具 |
|------|------|
| 文件操作 | `Read`, `Edit`, `Delete`, `Write`, `Move` |
| 搜索/浏览 | `Search`, `ListDir`, `List`, `Lsp` |
| 执行 | `Execute` (shell), `BackgroundTaskAction`, `WaitTasksAction`, `KillTaskAction` |
| 规划 | `Plan`, `EnterPlan`, `ExitPlan` |
| 网络 | `WebSearch`, `WebFetch` |
| 记忆 | `MemorySearch`, `MemoryGet` |
| Agent | `Task` (subagent), `Skill`, `AskUser` |
| 生成 | `ImageGen`, `VideoGen`, `ImageToVideo` |
| 部署 | `DeployApp`, `Monitor` |
| 其他 | `SearchTool`, `UseTool`, `GoalUpdate` |

### 5.2 多命名空间工具

Grok 支持**6 种工具命名空间**（`ToolNamespace`）：

| 命名空间 | 说明 |
|----------|------|
| `GrokBuild` | 默认工具集 |
| `GrokBuildConcise` | 精简版（更短的工具描述） |
| `GrokBuildHashline` | 基于 hash-line 的工具（类似 Codex 的行哈希寻址） |
| **`Codex`** | **从 openai/codex 移植的工具** |
| **`OpenCode`** | **从 sst/opencode 移植的工具** |
| `MCP` | MCP 服务器提供的动态工具 |

### 5.3 OpenCode 移植工具

**文件:** `crates/codegen/xai-grok-tools/src/implementations/opencode/`

从 sst/opencode (MIT License) 移植的工具：
- `bash` — shell 执行
- `edit` — 文件编辑（`filePath`, `oldString`, `newString`）
- `glob` — 文件匹配
- `grep` — 内容搜索
- `read` — 文件读取
- `skill` — 技能调用
- `todowrite` — TODO 管理
- `write` — 文件写入

注意：`write` 工具的参数被规范化为了 snake_case (`file_path`) 以保持 grok_build 一致性——其他 OpenCode 工具保留 camelCase 命名。

### 5.4 Codex 移植工具

**文件:** `crates/codegen/xai-grok-tools/src/implementations/codex/mod.rs`

从 openai/codex (Apache 2.0, Copyright 2025 OpenAI) 移植的 **4 个工具**：
- `apply_patch` — 应用补丁
- `grep_files` — 内容搜索
- `list_dir` — 目录列表
- `read_file` — 文件读取

### 5.5 工具注册流程

**文件:** `crates/codegen/xai-grok-tools/src/registry/types.rs:657-743`

```rust
// ToolRegistryBuilder::new() 是单例入口点
// 通过 register::<T>() 或 register_with_params::<T, P>() 注册
// 自动生成 FQN: "<Namespace>:<id>" 如 "GrokBuild:read_file"
```

工具系统使用**双 Trait 架构**：
1. `xai_tool_runtime::Tool` — 运行时 trait（`Args`、`Output`、`run()`/`execute()`）
2. `ToolMetadata` — 元数据 trait（`kind()`、`tool_namespace()`）

工具分发通过 `ToolDispatch` trait（object-safe）和 `ToolDyn` blanket impl 实现类型擦除，流式输出遵循 `[Progress*, Terminal]` 不变式。

### 5.6 MCP 集成

**文件:** `crates/codegen/xai-grok-mcp/src/`

- 使用 `rmcp` 2.1 Rust 库
- 支持 Streamable HTTP 和 stdio 两种 transport
- OAuth 支持（浏览器-based 流程）
- 凭证持久化到 `$GROK_HOME/mcp_credentials.json`

### 5.6 工具规范化的 `_meta` 信封

**文件:** `crates/codegen/xai-grok-tools/src/tool_taxonomy.rs`

Grok 在每个 tool call 的 `_meta` 中附加一个规范化的 `x.ai/tool` 信封：

```json
{
  "version": 1,
  "name": "read_file",
  "kind": "read",
  "namespace": "grok_build",
  "label": "Read",
  "read_only": true,
  "input": { "path": "/a" }
}
```

这个信封允许跨 harness（grok-build、Codex、OpenCode）统一分析工具调用，即使底层工具名称不同。

---

## 6. Workspace & VCS

### 6.1 VCS 支持

**文件:** `crates/codegen/xai-grok-workspace/src/session/git.rs`, `jj.rs`

Grok 支持**两种** VCS，通过统一的 `GitInfoData`/`GitStatusData` 接口抽象：

| VCS | 说明 |
|-----|------|
| **Git** | 完整支持：info、status、diff、log、branch、commit |
| **Jujutsu (jj)** | 与 git colocated 使用，通过 `jj` CLI 操作 |

### 6.2 Checkpoint / Rewind 机制（三级系统）

**文件:** `crates/codegen/xai-grok-workspace/src/session/checkpoint.rs` (1049 行)

Grok 的 checkpoint 是**三级系统**，在每个 turn 边界自动捕获：

| 级别 | 内容 | 用途 |
|------|------|------|
| 文件系统快照 | `RewindPoint` 文件状态 | 文件级回退 |
| Git HEAD/index | 当前 git 状态 | VCS 级回退 |
| Hunk delta | `HunkTurnDelta` 增量 | 精确到 hunk 的回退 |

- 每个 `prompt_index` 一个 checkpoint
- 可选持久化到 `.grok/rewind-checkpoints/`
- `TurnBoundary` 定义了 turn 开始/结束的回调
- 回滚只恢复启用的域（一起恢复或单独恢复）

### 6.3 Sandbox 隔离

**文件:** `crates/codegen/xai-grok-pager/docs/user-guide/18-sandbox.md`

Grok 的沙箱使用 **OS 级内核原语**（Linux: Landlock, macOS: Seatbelt）：

| Profile | FS 读取 | FS 写入 | 子进程网络 | 场景 |
|---------|---------|---------|-----------|------|
| `off` | 无限制 | 无限制 | 无限制 | 默认 |
| `workspace` | 全局 | CWD + ~/.grok/ + /tmp | 允许 | 日常开发 |
| `read-only` | 全局 | ~/.grok/ + /tmp | 阻止¹ | 代码审查 |
| `strict` | CWD + 系统路径 | CWD + ~/.grok/ + /tmp | 阻止¹ | 不信任代码 |
| `devbox` | 全局 | 除 /data 外的所有顶层目录 | 允许 | 可销毁开发 VM |

¹ 子进程网络阻止仅在 Linux 有效（seccomp），macOS 是 no-op。

支持**自定义 profile**：可继承内置 profile 并添加 `deny` 列表、`restrict_network` 等覆盖。

---

## 7. 安全模型

### 7.1 权限模式

**文件:** `crates/codegen/xai-grok-workspace/src/permission/rules.rs`

| 模式 | 效果 |
|------|------|
| `default` | 默认询问 |
| `acceptEdits` | 自动接受编辑操作 |
| `plan` | 计划模式（只读除 plan.md） |
| `auto` | 分类器 auto 模式 |
| `dontAsk` | 不询问 |
| `bypassPermissions` | 完全绕过权限检查 |

这和 Claude Code 的权限模式基本一一对应。

### 7.2 Plan Mode

**文件:** `crates/codegen/xai-grok-pager/docs/user-guide/19-plan-mode.md`

- 进入后 agent **只读**（除 plan.md 外）
- 编辑非 plan 文件直接拒绝（在任何权限模式下）
- 用户审批 plan 后才能进入实现阶段
- 可通过 `/plan` 或 `Shift+Tab` 切换

---

## 8. TUI 和客户端

### 8.1 TUI 架构

**文件:** `crates/codegen/xai-grok-pager/src/`

- 基于 **ratatui** Rust TUI 框架，但建立了**自定义渲染管线**
- `xai-ratatui-inline::Terminal` 实现了 **cell 级 diff 渲染**——只重绘变化的单元格，性能优于 ratatui 标准 API
- 组件树：`AppView → AgentView → ScrollbackPane/PromptWidget` 三层结构
- 输入路由：**三级冒泡**（overlay → pane → agent → global）
- 支持 OSC 8 超链接、光标去重
- 自定义组件：`xai-ratatui-textarea`（文本区域）
- `views/` 模块：welcome、timeline、turn_status、todo_pane、tasks_pane
- 支持 **minimal 模式**（scrollback-native）通过 `xai-grok-pager-minimal` crate

相比 Claude Code 的 Ink (React for CLI)，grok 的 ratatui 方案在渲染性能上有显著优势——cell 级 diff 避免了全屏重绘。

### 8.2 ACP (Agent Client Protocol) 集成

- stdio 模式：IDE 扩展（Zed, Neovim, Emacs）
- WebSocket server 模式：远程客户端
- WebSocket relay 模式：通过互联网连接 agent

---

## 9. 对比分析与关键洞察

### 9.1 Grok Build vs Claude Code vs Codex CLI

| 维度 | Grok Build | Claude Code | Codex CLI |
|------|-----------|-------------|-----------|
| 语言 | **Rust** | TypeScript/Node.js | Rust |
| TUI 框架 | **ratatui** (Rust native) | Ink (React for CLI) | crossterm + custom |
| 压缩策略 | **full-replace** | 结构化摘要 + 尾部保留 | Memento 本地 + remote v2 |
| VCS 支持 | **Git + Jujutsu** | Git | Git |
| 沙箱 | **Landlock/Seatbelt** (OS 内核级) | 无 OS 级沙箱 | 容器/沙箱 |
| 工具生态 | **6 种工具命名空间**（含 Codex/OpenCode 移植） | 自有工具 | 自有工具 + MCP |
| IDE 集成 | **ACP 协议** | LSP + 自有协议 | 自有协议 |
| 多客户端 | ✅ Leader-follower IPC | 🟡 单实例 | 🟡 单实例 |
| 子代理 | ✅ 独立 context window | ✅ 独立 context | ✅ 独立 context |
| Goal 系统 | ✅ 内置多阶段 planner | 🟡 通过 system prompt | ❌ |

### 9.2 我认为最有价值的设计

1. **full-replace 压缩是大胆但有风险的选择。** 9 段结构化摘要模板是见过最详细的，但完全依赖摘要质量。一旦摘要有遗漏，后续工作就会出问题。Claude Code 的"摘要 + 尾部保留"更稳健。

2. **多工具命名空间是 grok 的杀手级特性。** 能同时加载 GrokBuild、Codex、OpenCode、MCP 四套工具，这是其他 agent 没有的。这让 grok 成为"agent 的 agent"——可以用 Codex 工具调用 Codex 能做的事，用 OpenCode 工具调用 OpenCode 能做的事。

3. **Goal 系统是隐式的 multi-agent。** `planner → strategist → verifier → summarizer` 流水线本质上就是一个内置的 multi-agent 编排框架，但完全内嵌在 session 模板中而不需要用户配置。

4. **Rust + ratatui 的性能优势。** 相比 Claude Code 的 Node.js + Ink，Grok 的启动速度和内存占用应该有数量级的优势。60+ crates 的 workspace 虽然大，但编译后只有一个二进制。

5. **Jujutsu 支持是前瞻性的。** 很少有 AI coding agent 支持 git 以外的 VCS。jj 是 Google 的下一代 VCS，grok 第一梯队支持它。

6. **内核级沙箱比容器方案更轻量。** Landlock/Seatbelt 是 OS 内核特性，不需要 Docker/VM 开销。这在 CI 场景下是巨大的优势。

### 9.3 值得警惕的设计

1. **不接受外部贡献。** 这意味着 bug 修复和功能改进只能靠 xAI 内部团队。如果项目停滞，社区无法自救。

2. **monorepo 同步模式。** 开源仓库只是 monorepo 的"影子副本"，`SOURCE_REV` 记录版本。这意味着开源版本可能滞后于内部版本，且 PR 不被接受。

3. **full-replace 压缩的风险。** 如果摘要模型不够强（比如用便宜的模型做 compaction），摘要质量下降会导致 agent "失忆"。实测中可能需要在 compaction 模型选择上格外小心。

4. **60+ crates 的复杂度。** 虽然模块化好，但新人上手需要理解复杂的 crate 依赖图。

---

## 10. 对你（Hermes/pucking-images）的启示

基于你的使用场景（pucking-images 修图/滤镜），以下是几点可以借鉴的：

1. **如果你的 agent 也用 full-replace 压缩**：Grok 的 9 段结构化 prompt 值得直接参考。特别是"Current Work"段要求足够具体以便 mid-stream 恢复。

2. **多工具命名空间模式**：如果你的 agent 需要同时支持多种工具风格，grok 的 `ToolNamespace` + `CanonicalToolMeta` 设计可以借鉴——通过 `x.ai/tool` `_meta` 信封统一不同命名空间。

3. **Goal 系统**：`goal_task_discipline.md` 中的规则（"先调用工具再叙述"、"不要问不必要的权限"、"不要停下"）可以直接复用为你的 agent 的 system prompt 补充。

4. **Sandbox**：如果你的 agent 需要安全执行用户上传的图片处理脚本，Landlock 沙箱是一个理想的轻量方案。

---

## 附录：关键文件索引

| 文件 | 内容 |
|------|------|
| `crates/codegen/xai-grok-shell/src/session/acp_session_impl/turn.rs` | Turn 三层循环：`handle_prompt()` / `process_conversation_turn()` |
| `crates/codegen/xai-grok-shell/src/session/acp_session_impl/sampler_turn.rs` | LLM 流式交互 + 失败恢复 |
| `crates/codegen/xai-grok-shell/src/session/acp_session_impl/run_loop.rs` | Session 主事件循环 `run_session()` |
| `crates/codegen/xai-grok-shell/src/agent/mvp_agent/mod.rs` | MvpAgent 中央调度器 |
| `crates/codegen/xai-grok-shell/src/agent/mvp_agent/subagent_coordinator.rs` | 子代理协调器 |
| `crates/codegen/xai-grok-shell/src/agent/subagent/handle_request.rs` | 子代理 spawn 流程 |
| `crates/codegen/xai-grok-shell/src/agent/mvp_agent/session_lifecycle.rs` | Session 生命周期管理 |
| `crates/codegen/xai-grok-shell/src/session/handle.rs` | SessionHandle 定义 |
| `crates/codegen/xai-grok-shell/src/leader/mod.rs` | Leader IPC 架构 |
| `crates/codegen/xai-grok-shell/src/session/templates/goal_task_discipline.md` | Goal 任务纪律 |
| `crates/common/xai-grok-compaction/src/lib.rs` | 压缩引擎入口 |
| `crates/common/xai-grok-compaction/src/code_compaction/compact.rs` | full-replace 编排 |
| `crates/common/xai-grok-compaction/src/code_compaction/config.rs` | 压缩配置 |
| `crates/common/xai-grok-compaction/src/code_compaction/templates/full_replace_summary_prompt.txt` | 9 段摘要 prompt |
| `crates/common/xai-grok-compaction/src/intra_compaction/compact.rs` | Intra 4 种模式 |
| `crates/common/xai-grok-compaction/src/intra_compaction/config.rs` | Intra 配置参数 |
| `crates/common/xai-grok-compaction/src/intra_compaction/trigger.rs` | `should_compact()` 触发 |
| `crates/common/xai-grok-compaction/src/select.rs` | SplitPlan 分割算法 |
| `crates/codegen/xai-grok-tools/src/tool_taxonomy.rs` | ToolKind + `_meta` 信封 |
| `crates/codegen/xai-grok-tools/src/registry/types.rs` | 工具注册入口 |
| `crates/codegen/xai-grok-tools/src/implementations/opencode/` | OpenCode 工具移植 |
| `crates/codegen/xai-grok-tools/src/implementations/codex/` | Codex 工具移植 |
| `crates/common/xai-tool-runtime/src/tool.rs` | Tool/DynTool 双 trait |
| `crates/common/xai-tool-runtime/src/dispatch.rs` | ToolDispatch 分发 |
| `crates/codegen/xai-grok-mcp/src/servers.rs` | MCP 服务器管理 |
| `crates/codegen/xai-grok-workspace/src/session/checkpoint.rs` | 三级 checkpoint |
| `crates/codegen/xai-grok-workspace/src/session/jj.rs` | Jujutsu VCS 支持 |
| `crates/codegen/xai-grok-workspace/src/permission/rules.rs` | 权限模式 |
| `crates/codegen/xai-grok-pager/src/` | TUI 完整实现 |
| `crates/codegen/xai-grok-pager/docs/user-guide/` | 用户指南（27 篇） |
