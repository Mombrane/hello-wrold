# Mastra Observational Memory 深度分析

## 1. Mastra 框架概述

**Mastra** 是由 Gatsby 团队创建的 TypeScript AI Agent 框架，GitHub 星标 24.9k，Y Combinator W25 孵化项目。

### 核心架构

```
packages/
├── core/          # 核心框架：Agent、Memory、Storage、Workflows、LLM
├── memory/        # 独立的 Memory 包，包含 Observational Memory 实现
├── stores/        # 存储适配器（pg、libsql、mongodb、upstash 等）
└── explorations/  # 探索性项目（包括 LongMemEval 基准测试）
```

Mastra 是一个模块化的 Agent 框架，核心特性包括：
- **模型路由**：40+ 提供商统一接口
- **Agent 抽象**：带工具、记忆、语音的自主 Agent
- **工作流引擎**：基于图的执行引擎（`.then()`、`.branch()`、`.parallel()`）
- **记忆系统**：对话历史、语义召回、工作记忆、观察记忆
- **处理器系统**：输入/输出处理器流水线

---

## 2. Mastra 记忆架构

Mastra 的记忆系统是**四层架构**：

### 2.1 对话历史（Message History）
- 基于线程的对话组织
- 配置 `lastMessages` 控制保留最近 N 条消息
- 默认 10 条

### 2.2 语义召回（Semantic Recall）
- 基于向量嵌入的 RAG 检索
- 需要向量数据库（PgVector、Pinecone、Qdrant 等）+ 嵌入模型
- 配置 `topK`、`messageRange`、`scope`（thread/resource）
- 支持元数据过滤和相似度阈值

### 2.3 工作记忆（Working Memory）
- LLM 维护的结构化用户数据
- 支持 Markdown 模板或 JSON Schema
- 通过工具调用（`updateWorkingMemory`）更新
- 可选 thread 或 resource 作用域

### 2.4 观察记忆（Observational Memory）⭐
- **核心创新**：三级记忆系统（消息 → 观察 → 反思）
- 两个后台 Agent（Observer + Reflector）自动压缩历史
- 在 LongMemEval 基准测试中达到 **94.87% QA 准确率**

### 记忆配置示例

```typescript
const memory = new Memory({
  storage: new LibSQLStore({ url: "file:./memory.db" }),
  vector: new PgVector({ connectionString: process.env.DATABASE_URL }),
  embedder: "openai/text-embedding-3-small",
  options: {
    lastMessages: 10,
    semanticRecall: { topK: 5, messageRange: 2, scope: 'resource' },
    workingMemory: { enabled: true, scope: 'resource', template: '...' },
    observationalMemory: true,  // 或详细配置对象
  },
});
```

---

## 3. Observational Memory 架构详解

### 3.1 三 Agent 架构

```
┌─────────────────────────────────────────────────────────┐
│                    Actor (主 Agent)                       │
│  看到：观察日志 + 最近未观察的消息 + 建议续写               │
└───────────┬─────────────────────────────┬───────────────┘
            │ 消息超过阈值时触发           │ 观察超过阈值时触发
            ▼                             ▼
┌───────────────────────┐   ┌───────────────────────┐
│   Observer (观察者)     │   │  Reflector (反思者)    │
│  从消息中提取观察       │   │  压缩/重组观察日志     │
│  默认: gemini-2.5-flash│   │  默认: gemini-2.5-flash│
│  temperature: 0.3      │   │  temperature: 0        │
└───────────────────────┘   └───────────────────────┘
```

### 3.2 核心流程

#### Observation（观察）阶段
1. **触发条件**：未观察的消息 token 数超过 `messageTokens`（默认 30,000）
2. **Observer Agent** 接收格式化的历史消息
3. 输出结构化观察日志，包含：
   - 🔴 用户断言（`User stated...`）
   - 🟡 Agent 行动（`Agent used tool...`）
   - ✅ 完成标记（`Task completed...`）
   - 时间锚定（`(HH:MM) observation. (meaning DATE)`）
4. 压缩比通常 **5-40x**

#### Reflection（反思）阶段
1. **触发条件**：观察 token 数超过 `observationTokens`（默认 40,000）
2. **Reflector Agent** 重组和压缩观察
3. 保留所有重要信息（反思结果是 Agent 的**全部记忆**）
4. 合并相关条目，保留时间上下文

#### 异步缓冲（Async Buffering）
- **默认启用**：观察在后台异步运行
- `bufferTokens: 0.2` = 每 20% 阈值（~6k tokens）触发一次后台观察
- `bufferActivation: 0.8` = 激活时保留 20% 消息历史
- 到达阈值时**零延迟激活**（无需等待 LLM）
- `blockAfter: 1.2` = 超过 120% 阈值时强制同步观察

### 3.3 数据模型

```typescript
interface ObservationalMemoryRecord {
  id: string;
  scope: 'thread' | 'resource';
  threadId: string | null;
  resourceId: string;
  
  // 内容
  activeObservations: string;           // 当前活跃的观察
  bufferedObservationChunks?: Chunk[];  // 待激活的缓冲块
  bufferedReflection?: string;          // 待激活的反射
  
  // 元数据
  lastObservedAt?: Date;        // 最后观察时间
  originType: 'initial' | 'reflection';
  generationCount: number;      // 反思代数
  
  // Token 追踪
  totalTokensObserved: number;
  observationTokenCount: number;
  pendingMessageTokens: number;
  
  // 状态标志
  isReflecting: boolean;
  isObserving: boolean;
  isBufferingObservation: boolean;
  isBufferingReflection: boolean;
}
```

### 3.4 Observer 的提示词工程

Observer 的系统提示词非常精细（~800 行），关键设计：

```typescript
// 区分用户断言 vs 问题
"User stated has two kids" → 🔴 (断言，权威来源)
"User asked how many kids" → 🟡 (问题，不否定断言)

// 时间锚定
"(09:15) User will visit parents this weekend. (meaning June 17-18, 20XX)"

// 保留具体细节（非泛化摘要）
BAD:  "Assistant recommended 5 hotels"
GOOD: "Assistant recommended hotels: Hotel A (near station), Hotel B (budget)..."

// 保留用户原话的非标准措辞
"User stated they did a 'movement session' (their term for exercise)"

// 完成追踪
✅ 用于标记已完成的任务，防止 Agent 重复工作
```

---

## 4. LongMemEval 基准测试

### 4.1 什么是 LongMemEval

LongMemEval 是 ICLR 2025 论文提出的基准测试，评估聊天助手的长期记忆能力：

- **500 个精心策划的问题**
- **5 种核心能力**：
  1. 信息提取（Information Extraction）
  2. 多会话推理（Multi-Session Reasoning）
  3. 知识更新（Knowledge Updates）
  4. 时间推理（Temporal Reasoning）
  5. 抑制回答（Abstention）

- **三个数据集变体**：
  - `longmemeval_s`（Small）：~115k tokens/问题，30-40 会话
  - `longmemeval_m`（Medium）：~1.5M tokens/问题，500 会话
  - `longmemeval_oracle`：仅证据会话

### 4.2 Mastra 的 LongMemEval 实现

Mastra 在 `explorations/longmemeval/` 目录下实现了完整的基准测试套件：

```typescript
// 配置示例：observational-memory 配置
'observational-memory': {
  type: 'observational-memory',
  description: 'Observational Memory with GPT-4o (baseline OM config)',
  memoryOptions: {
    lastMessages: 0,              // 不使用最近消息（OM 管理所有历史）
    semanticRecall: false,        // 不使用语义召回
    workingMemory: { enabled: false },
  },
  needsRealModel: true,
  usesObservationalMemory: true,
  requiresSequential: true,
  agentModel: 'openai/gpt-4o',
  evalModel: 'openai/gpt-4o',
}
```

### 4.3 如何达到 94.87% 准确率

Mastra 的 Observational Memory 之所以能在 LongMemEval 上取得高分，关键在于：

#### 1. **精细化的观察提取**
- Observer 的提示词区分**断言 vs 问题**，确保用户陈述的事实不会被后续问题否定
- **时间锚定**：每个观察都标记消息时间和引用时间，支持时间推理
- **具体细节保留**：不是泛化摘要，而是保留名称、数字、列表等可查询细节

#### 2. **三级记忆的层次化处理**
- 最近消息 → 精确的历史记录（用于当前任务）
- 观察 → 压缩的关键信息（5-40x 压缩）
- 反思 → 进一步压缩的长期记忆

#### 3. **知识更新处理**
- Observer 专门标记状态变更：`"User will start doing X (changing from Y)"`
- 上下文指令要求 Agent 优先使用**最新信息**
- 日期标注帮助 Agent 判断信息新旧

#### 4. **完成追踪（✅ 标记）**
- 防止 Agent 重复已完成的工作
- 在 Abstention 类问题上特别有效（知道什么已完成/未完成）

#### 5. **评估方法**
- 使用官方 LongMemEval 评估提示词（与原始论文一致）
- GPT-4o 作为评估模型判断 yes/no
- 针对不同问题类型使用不同的评估提示词（如 temporal-reasoning 允许 ±1 天误差）

---

## 5. 与 MemPalace 的对比

| 维度 | Mastra Observational Memory | MemPalace |
|------|---------------------------|-----------|
| **架构** | 三 Agent 系统（Actor/Observer/Reflector） | 类似认知科学的记忆宫殿方法 |
| **压缩方式** | LLM 驱动的观察提取 + 反思压缩 | 空间化/结构化记忆组织 |
| **触发机制** | 基于 token 阈值的自动触发 | 可能基于不同策略 |
| **时间处理** | 显式时间锚定 + 时间推理指令 | 待研究 |
| **异步处理** | 内置异步缓冲，零延迟激活 | 待研究 |
| **存储** | 结构化记录 + 缓冲块 + 代数追踪 | 待研究 |
| **评估** | LongMemEval 94.87% | 待研究 |
| **开源状态** | 完全开源（Apache 2.0） | 待研究 |

### Mastra OM 的独特优势

1. **生产就绪**：不是论文原型，而是集成在生产框架中的完整实现
2. **异步缓冲**：后台观察不阻塞主 Agent，用户体验流畅
3. **提示缓存友好**：观察日志稳定追加，保持 prompt prefix 可缓存
4. **可配置性强**：阈值、模型、作用域、缓冲策略全部可调
5. **检索模式**：实验性功能，观察组保留原始消息指针，支持 recall 工具回溯

---

## 6. 关键源代码片段

### 6.1 Observer 系统提示词核心

```typescript
// packages/memory/src/processors/observational-memory/observer-agent.ts

export const OBSERVER_EXTRACTION_INSTRUCTIONS = `CRITICAL: DISTINGUISH USER ASSERTIONS FROM QUESTIONS

When the user TELLS you something about themselves, mark it as an assertion:
- "I have two kids" → 🔴 (14:30) User stated has two kids
- "I work at Acme Corp" → 🔴 (14:31) User stated works at Acme Corp

When the user ASKS about something, mark it as a question/request:
- "Can you help me with X?" → 🔴 (15:00) User asked help with X

STATE CHANGES AND UPDATES:
When a user indicates they are changing something, frame it as a state change:
- "I'm going to start doing X instead of Y" → "User will start doing X (changing from Y)"

TEMPORAL ANCHORING:
Each observation has TWO potential timestamps:
1. BEGINNING: The time the statement was made (from the message timestamp)
2. END: The time being REFERENCED, if different

FORMAT:
- With time reference: (TIME) [observation]. (meaning/estimated DATE)
- Without time reference: (TIME) [observation].`;
```

### 6.2 Reflector 系统提示词核心

```typescript
// packages/memory/src/processors/observational-memory/reflector-agent.ts

export function buildReflectorSystemPrompt(instruction?: string): string {
  return `You are the memory consciousness of an AI assistant. Your memory observation 
reflections will be the ONLY information the assistant has about past interactions.

IMPORTANT: your reflections are THE ENTIRETY of the assistants memory. Any information 
you do not add to your reflections will be immediately forgotten. Make sure you do not 
leave out anything. Your reflections must assume the assistant knows nothing.

When consolidating observations:
- Preserve and include dates/times when present
- Retain the most relevant timestamps
- Preserve ✅ completion markers
- Condense older observations more aggressively, retain more detail for recent ones

CRITICAL: USER ASSERTIONS vs QUESTIONS
- "User stated: X" = authoritative assertion
- "User asked: X" = question/request
USER ASSERTIONS TAKE PRECEDENCE.`;
}
```

### 6.3 默认配置

```typescript
// packages/memory/src/processors/observational-memory/constants.ts

export const OBSERVATIONAL_MEMORY_DEFAULTS = {
  observation: {
    model: 'google/gemini-2.5-flash',
    messageTokens: 30_000,
    modelSettings: { temperature: 0.3, maxOutputTokens: 100_000 },
    maxTokensPerBatch: 10_000,
    bufferTokens: 0.2,      // 每 20% 阈值触发异步缓冲
    bufferActivation: 0.8,  // 激活时保留 20% 消息
  },
  reflection: {
    model: 'google/gemini-2.5-flash',
    observationTokens: 40_000,
    modelSettings: { temperature: 0, maxOutputTokens: 100_000 },
    bufferActivation: 0.5,  // 50% 阈值开始异步反思
  },
};
```

### 6.4 处理器集成

```typescript
// packages/memory/src/processors/observational-memory/processor.ts

export class ObservationalMemoryProcessor implements Processor<'observational-memory'> {
  readonly id = 'observational-memory' as const;
  
  async processInputStep(args: ProcessInputStepArgs): Promise<MessageList> {
    // 1. 获取线程上下文
    const context = this.engine.getThreadContext(requestContext, messageList);
    
    // 2. 创建 Turn（跟踪单次对话轮次的生命周期）
    this.turn = this.engine.beginTurn({ threadId, resourceId, messageList });
    
    // 3. 运行 Step 准备（激活、阈值检查、观察、过滤）
    const step = this.turn.step(stepNumber);
    const ctx = await step.prepare();
    
    // 4. 注入系统消息（观察 + 续写提示）
    injectObservationContextMessages({ messageList, systemMessages: ctx.systemMessage });
    
    return messageList;
  }
  
  async processOutputResult(args: ProcessOutputResultArgs): Promise<MessageList> {
    // 结束 Turn（触发消息保存、观察检查）
    await turn.end();
    return messageList;
  }
}
```

---

## 7. 总结

Mastra 的 Observational Memory 是目前开源社区中最完整的长期记忆实现之一。它的核心创新在于：

1. **认知启发的三 Agent 架构**：模拟人类的观察→反思→长期记忆过程
2. **生产级异步缓冲**：后台观察零延迟激活，不阻塞用户体验
3. **精细化的提示词工程**：区分断言/问题、时间锚定、具体细节保留
4. **在 LongMemEval 上验证**：94.87% 的 QA 准确率证明了其有效性

对于 MemPalace 项目来说，Mastra 的设计提供了宝贵的参考：
- 观察/反思的双阶段处理模式
- 基于 token 阈值的自动触发机制
- 时间感知的记忆组织
- 异步处理以保持用户体验流畅

---

*分析基于 Mastra 仓库 `packages/memory/src/processors/observational-memory/` 目录下的源代码和 `docs/src/content/en/docs/memory/observational-memory.mdx` 文档。*

*LongMemEval 基准测试代码位于 `explorations/longmemeval/` 目录。*
