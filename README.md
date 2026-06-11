# hello-wrold

AI Agent 技术调研与架构分析报告集。

## 📋 报告索引

| 日期 | 报告 | 主题 |
|------|------|------|
| 2026-06-11 | [Hindsight 记忆系统深度分析：仿生四网络架构、TEMPR 时序实体图与 LongMemEval SOTA 源码解析](reports/hindsight-memory-analysis.md) | 仿生四网络(World/Experiences/Mental Models/Opinion Network)、TEMPR 时序实体图谱、5W 结构化事实提取、4路并行检索(Semantic+BM25+Graph+Temporal)+RRF+Cross-Encoder、Consolidation 自动整合、Reflect Agentic 反思、PostgreSQL 全栈存储 |
| 2026-06-11 | [OpenAI Codex CLI 记忆系统深度分析：离线批处理管线、Git 记忆管理与 1430 行 Prompt 工程源码解析](reports/codex-memory-analysis.md) | JSONL+SQLite+Markdown 三层存储、Phase 1 并发 8 路提取(570行prompt)、Phase 2 Sub-Agent 整合(880行prompt)、ContextContributor 注入、Git diff 驱动增量更新、与 MemPalace/Mastra 三方对比 |
| 2026-06-11 | [Mastra Observational Memory 深度分析：三 Agent 架构、异步缓冲与 LongMemEval 94.87% 源码解析](reports/mastra-memory-analysis.md) | Observer/Reflector 双 Agent 提示词工程、断言vs问题区分、时间锚定、5-40x压缩比、异步缓冲零延迟激活、与 MemPalace 对比 |
| 2026-06-11 | [MemPalace 深度技术分析：宫殿架构、写入管道与召回机制源码全解析](reports/mempalace-deep-analysis-report.md) | 50个真实源码片段逐行解析——Wing/Room/Drawer/Closet分层架构、对话分块与批量写入、BM25+向量混合排序、排名基Closet Boost、Drawer-Grep增强、知识图谱时间查询、四层记忆堆栈(L0-L3) |
| 2026-06-10 | [10分钟了解Claude Code记忆系统：源码拆解AI的"长期记忆"是怎么实现的](reports/claude-code-memory-system-report.md) | 基于源码逆向分析——四层固定类型（user/feedback/project/reference）、双路径写入互斥、Sonnet 侧查询召回、漂移验证机制全解析，含6张配图 |
| 2026-06-09 | [LongMemEval 技术报告：评测、架构与自定义记忆系统接入指南](reports/longmemeval-technical-report.md) | ICLR 2025 长期记忆基准深度解析——5大能力×7种题型、属性控制数据构建、统一三阶段框架、LLM-as-Judge 评测、自定义系统接入方法 |
| 2026-06-08 | [agentmemory 知识图谱：构建与召回全流程深度解析](reports/agentmemory-graph-pipeline-report.md) | 基于源码的图构建链路、Dijkstra 加权检索、RRF 三路融合、时间版本边、Snapshot 机制全解析 |
| 2026-06-05 | [Supermemory：Agent 记忆实现方案深度调研](reports/supermemory-agent-memory-report.md) | containerTags 多容器隔离机制、Memory+RAG 混合检索、自动遗忘、定价与生态集成分析 |
| 2026-06-04 | [Mem0 源码深度解析：AI Agent 记忆层架构](reports/mem0-source-code-analysis-report.md) | Mem0 核心源码分析——V3 记忆提取管线、三路混合检索、实体增强、评分融合，揭示"多层记忆"概念与单库实现的真相 |
| 2026-06-03 | [Hermes Holographic vs OpenClaw QMD 记忆机制对比](reports/hermes-vs-openclaw-memory-report.md) | Hermes HRR 符号代数 vs OpenClaw Embedding 语义搜索——两种 Agent 记忆范式的深度对比 |
| 2026-06-02 | [Java HashMap 哈希碰撞与扰动函数深度解析](reports/java-hashmap-collision-disturbance-report.md) | HashMap 碰撞的数学本质、自然溢出机制、扰动函数设计原理及 JDK 架构演进 |
| 2026-06-01 | [Hermes Agent 四层记忆架构技术报告](reports/hermes-memory-architecture-report.md) | Hermes Agent 记忆系统分层架构详解，含 8 种外部提供者对比 |
| 2026-05-30 | [oh-my-pi 记忆系统深度调研报告](reports/omp-memory-system-report.md) | OMP (oh-my-pi) 的 mnemopi 记忆引擎架构分析 |

## 📁 目录结构

```
hello-wrold/
├── README.md
└── reports/
    ├── assets/
    │   ├── hindsight/
    │   │   ├── hindsight-overview.png
    │   │   ├── hindsight-learning-pipeline.png
    │   │   ├── hindsight-memory-model.png
    │   │   ├── hindsight-retrieval.png
    │   │   ├── hindsight-benchmarks.png
    │   │   └── hindsight-comparison.png
    │   ├── codex/
    │   │   ├── codex-memory-overview.png
    │   │   ├── codex-memory-config.png
    │   │   ├── codex-phase1-extraction.png
    │   │   ├── codex-phase2-consolidation.png
    │   │   ├── codex-memory-injection.png
    │   │   └── codex-three-way-comparison.png
    │   ├── openclaw_qmd_arch.png
    │   ├── hermes_holographic_arch.png
    │   ├── hermes-memory-architecture.png
    │   ├── hermes-data-flow.png
    │   ├── omp-memory-layers.png
    │   ├── longmemeval-capability-taxonomy.png
    │   └── longmemeval-unified-memory-framework.png
    ├── images/
    │   ├── cover.png                  # 封面（GPT Image 2 生成）
    │   ├── four-layer-model.svg/.png  # 四层记忆模型
    │   ├── dual-path-write.svg/.png   # 双路径写入机制
    │   ├── recall-mechanism.svg/.png  # 二阶段召回机制
    │   ├── boundary-comparison.svg/.png # 持久化机制边界对比
    │   └── architecture-overview.svg/.png # 架构总览
    ├── codex-memory-analysis.md
    ├── mastra-memory-analysis.md
    ├── mempalace-deep-analysis-report.md
    ├── claude-code-memory-system-report.md
    ├── longmemeval-technical-report.md
    ├── mem0-source-code-analysis-report.md
    ├── supermemory-agent-memory-report.md
    ├── hermes-vs-openclaw-memory-report.md
    ├── hermes-memory-architecture-report.md
    ├── agentmemory-graph-pipeline-report.md
    ├── omp-memory-system-report.md
    └── java-hashmap-collision-disturbance-report.md
```

## 🔧 维护说明

- 由 Hermes Agent 自动生成并推送
- 新报告统一放入 `reports/` 目录
- 报告命名格式：`<主题>-report.md`
- 封面图由 GPT Image 2 生成，技术示意图由 SVG 代码生成
- 配图存放于 `reports/images/`，源文件（SVG）和渲染图（PNG）同时保留
