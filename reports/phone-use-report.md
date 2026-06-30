# Phone Use：AI 手机操控代理调研报告

> 调研时间：2026-06-30 | 数据来源：arXiv、GitHub、官方博客、源码分析

## 一、什么是 Phone Use？

**Phone Use** 是指 AI Agent 像人类一样，通过**看屏幕截图 → 理解界面 → 点击/滑动/输入**来操作手机 App，而不是通过 API 调用或预定义脚本。这是 LLM 从「聊天」走向「行动」的关键一步。

它与 **Computer Use**（Anthropic 2024年10月推出）同属 **GUI Agent** 范畴——区别仅在于操作手机还是电脑。核心技术栈完全一致：**VLM 视觉理解 + 元素定位 + 动作执行**。

| 维度 | Computer Use | Phone Use |
|------|-------------|-----------|
| 典型场景 | 浏览器自动化、办公软件 | 微信/小红书/外卖/支付/打车 |
| 屏幕 | 桌面显示器（大屏、多窗口） | 手机（小屏、单任务） |
| 操作动作 | 鼠标移动+点击+键盘 | 触屏点击+滑动+系统按键 |
| 权限模型 | 桌面 OS 权限较宽松 | Android 权限严格，需 AccessibilityService |
| 主要玩家 | Anthropic、OpenAI | 字节跳动、百度、OPPO、社区开源 |
| 产品化程度 | 较高（Claude Computer Use 已商用） | 较低（以论文和评测为主） |

## 二、行业全景

### 2.1 巨头的博弈

| 公司 | 产品/项目 | 状态 | 技术路线 |
|------|----------|------|---------|
| **Apple** | Apple Intelligence + App Intents | 已发布（iOS 18+） | 私有 API + 端侧模型。App 需主动声明 Intents，Agent 通过声明式接口操作，非截图模式。**封闭生态的典型方案** |
| **Google** | Gemini on Android + Project Mariner | 研发中 | Gemini 深度集成 Android，可能走「应用扩展」路线（类似 App Intents）。公开信息极少 |
| **Anthropic** | Claude Computer Use（桌面为主） | 已商用（Beta） | 纯截图+像素定位，不依赖 DOM/无障碍树。**通用性最强**但准确率仅 14.9%（OSWorld），离人类（70-75%）差距巨大 |
| **字节跳动** | PhoneWorld + PhoneHarness | 论文阶段（2026.5-6） | 34 个 App 仿真环境 + 混合动作（GUI + CLI + Tool），是目前**最系统化的 Phone Use 研究平台** |
| **百度** | OmegaUse | 论文（2026.1） | 端到端训练，手机+电脑通用 GUI Agent，ScreenSpot-V2 达 96.3% SOTA |
| **Rabbit** | R1 + DLAM | 已发售（硬件） | 独立 AI 硬件 + Claude Code 集成 + DLAM（电脑控制）。定位模糊，更接近「AI 遥控器」而非 Phone Use |

### 2.2 我的判断

**最务实的路径是字节跳动的 PhoneWorld/PhoneHarness 路线**，原因是：

- Apple/Google 的方案太封闭，只适用于被 App 开发者主动支持的应用，难以泛化到海量存量 App
- Anthropic 的纯截图方案通用但太慢，准确率远未达到可用状态（14.9% vs 75% 人类水平）
- 字节的做法是**仿真环境 + 确定性评测 + 混合动作**，兼顾了可复现性和实用性

**Phone Use 当前的真正瓶颈不是模型能力，而是缺少可靠可复现的训练/评测环境。** 这正是 PhoneWorld（34 个仿生 App + 自动验证）和 MobileGym（28 个仿真 App + 256 并行实例）要解决的问题。

## 三、学术前沿

### 3.1 重要论文一览

| 论文 | 时间 | 机构 | 核心贡献 |
|------|------|------|---------|
| **OS Agents Survey** (ACL 2025 Oral) | 2025.8 | 浙大+OPPO | 最全面的 OS Agent 综述，定义了环境/观测/动作空间三大组件 |
| **PhoneWorld** | 2026.5 | 字节跳动 | 将真实 GUI 轨迹转为可运行仿真环境，34 个 App，跨 16 领域。训练提升：HYMobileBench +17.7pt |
| **PhoneHarness** | 2026.6 | 字节跳动 | **混合动作基准**：GUI 截屏 + CLI 命令 + Tool 调用，突破纯 GUI 局限。75% 通过率，比最强纯 GUI 方案高 12.9pt |
| **OmegaUse** | 2026.1 | 百度 | MoE 架构 + SFT→GRPO 两阶段训练，ScreenSpot-V2 SOTA（96.3%），AndroidControl 79.1% |
| **MobileGym** | 2026.5 | 独立研究者 | 浏览器端仿真环境，28 个 App，256 并行实例，Sim-to-Real 转换保留率 95.1% |
| **Darwin Mobile Agent** | 2026.6 | 未知机构 | 自演化路线图：移除人类先验，通过云手机大规模 RL |
| **GoClick** | 2026.4 | 中科院自动化所 | 230M 轻量级元素定位模型，对标 2.5B+ 大模型 |
| **CAPED** | 2026.6 | 港中文 | 手机端隐私保护层，截图上传云端前自动脱敏 |
| **InfiGUIAgent** | 2025.1 | 浙大 | 两阶段 SFT：基础技能 → 层次推理，强调 Agent 的「原生推理能力」 |
| **CRAB** (ACL 2025 Findings) | 2024.7 | KAUST | 首个跨平台 Agent 基准框架，120 个跨设备任务 |

### 3.2 关键基准测试（Benchmarks）

| Benchmark | App 数 | 任务数 | 特点 |
|-----------|--------|--------|------|
| **AndroidWorld** | 21 | 116 | 真实 Android 模拟器，含社交/购物/邮件等日常 App |
| **AndroidControl** | 15 | 15,283 | 最大规模的 step-level 操作数据集 |
| **ScreenSpot-V2** | - | - | 元素定位（Grounding）专用，评测 VLM 能否精确找到按钮/输入框 |
| **MobileGym-Bench** | 28 | 416 | 浏览器仿真，**确定性评分**（不用 VLM 裁判），256 任务并行 ~6 分钟 |
| **PhoneHarness Bench** | - | - | 混合动作基准，评测执行结果而非中间答案 |
| **OS-Nav (ChiM-Nav)** | - | - | OmegaUse 自带：中文 Android 导航导航基准 |

### 3.3 MobileGym 排行榜（2026.4）

| 模型 | Overall SR | L4(最难) | 类型 |
|------|-----------|---------|------|
| Gemini 3.1 Pro | **58.8%** | 21.9% | 闭源 |
| Doubao-Seed-2.0-Pro | 52.0% | 6.2% | 闭源 |
| Qwen3.6-Plus | 45.7% | 3.8% | 闭源 |
| AutoGLM-Phone-9B | 20.0% | 1.9% | 开源 GUI 专用 |
| UI-TARS-1.5-8B | 13.8% | 1.6% | 开源 GUI 专用 |
| Qwen3-VL-4B | 9.4% | 0.3% | 开源通用 |
| **Qwen3-VL-4B + GRPO** | **22.2%** | **1.2%** | RL 微调后 |

> ⚠️ 最佳闭源模型在 L4 高难度任务上仅 21.9%，最佳开源模型仅 1.9%。**Phone Use 离"随手可用"还差很远。**

## 四、开源项目深度分析

### 4.1 OpenOmniBot ⭐1860

**定位**：运行在 Android 手机上的全能 AI Agent App。

| 维度 | 详情 |
|------|------|
| 技术栈 | Kotlin(Android 原生) + Flutter(UI) + Riverpod(状态管理) |
| 核心能力 | VLM 任务执行、技能商店、MCP 协议、定时任务、子代理、本地/云端双模型 |
| 亮点 | **真正的端侧运行**，不依赖电脑。技能生态和 MCP 支持远超同类 |
| 问题 | 重度依赖 Android 系统权限（AccessibilityService + Overlay），权限门槛高。代码质量参差（Flutter+Kotlin 混合） |

**批判分析**：
- OpenOmniBot 是目前**用户可用的最完整 Phone Use App**，但它的定位更像一个「万能 Agent 平台」而非纯粹的 GUI 操控工具。它把聊天、技能、自动化、MCP 等全部塞进一个 App，导致功能繁杂但每个都不够深。
- 最大的缺陷是**没有做 Benchmarking**——你不知道它在标准任务上的准确率是多少，这让它更像一个玩具而非工具。
- 优点在于它确实解决了 Phone Use 的「最后一公里」：用户不需要刷命令行，打开 App 就能用。

### 4.2 OpenGUI ⭐274

**定位**：专业的移动 GUI Agent 框架，面向开发者。

| 维度 | 详情 |
|------|------|
| 技术栈 | TypeScript 后端 + Android Kotlin 客户端，LangGraph 构图 |
| 核心能力 | 长任务（最多 12h）、多模型路由（规划+VLM 分离）、多通道接入（Discord/飞书/Telegram/REST） |
| 亮点 | **架构设计最成熟**：Plan Supervisor→Executor Graph→Summarizer 三阶段管道 |
| 问题 | 部署复杂（需 Docker+PostgreSQL+Redis），门槛高。手机端需 USB 连接电脑 |

**批判分析**：
- OpenGUI 是**架构最清晰的 Phone Use 框架**，三阶段流水线（规划→执行→总结）是业界最佳实践。但它依然有「实验室项目」的气质——部署一套后端服务才能用，跟「下载即用」的产品还有很大距离。
- 核心价值在于**多通道接入**：它可以让 Discord/飞书/Telegram 上的 AI Bot 直接操控手机，这是很多自动化场景的真正需求。
- 但 274 的 Star 数说明社区采用度不高，可能是因为部署太复杂+文档太简略。

### 4.3 MobileGym ⭐687

**定位**：浏览器内运行的手机仿真训练环境，不是 Agent，而是 Agent 的训练场。

| 维度 | 详情 |
|------|------|
| 技术栈 | React + Vite + TypeScript，浏览器渲染模拟手机 OS |
| 核心能力 | 28 个仿真 App，416 个参数化任务，确定性评分，256 并行实例 |
| 亮点 | Sim-to-Real 验证通过（95.1% 训练增益保留），**只需浏览器，零安装** |
| 问题 | 只覆盖仿真 App，不连接真实手机。App 数量和复杂度有限 |

**批判分析**：
- MobileGym 是**目前最好的 Phone Use 训练/评测平台**。它的关键创新是用「行为保真」替代「像素保真」——模拟器不需要像素级还原真机，只要 Agent 的行为逻辑一致即可。
- 但严肃地说，28 个 App 太少，且都是西方 App（Uber Eats、Airbnb 等），对中国用户毫无意义。中文 App（微信、支付宝、美团、抖音）完全缺席。
- 它的真正潜力在于**RL 训练基础设施**——如果把 MobileGym 的架构用于构建中国 App 的仿真环境，可能会产生第一个实用的中文 Phone Use Agent。

### 4.4 开源项目对比总结

| 项目 | 可用性 | 架构质量 | 生态 | 适合谁 |
|------|--------|---------|------|--------|
| **OpenOmniBot** | ⭐⭐⭐⭐ 开箱即用 | ⭐⭐ 混杂 | ⭐⭐⭐⭐ 技能市场 | 个人用户，尝鲜者 |
| **OpenGUI** | ⭐⭐ 需部署 | ⭐⭐⭐⭐⭐ 最佳 | ⭐⭐⭐ 多通道 | 开发者，自动化运维 |
| **MobileGym** | ⭐⭐⭐ 浏览器跑 | ⭐⭐⭐⭐ 优秀 | ⭐⭐⭐ 研究生态 | 研究人员，RL 训练 |

## 五、技术架构解析

### 5.1 Phone Use 的核心技术栈

一个完整的 Phone Use Agent 由以下组件构成：

1. **屏幕感知**（Observation）：截图 → VLM/OCR 理解界面布局和内容
2. **元素定位**（Grounding）：从自然语言指令定位到具体的像素坐标
3. **任务规划**（Planning）：将高级目标分解为操作步骤序列
4. **动作执行**（Action）：AccessibilityService 或 ADB 模拟点击/滑动/输入
5. **状态验证**（Verification）：判断操作是否成功，决定是否重试

### 5.2 三种技术路线

| 路线 | 代表方 | 优势 | 劣势 |
|------|--------|------|------|
| **纯视觉路线**（截图→VLM→动作） | Anthropic Computer Use | 最通用，不需要 App 适配 | 慢、贵、准确率低 |
| **声明式路线**（App 预定义接口） | Apple App Intents | 准确、快速、安全 | 需要 App 开发者配合，无法覆盖存量 |
| **混合路线**（视觉+无障碍树+工具） | PhoneHarness、OpenOmniBot | 兼顾通用性和精度 | 架构复杂，调试困难 |

### 5.3 PhoneHarness 的混合动作模型（目前最佳实践）

PhoneHarness 将手机 Agent 的能力分为三个「动作面」：

- **GUI 动作**：截图→定位元素→点击/滑动（传统路线，慢但通用）
- **CLI 动作**：通过 ADB Shell 执行系统级命令（快而精准，但适用范围窄）
- **Tool 动作**：调用结构化工具 API（最精确，但需预定义）

Agent 根据当前任务特征**动态路由**到最合适的动作面。例如：
- 打开 App → CLI（`am start`）
- 填写表单 → GUI（视觉定位+输入）
- 查询天气 → Tool（API 调用）

**这个架构设计的巧妙之处在于**：它不追求一个「万能」方案，而是承认不同子任务适合不同工具，让 Agent 自己决策用什么。

## 六、核心挑战

### 6.1 当前瓶颈

| 挑战 | 严重程度 | 说明 |
|------|---------|------|
| **定位不准** | 🔴 致命 | VLM 在手机上定位小元素（如图标、按钮）错误率极高。ScreenSpot-Pro 上最好模型仅 18.9% |
| **缺乏训练环境** | 🔴 致命 | 真实手机环境不可重置，训练 RL 几乎不可能。MobileGym/PhoneWorld 在解决，但 App 覆盖太少 |
| **长任务失效** | 🟡 严重 | 任务超过 20 步后准确率断崖式下降。错误累积 + 上下文漂移 |
| **速度太慢** | 🟡 严重 | 每步操作需要截图→上传→VLM 推理→返回→执行，端到端延迟 3-8 秒 |
| **隐私问题** | 🟡 中等 | 截图包含敏感信息（聊天内容、银行余额）。CAPED 等方案在研究，但未产品化 |
| **版本敏感** | 🟢 可控 | App UI 更新后，视觉 agent 的行为可能完全失效 |

### 6.2 我的观点

Phone Use 当前的状态让我想起 **2016 年的自动驾驶**——技术上看起来可行，demo 很炫，但离真正安全可用还差几个数量级。关键差异在于：

1. **自动驾驶有统一标准**（L0-L5），Phone Use 没有。每个团队定义自己的"成功"，互相无法比较。
2. **自动驾驶积累了亿级真实数据**，Phone Use 的真实操作数据极少。PhoneWorld 从 34 个 App 收集的轨迹数据已经是目前最好的了。
3. **自动驾驶的容错是渐进式的**（滑出车道 vs 碰撞），Phone Use 的容错是二元的（点了错误的按钮可能直接支付）。

**我认为 Phone Use 两年内的正确预期是**：
- ❌ 不要期待「通用手机 Agent」——能做所有 App 的所有操作
- ✅ 可以期待「垂直场景专用 Agent」——比如只做外卖下单、只做微信客服、只做小红书发布
- ✅ Phone Use 的最大价值可能不在面向消费者，而在**App 自动化测试**和**企业内部自动化**

## 七、实用建议

### 7.1 如果你想今天就用 Phone Use

| 需求 | 推荐 | 理由 |
|------|------|------|
| 在手机上尝试 | OpenOmniBot | 唯一可直接安装的 APK，有中文社区 |
| 做研究/评测 | MobileGym | 浏览器打开即用，有确定性 Bench |
| 搭建自动化平台 | OpenGUI + Claude Code | 架构最清晰，可通过 Discord/飞书远程操控 |
| 训练自己的 Agent | PhoneWorld（关注开源进展） | 最大规模的仿真数据集，但目前未完全开源 |

### 7.2 如果你要做 Phone Use 开发

关键决策点：

1. **选 Android 还是 iOS？** → **Android**。iOS 没有 AccessibilityService 等价物，无法做通用 GUI Agent。Apple 的 App Intents 是封闭生态。
2. **用截图还是无障碍树？** → **两者结合**。纯截图太慢，纯无障碍树太脆弱。PhoneHarness 的混合路线最优。
3. **云端还是端侧？** → 取决于延迟要求。云端模型（GPT-4o、Claude）能力更强但延迟高；端侧模型（Qwen3-VL）延迟低但准确率差 3-5 倍。

## 八、参考文献

| 论文/项目 | 链接 |
|-----------|------|
| OS Agents: A Survey (ACL 2025 Oral) | [arXiv:2508.04482](https://arxiv.org/abs/2508.04482) |
| PhoneWorld: Scaling Phone-Use Agent Environments | [arXiv:2605.29486](https://arxiv.org/abs/2605.29486) |
| PhoneHarness: Mixed GUI, CLI, and Tool Actions | [arXiv:2606.14832](https://arxiv.org/abs/2606.14832) |
| OmegaUse: General-Purpose GUI Agent | [arXiv:2601.20380](https://arxiv.org/abs/2601.20380) |
| MobileGym: Verifiable Simulation Platform | [mobilegym.dev](https://mobilegym.dev) |
| Darwin Mobile Agent: Self-Evolution Roadmap | [arXiv:2606.20622](https://arxiv.org/abs/2606.20622) |
| GoClick: Lightweight Element Grounding | [arXiv:2604.23941](https://arxiv.org/abs/2604.23941) |
| CAPED: Privacy for Mobile GUI Agents | [arXiv:2606.12666](https://arxiv.org/abs/2606.12666) |
| InfiGUIAgent: Native Reasoning | [arXiv:2501.04575](https://arxiv.org/abs/2501.04575) |
| CRAB: Cross-environment Benchmark (ACL 2025) | [arXiv:2407.01511](https://arxiv.org/abs/2407.01511) |
| OpenOmniBot | [github.com/omnimind-ai/OpenOmniBot](https://github.com/omnimind-ai/OpenOmniBot) |
| OpenGUI | [github.com/Core-Mate/OpenGUI](https://github.com/Core-Mate/OpenGUI) |
| Anthropic: Developing a Computer Use Model | [anthropic.com/news/developing-computer-use](https://www.anthropic.com/news/developing-computer-use) |
---

*本报告基于 2026 年 6 月 30 日的公开信息。Phone Use 领域发展极快，建议在一个月内回看。*
