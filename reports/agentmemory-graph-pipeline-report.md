# agentmemory 知识图谱：构建与召回全流程深度解析

> **基于源码分析的技术报告** | 仓库：[rohitg00/agentmemory](https://github.com/rohitg00/agentmemory) | 21.8k ⭐
>
> 分析版本：main 分支（2026-06-08）| 核心文件：`src/functions/graph.ts`、`src/functions/graph-retrieval.ts`、`src/state/hybrid-search.ts`、`src/state/schema.ts`、`src/types.ts`

---

## 一、图是什么

agentmemory 的知识图谱是其**三路混合检索**（BM25 + Vector + Graph）中的第三路，负责捕捉实体之间的**结构化关系**，弥补关键词匹配和向量相似度无法覆盖的"关系推理"能力。

图由两种核心数据结构组成：

### 1.1 GraphNode（节点）

```typescript
// src/types.ts
type GraphNodeType =
  | "file" | "function" | "concept" | "error" | "decision"
  | "pattern" | "library" | "person" | "project"
  | "preference" | "location" | "organization" | "event";  // 共 13 种

interface GraphNode {
  id: string;                          // "gn_xxx"
  type: GraphNodeType;                 // 节点类型
  name: string;                        // 实体名称，如 "JWT"
  properties: Record<string, unknown>; // 附加属性
  sourceObservationIds: string[];      // 来源 observation ID 列表
  createdAt: string;                   // 创建时间
  updatedAt?: string;                  // 更新时间
  aliases?: string[];                  // 别名
  stale?: boolean;                     // 是否过期
}
```

### 1.2 GraphEdge（边）

```typescript
// src/types.ts
type GraphEdgeType =
  | "uses" | "imports" | "modifies" | "causes" | "fixes"
  | "depends_on" | "related_to" | "works_at" | "prefers"
  | "blocked_by" | "caused_by" | "optimizes_for" | "rejected"
  | "avoids" | "located_in" | "succeeded_by";  // 共 16 种

interface GraphEdge {
  id: string;                          // "ge_xxx"
  type: GraphEdgeType;                 // 关系类型
  sourceNodeId: string;                // 源节点 ID
  targetNodeId: string;                // 目标节点 ID
  weight: number;                      // 关系强度 (0-1)
  sourceObservationIds: string[];      // 来源 observation ID 列表
  createdAt: string;                   // 创建时间

  // 时间版本字段（temporal graph 支持）
  tcommit?: string;                    // 提交时间
  tvalid?: string;                     // 生效时间
  tvalidEnd?: string;                  // 失效时间

  // 边上下文
  context?: {
    reasoning?: string;                // LLM 推理过程
    sentiment?: string;                // 情感倾向
    alternatives?: string[];           // 备选方案
    situationalFactors?: string[];     // 情境因素
    confidence?: number;               // 置信度
  };

  version?: number;                    // 版本号
  supersededBy?: string;               // 被哪条边取代
  isLatest?: boolean;                  // 是否最新版本
  stale?: boolean;                     // 是否过期
}
```

### 1.3 节点与边的关系

```
┌─────────────────────┐         ┌─────────────────────────────┐
│     GraphNode       │         │         GraphEdge           │
├─────────────────────┤         ├─────────────────────────────┤
│ id: "gn_001"        │         │ id: "ge_001"                │
│ type: "concept"     │         │ type: "depends_on"          │
│ name: "JWT"         │──┐      │ sourceNodeId: "gn_001"      │
│ properties: {       │  │      │ targetNodeId: "gn_002"      │
│   desc: "..."       │  │      │ weight: 0.9                 │
│ }                   │  └─────→│ sourceObsIds: ["obs_1"]     │
│ sourceObsIds: [...] │         │ context: {                  │
│ stale: false        │         │   reasoning: "JWT 在..."    │
└─────────────────────┘         │ }                           │
                                │ tvalid: "2026-06-01"        │
                                │ isLatest: true              │
                                └─────────────────────────────┘
```

每个节点/边都指向它来源的 `observation`，形成**可溯源的知识网络**。

---

## 二、图构建链路

### 2.1 触发时机

图构建不是每次 observation 写入都触发，而是**批量触发**：

```
触发条件（任一满足）：
  ├── SessionEnd hook 触发
  ├── mem::consolidate 完成后
  ├── 定时任务（iii-cron）周期性调用
  └── 手动调用 mem::graph-extract

触发时传入：data.observations（CompressedObservation[]）
  含 title、narrative、concepts、files、type 等结构化字段
```

### 2.2 Step 1：LLM 提取（`mem::graph-extract`）

**代码路径：** `src/functions/graph.ts`（约 550 行）

```typescript
// 伪代码还原自源码
sdk.registerFunction("mem::graph-extract", async (data) => {
  // 1. 构建 prompt
  const prompt = buildGraphExtractionPrompt(
    data.observations.map(o => ({
      title: o.title,
      narrative: o.narrative,
      concepts: o.concepts,
      files: o.files,
      type: o.type,
    }))
  );

  // 2. 调用 LLM
  const response = await provider.compress(GRAPH_EXTRACTION_SYSTEM, prompt);

  // 3. 解析 XML → nodes + edges
  const { nodes, edges } = parseGraphXml(response, obsIds);
});
```

LLM 输出的 XML 格式：

```xml
<entity type="concept" name="JWT" desc="JSON Web Token 认证"/>
<entity type="file" name="AuthInterceptor.java" desc="认证拦截器"/>

<relationship type="related_to" source="JWT" target="AuthInterceptor"
              weight="0.8" reasoning="JWT 在 AuthInterceptor 中实现"/>
<relationship type="depends_on" source="AuthInterceptor" target="TokenUtil"
              weight="0.9" reasoning="AuthInterceptor 调用 TokenUtil 解析 token"/>
```

**XML 解析实现细节：**
- 使用 **regex 两遍扫描**（不是 DOM parser）
  - 第一遍：自闭合 `<entity ... />` 标签
  - 第二遍：有 body 的 `<entity>...</entity>` 标签
- 支持 `<relationship>` 标签的 `type`、`source`、`target`、`weight` 属性

### 2.3 Step 2：去重与合并

**关键设计：** agentmemory 的 KV 存储不支持二级索引，所以手写了两个辅助索引实现 O(1) 查重。

```typescript
// 伪代码还原自源码
// ── 节点去重 ──
for (const node of nodes) {
  const indexKey = `${node.type}|${node.name}`;
  const existingId = await kv.get(KV.graphNameIndex, indexKey);

  if (existingId) {
    // 已存在 → merge
    const existing = await kv.get(KV.graphNodes, existingId);
    const merged = mergeNode(existing, node, obsIds, now);
    // merge 逻辑：union sourceObservationIds + spread-merge properties
    await kv.set(KV.graphNodes, existing.id, merged);
  } else {
    // 新增 → 写入节点 + nameIndex
    await kv.set(KV.graphNodes, node.id, node);
    await kv.set(KV.graphNameIndex, indexKey, node.id);
  }
}

// ── 边去重 ──
for (const edge of edges) {
  const eKey = `${edge.sourceNodeId}|${edge.targetNodeId}|${edge.type}`;
  const existingEdgeId = await kv.get(KV.graphEdgeKey, eKey);

  if (existingEdgeId) {
    // merge（同上）
  } else {
    await kv.set(KV.graphEdges, edge.id, edge);
    await kv.set(KV.graphEdgeKey, eKey, edge.id);
  }
}
```

**换到 MySQL，这两个辅助索引就是唯一约束：**

```sql
UNIQUE KEY uk_type_name (type, name)                              -- name-index
UNIQUE KEY uk_edge (source_node_id, target_node_id, type)         -- edge-key
```

### 2.4 Step 3：度数追踪与 Snapshot 更新

每次边写入后，增量更新度数和快照：

```typescript
// 1. 更新度数计数器
const degree = await kv.get(KV.graphNodeDegree, nodeId) || 0;
await kv.set(KV.graphNodeDegree, nodeId, degree + 1);

// 2. 增量维护 Snapshot（top-500 节点）
applyDegreeDelta(nodeId, newDegree);
// → 如果 newDegree 进入 top-500，替换最低度数节点
// → 重新收集 top-500 节点之间的边
```

**Snapshot 结构：**

```typescript
interface GraphSnapshot {
  version: 1;
  topNodes: GraphNode[];     // 度数 top-500 的节点
  topEdges: GraphEdge[];     // 这些节点之间的边
  topDegrees: Record<string, number>;  // 度数排名
  stats: {
    totalNodes: number;
    totalEdges: number;
    nodesByType: Record<string, number>;
    edgesByType: Record<string, number>;
  };
  updatedAt: string;
  dirty: boolean;
  resetAt?: string;
}
```

**重建上限：** 25,000 节点 — 超过此数拒绝全量重建，只做增量 extract。

---

## 三、存储结构

### 3.1 KV Scopes 完整列表

```typescript
// src/state/schema.ts
const KV = {
  // ── 图核心存储 ──
  graphNodes:       "mem:graph:nodes",        // 所有节点（按 nodeId）
  graphEdges:       "mem:graph:edges",        // 所有边（按 edgeId）

  // ── 辅助索引（O(1) 查重）──
  graphNameIndex:   "mem:graph:name-index",   // type|name → nodeId
  graphEdgeKey:     "mem:graph:edge-key",     // srcId|tgtId|type → edgeId

  // ── 度数与快照 ──
  graphNodeDegree:  "mem:graph:node-degree",  // nodeId → degree
  graphSnapshot:    "mem:graph:snapshot",     // top-500 预计算快照

  // ── 时间版本 ──
  graphEdgeHistory: "mem:graph:edge-history", // 被取代的历史边
};
```

### 3.2 设计亮点

| 设计 | 说明 |
|------|------|
| **手写二级索引** | KV 不支持二级索引，用 `name-index` 和 `edge-key` 两个 scope 模拟唯一约束 |
| **增量 Snapshot** | 边写入时通过 `applyDegreeDelta` 增量维护 top-500，避免全量重建 |
| **6 秒查询预算** | `graph-query` 的实时遍历有 6 秒超时，超时自动降级到 Snapshot |
| **重建保护** | 超过 25,000 节点时拒绝全量重建，只做增量 |
| **时间版本边** | 边有 `tvalid/tvalidEnd` 字段，支持时间旅行查询，旧版本存入 `edge-history` |

---

## 四、图召回链路

图参与检索的入口是 `HybridSearch.tripleStreamSearch` 中的**第三流**。

### 4.1 在混合检索中的位置

```typescript
// src/state/hybrid-search.ts → tripleStreamSearch()

// 流 1：BM25 关键词（权重 0.4）
const bm25Results = this.bm25.search(query, limit * 2);

// 流 2：向量语义（权重 0.6）
const queryEmbedding = await this.embeddingProvider.embed(query);
const vectorResults = this.vector.search(queryEmbedding, limit * 2);

// 流 3：图检索（权重 0.3）
const entities = extractEntitiesFromQuery(query);
const graphResults = await this.graphRetrieval.searchByEntities(entities, 2, limit);

// 额外：向量 top-5 反向扩展图
const topVectorObs = vectorResults.slice(0, 5).map(r => r.obsId);
if (topVectorObs.length > 0) {
  const expansionResults = await this.graphRetrieval.expandFromChunks(
    topVectorObs, 1, 5
  );
  graphResults = [...graphResults, ...expansionResults];
}
```

### 4.2 图检索的两个入口

#### 入口 1：`searchByEntities` — 实体驱动检索

```typescript
// src/functions/graph-retrieval.ts → GraphRetrieval.searchByEntities()

async searchByEntities(entityNames, maxDepth = 2, maxResults = 20) {

  // Step 1：全量加载节点和边（过滤 stale）
  const allNodes = (await this.kv.list<GraphNode>(KV.graphNodes))
    .filter(n => !n.stale);
  const allEdges = (await this.kv.list<GraphEdge>(KV.graphEdges))
    .filter(e => !e.stale);

  // Step 2：实体名双向子串模糊匹配 → 找到种子节点
  const matchingNodes = allNodes.filter(n => {
    const nameLower = n.name.toLowerCase();
    return entityNames.some(e =>
      nameLower.includes(e.toLowerCase()) ||  // 节点名包含实体
      e.toLowerCase().includes(nameLower)      // 实体包含节点名
    );
  });

  if (matchingNodes.length === 0) return [];

  // Step 3：对每个种子节点做 Dijkstra 加权遍历（maxDepth=2）
  for (const startNode of matchingNodes) {
    const paths = this.dijkstraTraversal(startNode, allNodes, allEdges, maxDepth);

    for (const path of paths) {
      const lastNode = path[path.length - 1].node;

      // 收集路径终点节点的所有 observation IDs
      for (const obsId of lastNode.sourceObservationIds) {
        const pathLength = path.length;
        const avgWeight = path 中所有边的平均 weight;
        const score = avgWeight * (1 / pathLength);
        // 路径短 + 边权高 = 分数高

        results.push({ obsId, score, graphContext, pathLength });
      }
    }

    // 起始节点自身的 observation 直接得 1.0 分（fallback）
    for (const obsId of startNode.sourceObservationIds) {
      results.push({ obsId, score: 1.0, graphContext: null, pathLength: 0 });
    }
  }

  // Step 4：排序返回 top-K
  results.sort((a, b) => b.score - a.score);
  return results.slice(0, maxResults);
}
```

#### 入口 2：`expandFromChunks` — 向量结果反向扩展

```typescript
// 向量检索拿到 top-5 后，反向扩展图
// hybrid-search.ts
const topVectorObs = vectorResults.slice(0, 5).map(r => r.obsId);
const expansionResults = await this.graphRetrieval.expandFromChunks(
  topVectorObs, 1, 5
);

// expandFromChunks 实现
async expandFromChunks(obsIds, maxDepth = 1, maxResults = 10) {
  // 1. 找到引用了这些 observation 的图节点
  const linkedNodes = allNodes.filter(n =>
    n.sourceObservationIds.some(id => obsIds.includes(id))
  );

  // 2. 从这些节点出发 Dijkstra 探索
  for (const node of linkedNodes) {
    const paths = this.dijkstraTraversal(node, allNodes, allEdges, maxDepth);
    // 收集每条路径终点节点的 observation IDs
  }

  // 评分：score = 0.5 * (1 / (pathLength + 1))
  // 比 searchByEntities 评分低（因为是间接关联）
}
```

### 4.3 Dijkstra 遍历详解

```typescript
private dijkstraTraversal(startNode, allNodes, allEdges, maxDepth) {
  // cost = 1 / edge.weight
  // 权重越高的边，遍历代价越低

  // 1. 构建邻接表（O(V+E)，一次完成）
  const adjacency = new Map();
  for (const edge of allEdges) {
    adjacency.get(edge.sourceNodeId).push({ neighborId: edge.targetNodeId, edge });
    adjacency.get(edge.targetNodeId).push({ neighborId: edge.sourceNodeId, edge });
    // 注意：边是无向的，双向都加入邻接表
  }

  // 2. MinHeap 优先队列（替代早期的 O(n) queue.shift()，#328 优化）
  const heap = new MinHeap<{ node, cost, depth, path }>((a, b) => a.cost - b.cost);

  // 3. 标准 Dijkstra
  // → 按 cost 排序，depth < maxDepth 时继续扩展
  // → 返回：所有可达节点的路径（不包括起点自身）
}
```

**MinHeap 实现：** 内联二叉最小堆，用于 Dijkstra 的优先队列，替代早期的 O(n) `Array.shift()`。

### 4.4 第三入口：`temporalQuery` — 时间旅行查询

```typescript
// src/functions/graph-retrieval.ts
async temporalQuery(entityName, asOf?) {
  // 1. 找到实体对应的节点
  // 2. 过滤边：tvalid <= asOf && (tvalidEnd > asOf || !tvalidEnd)
  // 3. 按 source|target|type 分组，取最新版本
  // 4. 返回：当前状态 + 历史记录
}
```

这是 agentmemory 的独特能力 —— 支持查询"某个时间点的知识状态"，例如："2026 年 5 月时，JWT 和 AuthInterceptor 的关系是什么？"

---

## 五、RRF 融合与后处理

### 5.1 三路 RRF 融合

```typescript
// src/state/hybrid-search.ts
const RRF_K = 60;
const BM25_WEIGHT = 0.4;
const VECTOR_WEIGHT = 0.6;
const GRAPH_WEIGHT = 0.3;

// 融合公式
combinedScore = BM25_WEIGHT * 1/(RRF_K + bm25Rank)
              + VECTOR_WEIGHT * 1/(RRF_K + vectorRank)
              + GRAPH_WEIGHT * 1/(RRF_K + graphRank);
```

**权重归一化：** 当某路为空时（如没有 embedding provider 则向量路为空），其余权重自动归一化到 sum=1。

### 5.2 会话多样化

```typescript
// 同一个 session 最多保留 3 条结果，超出的被过滤
// 过滤后不足 limit 条时，从被过滤的结果中 backfill
```

### 5.3 Enrichment

```typescript
// RRF 融合后，从 KV 获取完整的 CompressedObservation
// 如果 observation 不存在，fallback 到 Memory → memoryToObservation()
```

### 5.4 可选 Rerank

```typescript
// RERANK_ENABLED 环境变量开启时
// 对 top-20 结果做 cross-encoder 精排
```

### 5.5 `searchWithExpansion` — 多轮搜索

```typescript
// 对原始查询 + 改写 + 时间具体化做多轮搜索
// 每轮调用 tripleStreamSearch
// 最终按 max combinedScore 合并去重
```

---

## 六、完整召回链路图

```
查询: "JWT token 过期处理流程"
    │
    ├──────────────────────────────────────────────────────────────┐
    │                                                              │
    │              ┌──────────────────────────┐                    │
    │              │      实体提取             │                    │
    │              │  → ["JWT", "token"]       │                    │
    │              └────────────┬─────────────┘                    │
    │                           │                                  │
    ▼                           ▼                                  ▼
┌──────────────┐      ┌──────────────────┐              ┌──────────────────┐
│  BM25        │      │  图检索           │              │  Vector          │
│  w=0.4       │      │  w=0.3           │              │  w=0.6           │
│              │      │                  │              │                  │
│  title^3     │      │  1. 双向子串匹配  │              │  embed(query)    │
│  narrative^2 │      │     → 种子节点    │              │  → cosine sim    │
│  concepts    │      │  2. Dijkstra 2hop│              │  → top-K         │
│              │      │  3. 收集 obsIds  │              │                  │
│              │      │  4. 起始节点=1.0  │              │                  │
└──────┬───────┘      └────────┬─────────┘              └────────┬─────────┘
       │                       │                                 │
       │                       │                    ┌────────────┴──────────┐
       │                       │                    │  expandFromChunks     │
       │                       │                    │  top-5 向量结果       │
       │                       │                    │  → 反向找关联节点     │
       │                       │                    │  → Dijkstra 1hop     │
       │                       │                    │  → score=0.5/(len+1) │
       │                       │                    └────────────┬──────────┘
       │                       │                                 │
       ▼                       ▼                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          RRF 融合 (k=60)                                │
│  combinedScore = 0.4/(60+r_bm25) + 0.6/(60+r_vec) + 0.3/(60+r_graph)  │
│  权重归一化：某路为空时，其余权重 scale to sum=1                          │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    会话多样化 + Enrichment                               │
│  同 session 最多 3 条，不足 backfill                                     │
│  获取完整 CompressedObservation（fallback → Memory）                      │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    可选 Rerank (RERANK_ENABLED)                          │
│  Cross-encoder 精排 top-20                                               │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   ▼
                               Top-K 返回
```

---

## 七、与 Mem0、Hermes 的图能力对比

| 维度 | agentmemory | Mem0 | Hermes 内置 |
|------|-------------|------|-------------|
| **图存储** | KV 手写索引（SQLite） | Neo4j（独立数据库） | 无图 |
| **图构建** | LLM 提取 + 批量触发 | LLM 实时提取 | — |
| **节点类型** | 13 种 | entity/relation | — |
| **边类型** | 16 种 | 自定义 | — |
| **去重** | O(1) 辅助索引 | Neo4j MERGE | — |
| **检索方式** | Dijkstra 加权遍历 | Cypher 查询 | — |
| **时间版本** | ✅ tvalid/tvalidEnd | ❌ | — |
| **Snapshot** | ✅ top-500 预计算 | ❌ | — |
| **外部依赖** | 无（内嵌） | Neo4j（必须） | — |
| **查询超时降级** | ✅ 6s → Snapshot | 无 | — |

---

## 八、设计启示

### 8.1 KV 模拟二级索引的模式

agentmemory 在不支持二级索引的 KV 存储上，用两个辅助 scope 实现了 O(1) 查重。这个模式可以迁移到任何 KV 系统（Redis、DynamoDB、etcd）：

```
主存储:  graphNodes[nodeId] → node
索引 1:  graphNameIndex[type|name] → nodeId     // O(1) 节点去重
索引 2:  graphEdgeKey[src|tgt|type] → edgeId    // O(1) 边去重
```

### 8.2 增量 Snapshot 避免全量重建

图的 Snapshot 不是每次查询时重建，而是在边写入时通过 `applyDegreeDelta` 增量维护。查询时直接读 Snapshot，复杂度 O(1)。

### 8.3 超时降级策略

实时遍历有 6 秒预算，超时自动降级到预计算的 Snapshot。这保证了查询延迟的上界，适合生产环境。

### 8.4 时间版本边的启示

边有 `tvalid/tvalidEnd` 字段，旧版本存入 `edge-history`。这使得知识图谱支持"时间旅行"——查询任意历史时刻的知识状态。对于需要审计追踪的场景（如代码架构演进、决策变更历史）非常有价值。

---

## 九、总结

agentmemory 的知识图谱是一个**轻量但完整**的图系统：

| 特性 | 评价 |
|------|------|
| **构建** | LLM 提取 + 批量触发，质量依赖 LLM 能力 |
| **存储** | KV + 手写索引，零外部依赖 |
| **检索** | Dijkstra 加权遍历 + RRF 三路融合 |
| **扩展** | 时间版本、Snapshot、超时降级 |
| **定位** | 三路检索中的一路，不是独立图数据库 |

它不是 Neo4j 那样的通用图数据库，而是一个**为 Agent 记忆场景定制的轻量图层**。核心价值在于：用最少的外部依赖，实现了实体关系的结构化存储和加权检索，并通过 RRF 融合与 BM25、向量检索互补。

---

*报告生成时间：2026-06-08 | 基于 agentmemory main 分支源码分析*
