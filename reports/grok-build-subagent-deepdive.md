# Grok Build 子代理系统 — 深度分析

> 从源码级别分析 grok-build 的子代理完整生命周期、协调器架构、继承机制

---

## 一、子代理全景图

```
┌───────────────────────────────────────────────────────────────┐
│                    MvpAgent (单例)                              │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │              SubagentCoordinator (RefCell)                │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │  │
│  │  │ pending  │  │  active  │  │completed │              │  │
│  │  │HashMap   │  │ HashMap  │  │ HashMap  │              │  │
│  │  └──────────┘  └──────────┘  └──────────┘              │  │
│  │  ┌──────────────────────────────────────┐              │  │
│  │  │  block_wait_slots: HashMap<id, Vec>  │              │  │
│  │  └──────────────────────────────────────┘              │  │
│  └─────────────────────────────────────────────────────────┘  │
│         ▲  SubagentEvent channel                               │
│         │  (Spawn / Query / Cancel / ListActive / Completions) │
│  ┌──────┴──────────────────────────────────────────────────┐  │
│  │               TaskTool (session 内)                       │  │
│  │  model 调用 task tool → TaskTool::execute()               │  │
│  │  → SubagentBackend::spawn() → SubagentEvent::Spawn       │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

---

## 二、三大状态表

### 2.1 PendingSubagent — 生成中

```rust
// subagent/mod.rs — PendingSubagent 定义
struct PendingSubagent {
    subagent_id: String,
    subagent_type: String,
    description: String,
    persona: Option<String>,
    parent_prompt_id: Option<String>,
    parent_session_id: String,
    started_at: Instant,
    run_in_background: bool,
    surface_completion: bool,
    color: Option<AgentColor>,
    cancel_token: CancellationToken,
}
```

插入时机：`handle_subagent_request()` 开始，agent definition 解析通过后立即插入。此时子 session 尚未创建。

### 2.2 SubagentTracker — 运行中

```rust
// subagent/mod.rs:58
struct SubagentTracker {
    subagent_id: String,
    parent_session_id: String,
    parent_prompt_id: Option<String>,
    child_session_id: SessionId,       // 子 session 的实际 ID
    subagent_type: String,
    persona: Option<String>,
    description: String,
    started_at: Instant,
    child_handle: SessionHandle,       // 子 session 的 Handle
    cancel_token: CancellationToken,
    resumed_from: Option<String>,      // resume 来源
    child_cwd: String,                 // 子 session 工作目录
    worktree_path: Option<PathBuf>,    // isolation=worktree 时的路径
    effective_model_id: String,        // 子 session 实际使用的模型
    run_in_background: bool,
    surface_completion: bool,
    completion_output_cap: Option<usize>,
    block_waited: bool,                // 是否有 block=true 的等待者
    explicitly_killed: bool,           // 是否被 kill 工具显式杀死
}
```

插入时机：子 session actor 创建成功后，从 `pending` 移到 `active`。

### 2.3 CompletedSubagent — 已完成

```rust
// subagent/mod.rs:477
struct CompletedSubagent {
    subagent_id: String,
    parent_session_id: String,
    parent_prompt_id: Option<String>,
    child_session_id: String,
    description: String,
    subagent_type: String,
    persona: Option<String>,
    started_at: Instant,
    completed_at: Instant,
    result: SubagentResult,            // 最终结果
    resumed_from: Option<String>,
    child_cwd: String,
    worktree_path: Option<PathBuf>,
    snapshot_ref: Option<String>,      // worktree 快照的 git ref
    effective_model_id: String,
    block_waited: bool,
    explicitly_killed: bool,
    persisted_output_dir: Option<PathBuf>, // 持久化输出目录
}
```

插入时机：子 session 完成/失败/取消后，从 `active` 移到 `completed`。

**容量管理：** `enforce_completed_cap()` → 按 `completed_at` 时间排序，驱逐最旧的条目。输出文件 (`output.json`) 保留在磁盘上。

---

## 三、完整生命周期

## 三、完整生命周期：17 阶段详解

**文件:** `agent/subagent/handle_request.rs:77` (2032 行)

```
阶段  0: TaskTool 深度检查
         MAX_SUBAGENT_DEPTH = 1 (task/mod.rs:31)
         子代理不能递归生成子代理！

阶段  1: 构建 SubagentRequest
         解析 prompt、subagent_type、runtime_overrides
         后台模式: tokio::spawn → 立即返回 task_id
         阻塞模式: await backend.spawn() → 等待完成

阶段  2: 通道传输
         ChannelBackend::spawn() → SubagentEvent::Spawn(Box<SubagentRequest>)
         → mpsc::unbounded_channel → MvpAgent 协调器

阶段  3: 协调器事件分发
         SubagentCoordinator drain task 接收事件
         re-parenting: 子代理内的嵌套 spawn 重定向到 root session

阶段  4: resolve_agent_definition()
         内置 agent / 自定义 agent (.grok/agents/*.md) / 插件 agent

阶段  5: gate_subagent_type()
         Disabled? (config.toml toggle) / NotAllowed? (allowlist)

阶段  6: insert_pending()
         PendingSubagent { id, type, persona, cancel_token }

阶段  7: resolve_subagent_toolset()
         能力模式裁剪 + 深度裁剪 (strip_task_tools_at_max_depth)
         + 角色工具集 + CLI 覆写

阶段  8: Persona 解析
         ctx.subagent_personas.get(persona_name)
         → persona.soul 注入 system prompt

阶段  9: Role 解析
         ctx.subagent_roles.get(type) → capability_mode, isolation, max_turns

阶段 10: Runtime Overrides 应用
          model / reasoning_effort / capability_mode / isolation

阶段 11: MCP 继承
          filter_pool_by_inheritance(All/None/Named/Except)
          + agent definition MCP servers 解析

阶段 12: Skills 继承
          parent_skills snapshot + parent_skills_config

阶段 13: 上下文引导 (Bootstrap)
          优先级: Resume (硬失败) > Fork (live > disk fallback) > New
          Resume: 继承已完成的子代理的 raw transcript + tool state + model
          Fork: 从父对话中提取 context_prefix
          New: 空白 session

阶段 14: spawn_session_actor()
          构建 SessionInfo / AgentSessionConfig / WorkspaceConfig
          创建独立 SessionActor → pending → active

阶段 15: Auto-background 超时
          前台子代理 600s 预算超时 → 自动转换为后台模式
          不阻塞父 turn

阶段 16: 完成 → completed
          存活任务重归属 → block-wait delivery → auto-wake
```

```
Model 调用 task tool
    ↓
TaskTool::execute() 解析参数
    ↓
构造 SubagentRequest {
    id:            UUID v7,
    prompt:        "fix the bug in auth.rs",
    description:   "Fix auth bug",
    subagent_type: "general-purpose",
    parent_session_id: "abc123",
    parent_prompt_id: Some("prompt-1"),
    runtime_overrides: { persona: "concise", model: None, ... },
    run_in_background: false,
    surface_completion: true,
    fork_context: false,
    result_tx: oneshot::channel(),
}
    ↓
SubagentBackend::spawn() → SubagentEvent::Spawn(Box<SubagentRequest>)
    ↓
MvpAgent.subagent_event_rx 接收
```

### 3.2 预处理 → handle_subagent_request()

**文件:** `agent/subagent/handle_request.rs:77` (2032 行)

```rust
async fn handle_subagent_request(
    request: SubagentRequest,
    ctx: SubagentSpawnContext,
    coordinator: &RefCell<SubagentCoordinator>,
    gateway: &GatewaySender,
) {
    // ① 分辨率 agent definition
    let Some(definition) = resolve_agent_definition(&request.subagent_type, &ctx);
    
    // ② 门控检查
    match gate_subagent_type(&request.subagent_type, &ctx) {
        Disabled => send_pre_spawn_failure(...)  // 被 config.toml 禁用
        NotAllowed => send_pre_spawn_failure(...) // 不在允许列表
        _ => {}
    }
    
    // ③ 插入 pending 表
    coordinator.borrow_mut().insert_pending(PendingSubagent { ... });
    
    // ④ 解析工具集
    resolve_subagent_toolset(&request.subagent_type, &ctx, &mut definition);
    
    // ⑤ 解析 Persona
    let persona_soul = ctx.subagent_personas.get(persona_name).map(|p| p.soul.clone());
    // 将 persona SOUL 注入 definition 的 system prompt
    
    // ⑥ 解析 role
    let role = ctx.subagent_roles.get(&request.subagent_type);
    // role 决定 capability_mode、isolation、max_turns
    
    // ⑦ 应用 runtime overrides
    if let Some(model) = &request.runtime_overrides.model {
        definition.model = Some(model.clone());
    }
    
    // ⑧ 解析能力模式
    let capability_mode = request.runtime_overrides.capability_mode
        .or(role.and_then(|r| r.capability_mode));
    
    // ⑨ 解析隔离模式
    let isolation = request.runtime_overrides.isolation
        .or(role.and_then(|r| r.isolation));
    
    // ⑩ 创建子 session → 移到 active → 注入 prompt → 等待完成
    spawn_child_session(...).await
}
```

### 3.3 工具裁剪 — 深度限制

**文件:** `agent/subagent/handle_request.rs:31`

```rust
fn strip_task_tools_at_max_depth(tool_config: &mut ToolServerConfig, child_depth: u32) -> bool {
    if child_depth < MAX_SUBAGENT_DEPTH {  // MAX_SUBAGENT_DEPTH 定义在 task/types.rs
        return false;  // 还没到最大深度，不裁剪
    }
    tool_config.tools.retain(|tc| tc.kind != Some(ToolKind::Task));
    // 同时清理孤立的后台任务工具
    prune_orphaned_background_task_tools(tool_config);
}
```

**深度限制逻辑：**
- 根 session: depth = 0
- 一级子代理: depth = 1
- 当 `child_depth >= MAX_SUBAGENT_DEPTH` 时，移除子代理的 `task` 工具 → 子代理不能再 spawn 子代理
- 这形成了硬性的嵌套深度限制

### 3.4 子 Session 创建

```
spawn_child_session()
    ├── 构建 SessionInfo (id, cwd, worktree_path?)
    ├── 构建 AgentSessionConfig (model, tools, capability, hooks)
    ├── 构建 WorkspaceConfig (fs, terminal, hunk_tracker)
    ├── spawn_session_actor() → 独立的 SessionActor
    ├── 注入系统提示 (含 persona SOUL)
    ├── 注入 prompt → 启动 turn
    ├── pending.remove() → active.insert(SubagentTracker)
    └── 等待完成...
```

### 3.5 完成处理

```
子 session 完成 (TurnOutcome::Completed / Cancelled / Error)
    ↓
    active.remove(id)
    ↓
    completed.insert(id, CompletedSubagent { result, ... })
    ↓
    enforce_completed_cap() // 清理最旧的条目
    ↓
通知父 session:
    ├── 如果是 block-wait: 直接发送结果到 result_tx
    ├── 如果是 background: 不立即通知（等待 auto-wake 或 task_output 查询）
    ├── 如果 surface_completion: 发送 SubagentFinished notification
    └── 如果 auto-wake enabled: 注入合成 prompt 唤醒父 agent
```

---

## 四、Block-Wait 机制

**文件:** `agent/subagent/coordinator_query.rs`

Block-wait 允许父代理**同步等待**子代理完成：

```rust
// 轮询循环 (在 query.rs 中)
loop {
    match coordinator.lookup(&subagent_id) {
        Ready(snapshot) => return snapshot,  // 已完成 → 立即返回
        NeedsSignals(seed) => {
            // 运行中 → 等待 signals handle
            tokio::select! {
                _ = seed.signals_handle.completed() => {
                    // 子代理完成了 → 下一轮 lookup 会命中 Ready
                    continue;
                }
                _ = tokio::time::sleep(Duration::from_millis(200)) => {
                    // 每 200ms 检查一次
                    continue;
                }
                _ = cancel_token.cancelled() => return Cancelled,
            }
        }
        None => return NotFound,
    }
    // 总超时: 30 秒
    if elapsed > Duration::from_secs(30) {
        return Timeout;
    }
}
```

**关键机制：**
- `block_waited` 标志：标记子代理已被 block-wait 消费，防止 auto-wake 重复通知
- `BlockWaitSlot`：`Rc<RefCell<Option<oneshot::Sender>>>`——槽位机制防止竞态条件
- `block_wait_delivered_or_live()`：在子代理完成时检查 waiter 是否还活着——如果 waiter 已取消但标志未清除，则降级为 auto-wake

---

## 五、继承机制

### 5.1 SubagentSpawnContext — 父代理传给子代理的一切

**文件:** `agent/subagent/mod.rs:139` (包含了 40+ 个字段)

| 类别 | 继承内容 |
|------|----------|
| **文件系统** | `fs: Arc<dyn AsyncFileSystem>` — 共享文件系统 |
| **终端** | `terminal: Arc<dyn AsyncTerminalRunner>` — 共享终端环境 |
| **终端后端** | `parent_terminal_backend: Option<Arc<dyn TerminalBackend>>` — 后台任务存活 |
| **Hunk Tracker** | `hunk_tracker_handle: HunkTrackerHandle` — 共享编辑追踪 |
| **MCP Pool** | `parent_mcp_pool: Option<SharedMcpPool>` — 继承 MCP 连接 |
| **Client Hooks** | `client_hooks: ClientHooks` — 继承 PreToolUse 门控 |
| **LSP** | `lsp: Option<Arc<dyn LspBackend>>` — 共享 LSP |
| **Auth** | `auth_manager: Arc<AuthManager>` — 共享认证 |
| **Memory** | `memory_config: Option<MemoryConfig>` — 共享跨 session 记忆 |
| **通知** | `parent_notification_handle` — 子代理存活任务的通知重归属 |
| **调度器** | `parent_scheduler_handle` — 继承定时任务 |
| **环境变量** | `session_env: Arc<HashMap<String, String>>` — 继承 .envrc |
| **采样配置** | `sampling_config: SamplerConfig` — auth、模型等 |
| **压缩阈值** | `auto_compact_threshold_tiers` — 按子代理模型查表解析 |
| **权限** | `permission_handle: Option<PermissionHandle>` — 继承权限 |
| **工具快照** | `parent_tool_snapshot: Option<Vec<ToolSpec>>` — fork 时复用缓存 |

### 5.2 MCP Pool 继承过滤器

子代理可以**选择性继承**父代理的 MCP 连接，通过 `filter_pool_by_inheritance()` 实现 4 种模式：

| 模式 | 行为 |
|------|------|
| `All` | 继承父代理的所有 MCP 服务器连接 |
| `None` | 不继承任何 MCP 连接，子代理独立管理 |
| `Named(names)` | 只继承指定的 MCP 服务器（白名单） |
| `Except(names)` | 继承除指定外的所有 MCP 服务器（黑名单） |

### 5.3 Auto-background 机制

前台子代理有 600 秒预算超时。如果超时未完成：
- 自动转换为后台模式
- 不阻塞父 agent 的当前 turn
- 父 agent 后续可通过 `task_output` 工具查询结果
- 或由 auto-wake 在子代理完成时自动通知

### 5.2 存活任务重归属

当子代理退出时，它创建的后台任务（monitors、bg commands、scheduled tasks）需要"重归属"到父 session：

```
子代理退出
    ↓
检查 child_handle 中的所有存活任务
    ↓
swap_notification_handle(parent_notification_handle)
    ↓ 将任务的通知目标从子 session 切换到父 session
    ↓
swap_scheduler_handle(parent_scheduler_handle)
    ↓ 将定时任务从子调度器切换到父调度器
    ↓
子代理的存活任务现在由父 session 管理
```

---

## 六、Isolation 隔离模式

| 模式 | 实现 | 效果 |
|------|------|------|
| `None` (默认) | 共享父 session 的 cwd | 子代理直接操作父项目文件 |
| `Worktree` | 创建 git worktree (copy-on-write) | 子代理在独立目录工作，不污染父项目 |

**Worktree 模式流程：**
```
1. git worktree add --detach <temp_path>
2. 子 session cwd = worktree_path
3. 子代理完成时:
   - 如果 subagent_worktree_snapshot enabled:
     git commit + git tag → snapshot_ref
   - git worktree remove
```

---

## 七、Persona 和 Agent Resolution

### 7.1 解析链

```
Agent Type ("general-purpose")
    ↓
resolve_agent_definition() → AgentDefinition
    ├── 内置 agent: 从 agent config 加载
    ├── 自定义 agent: 从 .grok/agents/*.md 加载
    └── 插件 agent: 从 plugin registry 加载
    ↓
Persona 覆盖
    ├── ctx.subagent_personas.get("concise") → SubagentPersona
    └── persona.soul → 注入 system prompt
    ↓
Role 覆盖
    ├── ctx.subagent_roles.get("general-purpose") → SubagentRole
    ├── role.capability_mode → 工具集级别
    ├── role.isolation → 隔离模式
    └── role.max_turns → 最大轮次
    ↓
Runtime Overrides
    ├── request.runtime_overrides.model
    ├── request.runtime_overrides.reasoning_effort
    └── request.runtime_overrides.capability_mode
```

### 7.2 门控检查

```
gate_subagent_type(type, ctx)
    ├── ctx.subagent_toggle.get(type) == Some(false) → Disabled
    ├── ctx.allowed_subagent_types 存在且 type 不在列表 → NotAllowed
    └── 否则 → Allowed
```

---

## 八、通知机制

子代理完成后，通知父 session 的方式有三种：

| 方式 | 触发条件 | 效果 |
|------|----------|------|
| **Block-wait 直接返回** | `block=true` 时 | 通过 `result_tx` oneshot 直接返回 |
| **Auto-wake 合成 prompt** | 非 block-wait, 非 background | 注入 `SubagentCompleted` prompt，唤醒父 agent |
| **TaskOutput 查询** | 随时可查 | 父 agent 调用 `task_output` 工具获取结果 |
| **Idle drain** | 父 session 空闲时 | 批量注入所有已完成子代理的通知 |

**Auto-wake 抑制条件：**
- `explicitly_killed = true` → 模型主动杀死的，不通知
- `block_waited = true` 且 waiter 已收到 → 不重复通知
- `surface_completion = false` → harness 内部子代理，模型不可见
- `goal_loop_active = true` → 父 session 在 goal 循环中，不打断

---

## 九、文件索引

| 文件 | 内容 |
|------|------|
| `agent/subagent/mod.rs` | SubagentSpawnContext、SubagentTracker、CompletedSubagent |
| `agent/subagent/handle_request.rs:77` | handle_subagent_request() — 完整生成流程 (2032 行) |
| `agent/subagent/coordinator_query.rs` | lookup、block-wait、completed_finish |
| `agent/subagent/coordinator_lifecycle.rs` | pending↔active↔completed 状态转换 |
| `agent/mvp_agent/subagent_coordinator.rs` | SubagentCoordinator 事件循环 (644 行) |
| `tools/.../task/types.rs` | SubagentRequest、SubagentRuntimeOverrides |
| `subagent-resolution/src/config.rs` | SubagentRole、SubagentPersona 配置类型 |
| `subagent-resolution/src/overrides.rs` | Runtime override 解析 |
| `subagent-resolution/src/context.rs` | Bootstrap context 构建 |
| `subagent-resolution/src/resume.rs` | resume_from 逻辑 |
