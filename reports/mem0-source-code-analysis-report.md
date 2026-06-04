# Mem0 源码深度解析：AI Agent 记忆层架构技术报告

> **版本基准**: GitHub `mem0ai/mem0` (2026-06-04, Apache 2.0)
> **分析范围**: 核心 Python SDK (`mem0/memory/main.py`)、记忆提取 Prompt、混合检索管线、实体存储、评分系统
> **报告日期**: 2026-06-04

---

## 目录

1. [项目概览](#1-项目概览)
2. [核心架构：单库 + 标签过滤](#2-核心架构单库--标签过滤)
3. [Memory 类初始化：工厂模式的可插拔设计](#3-memory-类初始化工厂模式的可插拔设计)
4. [记忆写入管线：V3 分阶段批处理管道](#4-记忆写入管线v3-分阶段批处理管道)
5. [记忆检索管线：三路混合检索](#5-记忆检索管线三路混合检索)
6. [评分系统：加法融合与自适应参数](#6-评分系统加法融合与自适应参数)
7. [实体存储：第二向量库与实体增强](#7-实体存储第二向量库与实体增强)
8. [Prompt 工程：记忆提取的指令设计](#8-prompt-工程记忆提取的指令设计)
9. [概念分层 vs 实际实现](#9-概念分层-vs-实际实现)
10. [支持的组件矩阵](#10-支持的组件矩阵)
11. [设计评价与局限性](#11-设计评价与局限性)
12. [附录：关键源码索引](#12-附录关键源码索引)

---

## 1. 项目概览

Mem0 是一个 **AI Agent 通用记忆层**，为 AI 应用提供跨会话的持久化记忆能力。核心解决的问题是：传统 AI Agent 在每次对话后"失忆"，需要在 prompt 中重复塞入大量上下文。Mem0 通过自动提取、存储、检索记忆来解决这个问题。

**关键数据**:
- GitHub Stars: 57,648 ⭐
- License: Apache 2.0
- 孵化器: Y Combinator
- 核心语言: Python (主力) + TypeScript
- 核心文件: `mem0/memory/main.py` (~1800 行)

---

## 2. 核心架构：单库 + 标签过滤

### 2.1 物理存储层

从源码 `Memory.__init__()` 可以看到，Mem0 的物理存储层非常简洁，只有 **3 个核心组件**：

```python
# mem0/memory/main.py:331-358
class Memory(MemoryBase):
    def __init__(self, config: MemoryConfig = MemoryConfig()):
        self.embedding_model = EmbedderFactory.create(...)   # 嵌入模型
        self.vector_store = VectorStoreFactory.create(...)    # 向量数据库
        self.llm = LlmFactory.create(...)                    # LLM（记忆提取用）
        self.db = SQLiteManager(self.config.history_db_path) # SQLite 历史存储
        self.reranker = None  # 可选 Reranker
        self._entity_store = None  # 实体存储（懒加载）
```

| 组件 | 存储内容 | 技术实现 |
|------|----------|----------|
| **向量数据库** | 所有记忆的 embedding + metadata | Qdrant / Pinecone / Chroma / FAISS / Milvus 等 25+ 后端 |
| **SQLite** | 对话原始历史（不进向量库） | `SQLiteManager`，用于获取 `last_k_messages` |
| **Entity Store** | 实体索引（第二向量集合） | 与主向量库同后端，集合名 `{collection}_entities` |

### 2.2 "分层" 的真相：Metadata 过滤

Mem0 官方文档描述了 4 层记忆（Conversation / Session / User / Org），但**底层并不使用独立的存储层**。分层完全通过 metadata 标签 + 查询过滤实现：

```python
# mem0/memory/main.py:99-100
ENTITY_PARAMS = frozenset({"user_id", "agent_id", "run_id"})
```

写入时，记忆附带 metadata：
```python
metadata["user_id"] = "alice"    # 用户级记忆
metadata["agent_id"] = "bot1"    # Agent 级记忆
metadata["run_id"] = "sess-42"   # 会话级记忆
```

查询时，通过 filter 限定范围：
```python
filters = {"user_id": "alice"}
self.vector_store.search(query=..., filters=filters)
```

**结论**：Mem0 的"多层记忆"是**逻辑分层**，不是物理分层。所有记忆存储在同一个向量库中，通过 metadata 标签隔离作用域。

---

## 3. Memory 类初始化：工厂模式的可插拔设计

Mem0 使用工厂模式实现组件的可插拔替换：

```python
# mem0/utils/factory.py
class LlmFactory:
    provider_to_class = {
        "ollama": ("mem0.llms.ollama.OllamaLLM", OllamaConfig),
        "openai": ("mem0.llms.openai.OpenAILLM", OpenAIConfig),
        "anthropic": ("mem0.llms.anthropic.AnthropicLLM", AnthropicConfig),
        "deepseek": ("mem0.llms.deepseek.DeepSeekLLM", DeepSeekConfig),
        "gemini": ("mem0.llms.gemini.GeminiLLM", BaseLlmConfig),
        "vllm": ("mem0.llms.vllm.VllmLLM", VllmConfig),
        # ... 17+ providers
    }
```

四个工厂类：
- `LlmFactory` — 17+ LLM 提供者
- `EmbedderFactory` — 14+ 嵌入模型
- `VectorStoreFactory` — 25+ 向量数据库
- `RerankerFactory` — 6 种 Reranker

通过 `Memory.from_config()` 或直接传入 `MemoryConfig` 即可切换任意组件。

---

## 4. 记忆写入管线：V3 分阶段批处理管道

`add()` 方法是记忆写入的入口。当 `infer=True`（默认）时，触发 V3 分阶段批处理管道：

### 4.1 管线总览

```
add(messages, user_id="alice")
    │
    ├── 构建 filters & metadata
    ├── 视觉消息解析（如果启用 vision）
    │
    └── _add_to_vector_store()
         │
         ├── Phase 0: 上下文收集
         │   └── db.get_last_messages(session_scope, limit=10)
         │
         ├── Phase 1: 已有记忆检索
         │   └── vector_store.search(query, top_k=10)
         │
         ├── Phase 2: LLM 提取（单次调用）
         │   ├── system_prompt = ADDITIVE_EXTRACTION_PROMPT
         │   ├── user_prompt = generate_additive_extraction_prompt(
         │   │       existing_memories, new_messages, last_k_messages, custom_instructions
         │   │   )
         │   └── response = llm.generate_response(response_format={"type": "json_object"})
         │
         ├── Phase 3: 批量嵌入
         │   └── embedding_model.embed_batch(mem_texts, "add")
         │
         ├── Phase 4: CPU 处理 + Hash 去重
         │   ├── md5(text) 去重
         │   └── lemmatize_for_bm25(text) 生成 BM25 索引词
         │
         ├── Phase 5: 批量持久化
         │   ├── vector_store.insert(vectors, ids, payloads)
         │   └── db.batch_add_history(history_records)
         │
         ├── Phase 7: 批量实体链接
         │   ├── extract_entities_batch(all_texts)
         │   ├── 实体去重 → 批量嵌入
         │   ├── entity_store.search_batch() 查找已有实体
         │   └── 区分 insert vs update → 批量写入
         │
         └── Phase 8: 保存消息历史 + 返回结果
```

### 4.2 关键设计决策

**UUID 反幻觉映射**（Phase 2）：

```python
# 用整数 ID 替换 UUID 传给 LLM，防止 LLM 幻觉出不存在的 UUID
uuid_mapping = {}
for idx, mem in enumerate(existing_results):
    uuid_mapping[str(idx)] = mem.id
    existing_memories.append({"id": str(idx), "text": mem.payload.get("data", "")})
```

LLM 输出使用整数 ID（"0", "1", ...），代码再映射回真实 UUID。这是一个精巧的反幻觉设计。

**批量 fallback 机制**：

每个批量操作都有逐条 fallback：
```python
try:
    self.vector_store.insert(vectors=all_vectors, ids=all_ids, payloads=all_payloads)
except Exception:
    for mid, vec, pay in zip(all_ids, all_vectors, all_payloads):
        try:
            self.vector_store.insert(vectors=[vec], ids=[mid], payloads=[pay])
        except Exception as e:
            logger.error(f"Failed to insert memory {mid}: {e}")
```

### 4.3 记忆 Metadata 结构

每条记忆在向量库中的 payload 结构：

```python
{
    "data": "用户喜欢喝拿铁",           # 记忆原文
    "hash": "a1b2c3...",                # MD5 去重哈希
    "text_lemmatized": "user like latte", # BM25 索引词（词形还原）
    "created_at": "2026-06-04T...",      # 创建时间
    "updated_at": "2026-06-04T...",      # 更新时间
    "user_id": "alice",                  # 作用域标签
    "agent_id": None,                    # 可选
    "run_id": None,                      # 可选
    "role": "user",                      # 消息来源角色
    "actor_id": None,                    # 可选，多角色场景
    "attributed_to": None                # 可选，记忆归属
}
```

---

## 5. 记忆检索管线：三路混合检索

`search()` 方法触发三路混合检索管线：

### 5.1 检索流程

```
search(query="Alice 喜欢什么咖啡？", filters={"user_id": "alice"})
    │
    ├── Step 1: 查询预处理
    │   ├── query_lemmatized = lemmatize_for_bm25(query)
    │   └── query_entities = extract_entities(query)
    │
    ├── Step 2: 语义向量化
    │   └── embeddings = embedding_model.embed(query, "search")
    │
    ├── Step 3: 语义搜索（过量召回）
    │   └── semantic_results = vector_store.search(top_k=max(limit*4, 60))
    │
    ├── Step 4: 关键词搜索（BM25）
    │   └── keyword_results = vector_store.keyword_search(query_lemmatized)
    │
    ├── Step 5: BM25 分数归一化
    │   └── sigmoid(raw_score, midpoint, steepness) → [0, 1]
    │
    ├── Step 6: 实体增强计算
    │   └── entity_boosts = _compute_entity_boosts(query_entities)
    │
    ├── Step 7: 候选集构建
    │   └── 以语义搜索结果为主候选集
    │
    ├── Step 8: 评分融合
    │   └── score_and_rank(semantic, bm25, entity_boost, threshold, top_k)
    │
    └── Step 9: 格式化输出
```

### 5.2 语义搜索

标准向量相似度搜索，但**过量召回**（4x top_k 或至少 60 条），为后续融合评分提供足够候选池：

```python
internal_limit = max(limit * 4, 60)
semantic_results = self.vector_store.search(
    query=query, vectors=embeddings, top_k=internal_limit, filters=filters
)
```

### 5.3 BM25 关键词搜索

如果向量数据库支持 `keyword_search` 方法，则同时执行 BM25 搜索。使用 **spaCy 词形还原**作为预处理：

```python
# mem0/utils/lemmatization.py
query_lemmatized = lemmatize_for_bm25(query)  # "喜欢喝咖啡" → 词形还原后
keyword_results = self.vector_store.keyword_search(query=query_lemmatized, ...)
```

---

## 6. 评分系统：加法融合与自适应参数

### 6.1 BM25 归一化

BM25 原始分数无上界，Mem0 使用 **sigmoid 函数**归一化到 [0, 1]：

```python
# mem0/utils/scoring.py
def normalize_bm25(raw_score, midpoint, steepness):
    return 1.0 / (1.0 + math.exp(-steepness * (raw_score - midpoint)))
```

**自适应参数**：根据查询长度调整 sigmoid 参数，长查询的 BM25 分数天然更高：

| 查询词数 | midpoint | steepness |
|----------|----------|-----------|
| ≤ 3 | 5.0 | 0.7 |
| ≤ 6 | 7.0 | 0.6 |
| ≤ 9 | 9.0 | 0.5 |
| ≤ 15 | 10.0 | 0.5 |
| > 15 | 12.0 | 0.5 |

### 6.2 加法融合评分

三个信号源**加法融合**（非加权平均）：

```python
# mem0/utils/scoring.py:60-84
def score_and_rank(semantic_results, bm25_scores, entity_boosts, threshold, top_k):
    max_possible = 1.0
    if has_bm25:    max_possible += 1.0      # +1.0
    if has_entity:  max_possible += 0.5      # ENTITY_BOOST_WEIGHT

    for result in semantic_results:
        semantic_score = result["score"]      # [0, 1]
        bm25_score = bm25_scores.get(id, 0)  # [0, 1]
        entity_score = entity_boosts.get(id, 0)  # [0, 0.5]

        combined = (semantic_score + bm25_score + entity_score) / max_possible
```

**阈值门控**：语义分数低于 threshold 的候选直接排除，即使 BM25/实体能提升也不通过。

### 6.3 信号组合与最大可能分

| 信号组合 | max_possible | 说明 |
|----------|-------------|------|
| 仅语义 | 1.0 | 最简场景 |
| 语义 + BM25 | 2.0 | 关键词匹配增强 |
| 语义 + 实体 | 1.5 | 实体关联增强 |
| 语义 + BM25 + 实体 | 2.5 | 全信号融合 |

---

## 7. 实体存储：第二向量库与实体增强

### 7.1 Entity Store 架构

Entity Store 是一个**独立的向量集合**，与主记忆向量库同后端：

```python
# mem0/memory/main.py:389-411
@property
def entity_store(self):
    if self._entity_store is None:
        entity_collection = f"{self.collection_name}_entities"  # 如 "mem0_entities"
        self._entity_store = VectorStoreFactory.create(...)
    return self._entity_store
```

每条实体记录的结构：
```python
{
    "data": "拿铁",                    # 实体文本
    "entity_type": "proper_noun",      # 实体类型
    "linked_memory_ids": ["uuid1", "uuid2"],  # 关联的记忆 ID 列表
    "user_id": "alice"                 # 作用域
}
```

### 7.2 实体提取策略

使用 **spaCy NLP** 提取 4 类实体：

| 类型 | 示例 | 说明 |
|------|------|------|
| proper_noun | "John", "San Francisco" | 首字母大写的多词序列 |
| quoted_text | "'The Great Gatsby'" | 引号内的文本 |
| noun_compound | "machine learning" | 多词名词短语 |
| noun_fallback | 单名词 | 环境复合模式的回退 |

带有大量过滤规则（`_GENERIC_HEADS`, `_NON_SPECIFIC_ADJ`, `_GENERIC_CAPS`），避免提取噪声实体。

### 7.3 实体增强搜索

查询时，从查询中提取实体，在 Entity Store 中查找匹配实体，然后 boost 关联的记忆：

```python
def _compute_entity_boosts(self, query_entities, filters):
    for _, entity_text in deduped[:8]:  # 最多 8 个实体
        entity_embedding = self.embedding_model.embed(entity_text, "search")
        matches = self.entity_store.search(query=entity_text, top_k=500, filters=...)

        for match in matches:
            if match.score < 0.5:  # 相似度阈值
                continue
            linked_memory_ids = match.payload.get("linked_memory_ids", [])

            # Spread-attenuated boost: 链接越多记忆的实体，boost 越弱
            num_linked = max(len(linked_memory_ids), 1)
            memory_count_weight = 1.0 / (1.0 + 0.001 * ((num_linked - 1) ** 2))
            boost = similarity * 0.5 * memory_count_weight  # ENTITY_BOOST_WEIGHT = 0.5

            for memory_id in linked_memory_ids:
                memory_boosts[memory_id] = max(memory_boosts.get(memory_id, 0), boost)
```

**关键设计**：Spread-attenuated boost —— 一个实体如果关联了太多记忆，其 boost 效果会被衰减，避免"万金油实体"过度影响排序。

---

## 8. Prompt 工程：记忆提取的指令设计

### 8.1 ADDITIVE_EXTRACTION_PROMPT（V3 核心 Prompt）

这是 V3 管线的核心 Prompt，指导 LLM 从对话中提取记忆。关键设计：

**角色定义**：
> You are a Memory Extractor — a precise, evidence-bound processor responsible for extracting rich, contextual memories from conversations. Your sole operation is ADD.

**双角色提取**：
- User 消息：个人信息、偏好、计划、经历
- Assistant 消息：建议、推荐、计划、方案（以用户视角归因）

**记忆关联**：
> When a new memory is related to an Existing Memory [...] include the Existing Memory's ID in the new memory's "linked_memory_ids" array.

**时间锚定**：
> "User went to Paris last week" is useless 6 months later. "User went to Paris the week of May 15, 2023" is meaningful forever.

**反重复指令**：
> If new information in New Messages is semantically equivalent to an Existing Memory with no meaningful new context, skip it.

### 8.2 多 Prompt 体系

| Prompt | 用途 | 版本 |
|--------|------|------|
| `ADDITIVE_EXTRACTION_PROMPT` | V3 主提取 Prompt（ADD-only） | 当前默认 |
| `FACT_RETRIEVAL_PROMPT` | V1 事实提取 | 旧版 |
| `USER_MEMORY_EXTRACTION_PROMPT` | 用户记忆提取（仅用户消息） | 平台版 |
| `AGENT_MEMORY_EXTRACTION_PROMPT` | Agent 记忆提取（仅助手消息） | 平台版 |
| `DEFAULT_UPDATE_MEMORY_PROMPT` | ADD/UPDATE/DELETE/None 四操作 | 旧版 |
| `PROCEDURAL_MEMORY_SYSTEM_PROMPT` | 程序性记忆摘要 | 特殊用途 |

### 8.3 程序性记忆

当 `memory_type="procedural_memory"` 且有 `agent_id` 时，走独立的 `_create_procedural_memory()` 路径，使用 LLM 生成结构化的执行历史摘要，适合 Agent 工作流记录。

---

## 9. 概念分层 vs 实际实现

### 9.1 官方文档的 4 层描述

| 层级 | 名称 | 生命周期 | 认知类比 |
|------|------|----------|----------|
| L1 | Conversation memory | 单次响应 | 工作记忆 |
| L2 | Session memory | 分钟~小时 | 短期记忆 |
| L3 | User memory | 永久 | 长期记忆 |
| L4 | Org memory | 全局 | 团队知识 |

### 9.2 实际实现映射

| 概念层 | 实际实现 | 存储位置 |
|--------|----------|----------|
| 工作记忆 | SQLite 中的 `last_k_messages` | SQLite（不进向量库） |
| 短期记忆 | 向量库中带 `run_id` 标签的记忆 | 同一向量库 |
| 长期记忆 | 向量库中带 `user_id` 标签的记忆 | 同一向量库 |
| Agent 记忆 | 向量库中带 `agent_id` 标签的记忆 | 同一向量库 |
| 情景记忆 | ❌ 无独立实现 | — |
| 程序性记忆 | `_create_procedural_memory()` | 同一向量库 |

### 9.3 关键结论

> Mem0 的"多层记忆"是**逻辑分层，非物理分层**。底层是单一向量数据库 + metadata 标签过滤，而非不同存储后端承载不同记忆层级。

---

## 10. 支持的组件矩阵

### 10.1 LLM 提供者（17+）

OpenAI、Anthropic、Azure OpenAI、Ollama、Together、Groq、LiteLLM、Mistral、Google Gemini、AWS Bedrock、DeepSeek、MiniMax、xAI、Sarvam、LM Studio、vLLM、LangChain

### 10.2 向量数据库（25+）

Qdrant、Pinecone、Chroma、FAISS、Milvus、PGVector、Elasticsearch、OpenSearch、Redis、MongoDB、Weaviate、Supabase、Upstash、Valkey、Azure AI Search、Azure MySQL、Baidu、Cassandra、Databricks、Neptune Analytics、S3 Vectors、Turbopuffer、Vertex AI、LangChain

### 10.3 嵌入模型（14+）

OpenAI、Azure OpenAI、Ollama、Together、Gemini、AWS Bedrock、HuggingFace、FastEmbed、VertexAI、LM Studio、LangChain、Mock（测试用）

### 10.4 Reranker（6 种）

Cohere、Sentence Transformer、HuggingFace、Zero Entropy、LLM-based、LangChain

---

## 11. 设计评价与局限性

### 11.1 优点

1. **架构简洁**：单向量库 + metadata 过滤，降低了运维复杂度
2. **组件可插拔**：工厂模式 + 配置驱动，切换后端零代码改动
3. **混合检索**：语义 + BM25 + 实体增强三路融合，比纯向量检索更鲁棒
4. **反幻觉设计**：UUID→整数映射防止 LLM 编造 ID
5. **批量优化**：V3 管线的批量嵌入、批量实体搜索，减少 API 调用
6. **实体增强**：独立的 Entity Store + Spread-attenuated boost，提升实体相关查询精度
7. **时间锚定**：Prompt 中强制将相对时间转为绝对日期

### 11.2 局限性

1. **无真正的多层存储**：所有记忆在同一向量库，无法针对不同层级使用不同存储策略（如短期用缓存、长期用持久化数据库）
2. **无情景记忆**：没有事件序列/经历的时间线存储
3. **无知识图谱**：Memory Graph 已从当前版本移除
4. **LLM 依赖重**：每次 add 都需要 LLM 调用，成本和延迟不可忽视
5. **BM25 支持依赖后端**：`keyword_search` 非所有向量数据库都支持
6. **Entity Store 额外开销**：每次 add 都要维护实体索引，写入放大

---

## 12. 附录：关键源码索引

| 文件 | 行数 | 核心功能 |
|------|------|----------|
| `mem0/memory/main.py` | ~1800 | Memory 类：add/search/get/update/delete，V3 管线 |
| `mem0/configs/prompts.py` | ~550 | 所有 Prompt 模板（提取、更新、程序性记忆） |
| `mem0/utils/scoring.py` | ~120 | BM25 归一化、加法融合评分 |
| `mem0/utils/entity_extraction.py` | ~200 | spaCy 实体提取（4 类实体 + 过滤规则） |
| `mem0/utils/factory.py` | ~300 | LLM/Embedding/VectorStore/Reranker 工厂 |
| `mem0/utils/lemmatization.py` | ~50 | spaCy 词形还原（BM25 预处理） |
| `mem0/memory/storage.py` | ~100 | SQLiteManager（对话历史存储） |
| `mem0/memory/base.py` | ~50 | MemoryBase 基类 |
| `mem0/configs/base.py` | ~100 | MemoryConfig / MemoryItem 数据模型 |
| `mem0/configs/enums.py` | ~10 | MemoryType 枚举 |

---

*本报告基于 Mem0 开源代码的直接分析生成，所有代码引用均指向实际源文件和行号。*
