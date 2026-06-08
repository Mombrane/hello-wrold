# hello-wrold

AI Agent 技术调研与架构分析报告集。

## 📋 报告索引

| 日期 | 报告 | 主题 |
|------|------|------|
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
    │   ├── openclaw_qmd_arch.png
    │   ├── hermes_holographic_arch.png
    │   ├── hermes-memory-architecture.png
    │   ├── hermes-data-flow.png
    │   └── omp-memory-layers.png
    ├── mem0-source-code-analysis-report.md
    ├── supermemory-agent-memory-report.md
    ├── hermes-vs-openclaw-memory-report.md
    ├── hermes-memory-architecture-report.md
    ├── agentmemory-graph-pipeline-report.md
    └── omp-memory-system-report.md
```

## 🔧 维护说明

- 由 Hermes Agent 自动生成并推送
- 新报告统一放入 `reports/` 目录
- 报告命名格式：`<主题>-report.md`
- 图表由 AI 生成，存放于 `reports/assets/` 目录
