# Grok Build 上下文压缩机制 — 深度分析

> 从源码级别分析 grok-build 的 full-replace 压缩 pipeline

---

## 一、压缩全景图

```
┌──────────────────────────────────────────────────────────────────┐
│                     Agent Loop (turn.rs)                         │
│  check_auto_compact_needed() → context window 超 85%?           │
│         ↓ 是                                                     │
│  ┌─────────────────── code_compaction ──────────────────────┐   │
│  │                                                            │   │
│  │  sample_full_replace_summary()                             │   │
│  │    ├── build_summary_prompt()      ← 构建 9 段摘要 prompt │   │
│  │    ├── sample_summary_with_retries() ← 带重试的 LLM 调用  │   │
│  │    │     ├── success: 非空 + 非退化 → Ok                   │   │
│  │    │     ├── empty/退化: transient → retry                 │   │
│  │    │     ├── deterministic error: 不重试 → Err              │   │
│  │    │     └── context_overflow: 通知 harness 缩减输入        │   │
│  │    └── observer.on_success/on_error                         │   │
│  │                                                            │   │
│  │  apply_full_replace_compaction()                            │   │
│  │    ├── sample_full_replace_summary() ← 上面那个              │   │
│  │    ├── format_compact_summary_content() ← 清洗 + 加 preamble│   │
│  │    └── assemble_compacted_history()  ← 重建对话             │   │
│  │                                                            │   │
│  └────────────────────────────────────────────────────────────┘   │
│         ↓                                                        │
│  新的 compacted history 替换原始 conversation                      │
└──────────────────────────────────────────────────────────────────┘
```

---

## 二、数据结构

### 2.1 FullReplaceConfig — 压缩配置

```rust
// code_compaction/config.rs:24
pub struct FullReplaceConfig {
    pub max_attempts: u32,            // 最多 LLM 调用次数 (默认 3)
    pub retry_delay_secs: u64,        // 重试等待秒数 (默认 3)
    pub sampling_timeout_secs: u64,   // 单次 LLM 超时秒数 (默认 120)
}
```

### 2.2 FullReplaceContext — harness 提供的上下文

```rust
// code_compaction/compact.rs:34
pub struct FullReplaceContext<T> {
    pub system_message: T,                 // 原始 system prompt（原样保留）
    pub user_message_prefix: String,       // <user_info> 块
    pub agents_md_reminder: Option<String>,// AGENTS.md 项目指令
    pub last_user_query: Option<String>,   // 最后一条用户真实查询
    pub recent_messages: Vec<T>,           // 当前 turn 的最近消息（原样保留）
    pub system_reminder: Option<String>,   // <system-reminder>（编辑文件、运行任务等）
    pub transcript_hint: Option<String>,   // 转录位置指针
}
```

### 2.3 FullReplaceOutput — 压缩产物

```rust
// code_compaction/compact.rs:88
pub struct FullReplaceOutput<T> {
    pub history: Vec<T>,     // 重建后的完整对话
    pub summary: String,     // 原始模型摘要（未经清洗，用于持久化）
    pub attempts: u32,       // LLM 调用次数
}
```

### 2.4 CompactedHistoryParts — 拼装输入

```rust
// code_compaction/assemble.rs:27
pub struct CompactedHistoryParts<T> {
    pub system_message: T,
    pub user_message_prefix: String,
    pub agents_md_reminder: Option<String>,
    pub last_user_query: Option<String>,
    pub recent_messages: Vec<T>,
    pub compaction_summary: String,  // 清洗后的摘要文本
    pub system_reminder: Option<String>,
    pub transcript_hint: Option<String>,
}
```

---

## 三、完整 Pipeline 分步解析

### Step 1: 构建 Prompt

**`build_summary_prompt()`** → `code_compaction/prompt.rs:15`

```
用户可选的 /compact <context> 文本 → 内联插入
                ↓
使用模板文件 full_replace_summary_prompt.txt
    ↓
返回 CompactionPrompt { system: "", user: "<完整 9 段指令>" }
```

注意：grok-build 的 compaction **不设 system prompt**——所有指令都作为 user message 发送。

### Step 2: 采样（带重试）

**`sample_summary_with_retries()`** → `code_compaction/sample.rs:80`

这是 compaction 最核心的循环：

```
for attempt in 1..=max_attempts:
    match sampler.sample_compaction(turns, prompt, timeout):
    
    ├── Ok(response) 且 response 非空:
    │     ├── is_degenerate_summary(response)? 
    │     │     是 → observer Degenerate → retry
    │     │     否 → observer Success → 返回 SampledSummary
    │
    ├── Ok(空 response):
    │     observer EmptyResponse → retry
    │
    └── Err(e):
          ├── is_context_length_error(msg)? 
          │     是 → deterministic + context_overflow → 立即返回 Err
          ├── e.is_deterministic()?
          │     是 → 立即返回 Err (不重试)
          └── 否 → transient → retry
    
    sleep(retry_delay)
    
耗尽 → Err(Empty { attempts }) 或 Err(Failure { ... })
```

**退化的判定** → `summary.rs:123`:
```rust
fn is_degenerate_summary(raw: &str) -> bool {
    format_compact_summary(raw).chars().count() < MIN_SUMMARY_SEED_CHARS  // 500
}
```

**失败分类:**
- `transient`: timeout、临时网络故障 → 可重试
- `deterministic`: Build 错误（"bad model"）、Auth 错误 → 不可重试
- `context_overflow`: prompt 太长 → 不可重试当前输入，但 harness 可用更小输入重试（verbatim→fitted→lossy 阶梯）

### Step 3: 清洗

**`format_compact_summary()`** → `code_compaction/summary.rs:19`

三步清洗 pipeline：

```
1. 剥离前导 <analysis>…</analysis> 草稿块
   - 循环移除多个前导 analysis 块
   - 只移除真正前导的（在 <summary> 之前）
   - 正文中引用的 analysis 标签保留

2. 转换 <summary>…</summary> 为 "Summary:\n{inner}"
   - 用 rfind 匹配外层闭合标签（防止正文中的 </summary> 截断）
   - 剥离内部前导草稿（**Analysis** 风格的 markdown）
   - 保留已编号开头的段落

3. 中和控制 token
   - <summary>  → <​summary>   (插入零宽空格)
   - </summary> → <​/summary>
   - <analysis> → <​analysis>
   - </analysis>→ <​/analysis>
   - 同样处理 summary_request 标签
   
4. 折叠多余空行 (3+ → 2)
```

**为什么需要中和控制 token？** 因为模型有时会在摘要的第 6 段（"All User Messages"）中引用 compaction 指令本身。如果不清洗这些标签，下一轮对话可能被误导重新输出 `<summary>` 块。

### Step 4: 拼装

**`assemble_compacted_history()`** → `code_compaction/assemble.rs:62`

拼装顺序（精确）：

```
[0] System message        ← 原始 system prompt，原样保留
[1] User message prefix   ← <user_info>OS: macos...</user_info> 作为 user_meta
[2] AGENTS.md reminder    ← 项目指令，作为 ProjectInstructions 重新注入
[3] Last user query       ← 最后一条用户查询，用 <user_query> 包装
[4] Recent messages       ← 当前 turn 的最近消息（原样保留）
[5] Compaction summary    ← "This session is being continued..." + 清洗后摘要
[6] System reminder       ← <system-reminder> 编辑文件、运行任务等状态
```

**为什么要重建而不是拼接？** 因为 full-replace 丢弃了所有旧消息，新对话从零开始。每一层都有明确的语义目的：
- System message = 身份定义
- User prefix = 环境信息
- AGENTS.md = 项目规则（不依赖摘要质量）
- Last query = 用户意图（不依赖摘要质量）
- Recent messages = 当前上下文（不依赖摘要质量）
- Summary = 历史压缩（依赖 LLM 质量）
- System reminder = 运行时状态

---

## 四、触发机制

### 4.1 Token 阈值触发

**`should_compact()`** → `intra_compaction/trigger.rs:117`

```rust
fn should_compact(
    last_prompt_tokens: u64,
    context_window: u64,
    config: &IntraCompactionConfig,
) -> bool {
    last_prompt_tokens > context_window * config.trigger_threshold_percent / 100
    // 即: last_prompt_tokens > context_window * 85 / 100
}
```

触发条件三要素：
1. `enabled = true`
2. `context_window != 0`
3. `last_prompt_tokens > context_window * 85%`

### 4.2 IntraCompaction 配置

```rust
// intra_compaction/config.rs:84
trigger_threshold_percent: 85    // 触发阈值
target_threshold_percent:  50    // 压缩后目标（压缩到 50% 窗口大小）
min_compactable_tokens:     5000 // 小于此值不值得压缩
max_reduction_ratio:        0.8  // 至少减少 20%
compaction_model_name:      "grok-4.20"  // 专用压缩模型
min_steps_before_compact:   3    // 最少步数（FullReplace 忽略）
```

### 4.3 输入阶梯 (Input Ladder)

当 compaction LLM 调用返回 `context_overflow` 错误时，harness 不放弃，而是逐步缩减输入。由 Shell 侧（非 compaction crate）驱动：

```
enum InputStage { Verbatim, VerbatimFitted, Lossy }
// compaction.rs:964-968

Verbatim (完整输入)
    prepare_conversation_for_verbatim_summarization()
    仅当 verbatim_input: true 时使用
    ↓ 如果 context_overflow

VerbatimFitted (裁剪后仍完整的输入)
    裁剪消息使总 token 适应窗口
    ↓ 如果 context_overflow

Lossy (有损压缩输入 — 默认)
    prepare_conversation_for_summarization()
    使用默认的简化的消息格式
    ↓ 如果还是失败

放弃压缩，agent 继续运行在当前 context 中
```

触发 `verbatim_input` 的条件（优先级从高到低）：
1. 环境变量 `GROK_COMPACTION_VERBATIM_INPUT`
2. 用户 config `features.compaction_verbatim_input`
3. Remote settings feature flag
4. 默认值 `true`

---

## 五、SplitPlan 分割算法

**`select_turns_to_compact()`** → `select.rs:60`

当使用 tail-keep 模式（IntraCompaction 的 StepsOnly/HistoryOnly）时，需要决定在对话的哪个位置切割：

```
算法:
1. 从最新项向前遍历，累计 "保留" 端的 token
2. 当添加下一项会超出 target_tokens 时，设置分割点
3. 安全边界修正:
   - 如果分割点落在 tool-result 项上
   - 前移越过所有连续的 tool-result 项
   - 原因: 孤立的 tool 结果（没有对应的 assistant 消息）会导致 API 400 错误
4. 如果可压缩 token < min_compactable (5000)，返回 None（不值得压缩）
```

---

## 六、与其他 Agent 的深度对比

### 6.1 压缩策略对比

| 维度 | Grok Build | Claude Code | OpenCode |
|------|-----------|-------------|----------|
| **策略名** | Full-Replace | 结构化摘要 + 尾部保留 | 结构化摘要 + 增量更新 |
| **保留什么** | 系统提示 + user_info + AGENTS.md + 最后查询 + 最近消息 | 系统提示 + 最近 N 轮 + 摘要 | 系统提示 + 增量摘要 |
| **丢弃什么** | 所有历史 tool 调用和结果 | 超出保留窗口的旧轮次 | 旧轮次 |
| **重建方式** | 从零拼装 7 层结构 | 摘要插入 + 尾部拼接 | 增量摘要追加 |
| **模型依赖** | 专用 `grok-4.20` | 主力模型 | 主力模型 |

### 6.2 清洗机制对比

| 清洗步骤 | Grok | Claude Code |
|----------|------|-------------|
| 剥离 reasoning 草稿 | ✅ `<analysis>` 标签剥离 | ✅ thinking 标签剥离 |
| 转换 XML → 纯文本 | ✅ `<summary>` → `Summary:\n` | ✅ `<summary>` → 纯文本 |
| 控制 token 中和 | ✅ 零宽空格注入 | ❌ 不需要（不同格式） |
| 退化检测 | ✅ < 500 chars → 重试 | ✅ 长度阈值 |
| 空白行整理 | ✅ 3+ → 2 | ✅ |

### 6.3 我的判断

**Grok 的 full-replace 是"赌注最大"的设计。** 它完全信任 LLM 摘要质量。好处是：
- 压缩后 context 最小（没有冗余的旧消息）
- 新对话"干净"，不会受旧错误影响

风险是：
- **摘要遗漏**：如果摘要忘了某个关键文件路径，后续 agent 就无法知道
- **AGENTS.md 和 last_user_query 是安全网**：这两个不依赖摘要，保证最基本信息不丢失
- **clean summary 的细节处理非常考究**：零宽空格中和、多前导 analysis 循环剥离、markdown Analysis 头的处理——这些细节说明他们踩过很多坑

相比之下，Claude Code/OpenCode 的"摘要 + 尾部保留"更保守但更安全——即使摘要质量差，尾部原样保留的最近对话也能兜底。

---

## 七、附录：文件索引

| 文件 | 内容 |
|------|------|
| `code_compaction/compact.rs` | 编排器：`apply_full_replace_compaction()` + `sample_full_replace_summary()` |
| `code_compaction/sample.rs` | 采样循环：`sample_summary_with_retries()` — 含退化检测和失败分类 |
| `code_compaction/assemble.rs` | 拼装器：`assemble_compacted_history()` — 7 层重建 |
| `code_compaction/summary.rs` | 清洗器：`format_compact_summary()` — 3 步清洗 pipeline |
| `code_compaction/prompt.rs` | Prompt 构建：两种 prompt（Structured / SelfSummary） |
| `code_compaction/config.rs` | 配置：`FullReplaceConfig` + 默认阈值 |
| `code_compaction/failure.rs` | 失败分类：`FailureKind` + `is_context_length_error()` |
| `code_compaction/templates/full_replace_summary_prompt.txt` | 9 段结构化摘要模板 |
| `select.rs` | SplitPlan：`select_turns_to_compact()` — tool-pair 安全边界 |
| `intra_compaction/trigger.rs` | 触发器：`should_compact()` 85% 阈值 |
| `intra_compaction/config.rs` | Intra 配置：`IntraCompactionConfig` |
| `intra_compaction/compact.rs` | Intra 编排：4 种模式分发 |
