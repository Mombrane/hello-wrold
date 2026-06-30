# omp Agent Loop 深度源码分析报告

> 调研日期：2026-06-30 · 源码版本：`main` @ 2026-06-30 · 仓库：`can1357/oh-my-pi`
> 本地 clone：`~/.hermes/repos/oh-my-pi-omp` (shallow)
> 核心文件：`packages/agent/src/agent-loop.ts` (2137 行)

---

## 一、架构总览

omp 的 agent loop 实现在 `packages/agent/`（核心引擎，纯 TypeScript）和 `packages/coding-agent/`（CLI 应用层）中。整体分三层：

```
┌──────────────────────────────────────────────────────────────┐
│  coding-agent/src/  (CLI & 工具层)                            │
│  ├─ task/  → 子代理系统 (index.ts 1441行, executor.ts 2440行)│
│  ├─ advisor/ → 第二模型监视 (runtime.ts 518行)               │
│  ├─ ttsr/ → 时间旅行流规则                                    │
│  └─ tools/ → 32个工具实现                                     │
├──────────────────────────────────────────────────────────────┤
│  agent/src/  (agent 运行引擎)                                 │
│  ├─ agent.ts (1452行) → Agent 类封装                         │
│  ├─ agent-loop.ts (2137行) → 核心循环 ★                     │
│  └─ compaction/ → 上下文压缩 (compaction.ts 1505行)          │
├──────────────────────────────────────────────────────────────┤
│  ai/  (LLM 客户端)                                           │
│  └─ streamSimple / dialect / harmony-leak                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 二、核心循环：双重 while 结构

**文件位置**：`packages/agent/src/agent-loop.ts:700-1099`

这是与其他 agent 最大的架构差异。omp 使用**嵌套双层 while**：

```typescript
// agent-loop.ts:700-1091
async function runLoopBody(
    currentContext: AgentContext, newMessages: AgentMessage[],
    config: AgentLoopConfig, signal, stream, telemetry,
    invokeAgentSpan, stepCounter, streamFn
): Promise<void> {
    // 设置 deadline timer (712-723行)
    // ...

    // ====== 外层循环 ======
    // 处理 follow-up、late steering、aside 消息
    while (true) {                                     // 753行
        let hasMoreToolCalls = true;

        // ====== 内层循环 ======
        // 核心 ReAct turn: LLM → tool → result → repeat
        while (hasMoreToolCalls || pendingMessages.length > 0) {  // 757行

            // ① 检查 deadline (758行)
            // ② yield event loop 防 busy-wait (764行)
            // ③ 注入 pendingMessages（steering/aside）(772行)

            // ④ 刷新 context：实时同步 system prompt + tools (783行)
            await config.syncContextBeforeModelCall(currentContext);

            // ⑤ 解析 tool-choice 指令 (799行)
            //    - hard ToolChoice: 直接应用
            //    - SoftToolRequirement: remind→escalate 生命周期

            // ⑥ 调用 LLM → 流式获取 AssistantMessage (826行)
            message = await streamAssistantResponse(...);

            // ⑦ 异常处理 (886-913行)
            //    - error/aborted → 创建占位 tool results → return
            //    - HarmonyLeakInterruption → continue 重试

            // ⑧ 工具执行 (982行)
            const executionResult = await executeToolCalls(...);

            // ⑨ paused_turn 恢复 (1022-1035行)
            // ⑩ emit turn_end (1037行)
            // ⑪ 收集下一轮 pending + aside (1051行)
            pendingMessages = ...;
        }

        // ====== 外层循环尾部 ======
        await config.onBeforeYield?.();                // 1070行
        const followUp = await config.getFollowUpMessages?.(); // 1082行
        if (followUp.length > 0 || lateSteering.length > 0) {
            pendingMessages = [...lateSteering, ...asides, ...followUp];
            continue;  // 重新进入内循环
        }
        break;         // 真正退出
    }
    endAgentStream(stream, newMessages, telemetry, stepCounter.count);
}
```

**设计要点**：

| 机制 | 源码位置 | 说明 |
|------|----------|------|
| **外层 while(true)** | 753 行 | 处理 follow-up。agent 应退出但外部有新消息→继续，不重建 session |
| **内层 while** | 757 行 | 标准 ReAct turn 循环，条件：`hasMoreToolCalls \|\| pendingMessages.length > 0` |
| **deadline 多点检查** | 758/934/1041/1064/1072 行 | wall-clock deadline buried in 5 places |
| **yieldIfDue()** | 764 行 | 防止 event loop 被连续的 tool 执行阻塞 |
| **syncContextBeforeModelCall** | 783 行 | 每轮 LLM 调用前实时刷新 system prompt + tools，支持热重载 |

### 为什么双层而不用单层？

单层循环的问题是：当 agent 完成工作（`hasMoreToolCalls=false` 且 `pendingMessages=[]`），如果有异步到来的 follow-up 消息（如 Advisor 的 blocker、用户在中途的 steer），只能退出循环再新建 session。omp 的外层循环让这些消息无缝注入，保持 session 连续性，避免 prompt cache 失效。

---

## 三、LLM 调用流程：streamAssistantResponse

**文件位置**：`packages/agent/src/agent-loop.ts:1122-1477`

12 步 pipeline：transformContext → convertToLlm → normalize → build context → dialect → resolve keys → call LLM → stream → detect Harmony → transform → return

### 3.1 Abort Race 机制（1326-1340 行）

与其他 agent 不同，omp 不是每次 `iterator.next()` 都重新注册 abort listener，而是**复用同一个 Promise.race**：

```typescript
// agent-loop.ts:1329-1340
let abortRacePromise: Promise<typeof ABORTED> | undefined;
let detachAbortListener: (() => void) | undefined;
if (requestSignal) {
    if (requestSignal.aborted) {
        return await finishAbortedStream();
    }
    const { promise, resolve } = Promise.withResolvers<typeof ABORTED>();
    const onAbort = () => resolve(ABORTED);
    requestSignal.addEventListener("abort", onAbort, { once: true });
    abortRacePromise = promise;
    detachAbortListener = () => requestSignal.removeEventListener("abort", onAbort);
}

// 流循环中（1343-1358 行）
while (true) {
    let next: IteratorResult<AssistantMessageEvent>;
    if (abortRacePromise) {
        const result = await Promise.race([responseIterator.next(), abortRacePromise]);
        if (result === ABORTED) return await finishAbortedStream();
        next = result;
    } else {
        next = await responseIterator.next();
    }
    if (next.done) break;
    // ... 处理 event
}
```

**为什么这么做？** 减少 GC 压力。每个 streaming chunk（可能每几 ms 一个 delta）都创建新的 Promise.withResolvers + add/removeEventListener 对性能有影响。

### 3.2 Harmony Leak 防御（1362-1377 / 1464-1478 行）

GPT-5 可能泄漏内部 Harmony 协议标记（如 `<｜harmony｜>`）。omp 在流结束时检测：

```typescript
// agent-loop.ts:1362-1377
if (harmonyMitigationEnabled) {
    const detection = detectHarmonyLeakInAssistantMessage(finalMessage);
    if (detection) {
        // 抛弃已追加到 context 的部分消息
        if (addedPartial) {
            emitDiscardedHarmonyPartial(partialMessage, stream,
                `Discarded after GPT-5 Harmony protocol leakage`);
            context.messages.pop();
            addedPartial = false;
        }
        throw new HarmonyLeakInterruption(detection, removed, recovered);
    }
}
```

外层捕获后的恢复策略（842-868 行）：
- **abort_retry**：重启 LLM 请求（最多 2 次），每次 temperature +0.05 增加多样性
- **truncate_resume**：截断泄漏部分，保留有效内容继续（最多 2 次 cross-turn）

### 3.3 Paused Turn 继续（1019-1035 行）

Codex 等 provider 可能返回非终态的 `pause_turn`（`end_turn: false`），表示「我还在想」。omp 自动重采样：

```typescript
// agent-loop.ts:1022-1035
if (toolCalls.length > 0) {
    pausedTurnContinuations = 0;  // 有 tool call → reset
} else if (
    !hasMoreToolCalls &&
    message.stopReason === "stop" &&
    message.stopDetails?.type === "pause_turn" &&
    pausedTurnContinuations < MAX_PAUSED_TURN_CONTINUATIONS  // 8
) {
    pausedTurnContinuations++;
    hasMoreToolCalls = true;  // 重新进入内循环
}
```

---

## 四、工具执行：executeToolCalls

**文件位置**：`packages/agent/src/agent-loop.ts:1638-2137`

### 4.1 并发执行 + steering 中断

```typescript
// agent-loop.ts:1663-1714
const shouldInterruptImmediately = interruptMode !== "wait";
const steeringAbortController = new AbortController();
const toolSignal = signal
    ? AbortSignal.any([signal, steeringAbortController.signal])
    : steeringAbortController.signal;

// 250ms 轮询是否有 steering 消息
const checkSteering = async (): Promise<void> => {
    if (!shouldInterruptImmediately || interruptState.triggered || signal?.aborted) return;
    let hasMessages = await hasSteeringMessages?.();  // peek, 不消费队列
    if (hasMessages) {
        interruptState.triggered = true;
        steeringAbortController.abort();
    }
};
```

**关键**：`hasSteeringMessages()` 是 peek 而非 consume。steering 消息在 outer loop 被 `getSteeringMessages()` 正式消费。这样 tool interrupt 和 steering injection 不会竞争同一队列。

### 4.2 Soft Tool Requirement（939-981 行）

这是 omp 独有的「模型必须调用某个工具」机制：

```
1. 设置 soft requirement（如："必须调用 ask 向用户确认"）
2. 注入 reminder 消息
3. 如果模型调了别的工具 → 不执行，返回 skipped + 强制 toolChoice
4. 如果模型还是不听 → 最多 escalate 3 次后抛异常
```

代码逻辑（942-981 行）：
```typescript
const calledOnlyRequiredTool =
    softRequiredTool !== undefined &&
    toolCalls.length > 0 &&
    toolCalls.every(tc => tc.name === softRequiredTool);
const softNonCompliant = softGateActive && !calledOnlyRequiredTool;

if (softNonCompliant) {
    if (softEscalations >= 3) throw new Error("...");
    for (const toolCall of toolCalls) {
        // 返回 skipped 结果，不执行副作用
        const result = createAbortedToolResult(toolCall, stream, "skipped", ...);
    }
    forcedToolChoice = { type: "tool", name: softRequiredTool };
    softEscalations++;
    hasMoreToolCalls = true;  // 虽然没执行工具，但强制继续循环
}
```

---

## 五、TTSR：时间旅行流规则

**文件位置**：`packages/coding-agent/src/export/ttsr.ts` (583 行) + `commands/ttsr.ts`

### 5.1 架构

TTSR 不是在 agent-loop.ts 里实现的——它作为一个中间件插入在 `streamAssistantResponse` 的流事件处理中。当流式输出触发正则匹配时，TTSR 通过 `onAssistantMessageEvent` hook (agent-loop.ts:1444) 检测：

```
LLM 流式输出
  │
  ├─ streamAssistantResponse 事件遍历
  │   ├─ text_delta / thinking_delta / toolcall_delta
  │   ├─ onAssistantMessageEvent() ← TTSR hook
  │   │   ├─ regex match on accumulated text?
  │   │   ├─ YES → inject rule + abort stream
  │   │   └─ NO  → continue
  │   └─ ...
  └─ finishChat()
```

触发源（`TtsrMatchSource`）：
- `text` — 模型文本输出
- `thinking` — 模型思考过程（如 Claude thinking blocks）
- `tool` — 工具调用参数（如 `edit` 的补丁内容或 `write` 的文件内容）

### 5.2 匹配机制

```typescript
// ttsr.ts:40-47
interface TtsrEntry {
    rule: Rule;
    conditions: RegExp[];           // 正则匹配
    astConditions: string[];        // ast-grep 模式匹配（仅 edit/write）
    scope: TtsrScope;
    globalPathGlobs?: Bun.Glob[];   // 路径过滤
}
```

TTSR 支持正则 + ast-grep 双重匹配。`astConditions` 仅对 `edit`/`write` 工具参数使用 ast-grep 做结构化代码匹配（如在补丁中检测 `Box::leak` 模式）。

### 5.3 注入与持久化

README 声称「injection survives compaction」，意味着注入的 rule 不会被上下文压缩掉。实现上应该是：TTSR 注入的消息被标记为 `isTtsrInjection` 或有特殊 protection flag，在 `compaction/tool-protection.ts` 中被保护。

---

## 六、子代理（Task）系统

**文件位置**：`packages/coding-agent/src/task/` (index.ts 1441行, executor.ts 2440行)

### 6.1 入口：taskTool handler

```typescript
// task/index.ts（简化）
export const taskTool: AgentTool = {
    name: "task",
    description: "Delegate tasks to specialized agents",
    // ...
    async handler(args, signal, context) {
        // 1. 发现 agent 定义 (bundled/user/project)
        const agentDef = getAgent(args.agent);

        // 2. 并行执行
        const results = await mapWithConcurrencyLimit(
            tasks, semaphore,
            async (task) => {
                if (config.isolation) {
                    return runIsolatedSubprocess(task, isolationCtx);
                }
                return runSubprocess(task);
            }
        );

        // 3. yield assembly → schema-validated result
        return assembleYield(results);
    }
};
```

### 6.2 隔离后端（isolation-runner.ts 368 行）

```typescript
// isolation-runner.ts 核心
async function prepareIsolationContext(mode: IsolationMode): Promise<IsolationContext> {
    switch (mode) {
        case "apfs-clone":    return prepareApfsClone();     // macOS CoW
        case "btrfs-reflink": return prepareBtrfsReflink();  // Linux reflink
        case "zfs-clone":     return prepareZfsClone();      // ZFS
        case "overlayfs":     return prepareOverlayfs();     // Linux overlay
        case "projfs":        return prepareProjfs();        // Windows
        case "rcopy":         return prepareRcopy();         // cross-platform
        case "git-worktree":  return prepareGitWorktree();   // git worktree
        default:              return { workdir: cwd };      // shared
    }
}
```

8 种后端按优先级自动选择：检查文件系统类型 → 选最优 CoW 方案 → 降级到 rcopy。

### 6.3 并发控制（parallel.ts）

```typescript
// Semaphore + mapWithConcurrencyLimit，默认最大 32 并发子代理
const semaphore = new Semaphore(config.maxConcurrency ?? 32);
```

每个子代理是完整 agent loop——启动独立进程（`Bun.spawn`），有自己的 context、model、tools。父 agent 通过 `agent://<id>/findings.0.path` 内部 URI 提取结构化结果。

---

## 七、Advisor 系统

**文件位置**：`packages/coding-agent/src/advisor/` (runtime.ts 518行, watchdog.ts 135行)

Advisor 是一个**并行运行的独立 agent 实例**，使用不同的模型（通常更便宜/更快），监视主 agent 的每一个 turn。

### 7.1 工作流程

```
主 Agent Loop                        Advisor Watchdog
    │                                      │
    ├─ turn_end event ──────────────────→│
    │                                      ├─ 读取 transcript
    │                                      ├─ 调用 advisor agent (独立 model)
    │                                      │   ├─ 分析主 agent 决策
    │                                      │   ├─ 判断 severity
    │                                      │   └─ 生成 advice
    │                                      │
    │  ← aside 消息注入 ──────────────────┤
    │  (aside / concern / blocker)         │
    │                                      │
    ├─ 下个 turn 开始                     │
    └─ 处理 aside → 纠正行为              │
```

### 7.2 三个 severity level

| level | 行为 |
|-------|------|
| **aside** | 静默旁注，不影响主 agent 逻辑，仅供参考 |
| **concern** | 提醒主 agent 注意，但不打断 |
| **blocker** | 阻止主 agent 继续，必须先解决 |

### 7.3 Emission guard

`emission-guard.ts` 防止 advisor 的 advice 递归触发自身（即 advisor 分析自己的输出又生成新 advice）。实现方式：标记 advice 消息为 `fromAdvisor`，advisor watchdog 跳过这些消息。

---

## 八、上下文压缩

**文件位置**：`packages/agent/src/compaction/compaction.ts` (1505 行)

### 8.1 触发条件

```typescript
// compaction.ts:245
export function shouldCompact(
    contextTokens: number,
    contextWindow: number,
    settings: CompactionSettings
): boolean {
    const threshold = resolveThresholdTokens(contextWindow, settings);
    return contextTokens > threshold;
}
```

阈值：`contextWindow * compactionThreshold`（默认 0.8，即超过窗口 80% 时触发）

### 8.2 多层压缩策略

| 层级 | 文件 | 机制 |
|------|------|------|
| **snapcompact** | `@oh-my-pi/snapcompact` | 位图帧压缩，将长对话压缩为结构化摘要帧 |
| **Shake** | `compaction/shake.ts` | 精简工具输出：移除冗余、格式化、截断 |
| **Pruning** | `compaction/pruning.ts` | 裁剪老旧消息（保留最新 N turn） |
| **Branch summarization** | `compaction/branch-summarization.ts` | 子代理分支压缩为摘要 |
| **V2 streaming compaction** | `compaction-v2-streaming.ts` | 流式压缩 v2，远程/本地可切换 |
| **Append-only context** | `append-only-context.ts` (348行) | 前缀字节不变，最大化 prompt cache hit |

### 8.3 AppendOnlyContextManager

核心思想：让 system prompt + tool spec 在多次 LLM 调用间保持字节级不变。DeepSeek/Anthropic 的 prompt cache 依赖前缀稳定性——前缀变了 cache 就 miss。append-only 模式保证：
- 前缀（system + tools）一次构建，永不修改
- 消息只追加不修改
- 跨 turn 的 cache hit rate 最大化

---

## 九、事件系统

```
agent_start         → 新 prompt/continue 开始
  turn_start        → 新 turn
    message_start   → 模型开始输出
    message_update  → 流式增量（text_delta / thinking_delta / toolcall_delta）
    message_end     → 模型输出完成
    tool_execution_start → 工具执行中
    tool_execution_end   → 工具完成
  turn_end          → turn 结束（含 message + toolResults）
agent_end           → 全部完成（含 all messages + telemetry）
```

Agent 层（`agent.ts:1198-1245`）通过 `for await (const event of stream)` 消费事件流，更新内部 state 并转发给 UI listeners。

---

## 十、与 Hermes Agent Loop 的对比

| 维度 | omp | Hermes |
|------|-----|--------|
| 语言 | TypeScript (Bun) | Python |
| **循环结构** | 双层 while（外层 follow-up + 内层 turn） | 单层 while + conversation_loop |
| **LLM 调用** | `streamFn()` → asyncIterator + Promise.race abort | `run_agent.py` → sync API call |
| **工具执行** | 并发 + semaphore + 250ms steering interrupt | sequential / concurrent batch |
| **工具中断** | mid-execution abort signal (immediate/wait 可配) | 仅 turn 间 |
| **上下文管理** | Append-only + snapcompact + shake + v2 streaming | 简单 truncation |
| **子代理隔离** | 8 种 CoW 后端 (APFS/btrfs/zfs/overlayfs/…) | subprocess 无隔离 |
| **模型防御** | Harmony leak + paused turn + soft tool req | ❌ |
| **Prompt cache** | 字节级稳定前缀 | ❌ |
| **Advisor** | 第二模型实时审查 | ❌ |
| **TTSR** | 流中正则匹配 → abort → inject → retry | ❌ (skills 事后生效) |

---

## 十一、批判性分析

### 优点

1. **双层循环是真正的创新**。大多数 agent（包括 Hermes、Claude Code）都是单层 while，处理 follow-up/aside 需要退出循环后重新进入。omp 的设计让这些异步消息在循环内部无缝注入，减少了 prompt cache 失效。
2. **防御性编程深度惊人**。Harmony leak 检测、paused turn 重采样、soft tool requirement escalate——这些都是针对「模型不可靠」场景的实战防御，是长期使用后沉淀下来的工程智慧。
3. **Abort race 复用**是性能优化的好例子。一个 Promise.race 复用整个 stream，而不是每个 chunk 注册新 listener。
4. **TTSR 的「匹配才注入」模式**比 Hermes 的 skills（每次都注入）更省 token。但 TTSR 需要 abort + retry，对 provider 有额外调用成本。

### 问题

1. **双层循环增加了心智负担**。`pendingMessages` 在内外循环交接处的行为不容易直观理解（如 "stop boundary" vs "mid-work" 对 aside 的不同处理逻辑，见 1052-1061 行）。
2. **压缩逻辑耦合在 agent-loop 的外部**。`shouldCompact()` 的判断在 session manager 层而非 loop 内，loop 自己不知道是否被压缩了——这在多进程场景下可能导致不一致。
3. **TTSR 的实现位置分散**。规则匹配在 `onAssistantMessageEvent` hook 中（不在 agent-loop.ts 内），注入逻辑通过外层 steering queue，追踪一条 TTSR 规则的完整生命周期需要跨 3-4 个文件。
4. **子代理的 8 种隔离后端是过度设计**。实际生产环境中 99% 的使用场景只需要 rcopy 或 git worktree，APFS clone / btrfs reflink / zfs clone 的代码覆盖率和测试不足。
5. **没有显式的 budget/token 追踪在 loop 内部**。依赖外部的 `CompactionSettings` 判断何时压缩，loop 自身不感知 token 消耗速度。

### 对 Hermes 的可操作建议

| 建议 | 优先级 | 复杂度 |
|------|--------|--------|
| **引入软工具要求（Soft Tool Requirement）** | 高 | 中 |
| 当模型反复拒绝调用某个关键工具时，omp 的 remind→escalate 模式很有效。Hermes 可以在 `_should_parallelize_tool_batch()` 后追加类似检查 | | |
| **Abort race 复用优化** | 中 | 低 |
| Hermes 的 async generator 每次 yield 不需要注册新 listener，但 omp 的 Promise.race 复用思路在 Python 中对应 `asyncio.wait(iterator.__anext__(), abort_future)` | | |
| **双循环结构** | 低 | 高 |
| 对于 Discord/微信场景，外层 follow-up 循环让 agent 能无缝处理异步到来的用户消息。但改动量大 | | |
| **TTSR 风格的条件注入** | 中 | 中 |
| 类比 Hermes 的 skills：skills 每次 turn 都注入。可以增加「有条件注入」的 skill 类型——只有正则匹配到上下文时才注入 | | |

---

## 十二、源码导航

| 文件 | 行数 | 核心内容 |
|------|------|----------|
| `packages/agent/src/agent-loop.ts` | 2137 | **核心循环**：`runLoopBody` + `streamAssistantResponse` + `executeToolCalls` |
| `packages/agent/src/agent.ts` | 1452 | Agent 类：`prompt()` → `#runLoop()` → 事件转发 |
| `packages/agent/src/types.ts` | 709 | `AgentLoopConfig`、`AgentEvent` 等类型 |
| `packages/agent/src/compaction/compaction.ts` | 1505 | 压缩核心：`shouldCompact`、`findCutPoint`、`compact` |
| `packages/agent/src/compaction/compaction-v2-streaming.ts` | - | V2 流式压缩 |
| `packages/agent/src/append-only-context.ts` | 348 | 不可变前缀缓存 |
| `packages/coding-agent/src/task/index.ts` | 1441 | **子代理入口**：taskTool handler + 并发调度 |
| `packages/coding-agent/src/task/executor.ts` | 2440 | 子代理进程执行 |
| `packages/coding-agent/src/task/isolation-runner.ts` | 368 | 8 种 CoW 隔离后端 |
| `packages/coding-agent/src/advisor/runtime.ts` | 518 | Advisor 独立 agent 实例 |
| `packages/coding-agent/src/advisor/watchdog.ts` | 135 | Advisor 事件轮询触发器 |
| `packages/coding-agent/src/export/ttsr.ts` | 583 | TTSR 规则管理器 |
| `packages/coding-agent/src/commands/ttsr.ts` | 125 | `omp ttsr` CLI 命令 |
| `packages/ai/` | - | 多供应商 LLM 客户端 |
