# hello-wrold

AI Agent 技术调研与架构分析报告集。

## 📋 报告索引

| 日期 | 报告 | 主题 |
|------|------|------|
| 2026-06-30 | [CORAL Protocol 深度技术调研：Internet of Agents](reports/coral-protocol-report.md) | CoralOS/Kubernetes for agents、A2A MCP 多智能体通信、Anemoi GAIA 63.64%、coral-agent.toml 标准化、竞品对比、工程成熟度批判分析 |
| 2026-06-30 | [HGM 论文+源码联合分析：CMP 搜索与代码实现](reports/hgm-code-analysis-report.md) | ICLR 2026 Oral、2668行源码逐模块解读、CMP+Thompson采样+UCB-Air 核心算法、Docker沙箱自改进管道、8个代码实战细节、与RQGM对比 |
| 2026-06-30 | [omp (oh-my-pi) Agent Loop 深度源码分析](reports/omp-agent-loop-report.md) | 双层 while 循环架构、streamAssistantResponse 12 步 LLM 调用管线、TTSR 流规则匹配、8 种子代理隔离后端、Advisor 第二模型审查、Harmony Leak 防御、与 Hermes 对比 + 可操作建议 |
| 2026-06-30 | [oh-my-pi (omp) 项目调研报告](reports/oh-my-pi-research-2026-06-30.md) | 15K+ 星终端编码 agent、42 供应商/32 工具/55K Rust 核心、20 大特性、与 Claude Code/Codex CLI 对比 |
| 2026-06-30 | [pi 引擎深度分析：OpenClaw 的 AI Agent 运行时](reports/pi-engine-deep-analysis.md) | pi 引擎四层架构、API Registry 机制、双层 Agent Loop + 双队列中断、Context Compaction 自动压缩、240+ 模型目录、批判性分析 |
| 2026-06-30 | [Red Queen Gödel Machine 技术调研：智能体与评估器共进化框架](reports/rqgm-technical-report.md) | 受控效用演化、评估器与任务智能体共进化、三领域 SOTA 超越（编码/论文/IMO）、对抗性评审去偏、1.35-1.86× 提升、批判性分析 |
| 2026-06-26 | [DeerFlow 2.0 深度技术分析：Agent Loop 与 Agentic 工作流](reports/deerflow-deep-analysis.md) | LangGraph ReAct 循环、26 层中间件洋葱模型、task() 子代理委托、流式处理、与 Hermes Agent 对比、批判性分析 |
| 2026-06-25 | [Headroom 压缩器实践与探索报告](reports/headroom-compressor-practice.md) | 实测验证三个压缩器真实效果、发现 2 个 Bug（Tier-2 0%、非 ASCII 压坏）、SmartCrusher 68~88%、CodeCompressor ~55%、方法论结论 |
| 2026-06-24 | [Agent Loop 源码实现深度对比：Hermes vs Claude Code](reports/agent-loop-implementation-report.md) | 4300行Python工业级引擎 vs 编译TypeScript轻量助手、5层错误恢复、上下文压缩、工具并行策略、批判性分析 |
| 2026-06-24 | [ReAct 架构深度调研：从论文到工程实践](reports/react-agent-architecture-report.md) | ReAct 核心机制、演进历程、Hermes/Codex/Claude Code 三大实现源码对比、批判性分析 |
| 2026-06-23 | [agentmemory BM25 检索：从分词到融合的全流程深度解析](reports/agentmemory-bm25-report.md) | BM25 评分算法、前缀匹配、同义词扩展、CJK 分词、索引分片持久化、RRF 三路融合全解析 |
| 2026-06-22 | [Java RPC 技术调研报告](reports/java-rpc-technology-report.md) | RPC 核心原理、Socket/RMI 原生实现、手写简易框架、Dubbo/gRPC/Thrift 生产级框架对比、选型建议 |
| 2026-06-18 | [OpenCode vs Codex CLI 上下文压缩机制深度对比](reports/context-compression-report.md) | LLM 驱动语义压缩、结构化摘要模板 vs Memento 三层防御、增量更新、64K 保留窗口、自动继续、远程压缩加密令牌 |
| 2026-06-18 | [Agent Loop 与 AI Agent 调研报告](reports/agent-loop-research.md) | Agent Loop 核心机制、ReAct/Reflexion/Plan-and-Execute 设计模式、三大核心组件、Agentic 自治光谱、Anthropic/OpenAI/LangChain 框架对比、2025-2026 趋势批判性分析 |
| 2026-06-18 | [Headroom：AI Agent 上下文压缩机制深度分析](reports/headroom-deep-analysis.md) | 6 种专业压缩器架构、Kompress ML 双头模型、ContentRouter 智能路由、CCR 可逆压缩、60-95% Token 节省率分析 |
| 2026-06-17 | [FastAPI vs Spring Boot vs Golang 框架对比分析报告](reports/fastapi-spring-golang-comparison-report.md) | 性能基准、开发效率、生态系统、适用场景多维度对比，含真实案例和批判性分析 |
| 2026-06-17 | [WebSocket 技术调研：协议原理、各语言实现与 SSE 对比](reports/websocket-technology-report.md) | RFC 6455 帧格式、握手流程、6 语言主流实现对比、WebSocket vs SSE 全方位对比、决策树、安全与性能分析 |
| 2026-06-16 | [claude-mem 源码深度分析：记忆写入与召回机制](reports/claude-mem-report.md) | AI 压缩+渐进式披露、7 阶段写入管道、3 条召回通路、SQLite+ChromaDB 双存储、PostHog 遥测审计 |
| 2026-06-12 | [2026年大模型预训练与后训练技术研究报告](reports/llm-training-2026-report.md) | DeepSeek V4 Engram 架构、General-Reasoner 全域 RL 推理、合成数据 Scaling Laws、GRPO 变体、推理时间计算、2026 六大趋势 |
| 2026-06-12 | [Zep/Graphiti：LLM 构建时间知识图谱技术深度调研](reports/graphiti-temporal-knowledge-graph-report.md) | 双时态事实模型、三层子图架构(Episode/Entity/Community)、增量式图构建、混合三路检索(Cosine+BM25+BFS)+5种重排策略、DMR 94.8%/LongMemEval +18.5% benchmark、与 GraphRAG/MemGPT 对比 |
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
    │   ├── agent-loop/
    │   │   ├── agent-loop-cycle.png
    │   │   ├── react-pattern.png
    │   │   ├── agentic-spectrum.png
    │   │   ├── framework-comparison.png
    │   │   └── three-components.png
    │   ├── agent-loop-impl/
    │   │   ├── diagram-1-agent-loop-cycle.png
    │   │   ├── diagram-2-hermes-architecture.png
    │   │   ├── diagram-3-comparison.png
    │   │   └── diagram-4-tool-execution.png
    │   ├── agentmemory-bm25/
    │   │   ├── bm25-architecture.png
    │   │   ├── bm25-tokenize.png
    │   │   ├── bm25-data-structures.png
    │   │   ├── bm25-query-flow.png
    │   │   ├── bm25-index-persistence.png
    │   │   └── bm25-rrf-fusion.png
    │   ├── headroom/
    │   │   ├── headroom-pipeline.png
    │   │   ├── headroom-kompress-model.png
    │   │   ├── headroom-router-decision.png
    │   │   └── headroom-performance.png
    │   ├── headroom-practice/
    │   │   ├── pipeline.png
    │   │   ├── smartcrusher-flow.png
    │   │   ├── bug-impact.png
    │   │   └── comparison.png
    │   ├── llm-training-2026/
    │   │   ├── timeline.png
    │   │   ├── pretraining-evolution.png
    │   │   ├── posttraining-evolution.png
    │   │   ├── test-time-compute.png
    │   │   └── trends-overview.png
    │   ├── locomo/
    │   │   ├── locomo-pipeline.png
    │   │   ├── locomo-qa-categories.png
    │   │   ├── locomo-eval-tasks.png
    │   │   ├── locomo-long-context-results.png
    │   │   ├── locomo-rag-results.png
    │   │   └── locomo-research-2026.png
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
    │   ├── graphiti/
    │   │   ├── graphiti-architecture.png
    │   │   └── graphiti-benchmark.png
    │   ├── websocket/
    │   │   ├── diagram-1.png
    │   │   ├── diagram-2.png
    │   │   ├── diagram-3.png
    │   │   ├── diagram-4.png
    │   │   ├── diagram-5.png
    │   │   └── diagram-6.png
    │   ├── claude-mem/
    │   │   ├── arch-overview.png
    │   │   ├── write-pipeline.png
    │   │   ├── recall-paths.png
    │   │   ├── progressive-disclosure.png
    │   │   └── dual-storage.png
    │   ├── context-compression/
    │   │   ├── opencode-flow.png
    │   │   ├── codex-flow.png
    │   │   ├── compare-grid.png
    │   │   └── summary-cards.png
    │   ├── rpc/
    │   │   ├── rpc-architecture.png
    │   │   ├── rpc-java-layers.png
    │   │   ├── rpc-frameworks.png
    │   │   └── rpc-rmi-vs-custom.png
    │   ├── rqgm/
    │   │   ├── arch.png
    │   │   ├── epoch.png
    │   │   ├── results.png
    │   │   ├── mechanism.png
    │   │   ├── paradigm.png
    │   │   ├── tradeoff.png
    │   │   └── summary.png
    │   ├── deerflow/
    │   │   ├── arch.png
    │   │   ├── loop.png
    │   │   ├── middleware.png
    │   │   ├── subagent.png
    │   │   ├── dataflow.png
    │   │   └── compare.png
    │   ├── hgm/
    │   │   ├── arch.png
    │   │   ├── loop.png
    │   │   ├── cmp.png
    │   │   ├── selfimprove.png
    │   │   └── dataflow.png
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
    ├── pi-engine/
    │   ├── architecture.png
    │   ├── api-registry.png
    │   ├── eventstream.png
    │   ├── agent-loop.png
    │   ├── tool-exec.png
    │   └── compaction.png
    ├── pi-engine-deep-analysis.md
    ├── react-agent-architecture-report.md
    ├── rqgm-technical-report.md
    ├── hgm-code-analysis-report.md
    ├── coral-protocol-report.md
    ├── agent-loop-implementation-report.md
    ├── agent-loop-research.md
    ├── java-rpc-technology-report.md
    ├── headroom-deep-analysis.md
    ├── headroom-compressor-practice.md
    ├── fastapi-spring-golang-comparison-report.md
    ├── websocket-technology-report.md
    ├── graphiti-temporal-knowledge-graph-report.md
    ├── llm-training-2026-report.md
    ├── claude-mem-report.md
    ├── codex-memory-analysis.md
    ├── mastra-memory-analysis.md
    ├── locomo-技术调研报告.md
    ├── mempalace-deep-analysis-report.md
    ├── claude-code-memory-system-report.md
    ├── longmemeval-technical-report.md
    ├── mem0-source-code-analysis-report.md
    ├── supermemory-agent-memory-report.md
    ├── hermes-vs-openclaw-memory-report.md
    ├── hermes-memory-architecture-report.md
    ├── agentmemory-graph-pipeline-report.md
    ├── agentmemory-bm25-report.md
    ├── omp-agent-loop-report.md
    ├── oh-my-pi-research-2026-06-30.md
    ├── omp-memory-system-report.md
    ├── java-hashmap-collision-disturbance-report.md
    ├── context-compression-report.md
    └── deerflow-deep-analysis.md
```

## 🔧 维护说明

- 由 Hermes Agent 自动生成并推送
- 新报告统一放入 `reports/` 目录
- 报告命名格式：`<主题>-report.md`
- 封面图由 GPT Image 2 生成，技术示意图由 SVG 代码生成
- 配图存放于 `reports/images/`，源文件（SVG）和渲染图（PNG）同时保留
