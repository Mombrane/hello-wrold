# DeepSeek DSA / CSA / HCA 技术调研报告

> 调研日期：2026-07-09  
> 来源：DeepSeek-V3.2 (arXiv:2512.02556)、DeepSeek-V4 (arXiv:2606.19348)、FlashMemory-DeepSeek-V4 (arXiv:2606.09079)

---

## 1. 概述：三者关系

DSA、CSA、HCA 是 DeepSeek 在长上下文注意力机制上的三个关键技术，**CSA 和 HCA 是 V4 中并行使用的两种注意力架构，而非替代关系**。DSA 源自 V3.2，在 V4 中被 CSA 复用为其稀疏选择组件。

```
V3.2 (2025.12)           V4 (2026.04)
    │                        │
    ├─ DSA ──────────────────┤─→ CSA 复用 DSA 做稀疏选择
    │  (DeepSeek Sparse     │   (压缩 + DSA)
    │   Attention)          │
    │                       └─→ HCA（并行独立设计）
    │                           (更激进压缩 + 稠密注意力)
```

| 缩写 | 全称 | 来源 | 核心思路 | 稀疏性 |
|------|------|------|----------|--------|
| **DSA** | DeepSeek Sparse Attention | V3.2 (2025.12) | 对 KV 做稀疏选择，只关注 top-k 个条目 | ✅ 稀疏 |
| **CSA** | Compressed Sparse Attention | V4 (2026.04) | 先压缩 KV → 再复用 DSA 做稀疏选择 | ✅ 稀疏 |
| **HCA** | Heavily Compressed Attention | V4 (2026.04) | 极度压缩 KV → 保持稠密注意力 | ❌ 稠密 |

**一句话总结**：DSA 是"稀疏注意力"的基石技术（V3.2 引入）；CSA = 压缩 + 复用 DSA（先压缩再稀疏）；HCA = 更狠的压缩 + 稠密注意力（独立于 DSA，用极致压缩换效率）。CSA 和 HCA 同时引入 V4，在 Transformer 层中交替部署。

---

## 2. DSA：DeepSeek Sparse Attention（V3.2）

### 2.1 背景与动机

DeepSeek-V3.2（2025 年 12 月发布）引入 DSA 作为其核心技术突破之一。传统 Transformer 的自注意力复杂度为 O(n²)，在长上下文场景下成为计算瓶颈。DSA 的目标是**大幅降低计算复杂度，同时保持模型在长上下文任务上的性能**。

### 2.2 核心机制

DSA 的核心思想是：**每个 query token 只关注 top-k 个最相关的 KV 条目，而非全部**。与标准全量注意力不同，DSA 通过一个外部索引机制预先选择每个 query 要关注的 KV 子集（`indices` 张量），内核只对选中的 KV 条目执行稀疏矩阵乘法。这种"索引-执行"分离的设计使得注意力计算复杂度从 O(n²) 降为 O(n·k)。

在 V4 中，CSA 复用 DSA 的稀疏选择机制，并额外增加了共享 KV MQA（Multi-Query Attention）来进一步减少 KV 参数量。

### 2.3 性能表现

DSA 使得 V3.2 在长上下文场景下大幅降低推理延迟和计算量，同时保持甚至超越全注意力模型的性能。DSA 是 V3.2 能在 IMO 和 IOI 竞赛中斩获金牌的关键技术之一。

---

## 3. CSA：Compressed Sparse Attention（V4）

### 3.1 设计动机

DeepSeek-V4 面临百万 token 上下文的挑战。单纯依赖 DSA 的稀疏选择在极端长度下仍不够高效，因为 KV 条目数本身随序列长度线性增长。CSA 的解决方案是：**先压缩，再稀疏选择**。

### 3.2 核心架构（两步走）

**第一步：KV 压缩**
- 将每 m 个 token 的 KV cache 压缩为 1 个条目
- 使用学习到的压缩权重和位置偏置进行加权聚合
- 压缩后的序列长度降为原来的 1/m
- V4-Pro 中 m=4（每 4 个 token 压缩为 1 个）

**第二步：DSA 稀疏选择**
- 在压缩后的 KV 条目上运行 Lightning Indexer
- 通过索引器 QK 计算 query 与每个压缩块的相关性分数
- top-k 选择，仅保留最相关的 k 个压缩条目
- 使用共享 KV MQA 执行核心注意力计算

**额外设计：滑动窗口**
- 为保留局部细粒度依赖，CSA 额外增加一个滑动窗口注意力分支
- 最近 n_win 个 token 的原始 KV 不参与压缩，直接参与注意力
- 解决了"query 无法看到同压缩块内其他 token"的问题

### 3.3 关键技术细节

| 组件 | 说明 |
|------|------|
| 压缩率 | m = 4（Pro），即序列长度压缩至 1/4 |
| 索引器 | Lightning Indexer，FP4 精度计算 |
| KV 格式 | MQA（共享 KV），RoPE 维度用 BF16，其余 FP8 |
| 输出投影 | Grouped Output Projection：先分头投影到中间维度再拼接 |
| 滑动窗口 | n_win 个原始 KV，增强局部建模 |

---

## 4. HCA：Heavily Compressed Attention（V4）

### 4.1 与 CSA 的关键区别

HCA 的设计哲学是"用更狠的压缩换效率，但保留稠密注意力以保证全局建模能力"。

| 维度 | CSA | HCA |
|------|-----|-----|
| 压缩率 | m（较小，如 4） | m'（远大于 m） |
| 注意力类型 | 稀疏（DSA, top-k） | 稠密（所有压缩条目） |
| 计算量 | 更少（稀疏） | 更多（稠密） |
| 全局视野 | 部分（仅 top-k 块） | 完整（所有压缩块） |
| 适用层 | 大部分中间层 | 前几层 + 部分中间层 |

### 4.2 核心架构

- **压缩策略**：与 CSA 类似，但压缩比 m' >> m，即更少的压缩条目覆盖更多原始 token
- **稠密注意力**：不进行 DSA 稀疏选择，query 关注所有压缩后的 KV 条目
- **Shared KV MQA**：与 CSA 相同，共享 KV 减少参数量
- **滑动窗口**：同样配备滑动窗口分支保留局部信息

### 4.3 设计直觉

HCA 之所以不使用稀疏注意力，是因为它认为在极度压缩的情况下，剩下的 KV 条目数量已经足够少，稠密注意力的额外计算开销可接受；同时稠密注意力保留了完整的全局视野，对模型理解整体上下文更有利。

---

## 5. V4 的混合架构：CSA + HCA 交替部署

DeepSeek-V4 并非只用 CSA 或 HCA，而是采用**混合交替部署**（interleaved hybrid configuration）。两个模型规格的架构配置有所不同：

| 配置项 | V4-Pro | V4-Flash |
|--------|--------|----------|
| Transformer 层数 | 61 | 43 |
| 前 2 层 | HCA | 纯滑动窗口注意力 |
| 后续层 | CSA + HCA 交替 | CSA + HCA 交替 |
| CSA 压缩率 m | 4 | 4 |
| HCA 压缩率 m' | 128 | 128 |
| CSA top-k | 1024 | 512 |
| 滑动窗口 n_win | 128 | 128 |
| Query heads | 128 | 64 |
| Query compression dim | 1536 | 1024 |
| Output projection groups | 16 | 8 |

**V4-Pro（61 层）设计直觉**：前 2 层用 HCA 建立全局上下文理解基础；后续 59 层中 CSA（压缩+稀疏）负责高效处理、HCA（极度压缩+稠密）定期补充全局信息。

**V4-Flash（43 层）设计差异**：前 2 层使用纯滑动窗口注意力（非 HCA），后续层同样 CSA+HCA 交替。这体现了 Flash 作为轻量版在浅层做了不同的取舍。

---

## 6. 效率收益（关键数据）

### 6.1 vs DeepSeek-V3.2（百万 token 上下文，以等效 FP8 FLOPs 计）

| 指标 | V4-Pro | V4-Flash |
|------|--------|----------|
| 单 token 推理 FLOPs | **27%**（vs V3.2） | **10%**（vs V3.2） |
| KV Cache 大小 | **10%**（vs V3.2） | **7%**（vs V3.2） |

> 注：FLOPs 以等效 FP8 精度计量。V4 的 MoE 专家参数使用 FP4 精度，在现有硬件上 FP4×FP8 的峰值 FLOPs 与 FP8×FP8 相同，但未来硬件上可再提效约 1/3。

### 6.2 vs GQA8 基线（标准 LLM 注意力配置）

在 1M token 上下文中，V4 的 KV cache 仅为 GQA8 基线的约 **2%**。

### 6.3 模型规格

| | V4-Pro | V4-Flash |
|------|--------|----------|
| 总参数量 | 1.6T | 284B |
| 激活参数量 | 49B | 13B |
| 训练数据 | 33T tokens | 32T tokens |
| 上下文窗口 | 1M tokens | 1M tokens |

---

## 补充：开源代码对照

### 代码现状

V4 论文提到"we also provide an open-source implementation"，但实际开源情况如下：

| 代码仓库 | 包含内容 | 缺失内容 |
|----------|---------|---------|
| [FlashMLA](https://github.com/deepseek-ai/FlashMLA) | DSA 稀疏注意力 CUDA 内核（`indices` 驱动的 top-k 选择），支持 V3.2 格式 | Lightning Indexer（`indices` 生成）、CSA/HCA 压缩逻辑 |
| [DeepSeek-V3](https://github.com/deepseek-ai/DeepSeek-V3) | MLA 注意力（k_lora_rank 低秩压缩） | DSA/CSA/HCA 全部缺失 |
| HF 模型权重 | `config.json` 包含完整架构参数 | 仅为推理配置，非可编译源码 |

### 关键代码发现

**1. DSA 的"索引-执行"分离设计**

FlashMLA 的稀疏注意力内核（`sparse_decode.h`）接收一个预计算的 `indices` 张量 `[b, s_q, topk]`，内核本身不解码、不学习、不预测——它只是一个稀疏矩阵乘法执行器。Lightning Indexer（生成 `indices` 的逻辑）在 FlashMLA 外部，可能在模型推理框架或权重中。

**2. Extra KV Cache（双缓存模式）**

FlashMLA 支持 `extra_kv` + `extra_indices` 机制，用于 MODEL1 架构（非 V3.2）。主 KV cache 用小 topk（如 128），extra KV cache 用大 topk（512-1024），概念上类似于 CSA/HCA 中的"滑动窗口 + 全局稀疏"模式，但实现方式是维护两套独立 KV cache 而非压缩。

**3. V3.2 KV Cache 格式**

每个 token 656 bytes：512B 量化 NoPE 部分（FP8）+ 16B scale factors（4×float32）+ 128B RoPE 部分（64×BF16）。内核强制 `h_kv == 1`（MQA 模式），确认 DSA 使用共享 KV。

---

## 7. 延伸：FlashMemory-DS-V4 的 LSA

FlashMemory 是一个外部团队基于 V4 架构构建的扩展项目（非 DeepSeek 官方），提出了 **LSA（Lookahead Sparse Attention）**：

- **Neural Memory Indexer**：不被动关注所有历史 token，而是主动预测未来上下文需求
- **效果**：在 500K token 尺度下，KV cache 超过 90% 的压缩率
- **平均**：物理 KV cache 仅为全量基线的 13.5%
- **性能**：在 LongBench-v2、LongMemEval、RULER 等基准上，精度不降反升（+0.6%）

---

## 8. 批判性分析

### 8.1 优点

1. **实用导向**：CSA/HCA 不是学术炫技，而是直接解决百万 token 上下文推理的工程瓶颈，效果惊人（KV cache → 2% 基线）
2. **设计优雅**：CSA 将"压缩+稀疏"两种互补策略无缝结合，DSA 复用了 V3.2 的已有投入
3. **混合策略合理**：不同层用不同注意力机制（浅层 HCA 建全局，深层 CSA 提效率）符合我们对 Transformer 层级功能分化的认知

### 8.2 潜在问题

1. **Flash 浅层策略差异未解释**：为什么 Pro 用 HCA 而 Flash 用纯滑动窗口？论文也没有解释这种差异的设计动机，可能是受限于 Flash 的参数量。
2. **DSA 的实现细节**：DSA 的 Lightning Indexer 在开源 FlashMLA 代码中并不存在——它作为一个外部索引生成组件，在 FlashMLA 内核外部预先计算 `indices` 并传入。`indices` 的生成逻辑（indexer QK 计算）在模型权重或推理框架中，当前未独立开源。
3. **压缩的信息损失**：每 m=4 个 token 压缩为 1 个必然有信息丢失，论文未充分分析在需要精确 token 级别定位的任务（如代码补全、精确引用）上的退化程度。
4. **密度 vs 稀疏的取舍缺乏消融实验**：为什么只有前 2 层用 HCA（Pro）？HCA 和 CSA 交替的比例如何确定？没有看到相关的消融研究。
5. **CSA/HCA 代码未独立开源**：FlashMLA 实现了 DSA 的稀疏注意力内核（包括 V3.2 格式支持），但 CSA 的压缩逻辑和 HCA 的极度压缩逻辑不在当前任何开源代码中。V4 论文提到"open-source implementation"但指向的是 HuggingFace 模型权重，非独立可编译的代码仓库。这意味着 CSA/HCA 的复现门槛较高。

### 8.3 与竞品对比

| 方案 | 来源 | 核心策略 | KV Cache 压缩 |
|------|------|----------|---------------|
| **CSA+HCA** | DeepSeek V4 | 压缩 + 稀疏/稠密混合 | ~2% GQA8基线 |
| **DSA** | DeepSeek V3.2 | 纯稀疏注意力（无压缩） | 基线 |
| **NSA** | DeepSeek (2025.02) | 原生可训练稀疏注意力 | 未公开 |
| **MLA** | DeepSeek V2/V3 | 低秩 KV 压缩 | ~5-10x |
| **Mamba/SSM** | 其他 | 状态空间模型替代注意力 | 常数 KV |
| **RingAttention** | 其他 | 序列并行 | 无压缩 |

**我的判断**：CSA+HCA 是目前开源模型中在百万 token 场景下效率提升最显著的方案。值得注意的是，V4 论文全文未提及 MLA——这意味着 V4 可能完全使用 CSA/HCA 替代了 MLA 的注意力架构（而不仅仅是叠加）。如果属实，这是一个架构上的重大转向：从"低秩压缩"（MLA）切换到"token 聚合压缩"（CSA/HCA）。

---

## 9. 参考来源

| 论文 | arXiv | 日期 |
|------|-------|------|
| DeepSeek-V3.2（DSA 来源） | [2512.02556](https://arxiv.org/abs/2512.02556) | 2025-12-02 |
| DeepSeek-V4（CSA/HCA 来源） | [2606.19348](https://arxiv.org/abs/2606.19348) | 2026-04-26 |
| FlashMemory-DS-V4（LSA） | [2606.09079](https://arxiv.org/abs/2606.09079) | 2026-06-08 |
| NSA（早期稀疏注意力） | [2502.11089](https://arxiv.org/abs/2502.11089) | 2025-02-16 |
