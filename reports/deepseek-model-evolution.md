# DeepSeek 开源模型发展路径与技术演进

> 调研日期：2026-07-03 | 覆盖范围：DeepSeek LLM → DeepSeek-V4 Pro
> 数据来源：16 篇 arXiv 论文原文、GitHub 官方仓库、HuggingFace 模型卡

---

## 一、演进全景

DeepSeek 开源模型从 2024 年 1 月至今约两年半，经历了清晰的五阶段演进。下图概括了主线模型的递进关系：

![DeepSeek 模型演进全景](assets/deepseek-evolution-overview.png)

**阶段划分**：基础探索（LLM/Coder/Math/VL）→ 架构奠基（V2 的 MLA+MoE）→ 规模扩展（V3 的 FP8+MTP）→ 推理突破（R1 的纯 RL）→ V3 系列迭代（V3.1/V3.2 的 DSA+规模化 RL）→ 长上下文革命（V4 的 CSA+HCA）。

DeepSeek 的路径与 OpenAI/Anthropic 有本质不同：后者追求通用 AGI，DeepSeek 则始终坚持 **"高效架构 × 经济训练 × 极致开源"** 三角策略。这一定位使它在受制裁硬件（H800）约束下反而催生了一系列工程创新。

| 阶段 | 代表模型 | 核心贡献 | 关键数字 |
|------|---------|---------|---------|
| 基础探索 | LLM 7B/67B | Scaling Law 研究、深架构设计 | 2T tokens, 95层 |
| 领域专精 | Coder/Math/VL | FIM训练、GRPO算法、混合视觉编码 | MATH 51.7%, 338种语言(Coder-V2) |
| 架构奠基 | V2 | MLA注意力、DeepSeekMoE | 236B/21B, KV减少93.3% |
| 规模扩展 | V3 | FP8训练、MTP、辅助损失自由 | 671B/37B, 训练$5.58M |
| 推理突破 | R1 | 纯RL推理涌现、GRPO | AIME 79.8%, Nature发表 |
| V3 系列迭代 | V3.1/V3.2 | DSA稀疏注意力、混合Thinking、规模化RL | DSA → CSA 前身，IMO/IOI金牌 |
| 长上下文革命 | V4 | CSA+HCA、mHC、Muon | 1.6T/49B, 1M上下文 |

---

## 二、模型参数全景

![参数规模演进](assets/deepseek-params-evolution.png)

DeepSeek 的总参数从 67B 增长到 1.6T（约 24 倍），但激活参数仅从 67B 增加到 49B（反而减少）。这是因为 MoE 架构让每个 token 只激活 ~3% 的专家，推理成本极低。

| 模型 | 总参数 | 激活 | 层数 | Hidden | Heads | 上下文 | 训练数据 | 训练成本 |
|------|--------|------|------|--------|-------|--------|----------|----------|
| LLM 67B | 67B | 67B | 95 | 8192 | 64 | 4K | 2T | - |
| V2 | 236B | 21B | 60 | 5120 | 128 | 128K | 8.1T | 比67B低42.5% |
| V3 | 671B | 37B | 61 | 7168 | 128 | 128K | 14.8T | $5.58M |
| V4-Flash | 284B | 13B | - | - | - | 1M | 32T+ | - |
| V4-Pro | 1.6T | 49B | - | - | - | 1M | 32T+ | - |
| R1 | 671B | 37B | 61 | 7168 | 128 | 128K | (复用V3) | RL后训练$294K¹ |

> **反直觉**：V4-Flash 激活参数仅 13B，比 V1 的 67B 小了 5 倍，但能力完全不在一个量级。参数规模不再是衡量模型能力的有效指标 —— 架构效率和数据质量更重要。
>
> ¹ R1 的 $294K 仅为 RL 后训练阶段成本，不含 V3 基座预训练的 $5.58M。R1 复用 V3-Base 权重做 GRPO 强化学习。

---

## 三、关键技术演进链

### 3.1 注意力机制：MHA → MLA → CSA+HCA

这是 DeepSeek 最具原创性的技术线。MLA（Multi-head Latent Attention）通过低秩联合压缩将 KV cache 映射到低维潜在空间，推理时吸收上投影矩阵，**既保持注意力表达能力，又将 KV cache 减少 93.3%**。

MLA 最精巧之处在于"解耦 RoPE"：因为旋转位置编码与压缩矩阵存在数学冲突，MLA 额外引入一组独立的 query/key 来承载位置信息，完美解决了压缩与位置感知之间的矛盾。

V4 的 CSA+HCA 则进一步在 token 维度做压缩和稀疏化：CSA 在 token 层面做稀疏选择，HCA 做深度压缩。两者叠加后，1M 上下文下的推理 FLOPs 仅为 V3.2 的 27%。

### 3.2 MoE 架构：DeepSeekMoE 的进化

DeepSeekMoE 比传统 MoE（如 GShard）多了两个关键设计：**细粒度专家分割**（将大专家切分成更多小专家）和**共享专家隔离**（专门处理通用知识，减少路由专家之间的冗余）。

V3 引入的"辅助损失自由负载均衡"是一大突破。传统 MoE 需要辅助损失函数来强制专家均衡，但这会损害模型性能。V3 改用动态偏置（bias）调整路由 —— 过载专家降 bias，欠载专家升 bias —— 既保证均衡又不牺牲性能。

### 3.3 强化学习：GRPO 的完整故事

GRPO（Group Relative Policy Optimization）是 DeepSeek 最重要的算法贡献。它的核心思想很简单：放弃传统 PPO 需要的 critic 网络，改为对同一问题采样多个输出，用组内相对排名来估计 advantage。这一改进使 RL 训练内存大幅降低。

GRPO 从 DeepSeekMath 提出，V3 用于对齐，最终在 R1-Zero 上实现质的飞跃 —— 完全不经过 SFT，纯 RL 就让模型自发涌现反思、验证、"aha moment"等推理行为。这篇论文发表于 **Nature**（vol 645, pages 633-638, 2025）。

### 3.4 FP8 训练：硬件约束下的极致优化

V3 是首个验证 FP8 混合精度在大规模模型上可行的案例。由于 H800 的 FP8 Tensor Core 累积精度仅约 14 bits，大矩阵乘法误差可达 2%，V3 通过 CUDA Core 做 FP32 全精度部分累积来补偿。这种"硬件-aware"的系统工程使 V3 在 2048 块 H800 上仅用两个月完成预训练，总成本 $5.58M。

---

## 四、Benchmark 进步：能力的量化跃迁

![Benchmark 进步](assets/deepseek-benchmark-progress.png)

| Benchmark | V1 67B | V2 | V3 | R1 | V4-Pro Max | 最强闭源 |
|-----------|--------|----|----|----|------------|----------|
| MMLU | 71.3 | 78.4 | 87.1 | 90.8 | 87.5 | Gemini-3.1: 91.0 |
| MMLU-Pro | - | 51.4 | 64.4 | 84.0 | 87.5 | Gemini-3.1: 91.0 |
| MATH | 18.7 | 43.6 | 61.6 | **97.3** | - | o1: 96.4 |
| HumanEval | 42.7 | 48.8 | 65.2 | **84.8** | 76.8(base) | GPT-4o: 91.0 |
| LiveCodeBench | - | 11.6 | 40.5 | 65.9 | **93.5** | Gemini-3.1: 91.7 |
| Codeforces | - | - | 51.6(%ile) | 96.3(%ile) | **3206**(Elo) | GPT-5.4: 3168(Elo) |
| AIME 2024 | - | - | 39.2 | 79.8 | **89.8** | o1: 79.2 |
| SWE Verified | - | - | 42.0 | 49.2 | **80.6** | Opus-4.6: 80.8 |
| 1M MRCR | - | - | - | - | 83.5 | Opus-4.6: 92.9 |

> **注**：Codeforces 指标在 R1 和之前模型中为百分位（percentile），V4 为 Elo 评分，两者量纲不同，不可直接比较。V4 的 MMLU（87.5）低于 R1（90.8），反映了知识密集型任务上的回归，详见批判性分析。

**三个最显著的跃进**：
- **MATH**：V1 的 18.7% → R1 的 97.3%，提升 5.2 倍
- **SWE Verified**：V3 的 42.0% → V4-Pro Max 的 80.6%，接近翻倍
- **LiveCodeBench**：V2 的 11.6 → V4-Pro Max 的 93.5，提升 8 倍

---

## 五、批判性分析

### 5.1 做得好的地方

**架构聚焦，不瞎折腾**。MLA 和 DeepSeekMoE 从 V2 一直用到 V4，只在上面叠加优化（FP8、MTP、CSA），而非每代推翻重建。这与 Google 反复换架构的风格形成鲜明对比，带来了极高的研发效率。

**论文质量行业标杆**。V3 的 53 页技术报告是 LLM 论文的典范 —— 从架构公式到训练基础设施到失败案例（如 FP8 累积精度问题），透明度远超 OpenAI 和 Anthropic 的非正式博客。R1 论文更是长达 86 页并发表于 Nature。

**约束条件下的创新**。H800 是被制裁 GPU，NVLink 带宽受限，反而逼出了 DualPipe 并行、FlashMLA kernel、FP8 训练等极致优化。证明限制不是创新的敌人。

### 5.2 值得担忧的

**V4 的开源透明度下降**。V3 公布了完整的架构参数、训练配置、基础设施细节；V4 的技术报告（arXiv 2606.19348）对这些关键细节的披露明显减少。与此形成对比的是，V3.2 单独发布了一份技术报告（PDF），包含了完整的 benchmark 数据和训练方法论（DSA、RL scaling、合成数据管线），但同样回避了具体的架构参数和训练成本细节。担心这是从"真开源"滑向"开放权重"（open-weight）的转折点——MIT 许可证提供了法律上的自由，但技术细节的缺失意味着社区无法真正复现。

**知识类基准仍落后**。V4-Pro Max 在 SimpleQA 上仅 57.9%，远低于 Gemini-3.1 的 75.6% 和 Claude Opus-4.6 的 72.9%。在需要事实记忆而非推理的任务上，DeepSeek 还有明显差距。

**FP4 推理的生态风险**。V4 使用 FP4+FP8 混合精度，但目前开源推理框架（vLLM、llama.cpp 等）对 FP4 的支持远不成熟。这意味着社区实际可用性可能不如 V3 时代的"开箱即用"。

### 5.3 对 V4 的独立判断

V4 真正的战略意义不是模型能力的线性增长，而是**从"对话模型"转型为"Agent 运行时基础设施"**。1M 上下文 + 384K 输出 + 多级推理模式（Non-think/Think High/Think Max）的组合，使 V4 更像一个可编程的推理引擎而非传统 chatbot。这比单纯的 benchmark 分数提升更有远见。

---

## 六、补充：遗漏内容汇总

> 本节补充原报告未覆盖的重要模型迭代、开源基础设施、多模态系列、训练成本及许可协议变化。

---

### 6.1 V3.1 与 V3.2 系列：从 V3 到 V4 的中间迭代

原有报告在 V3 和 V4 之间存在真空地带。实际上 V3 发布后经历了一连串"悄无声息但意义重大"的版本迭代，每一版都为 V4 的架构决策做了铺垫：

| 版本 | 发布日期 | 核心变化 | 关键贡献 |
|------|----------|---------|---------|
| **V3-0324** | 2025-03-24 | Bug 修复 + 性能微调 | 首次引入 Thinking/Non-Thinking 双模雏形；修复代码生成一致性 |
| **V3.1** | 2025-08-21 | 混合思考模式正式化 | UE8M0 FP8 格式（microscaling）、tool-call 增强、长上下文二次扩展（32K→630B tokens, 128K→209B tokens） |
| **V3.1-Terminus** | 2025-09-16 | 搜索 Agent 专项优化 | 语言一致性修复（减少中英混杂）、Code/Search Agent 大幅提升（BrowseComp 30.0→38.5, SWE Verified 66.0→68.4） |
| **V3.2-Exp** | 2025-09-29 | DSA 实验性引入 | 首次实现 **DeepSeek Sparse Attention (DSA)**，稀疏注意力在保持性能无损的前提下大幅降低长上下文计算成本；与 V3.1-Terminus 基准对齐验证 |
| **V3.2-Speciale** | 2025-11-28 | 深度推理专用变体 | 纯推理模型（不支持 tool-call），GPT-5 级推理能力，IMO/IOI 2025 金牌 |
| **V3.2** | 2025-12-01 | 正式版发布 | DSA + 规模化 RL + Agentic 合成数据管线；引入 `developer` 角色（搜索 Agent 专用）；Chat Template 大改（不再使用 Jinja 格式） |

**V3.2 对 V4 的衔接意义**：

V3.2 的 DSA（DeepSeek Sparse Attention）是 V4 中 CSA+HCA 的直接前身。DSA 首次在 token 维度验证了稀疏注意力的可行性，为 V4 在百万上下文下大胆采用 CSA（token 级稀疏选择）+ HCA（深度压缩）提供了实验依据。V4 技术报告中明确指出 CSA+HCA 使 1M 上下文下的推理 FLOPs 仅为 V3.2 的 27%，V3.2 就是那个被用作基准线的"前任"。

V3.2 引入的规模化 RL 框架和 Agentic 合成数据管线也被 V4 继承。V3.2-Speciale 通过 RL scaling 达到 GPT-5 级推理能力的经验，直接影响了 V4 的 multi-tier reasoning 设计（Non-think / Think High / Think Max）。

**V3.2-Speciale 的 benchmark 亮点**：

- IMO 2025 / IOI 2025：金牌（官方提交已开源验证）
- 推理能力对标 Gemini-3.0-Pro，超越 GPT-5
- 仅支持纯推理（无 tool-call），专为数学/编程竞赛设计

---

### 6.2 开源基础设施项目：DeepSeek 的"六件套"工程栈

DeepSeek 在模型之外还开源了六个核心基础设施库，构成了一整套 AI 训练/推理工程栈。这些项目是 DeepSeek 在受限硬件（H800）上实现极致效率的关键，也形成了一个颇具生态野心的系统级开源矩阵：

| 项目 | GitHub Stars | 定位 | 核心贡献 |
|------|-------------|------|---------|
| **[FlashMLA](https://github.com/deepseek-ai/FlashMLA)** | 12,733 | 高效 MLA 注意力 Kernel | CUDA/CUTLASS 实现的高吞吐 MLA 解码 kernel，支持可变长度序列 BF16/FP8 推理；H800 上实测 3000+ GB/s 显存带宽、580+ TFLOPS 算力 |
| **[DeepGEMM](https://github.com/deepseek-ai/DeepGEMM)** | 7,476 | FP8 GEMM 计算库 | 仅 ~300 行核心代码的极简 BLAS 库，针对 MoE 分组矩阵乘法优化；支持 UE8M0 FP8（microscaling 格式），V3.1/V4 预训练的关键加速组件 |
| **[DeepEP](https://github.com/deepseek-ai/DeepEP)** | 9,805 | 专家并行通信库 | 专为 MoE 模型设计的高吞吐低延迟 All-to-All 通信；支持 NVLink + RDMA 混合通信，解决了专家路由场景下跨节点通信瓶颈 |
| **[3FS](https://github.com/deepseek-ai/3FS)** | 10,026 | 分布式文件系统 | 为 AI 训练/推理定制的 POSIX 兼容文件系统；支持 6+ TB/s 读取吞吐（180 节点集群），SSD + RDMA 网络直通，解决 checkpoint 保存/加载和高并发数据读取 |
| **[DualPipe](https://github.com/deepseek-ai/DualPipe)** | 2,977 | 双向流水线并行算法 | V3/R1 训练中使用的计算-通信重叠算法；通过前向/反向传递的交错调度，使通信开销几乎完全被计算隐藏 |
| **[EPLB](https://github.com/deepseek-ai/EPLB)** | 1,395 | 专家并行负载均衡器 | 解决 MoE 训练中不同专家的 token 分布不均问题；基于"冗余专家"策略——复制高负载专家、启发式分配——实现近乎完美的负载均衡 |

这六个项目按依赖关系构成一条完整的训练/推理链路：**3FS（存储）→ DeepEP（通信）→ DualPipe（调度）+ EPLB（均衡）→ DeepGEMM（计算）→ FlashMLA（注意力）**。这种系统级的全栈开源策略，意味着社区理论上可以完全复现 DeepSeek 的训练基础设施，而不只是下载模型权重。

---

### 6.3 多模态系列：Janus/Janus-Pro 和 DeepSeek-OCR

原报告仅覆盖了 DeepSeek-VL/VL2（视觉语言理解），但 DeepSeek 的多模态布局远不止于此。

**Janus / Janus-Pro**（arXiv: 2501.17811）

Janus 系列是 DeepSeek 的"理解+生成统一多模态模型"，核心创新是**解耦视觉编码**：

- **理解路径**：使用 SigLIP-L 编码器（384×384），独立处理图像理解
- **生成路径**：使用独立的 VQ tokenizer（降采样率 16×），处理图像生成
- **统一 Transformer**：两条路径共享同一个自回归 Transformer 处理

与传统的"统一多模态模型"（必须在一个编码器中同时满足理解与生成需求）不同，Janus 的解耦设计消除了视觉编码器在理解和生成角色之间的冲突——理解需要语义抽象，生成需要像素级精度，两者天然矛盾。解耦后，Janus-Pro 在理解任务上匹配了任务专有模型，在图像生成上也超越了此前的统一模型（如 DALL-E 风格的自回归方法）。

Janus-Pro 基于 DeepSeek-LLM-1.5B/7B 构建，模型卡标注 17,757 GitHub stars，采用 MIT 许可证（代码） + DeepSeek Model License（权重）。

**DeepSeek-OCR**（arXiv: 2510.18234）

DeepSeek-OCR 将 OCR 重新定义为"视觉上下文压缩"（Context Optical Compression）问题。核心理念：图像→文本本质上是极高压缩比的信息转换，DeepSeek-OCR 通过专门的压缩-解压架构实现。支持 Gundam 模式（`base_size=1024, image_size=640, crop_mode=True`）等双阶段处理，23,493 GitHub stars。

- 支持直接 Free OCR 和 Grounding OCR（文档→Markdown）
- 提供 Tiny/Small/Base/Large/Gundam 五档精度配置
- 支持 vLLM 部署加速
- 许可证：MIT

这与 GPT-4V/Gemini 的通用视觉方案有本质差异——DeepSeek-OCR 是专用压缩器，而非通用理解器，再次体现了 DeepSeek"用小模型解决特定问题"的效率哲学。

---

### 6.4 其他研究项目

| 项目 | GitHub Stars | 描述 |
|------|-------------|------|
| **Engram** | 4,489 | 条件记忆（Conditional Memory）通过可扩展查找表实现 LLM 的新稀疏性维度——本质相当于给模型增加了一个"外部知识数据库"，通过 key-value lookup 而非参数存储来记忆事实 |
| **DeepSpec** | 5,920 | 全栈推测解码（Speculative Decoding）训练与评估代码库。在 V4 的推理加速中也用到了推测解码技术；支持多种 draft model 策略 |
| **ESFT** | 738 | 专家专业化微调（Expert Specialized Fine-Tuning）——针对 MoE 架构的微调方法，不同下游任务仅微调相关的专家子集，避免全参数微调的成本和灾难性遗忘 |

---

### 6.5 小型模型：V2-Lite 和 MoE 16B 的角色

原报告只覆盖了主线大模型，但 DeepSeek 的小型模型在架构验证和社区推广中扮演了重要角色：

| 模型 | 发布时间 | 总参/激活 | 训练数据 | 定位 |
|------|---------|-----------|---------|------|
| **DeepSeekMoE 16B** | 2024-01 | 16B/2.8B | 2T tokens | MoE 架构验证模型，验证细粒度专家分割+共享专家隔离的可行性；在 16B 规模上证明了 MoE 比同体量 Dense 模型（如 DeepSeek 7B）在编码和数学上大幅领先 |
| **DeepSeek-V2-Lite** | 2024-05-16 | 16B/2.4B | 5.7T tokens | 首个开源 MLA+MoE 小型模型，单张 40G GPU 可部署、8×80G 可微调；充当 V2 架构的"试吃装"，让社区在廉价硬件上体验 MLA 的 KV cache 压缩效果 |
| **DeepSeek-Coder-V2-Lite** | 2024-06 | 16B/2.4B | - | MoE 代码模型，V2 架构 + FIM 训练；HuggingFace 下载量超 109 万，说明小型 MoE 在代码场景的实际需求远超纯文本 |

这些小型模型的战略意义：DeepSeekMoE 16B 在 MoE 论文（arXiv: 2401.06066）中做了首次大规模验证，DeepSeek-V2-Lite 则解决了社区对"236B 太大无法复现研究"的顾虑。两者均使用 DeepSeek License（非标准开源协议的定制许可证，允许商业使用但附带使用限制）。

---

### 6.6 V4 训练成本估算

DeepSeek 未公开 V4 的确切训练成本，但我们可以基于已知数据做合理推算：

| 参考基线 | 成本 | 上下文 |
|----------|------|--------|
| V3 预训练 | $5.58M | 2048×H800, 2 个月, 14.8T tokens, FP8 |
| V3.1 长上下文扩展 | 估算 $200K-$500K | 32K→630B + 128K→209B tokens（增量训练） |
| R1 推理训练 | $294K | 基于 V3 checkpoint 的 RL 后训练 |

**V4 的成本推演**：

1. **预训练成本增幅因子**：V4 训练数据量 32T+ tokens，约为 V3（14.8T）的 2.2 倍；V4-Pro 总参数 1.6T，约为 V3（671B）的 2.4 倍；激活参数 49B vs 37B（1.32 倍）。综合训练计算量约 V3 的 3-5 倍。
2. **架构优化抵消**：DSA（稀疏注意力）和 UE8M0 FP8（microscaling）在训练时也可节省计算量；DualPipe 进一步提高 GPU 利用率。假设节省 20-30%。
3. **粗估**：$5.58M × 3-5 × 0.7-0.8 ≈ **$12M - $22M** 量级。

如果考虑 V4-Flash 和 V4-Pro 是同一家族的多次训练，加上 RL 后训练（类似 R1 的强化学习阶段）和 1M 上下文的增量训练，**V4 全系列的估计成本在 $15M - $30M 之间**——与 GPT-4 传闻的 $100M+ 相比仍低一个数量级，但显著高于 V3。

**不确定性**：V4 是否仍使用 H800/H100 集群？如果 DeepSeek 已有更新的硬件（H20/B200？），实际成本可能低于估算。这些都是基于间接证据的推测，DeepSeek 官方未披露训练硬件和具体成本。

---

### 6.7 许可协议变化趋势

DeepSeek 的许可协议经历了一个从 **"定制专属"→"MIT 标准化"** 的演进路径，这是一个值得注意的战略转向：

| 阶段 | 代表模型 | 许可证类型 | 特点 |
|------|---------|-----------|------|
| **期 I：DeepSeek License** | LLM 7B/67B, MoE 16B, V2/V2-Lite, Coder-V2 | DeepSeek License Agreement v1.0 (2023.10.23) | 类 Apache 2.0 的版权+专利授权，但附带**严格的使用限制**（禁止有害用途、需向下游传递限制条款）、需署名和保留版权声明。更像是"负责任的开放"而非传统开源 |
| **期 II：MIT 过渡** | V3（2024.12）起 | 模型权重：MIT + 代码：MIT | V3 是第一个标注 MIT 的主线模型（HuggingFace 标签 `license:mit`），但仍保留了部分 DeepSeek License 的影子行为（如 README 建议引用） |
| **期 III：全面 MIT** | V3.1, V3.2, V4 系列, Janus-Pro, OCR | MIT | 从 V3.1 开始，所有新发布的模型明确标注 MIT License。V3.1/V3.2/V4/V4-Pro/Janus-Pro/OCR 均使用 MIT |

**趋势解读**：

1. **"开源诚意"信号**：从定制化的 DeepSeek License 转向标准 MIT，意味着移除使用限制、允许完全自由的商业和二次分发。这与 DeepSeek 从"偏保守的中国 AI 公司"到"全球开源标杆"的品牌转型同步。

2. **V2-Lite 是最后的"旧许可证"模型**：V2-Lite（2024.05）使用 `license:other`（即 DeepSeek License），但此后的 V3 立即切换为 MIT。这暗示 DeepSeek 在 2024 年中左右做出了许可协议的战略转向。

3. **与"开放权重"的界限**：Meta 的 Llama 系列虽称"开源"但使用定制许可证（有商业限制），DeepSeek 的 MIT 转换在形式上比 Meta 更接近传统开源定义。但在 V4 阶段，透明度下降（技术细节减少）引发了"MIT 壳 + 封闭技术细节"的争议——许可证开放了但知识未开放。

4. **影响**：MIT 许可证意味着任何人都可以将 DeepSeek 模型用于商业产品、无需署名、无需公开衍生模型。这在理论上为"DeepSeek 生态"的商业化铺平了道路，但也意味着 DeepSeek 无法通过许可协议约束下游使用。

> **注意**：虽然 V3 被标记为 MIT，但其 LICENSE 文件链接的仍是 DeepSeek License Agreement。V3.1 起明确改为 MIT。这一过渡在 2025 年 3-8 月间完成，可能是渐进的。

---

## 七、参考来源

| 模型 | 日期 | arXiv ID | 标题 |
|------|------|----------|------|
| DeepSeek LLM | 2024-01-05 | [2401.02954](https://arxiv.org/abs/2401.02954) | Scaling Open-Source Language Models with Longtermism |
| DeepSeek-Coder | 2024-01-25 | [2401.14196](https://arxiv.org/abs/2401.14196) | When the Large Language Model Meets Programming |
| DeepSeek-Math | 2024-02-05 | [2402.03300](https://arxiv.org/abs/2402.03300) | Pushing the Limits of Mathematical Reasoning |
| DeepSeek-VL | 2024-03-08 | [2403.05525](https://arxiv.org/abs/2403.05525) | Towards Real-World Vision-Language Understanding |
| DeepSeekMoE | 2024-01-11 | [2401.06066](https://arxiv.org/abs/2401.06066) | Towards Ultimate Expert Specialization |
| DeepSeek-V2 | 2024-05-07 | [2405.04434](https://arxiv.org/abs/2405.04434) | A Strong, Economical, and Efficient MoE Language Model |
| DeepSeek-Coder-V2 | 2024-06-17 | [2406.11931](https://arxiv.org/abs/2406.11931) | Breaking the Barrier of Closed-Source Models |
| DeepSeek-V3 | 2024-12-27 | [2412.19437](https://arxiv.org/abs/2412.19437) | Technical Report |
| DeepSeek-VL2 | 2024-12-13 | [2412.10302](https://arxiv.org/abs/2412.10302) | MoE Vision-Language Models |
| DeepSeek-R1 | 2025-01-22 | [2501.12948](https://arxiv.org/abs/2501.12948) | Incentivizing Reasoning via RL (Nature vol 645, pp 633-638) |
| DeepSeek-Prover-V2 | 2025-04-29 | [2504.21801](https://arxiv.org/abs/2504.21801) | Advancing Formal Mathematical Reasoning |
| DeepSeek-V4 | 2026-04-26 | [2606.19348](https://arxiv.org/abs/2606.19348) | Towards Highly Efficient Million-Token Context |
| Janus/Janus-Pro | 2025-01-29 | [2501.17811](https://arxiv.org/abs/2501.17811) | Unified Multimodal Understanding and Generation |
| DeepSeek-OCR | 2025-10 | [2510.18234](https://arxiv.org/abs/2510.18234) | Contexts Optical Compression |
| DeepSeek-V3.2 | 2025-12 | - | Pushing the Frontier of Open Large Language Models |

所有 GitHub 仓库见 [github.com/deepseek-ai](https://github.com/deepseek-ai)，HuggingFace 模型见 [huggingface.co/deepseek-ai](https://huggingface.co/deepseek-ai)。
