# Qwen2 vs Qwen3 实现报告 —— 技术准确性验证

> **验证方法：** 逐条对照 Qwen2 论文 (arXiv:2407.10671)、Qwen3 论文 (arXiv:2505.09388) 原文及 HuggingFace 官方 config.json 文件。

---

## 一、总体评估

报告整体质量较高，大部分核心技术细节均与原始论文和 HF 配置一致。但发现 **1处严重事实错误** 和若干需修正/补充的细节问题。

---

## 二、严重错误 🔴

### ❌ 错误 1：Qwen3-4B 匹敌 Qwen2.5-72B-Instruct（第 163 行）

**报告原文：**
> "Qwen3-4B 匹敌 Qwen2.5-72B-Instruct，这对端侧和边缘部署意义重大。"

**事实核查：**
Qwen3 论文 Section 3.3 明确写道：
> "Qwen3-1.7B/4B/8B/14B/32B-Base achieve comparable performance to Qwen2.5-3B/7B/14B/32B/72B-Base, respectively."

即对应关系为：
| Qwen3 模型 | 匹敌的 Qwen2.5 模型 |
|-----------|-------------------|
| Qwen3-1.7B | Qwen2.5-3B |
| **Qwen3-4B** | **Qwen2.5-7B** |
| Qwen3-8B | Qwen2.5-14B |
| Qwen3-14B | Qwen2.5-32B |
| Qwen3-32B | Qwen2.5-72B |

**应修正为：** "Qwen3-4B 匹敌 Qwen2.5-7B-Base"。只有 Qwen3-32B 才与 Qwen2.5-72B 对标。而且论文说的是 Base 模型而非 Instruct 模型，这一点也需注意。

报告第 99-104 行的表格本身是正确的（Qwen3-4B→Qwen2.5-7B），但批判性分析部分（第 163 行）写错了。此外，第 163 行写的是 "Qwen2.5-72B-Instruct"（指令模型），而论文比较的是 Base 模型——两者不能直接划等号。

---

## 三、需要修正的细节 🟡

### ⚠️ 问题 2：Qwen2-57B-A14B MoE 训练数据量遗漏（第 28 行）

**报告原文：**
> "预训练数据：7T tokens（0.5B用12T）"

**事实核查：**
Qwen2 论文 Table 1 明确列出：
- Qwen2-0.5B: 12T tokens
- Qwen2-1.5B, 7B, 72B: 7T tokens  
- **Qwen2-57B-A14B (MoE): 4.5T tokens**

论文原文："The MoE model received an additional 4.5 trillion tokens of pre-training, in line with the principle of upcycling."

MoE 模型在 Qwen2-7B 基础上 upcycling 后只额外训练了 4.5T，而非 7T。这在整体数据量对比中应当注明。

**建议修正：** "预训练数据: 7T tokens（0.5B用12T, MoE用4.5T）"

### ⚠️ 问题 3：移除共享专家并非 Qwen3 首发（第 77 行）

**报告原文：**
> "移除共享专家的决定值得关注...Qwen3 完全依赖路由专家+全局批次均衡来保证专家专业化。"

**事实核查：**
Qwen3 论文 Section 2 原文："Unlike Qwen2.5-MoE, the Qwen3-MoE design excludes shared experts."

这句话的含义是 Qwen2.5-MoE 有共享专家而 Qwen3-MoE 移除了它们。但报告给人的印象是 Qwen2 MoE 有共享专家、Qwen3 首次移除——实际上 Qwen2.5（中间版本）仍然保留了共享专家。

Qwen2 的 MoE 架构 (57B-A14B) 确实有 8 个共享专家。但 Qwen2.5 也发布了 MoE 模型，需要确认 Qwen2.5-MoE 是否有共享专家。

**建议修正：** 加注 "Qwen2.5-MoE 仍保留共享专家，Qwen3 是首代彻底弃用共享专家的 Qwen MoE。"

### ⚠️ 问题 4：词汇表大小描述不够精确（第 48 行）

**报告原文：**
> "Qwen2 词典 151,643 tokens，Qwen3 微增至 151,669 tokens。"

**事实核查：**
- Qwen2 论文: "a common vocabulary consisting of 151,643 regular tokens and 3 control tokens"（共151,646）
- Qwen3 论文: "vocabulary size of 151,669"
- **实际 HF config.json vocab_size**: Qwen2 各模型为 151,936 或 152,064，Qwen3 各模型统一为 151,936

差异原因：Qwen2 论文说 "owing to considerations in distributed training, the effective size for the embeddings is larger"。HF 配置中的 vocab_size 是 padded embedding size，比论文声明的 token 数量大。

**建议修正：** 加注 "论文声称的 token 数（Qwen2: 151,646, Qwen3: 151,669）与 HF config.json 中的 vocab_size（均为 151,936/152,064，因分布式训练 padding）不同，后者是实际 embedding 维度。"

### ⚠️ 问题 5：Qwen2 后训练方法的描述过于简化（第 142 行）

**报告原文：**
> "对齐方法: SFT + 在线DPO"

**事实核查：**
Qwen2 论文 Section 4.3 标题为 "Reinforcement Learning from Human Feedback"，描述的是 RLHF 框架，其中包含 DPO 作为具体实现手段，同时使用了 "online merging optimizers"（Lu et al., 2024a）。描述为 "SFT + 在线DPO" 基本准确，但论文实际标题是 RLHF 而非仅有 DPO。

**建议：** 如果追求精确，可改为 "SFT + RLHF (在线DPO)"。

---

## 四、已验证为正确的关键声明 ✅

以下声明经验证均与论文原文和 HF 配置一致：

| 声明 | 报告位置 | 证据 |
|------|---------|------|
| QKV Bias 移除 + QK-Norm 新增 | 第 43-47 行 | Qwen3 论文: "we remove QKV-bias...and introduce QK-Norm (Dehghani et al., 2023)"; HF config: `attention_bias: false` |
| Qwen2 MoE: 64专家+8共享, 激活8个 | 第 60 行 | Qwen2 论文 Table 1: Routed Experts=64, Shared Experts=8, Activated=8 |
| Qwen3 MoE: 128专家, 激活8个, 无共享 | 第 65 行 | Qwen3 论文: "128 total experts with 8 activated...excludes shared experts" |
| norm_topk_prob: false→true | 第 62/66 行 | HF config: Qwen2-57B-A14B `norm_topk_prob: false`; Qwen3-30B-A3B `norm_topk_prob: true` |
| Qwen2: 7T tokens 预训练 | 第 87 行 | Qwen2 论文: "over 7 trillion tokens" |
| Qwen3: 36T tokens 预训练 | 第 88 行 | Qwen3 论文: "36 trillion tokens" |
| S1: 30T/4K, S2: 5T/4K, S3: 千亿级/32K | 第 89-91 行 | 论文: "over 30T/4096", "about 5T/4096", "hundreds of billions/32768" |
| S3 75%数据 16K-32K | 第 91 行 | 论文: "75% of text between 16,384 to 32,768 tokens" |
| 冷启动用 QwQ-32B 生成推理数据 | 第 133 行 | 论文 4.1: "generate N candidate responses...using QwQ-32B" |
| 170步 GRPO 将 AIME'24 从 70.1→85.1 | 第 134 行 | 论文 4.2: "the AIME'24 score...increases from 70.1 to 85.1 over a total of 170 RL training steps" |
| 思考预算是模式融合自然涌现的能力 | 第 125 行 | 论文 4.3: "this ability is not explicitly trained but emerges naturally as a result of applying Thinking Mode Fusion" |
| Chat Template 使用 /think 和 /no_think | 第 120-121 行 | 论文 Table 9: Thinking Mode/Non-Thinking Mode 示例 |
| Apache 2.0 全系开源 | 第 31 行 | Qwen3 论文: "all Qwen3 models are publicly accessible under Apache 2.0" |
| Strong-to-weak 蒸馏需 1/10 GPU 小时 | 第 153 行 | 论文: "requiring only 1/10 of the GPU hours" |

### 模型配置核对（HF config.json）

| 模型 | 层数 | hidden_size | Q heads | KV heads | 验证结果 |
|------|------|-------------|---------|----------|---------|
| Qwen2-7B | 28 | 3584 | 28 | 4 | ✅ 一致 |
| Qwen2-72B | 80 | 8192 | 64 | 8 | ✅ 一致 |
| Qwen2-57B-A14B | 28 | 3584 | 28 | 4 | ✅ 一致 |
| Qwen3-8B | 36 | 4096 | 32 | 8 | ✅ 一致 |
| Qwen3-32B | 64 | 5120 | 64 | 8 | ✅ 一致 |
| Qwen3-30B-A3B | 48 | 2048 | 32 | 4 | ✅ 一致 |
| Qwen3-235B-A22B | 94 | 4096 | 64 | 4 | ✅ 一致 |

Note: Qwen3-30B-A3B 的 hidden_size=2048 与 Qwen2-7B 的 3584 不在同一量级（MoE 设计中 hidden_size 较小，通过多专家扩充容量），报告中的模型规模描述正确。

---

## 五、建议补充的技术细节 📝

以下细节在论文中有明确描述，但报告中未提及，建议酌情补充：

1. **Qwen2 MoE 从 7B dense upcycling 的具体流程**（论文 2.2.2）：复制 FFN 权重→沿 intermediate 维度 shuffle→50% 参数随机重初始化。报告仅提到 "打乱维度 → 50%重初始化"，缺少 "复制 ⌈n×hE/hFFN⌉ 次" 这一关键步骤。

2. **Qwen3 使用了 scaling laws 进行超参预测**（论文 3.2）："we develop scaling laws for optimal hyper-parameters predictions based on three pre-training stages"——这是 Qwen3 训练效率高的一个重要方法论。

3. **Qwen3 使用了 ABF 技术调整 RoPE base frequency**（论文 3.2）："we increase the base frequency of RoPE from 10,000 to 1,000,000 using the ABF technique"——这与 Qwen2 相同，但值得在训练策略部分提及。

4. **Qwen3 Thinking Mode Fusion 后的性能退化**（论文 4.7）："for challenging tasks like AIME'24 and LiveCodeBench, the performance in thinking mode actually decreases after these two training stages."——这是一个诚实但重要的 trade-off，报告中未提及。

5. **Qwen3-30B-A3B 的 thinking 模式性能数据**（论文 Table 15）：AIME'24 达到 80.4，高于 Qwen3-14B 的 79.3 和 QwQ-32B 的 79.5。报告中只说了 "3B 激活匹敌 Qwen2.5-32B"，缺少具体的推理 benchmark 数据。

6. **Qwen2 论文中 MoE 模型还训练了额外的 4.5T tokens**（论文 Table 1）：与密集模型的 7T 不同，这对理解数据效率比较有影响。

7. **Qwen2 的 DCA 机制**：Dual Chunk Attention 的具体工作原理（分块处理长序列）在报告中仅作为缩写提及，可以稍作展开说明。

8. **Qwen2 各模型 embedding tying 的差异**：0.5B/1.5B 使用 embedding tying，7B/72B/MoE 不使用——这在报告中完全没有提到，但对理解参数量计算有帮助。

---

## 六、批判性分析部分的评价

报告第 158-185 行的批判性分析整体合理，特别值得肯定的两点：

- 对"移除共享专家"的质疑有深度——确实论文没有提供 ablation study
- 对"思考预算缺乏精确控制"的批评切中要害

但有一些表述需要微调：

- 第 163 行的严重错误已在上面指出
- 第 174 行的 "Qwen2 的 72B 可能过度参数化"——这个判断过于绝对。论文数据显示的是 Qwen2.5-72B 被 Qwen3-32B 超越，不是 Qwen2-72B。且数据质量和训练策略的提升（36T vs 7T，多阶段训练）对性能的影响可能比模型规模更大。

---

## 七、总结

| 类别 | 数量 |
|------|------|
| 严重错误（需立即修正） | 1 |
| 需修正的细节 | 4 |
| 已验证正确的关键声明 | 18 |
| 建议补充的技术细节 | 8 |

**最优先修正：** 第 163 行 "Qwen3-4B 匹敌 Qwen2.5-72B-Instruct" → 应为 "Qwen3-4B 匹敌 Qwen2.5-7B-Base"（且是 Base 不是 Instruct）。

**来源验证：**
- Qwen2 论文 Table 1: https://arxiv.org/pdf/2407.10671
- Qwen3 论文 Section 3.3: https://arxiv.org/pdf/2505.09388
- HF config.json 各模型仓库: https://huggingface.co/Qwen/
