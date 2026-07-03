# 强化学习研究补充报告：重要缺失方向

> **补充日期**：2026-07-03
> **补充范围**：OpenAI o1/o3、Anthropic 对齐方法、Google DeepMind RL 进展、RL 技术融合（MCTS/扩散模型）、开源训练框架、代码 RL、中文 RL 生态
> **说明**：本报告是对主报告《强化学习技术调研报告》的补充，建议配合阅读。

---

## 一、OpenAI o1/o3：推理模型中的 RL 核心作用

### 1.1 o1 的 RL 架构

OpenAI 于 2024 年 9 月发布 o1-preview，2024 年 12 月发布正式版 o1，2025 年 2 月发布 o3-mini。o 系列模型的核心理念是 **"推理时计算"（test-time compute）**——在回答问题前先进行较长的内部推理链（chain-of-thought），而这一能力的获得**高度依赖强化学习**。

o1 训练中 RL 扮演了至少三个关键角色：

| 角色 | 说明 |
|------|------|
| **过程奖励模型（PRM）** | 不仅评判最终答案，还对推理链的每一步打分，训练模型学会"一步步推理" |
| **结果奖励模型（ORM）** | 传统 RLHF 的扩展——对最终答案的正确性给予奖励 |
| **RL 微调** | 使用大规模 RL 训练（很可能是 PPO 变体 + MCTS），让模型学会在推理时自我纠错、回溯、验证 |

### 1.2 o1/o3 的技术推断

虽然 OpenAI 未完全公开 o1/o3 训练细节，但社区广泛推断其使用了：

- **MCTS（蒙特卡洛树搜索）+ RL**：类似于 AlphaGo 在棋类游戏中的做法，在推理空间中搜索最优推理路径。DeepSeek-R1 和 Kimi K1.5 的公开技术报告进一步佐证了这一方向。
- **Process Reward Model**：OpenAI 在 2023 年就发表了 PRM 相关研究（"Let's Verify Step by Step"），o1 很可能是该方向的大规模实践。
- **大规模 RL 训练**：Sam Altman 曾表示 o1 使用了"前所未有的 RL 训练规模"。

### 1.3 o3 及后续

o3 在 2025 年 ARC-AGI 基准上取得了突破性成绩，展示了极强的推理泛化能力。o3-mini 在数学竞赛（AIME 2024）中达到约 96.7% 的准确率，进一步验证了 RL+推理时搜索的有效性。

**我的分析**：o1/o3 的成功标志着一个重要趋势——**RL 不再是"锦上添花"的对齐工具，而是大模型获得推理能力的核心引擎**。这也解释了为什么 2025-2026 年 RL 迎来了历史性复兴。

---

## 二、Anthropic 的对齐新工作（2025-2026）

### 2.1 Constitutional AI 的演进

Anthropic 在 2022 年底提出了 Constitutional AI（CAI），核心思路是用一组原则（宪法）替代人类标注来做 RL 训练：

```
标准 RLHF: 人类偏好 → 奖励模型 → PPO
Constitutional AI: 宪法原则 → AI 自我批评 → RLAIF（AI 反馈的 RL）
```

### 2.2 2025-2026 年新进展

| 方向 | 说明 |
|------|------|
| **RLAIF 规模化** | Anthropic 在 Claude 训练中大规模使用 RLAIF，用 AI 生成的偏好数据替代人类标注，降低了对人类标注员的依赖 |
| **多层级宪法** | 从单一宪法扩展到分层宪法体系：基础安全原则 → 任务特定原则 → 用户自定义原则 |
| **可解释性与 RL 结合** | 2024-2025 年 Anthropic 发表了多篇关于"从神经元层面理解模型行为"的论文，将可解释性工具用于监控和改进 RL 训练过程 |
| **Constitutional Classifiers** | 2025 年提出的新型安全机制，用宪法原则训练分类器来检测和阻止有害输出 |
| **Model Written Evaluations** | 用模型自动生成评估数据来替代人工评估，降低对齐成本 |

### 2.3 Claude 的对齐策略

Anthropic 的 Claude 系列模型使用了**多阶段对齐**：

1. **预训练** → 
2. **RLHF 初始对齐**（人类偏好） → 
3. **Constitutional AI 训练**（RLAIF） → 
4. **Multi-Objective RL**（同时优化 helpfulness, honesty, harmlessness 三个目标）

**我的分析**：Anthropic 的核心贡献在于**降低 RLHF 对人类标注的依赖**。如果 RLHF 的本质是"多数人的暴政"（主报告中提到的问题），Anthropic 的办法是用明确的宪法原则替代隐性的人类偏好——这至少让价值观的权衡变得可审计和可讨论。

---

## 三、Google DeepMind 的 RL 进展

### 3.1 Gemini 中的 RL

Google DeepMind 的 Gemini 系列模型在训练中广泛使用了 RL：

| 阶段 | RL 角色 |
|------|---------|
| **后训练对齐** | 使用 RLHF（基于人类偏好数据）对 Gemini 进行对齐训练 |
| **推理增强** | Gemini 2.0/2.5 引入了类似 o1 的推理时计算，很可能使用了 RL + 搜索 |
| **多模态对齐** | 在多模态场景下使用 RL 使模型学会"看图说话"并遵循指令 |
| **长上下文 RL** | Gemini 1.5 Pro 的 1M token 长上下文能力部分通过 RL 训练获得 |

### 3.2 AlphaProof / AlphaGeometry 2

2024 年 7 月，DeepMind 发布了 AlphaProof 和 AlphaGeometry 2，在 IMO（国际数学奥林匹克）2024 中获得了银牌水平（28/42 分）：

- **AlphaProof**：结合预训练语言模型 + AlphaZero 风格的 RL + 形式化证明语言 Lean，实现了自动数学定理证明
- **AlphaGeometry 2**：在 AlphaGeometry 基础上的升级版，解决了几何证明问题
- **核心创新**：将 RL 用于**形式化推理**领域，证明了 RL 可以从头学习复杂的数学证明策略

### 3.3 Gemini Robotics / 具身智能

2025 年 3 月，DeepMind 发布了 Gemini Robotics 系列：

- **Gemini Robotics**：VLA（视觉-语言-动作）模型，使用 RL 进行精调
- **Gemini Robotics-ER**：具身推理（Embodied Reasoning）模型，RL 用于训练空间理解与操纵规划

### 3.4 Genie 2 / 世界模型

2024 年 12 月，DeepMind 发布 Genie 2——一个从视频数据中学习的基础世界模型，支持 RL Agent 在生成的环境中进行交互训练。这是 Model-based RL 的重要里程碑。

**我的分析**：DeepMind 在 RL 上的独特优势在于**将 RL 与形式化方法（AlphaProof）、世界模型（Genie）、多模态（Gemini）深度融合**。相比 OpenAI 侧重"大规模 RL 训练"，DeepMind 更注重算法创新和跨领域迁移。

---

## 四、RL 与关键技术的融合

### 4.1 RL + MCTS（蒙特卡洛树搜索）

这是 2025-2026 年最活跃的交叉方向之一：

| 工作 | 机构 | 核心思路 |
|------|------|---------|
| **AlphaGo Zero / MuZero 范式** | DeepMind | MCTS + 神经网络 value/policy，自博弈训练 |
| **o1 类推理模型** | OpenAI | 推理时用 MCTS 搜索推理路径 + RL 训练策略 |
| **DeepSeek-R1** | DeepSeek | 纯 RL 训练推理能力，隐含了"隐式搜索"行为 |
| **rStar / rStar-Math** | 微软 | 用 MCTS 生成高质量推理数据，再用 RL/SFT 训练小模型 |
| **ReST-MCTS*** | 清华/上交 | MCTS 引导的自训练 + 过程奖励 |
| **LATS** | 多家机构 | Language Agent Tree Search，在 Agent 任务中使用 MCTS |
| **Search-R1** | 多机构 | 将推理时搜索与 RL 训练结合，推理时用搜索引擎 + MCTS |

核心范式已经清晰：**RL 训练策略网络（学会"怎么想"），MCTS 在推理时搜索最佳路径（实际"怎么想"）**——这与 AlphaGo 在围棋上的成功如出一辙。

### 4.2 RL + 扩散模型

扩散模型（Diffusion Models）与 RL 的融合在 2025-2026 年快速发展：

| 方向 | 代表工作 | 说明 |
|------|---------|------|
| **RLHF for Diffusion** | D3PO, Diffusion-DPO | 将 RLHF/DPO 扩展到图像/视频生成模型 |
| **扩散策略（Diffusion Policy）** | 多机构 | 用扩散模型表示机器人策略，RL 用于优化 |
| **扩散世界模型** | Genie 2, DIAMOND | 用扩散模型做环境模拟器，RL Agent 在其中训练 |
| **扩散规划器** | Diffuser, Decision Diffuser | 用扩散模型做轨迹级别的规划 |
| **verl-omni** | verl 社区 | ⭐480，多模态 RL 训练框架，支持扩散模型 RL |

### 4.3 RL + 过程奖励模型

传统 RLHF 只对最终输出打分，但对于需要多步推理的任务（数学、代码、Agent），**过程奖励**至关重要：

- **PRM（Process Reward Model）**：对推理链的每一步打分
- **自动 PRM 标注**：用 MCTS 或 rollout 自动生成过程奖励标签
- **Math-Shepherd**：自动化过程奖励标注方法

---

## 五、开源 RLHF/RLVR 训练框架

### 5.1 主流框架对比

以下为 2025-2026 年最活跃的开源 RL 训练框架：

| 框架 | GitHub Stars | 定位 | 核心特点 |
|------|-------------|------|---------|
| **HuggingFace TRL** | ⭐18,752 | 通用 RLHF 训练库 | 最成熟的生态，支持 PPO/DPO/KTO/ORPO/GRPO，与 transformers 无缝集成 |
| **OpenRLHF** | ⭐9,736 | 高性能 Ray 分布式 | 基于 Ray，支持 PPO/DAPO/REINFORCE++，支持 vLLM 推理加速，VLM 训练 |
| **LLaMA-Factory** | ⭐40,000+ | 微调一站式平台 | 支持 SFT/DPO/ORPO/SimPO/GRPO 等，Web UI，极低门槛 |
| **verl (Volcano Engine RL)** | ⭐活跃 | 大规模 RL 训练 | 字节跳动开源，支持 PPO/GRPO 等，针对大规模分布式训练优化 |
| **NeMo-Aligner** | ⭐848 | NVIDIA 对齐工具 | NVIDIA 官方，支持 RLHF/DPO/SteerLM，GPU 优化 |
| **oat (Online Alignment)** | ⭐664 | 在线对齐研究框架 | 学术友好，支持在线 RL + 偏好学习 |
| **Trinity-RFT** | ⭐662 | 通用强化微调 | 通用 RL 微调框架，灵活可扩展 |
| **oxRL** | ⭐19 | 轻量后训练框架 | 51 种算法，38 个验证模型，支持 DeepSpeed/vLLM/Ray |
| **simpleRL-reason** | ⭐3,867 | 简洁推理 RL | 港科大出品，极简实现，快速复现 DeepSeek-R1 风格训练 |

### 5.2 框架选择指南

| 场景 | 推荐框架 |
|------|---------|
| 快速上手、实验 | LLaMA-Factory（Web UI）、TRL（API） |
| 学术研究、策略探索 | oat、simpleRL-reason |
| 大规模分布式训练 | OpenRLHF、verl |
| NVIDIA GPU 集群 | NeMo-Aligner |
| 极简复现 R1 | simpleRL-reason |
| 多模态 RL 训练 | verl-omni |

### 5.3 关键趋势

- **GRPO 成为标配**：几乎所有主流框架都在 2025 年加入了 GRPO 支持
- **vLLM 推理加速**：TRL、OpenRLHF 等框架都集成了 vLLM 来加速 RL 训练中的 rollout
- **Ray 统一分布式**：OpenRLHF、verl、oxRL 都基于 Ray 做分布式
- **在线 RL 回归**：oat、Trinity-RFT 强调在线训练，与 DPO 家族形成互补

---

## 六、RL 在代码生成领域的应用

### 6.1 重要工作概览

| 工作 | 机构 | 年份 | 核心贡献 |
|------|------|------|---------|
| **SWE-RL** | Meta FAIR | 2025-2026 | 自博弈 RL 训练代码修复 Agent，SWE-bench +10.4 |
| **CodeRL** | Salesforce | 2022 | 用 RL 训练代码生成，单元测试作为奖励 |
| **RLTF (RL from Test Feedback)** | 多机构 | 2024-2025 | 用编译器/测试反馈作为奖励信号 |
| **PPOCoder** | 清华 | 2023 | PPO 用于代码生成，执行反馈做奖励 |
| **DeepSeek-Coder-V2** | DeepSeek | 2024 | GRPO 训练的代码模型 |
| **Seed-Coder** | 字节跳动 | 2025 | ⭐754，轻量代码 LLM + RL 训练 |
| **OpenCodeInterpreter** | 多机构 | 2024 | 代码执行反馈 + RL |
| **ReflectionCoder** | 多机构 | 2024 | 自我反思 + RL 提升代码质量 |
| **Qwen2.5-Coder** | 阿里 | 2025 | RLHF 对齐的代码模型 |

### 6.2 RL for Code 的独特优势

代码领域是 RL 的"天然适配器"，原因有三：

1. **可验证奖励（RLVR）极其廉价**：代码对不对，跑一下单元测试就知道——不需要人类标注
2. **奖励信号密集且客观**：编译是否通过、测试是否通过、运行时间——都是硬指标
3. **持续自我改进**：Agent 可以不断写代码 → 测代码 → 修复代码，形成闭环

### 6.3 代码 RL 的技术栈

```
代码生成 → 执行环境（沙箱）→ 测试反馈 → 奖励计算 → RL 更新
                                                          ↓
                                              自我反思、错误分析
```

关键奖励设计：
- **编译奖励**：代码能否通过编译
- **正确性奖励**：单元测试通过率
- **效率奖励**：运行时间、内存占用
- **风格奖励**：代码规范、可读性

---

## 七、中国 RL 生态全景

### 7.1 核心玩家

| 机构/公司 | 代表工作 | 定位 |
|----------|---------|------|
| **DeepSeek** | DeepSeek-R1 (⭐91,977), DeepSeek-V3, GRPO 算法 | **中国 RL 标杆**，R1 是 2025 年影响力最大的 RL 工作 |
| **阿里/Qwen** | Qwen3 (⭐27,356), Qwen2.5-Coder, GRPO 训练 | 全系列模型均使用 RLHF/GRPO |
| **字节跳动** | DAPO (⭐1,838), Seed-Coder (⭐754), verl 框架 | RL 算法创新 + 开源框架双线推进 |
| **月之暗面/Kimi** | Kimi K1.5, Moonlight | 长上下文 + RL 推理训练 |
| **智谱 AI** | ChatGLM 系列, GLM-4, CogView | 模型对齐 + 多模态 RL |
| **01.AI/零一万物** | Yi 系列 (⭐7,823) | Yi-Lightning 等高效模型 |
| **上海人工智能实验室** | InternLM (⭐7,237) | 学术开源模型，RLHF 对齐 |
| **清华大学/THUDM** | ChatGLM, CogVLM | 学术前沿，模型对齐研究 |
| **OpenBMB/面壁智能** | MiniCPM 系列 | 端侧小模型 + RL |
| **MiniMax** | MiniMax-01, abab 系列 | 长上下文 + RL |
| **百川智能** | Baichuan 系列 | 模型对齐 |
| **阶跃星辰/StepFun** | Step 系列 | 多模态 + RL |
| **香港科大 (HKUST)** | simpleRL-reason (⭐3,867) | 极简 RL 推理训练 |

### 7.2 中国 RL 生态特点

| 维度 | 特点 |
|------|------|
| **算法创新** | DeepSeek 的 GRPO 是 2025 年最有影响力的 RL 算法创新之一 |
| **开源强度** | DeepSeek、Qwen、InternLM、MiniCPM 均为开源模型，远超美国公司 |
| **工程实力** | 字节的 verl、HKUST 的 simpleRL-reason 体现了顶尖工程能力 |
| **推理优先** | 中国团队在 RL for reasoning 方向尤其活跃 |
| **产学研一体** | 清华、港科大等高校与企业的紧密合作 |
| **成本优势** | DeepSeek-R1 的训练成本约为同类模型的 1/10，展示了高效的 RL 训练 |

### 7.3 中国 vs 美国对比

| 维度 | 美国 | 中国 |
|------|------|------|
| 最强玩家 | OpenAI (o1/o3), Anthropic (Claude), Google (Gemini) | DeepSeek (R1), Qwen, Kimi |
| 开源程度 | 低（o1/o3 细节不公开） | 高（R1 技术报告详细，模型权重开源） |
| 算法贡献 | PRM、Constitutional AI、RLHF 原始框架 | GRPO、DAPO、verl |
| 训练规模 | 超大（数万 GPU） | 高效（同等效果用更少 GPU） |

---

## 八、综合分析与建议

### 8.1 补充到主报告的要点

建议在主报告"四、2025-2026 RL 复兴"中新增以下内容：

1. **OpenAI o1/o3 小节**：说明 RL + MCTS 在推理模型中的核心作用
2. **Anthropic 对齐方法小节**：涵盖 Constitutional AI → RLAIF 的演进
3. **DeepMind RL 全景小节**：AlphaProof 的形式化推理 + Gemini Robotics 的具身智能
4. **RL + MCTS 融合小节**：说明推理时搜索正在成为 RL for reasoning 的标准范式
5. **代码 RL 小节**：扩展 SWE-RL 之外的工作全景

### 8.2 更新框架对比表

建议在主报告中新增开源框架对比表（见本报告第五节）。

### 8.3 更新中文生态

建议在主报告中新增"中国 RL 生态"板块，因为 DeepSeek-R1 是全球 RL 复兴的标志性事件，而中国在此方向上的贡献远超外界认知。

---

## 九、关键信息来源

- **OpenAI o1 System Card**: https://openai.com/index/openai-o1-system-card/
- **Anthropic Constitutional AI 论文**: "Constitutional AI: Harmlessness from AI Feedback" (2022)
- **DeepMind AlphaProof**: "AI achieves silver-medal standard solving International Mathematical Olympiad problems" (2024)
- **DeepSeek-R1 技术报告**: arXiv:2501.12948, Nature (2025)
- **Kimi K1.5 技术报告**: arXiv:2501.12599
- **OpenRLHF GitHub**: https://github.com/OpenRLHF/OpenRLHF
- **TRL GitHub**: https://github.com/huggingface/trl
- **verl GitHub**: https://github.com/volcengine/verl
- **simpleRL-reason**: https://github.com/hkust-nlp/simpleRL-reason

---

*补充报告完。请将此报告与主报告合并或作为独立章节插入。*
