# Attention Residuals：用注意力重构深度维信息流动

> **核心发现：AttnRes 将残差连接的均匀累加替换为跨层 Softmax 选择，以<2%延迟换取约1.25倍等效训练效率提升，首次在深度维引入可学习的内容相关聚合。**
> 调研日期：2026-07-29 | 来源：AttnRes 论文 (arXiv:2603.15031)、K3 技术报告、社区分析

## 一、概览

**AttnRes 的定位可以用一句话概括："让第93层直接翻看第1层的笔记。"**

传统残差连接（ResNet, 2015）将每一层的输出均匀地累加到下游。这意味着第93层接收的信号中，第1层的贡献被92次加法反复稀释——就像传话游戏，开头的信息传到末尾早已失真。AttnRes 用一个跨层 Softmax 选择机制替换了这个固定规则：每一层不再被迫接收"上一层 + 自己"，而是自由地从所有前置层中加权检索最相关的隐藏状态。

**关键指标速览：**

| 指标 | 数值 | 说明 |
|------|------|------|
| 层数到 block 压缩 | 93层 → 9 block | 每 block 约12层，加嵌入层 |
| 额外计算开销 | <2% 延迟 | 相比标准 PreNorm 残差 |
| GPQA-Diamond 提升 | +7.5 分 | Block AttnRes vs 无 AttnRes |
| 等效训练效率 | 约 1.25 倍 | 同等算力下达到相同性能 |
| Block AttnRes vs Full | 接近 Full 效果 | 但内存从 O(Ld) 降到 O(Nd) |
| 开源情况 | 论文+代码全开源 | 3.4k stars |

**为什么重要？** 这是残差连接诞生十年来首次被根本性重构。OpenAI 前研究副总裁 Jerry Tworek 称之为"深度学习2.0的标志"。Andrej Karpathy 评论："看来我们还没足够'字面'地理解 Attention is All You Need。"这句话的含义是：Transformer 声称"注意力是你所需要的一切"，但十年间，我们从未想过把注意力也用在深度维上。

## 二、从 ResNet 到 AttnRes：十年演进

**一句话预判本节结论：深度维的信息聚合方式经历了四次范式转移，而 AttnRes 是将路由能力首次引入深度维的关键突破。**

### 2.1 演进路线

残差连接的历史是一段"从固定累加到可学习选择"的渐进式解放进程：

| 方法 | 年份 | 连接方式 | 权重机制 | 跨层能力 | 核心局限 |
|------|------|----------|----------|----------|----------|
| ResNet | 2015 | h_l = h_{l-1} + F(h_{l-1}) | fixed = 1 | 仅上一层 | 均匀累加，深层稀释 |
| Highway Networks | 2015 | h_l = T_l⊙F + (1-T_l)⊙h_{l-1} | learnable gate | 仅上一层 | 门控可学习但不能跨层 |
| DenseNet | 2017 | concat all previous | full connection | 全部前层 | 维度爆炸，不可扩展 |
| RealFormer | 2021 | Attn_l += Attn_{l-1} | fixed = 1 | 残差传递注意力图 | 非选择性，无内容感知 |
| AttnRes | 2026 | Softmax(w_l^⊤ [h_0...h_{l-1}]) | content-dependent learnable | 全部前层（block级） | 仅 block 级别，非逐层 |

### 2.2 核心洞察

AttnRes 论文提出了一个简洁而有力的类比：

> RNN 用 Attention 解放了时间维 → AttnRes 用 Attention 解放了深度维

在 2017 年的 Transformer 中，Attention 替代了 RNN 的固定时序状态传递，让每一时刻可以直接关注任意历史时刻。AttnRes 在深度维上做了完全相同的事：替代了残差连接的固定逐层传递，让每一层可以直接关注任意前置层。

这不是技术巧合，而是一种概念对称。如果信息聚合在所有维度上都应该是可学习的、内容相关的，那么"注意力是深度维所需要的全部"这个命题，在逻辑上与"注意力是时序维所需要的全部"完全对等。

**My take：** 如果说 Transformer 是 RNN 的时间维注意力化，AttnRes 就是残差的深度维注意力化。前者的变革用了八年才被充分消化，后者的影响可能才刚刚开始。

## 三、AttnRes 的设计与消融

**一句话预判本节结论：Full AttnRes 理论最优但不实际，Block AttnRes 以极低代价逼近前者，block_size=12 的对齐设计是关键。**

### 3.1 Full AttnRes 的数学定义

对于深度维索引 l，Full AttnRes 将第 l 层的输出定义为：

```
h_l = Softmax(w_l^⊤ [h_0, h_1, ..., h_{l-1}]) · [h_0, h_1, ..., h_{l-1}]
```

其中：
- **w_l** 是一个可学习向量（称为"伪查询"），每层拥有独立的 w_l
- **[h_0, ..., h_{l-1}]** 是所有前置层的隐藏状态矩阵
- **Softmax 内积** 输出一个 (l) 维的注意力分布——即"该关注哪些前层"

w_l 的作用就像一个"信息需求问卷"——每层在学习过程中逐渐"理解"自己需要什么样的前置层信息，并通过可训练的参数表达出来。

### 3.2 从 Full 到 Block：一次务实的降维

Full AttnRes 让第93层直接对92个前层做 Softmax 检索，这在理论上最美但内存上是灾难：

- **内存复杂度**：O(L × d)，其中 L=93，d 是隐藏维度
- **实际影响**：在千亿参数模型上，Full AttnRes 的内存开销远超 2%

Block AttnRes 将相邻层分组，每个 block 输出一个聚合向量。K3 的分组策略：

```
93 层 = 7 × 12层（完整 block）+ 1 × 9层（尾部 block）
+ 嵌入层视为独立 block = 总共 9 个 block
```

每层现在只对 9 个 block 向量做检索，内存降到 O(N × d)，N=9。这就是"<2% 延迟增加"的来源。

### 3.3 block_size=12 为什么是这个数？

12 不是随机的。K3 的层结构采用 4 层周期：3 个 KDA（Key-Depth Attention）层 + 1 个 MLA（Multi-head Latent Attention）层。一个完整的 12 层 block 恰好包含 3 个完整周期。这使得：

1. 每个 AttnRes block 内部包含完整的注意力模式多样性
2. block 边界与架构周期边界对齐，避免语义割裂
3. 尾部 9 层（2 个周期 + 1 层）作为自然残差处理

这种对齐不是代码层面的 hack，而是结构与功能的设计一致性。

### 3.4 消融实验数据

| Configuration | Training PPL | GPQA-Diamond | 内存 | 备注 |
|--------------|-------------|-------------|------|------|
| 标准 PreNorm 残差（无 AttnRes） | baseline | baseline | 最低 | 隐藏状态幅度随深度膨胀 |
| Full AttnRes（每层关注所有前层） | best | — | O(Ld) | 不适合大规模训练 |
| Block AttnRes（K3 选择） | 接近 Full | **+7.5** | O(Nd) | 开销 <2% |
| Block AttnRes + Kimi Linear | 进一步改善 | — | O(Nd) | 在 1.4T tokens 预训练上验证 |

**关键发现：Block 凭什么接近 Full？**

直觉解释：相邻层的隐藏状态高度相关。如果第12层想"翻看第1层的笔记"，它通过关注 block_1（包含第1-12层的信息）几乎等效于直接关注第1层。这就像在一本书中，不需要逐页检索——跳到某一章的摘要通常就足够了。

**My take：** Block 方案的优雅之处在于它把"相邻层信息冗余"从缺陷变成了优势——恰好利用冗余来实现压缩。

## 四、AttnRes 的深层影响

**一句话预判本节结论：AttnRes 的核心价值不在"增加一个新模块"，而在系统性缓解了深层 Transformer 的信息衰减问题。**

### 4.1 PreNorm 稀释问题

在标准 PreNorm 残差连接下，第 L 层的输出近似为：

```
h_L ≈ h_0 + F_1(h_0) + F_2(h_1) + ... + F_L(h_{L-1})
```

每一层都在前一层的基础上"加一点"。问题在于：随着 L 增大，h_0 的相对贡献被后续的 L 个增量项不断稀释。深层无法有效利用浅层的原始信息。

AttnRes 通过 Softmax 选择打破了这个等权假设。深层现在可以"跳过"中间层，直接检索浅层的关键信号。这带来的两个可测量后果：

1. **幅度分布更均匀**：深层输出不再倾向于"随层数增大而膨胀"
2. **梯度分布更健康**：浅层梯度不再被中间层的加法操作反复衰减

### 4.2 Scaling Law 验证

K3 团队在多个模型规模上验证了改进的一致性。Block AttnRes 的 PPL 增益在不同参数量级上保持稳定——这意味着它不是一个小模型的"过拟合福利"，而是一种对 Transformer 架构的普适性改进。

### 4.3 与 MoE Router 的潜在协同

AttnRes 负责"深度维选择"（关注哪些前层），MoE Router 负责"宽度维选择"（激活哪些专家）。两者在同一层中形成正交的信息路由机制：

- MoE：当前层在专家空间中的条件计算
- AttnRes：当前层在深度空间中的信息检索

理论上，这两个路由信号可以相互增强——例如，某些专家可能天然更适合处理来自特定浅层 block 的信息。但目前尚无消融实验验证这一协同效应。

### 4.4 伪查询 w_l 的训练动态

论文报告了 w_l 在训练过程中的行为演化：

- **训练初期**：w_l 产生的注意力分布接近均匀——所有前层被平等对待
- **训练中期**：开始分化，某些层的 w_l 逐渐聚焦到特定 block 范围
- **训练收敛**：注意力分布呈现明显的稀疏模式——不同层形成了各自的"前层关注偏好"

这意味着模型在学习"深度维的信息路由策略"——一种之前从未被显式建模的能力。

**My take：** w_l 的训练行为是 AttnRes 最有趣的现象之一——它表明"深度偏好"不是被预设而是被发现的。这暗示 Transformer 可能一直在通过某种隐式方式实现类似行为，而 AttnRes 只是让它显式化了。

## 五、批判性分析与开放问题

**一句话预判本节结论：AttnRes 的潜力很大，但公开数据中的缺口恰好指向架构设计中最重要的几个决策点。**

### 5.1 block_size 是否还有更优选择？

论文仅报告了 block_size=12 的结果，未公开不同 block_size 的消融实验。这留下几个关键问题：

- block_size=6 是否会更好？更细粒度可能提高检索精度，但增加开销
- block_size=24 是否已经足够？更粗粒度可能进一步压缩开销
- block_size 的最优值是否与模型深度有关？对于 93 层是 12，对 200 层呢？

这些问题的答案将决定 AttnRes 是否是一种"即插即用"的通用方案。

### 5.2 深层关注偏好的可视化缺失

一个关键假设是：深层倾向于关注中间层 block 而非最近的前层。如果这个假设为真，说明 AttnRes 确实在"克服稀释"；如果深层主要关注紧邻的 block，那 AttnRes 的贡献就更多来自 Softmax 权重的小幅调整而非跨层跳跃。

目前这些可视化数据尚未公开。

### 5.3 MoE × AttnRes 的消融空白

虽然第 4.3 节讨论了理论协同，但论文并未报告同时使用 MoE Router 和 AttnRes 的消融实验。两者的路由器是否会互相干扰？联合训练是否能带来超线性收益？这些都是开放问题。

### 5.4 推理场景的性能评估不足

论文声称"<2% 延迟增加"，但评估基于训练场景。在推理时：

- **Batch inference 场景**：block 向量的 KV cache 复用方式可能与训练不同
- **单 batch 推理**：2% 的额外延迟对于对延迟敏感的应用是否可接受？
- **KV cache 的内存模型**：引入 block 级向量后，cache 结构是否需要重构？

### 5.5 对开源社区的启示

AttnRes 论文和代码已全部开源（3.4k stars）。从工程角度看，AttnRes 的集成难度很低：

- 不需要修改 Attention 计算核心
- 不需要改动优化器或学习率调度
- 仅需在层间插入一个轻量级的跨层 Softmax 池化模块

这意味着社区可以低成本地将 AttnRes 移植到 LLaMA、Mistral 等其他架构上。已有社区尝试在 7B 模型上复现，初步结果支持论文的结论。

### 5.6 更根本的一个问题

残差连接在 ResNet 时代被理解为"梯度高速公路"——它的首要功能是解决深层网络的梯度消失。AttnRes 的 Softmax 选择是否会影响这条高速公路的通行效率？

论文的 Scaling Law 数据表明不会——改进在多个规模上一致。但从数学上看，Softmax 的归一化特性可能在某些极端深度（200层以上）引入新的梯度瓶颈。这一点尚未有实验验证。

**My take：** AttnRes 最让人兴奋的不是它"有效"，而是它打开了"深度维学习"这个全新的设计空间。就像 2017 年的 Transformer 之后涌现了无数 Attention 变体，AttnRes 之后，"深度维注意力"可能成为一个新的子领域。

## 参考来源

- **AttnRes 论文**：arXiv:2603.15031（Kimi Team, 2026-03）
- **AttnRes GitHub**：github.com/MoonshotAI/Attention-Residuals（3.4k stars）
- **K3 技术报告**：github.com/MoonshotAI/Kimi-K3
- **ResNet**：He et al., "Deep Residual Learning for Image Recognition", CVPR 2016 (arXiv:1512.03385, 2015)
- **Highway Networks**：Srivastava et al., "Highway Networks", ICML 2015 Deep Learning Workshop (arXiv:1505.00387, 2015)
- **DenseNet**：Huang et al., "Densely Connected Convolutional Networks", CVPR 2017 (arXiv:1608.06993, 2016)
- **RealFormer**：He et al., "RealFormer: Transformer Likes Residual Attention", ACL 2021 Findings (arXiv:2012.11747, 2020)
