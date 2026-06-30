# X-PLUG/MobileAgent 深度调研报告

> **调研日期**: 2026-06-30  
> **来源**: GitHub 仓库分析 (x-plug/mobileagent, 8,892 ⭐) + 论文 (arxiv)  
> **团队**: 阿里巴巴通义实验室 (Tongyi Lab, Alibaba Group)  
> **许可证**: MIT

---

## 1. 项目概览

X-PLUG/MobileAgent 是阿里通义实验室推出的 **GUI Agent 家族**，从 2024 年初发展至今，经历了 v1 → v2 → v3 → v3.5 四个大版本迭代，每个版本都有顶会论文背书。与 DroidRun/MobileRun 不同，MobileAgent 的核心思路是「**训练专用的 GUI 视觉语言模型**」（GUI-Owl 系列），而不是调用通用 LLM。

项目获得 **8,892 ⭐**，论文发表于 ICLR Workshop、NeurIPS、ACL 等顶会，是学术界 + 工业界双重认可的标杆项目。

| 维度 | 数据 |
|------|------|
| 仓库 | X-PLUG/MobileAgent (8,892 ⭐, 894 forks) |
| 团队 | Alibaba Tongyi Lab |
| 仓库体积 | 473 MB（含模型权重等大文件） |
| 许可证 | MIT |
| 最新版本 | v3.5 (GUI-Owl 1.5, 2026.02) |
| 底层模型 | Qwen3-VL 系列 |
| 支持平台 | Android · HarmonyOS · Desktop(PC) · Browser |

## 2. 版本演进

MobileAgent 的迭代路径清晰，每个版本都有明确的创新点：

| 版本 | 时间 | 发表 | 核心创新 |
|------|------|------|---------|
| v1 | 2024.01 | ICLR 2024 Workshop | 单 Agent 多模态手机操作 |
| v2 | 2024.06 | **NeurIPS 2024** | 多 Agent 协作架构 |
| v3 | 2025.08 | Preprint | GUI-Owl 模型 + 跨平台多 Agent |
| v3.5 | 2026.02 | Preprint | GUI-Owl 1.5：原生多平台 + Tool/MCP + 长程记忆 |

此外还有多个子项目：
- **Mobile-Agent-E**：自我进化（Self-Evolving）的手机操作 Agent
- **GUI-Critic-R1**：操作前错误诊断（**NeurIPS 2025**）
- **PC-Agent**：PC 桌面操作（ICLR 2025 Workshop）
- **UI-S1**：半在线强化学习（**ACL 2026**）
- **ToolCUA**：端到端 GUI 工具编排（2026.05）

## 3. 核心架构：模型 vs 框架

MobileAgent-v3.5 与 DroidRun/MobileRun 的**根本设计哲学不同**：

| 维度 | X-PLUG/MobileAgent | DroidRun/MobileRun |
|------|-------------------|-------------------|
| 核心思路 | 训练专用 GUI-VLM | 通用 LLM + 工具框架 |
| 模型依赖 | GUI-Owl 1.5（专用模型） | OpenAI/Claude/Gemini 等通用模型 |
| UI 感知 | 纯视觉（截图 + 坐标标注） | a11y tree + 截图降级 |
| 坐标系统 | 归一化 0-1000 | 绝对像素 / a11y 索引 |
| Agent 架构 | 端到端（模型即 Agent） | 多 Agent 工作流 |
| 部署难度 | 需 GPU 部署模型 | 需 Portal App + ADB |
| 平台覆盖 | Android/鸿蒙/PC/Browser | Android/iOS |

**v3.5 的架构层次**：

```
GUI-Owl 1.5 模型（核心）
├── 端到端模式：模型直接输出 <tool_call> 动作
└── 多 Agent 模式：Planner / Executor / Verifier / Notetaker
```

**执行流程**（端到端模式）：
1. 截图 → 2. 调用 GUI-Owl 1.5 → 3. 解析 `<tool_call>` → 4. 坐标转换 → 5. ADB 执行 → 6. 循环

支持的 Action 类型：`click`, `long_press`, `type`, `scroll/swipe`, `system_button`(Back/Home), `wait`, `open`, `terminate`, `answer`, `call_user`

## 4. GUI-Owl 1.5 模型家族

GUI-Owl 1.5 是 MobileAgent-v3.5 的核心驱动力，基于 Qwen3-VL 训练，专门为 GUI 自动化的视觉理解和操作优化。

| 模型 | 参数量 | 特点 | HF 链接 |
|------|--------|------|---------|
| GUI-Owl-1.5-2B-Instruct | 2B | 轻量推理 | 🤗 |
| GUI-Owl-1.5-4B-Instruct | 4B | 平衡性能 | 🤗 |
| GUI-Owl-1.5-8B-Instruct | 8B | 主力模型 | 🤗 |
| GUI-Owl-1.5-8B-Thinking | 8B | 思考变体 | 🤗 |
| GUI-Owl-1.5-32B-Instruct | 32B | 最强性能 | 🤗 |
| GUI-Owl-1.5-32B-Thinking | 32B | 最强思考 | 🤗 |

**关键能力**：
- 🏆 **20+ GUI 基准 SOTA**：OSWorld、AndroidWorld、Mobile-World、WindowsAA、ScreenSpot-v2/Pro
- 🔧 **原生 Tool/MCP 调用**：不需外部编排，模型自己决定何时调用工具
- 🧠 **长程记忆**：内置记忆能力，不依赖外部工作流（MemGUI-Bench 领先）
- ⚡ **Instruct/Thinking 双变体**：小模型快速推理，大模型复杂规划

**坐标系统**：输出 0-1000 归一化坐标，支持跨分辨率部署。

## 5. 多平台支持

v3.5 是目前覆盖平台最广的 GUI Agent 框架之一：

| 平台 | 模块路径 | 控制方式 | 成熟度 |
|------|---------|---------|--------|
| Android | `mobile_use/` | ADB | 成熟 |
| HarmonyOS | (v3 支持) | HDC | 可用 |
| Desktop/PC | `computer_use/` | pyautogui | 可用 |
| Browser | `browser_use/` | Playwright | 可用 |
| iOS | ❌ 暂不支持 | - | - |

**Android 部署关键步骤**：
1. 安装 ADB + 开启 USB 调试
2. 安装 ADB Keyboard APK
3. 部署 GUI-Owl 1.5 模型（本地 GPU 或 vLLM API）
4. 运行 `run_gui_owl_1_5_for_mobile.py`

**云服务方案**：阿里云提供了 Bailian（百炼）在线 API 和无影云手机，可直接云端使用，无需本地部署模型。

## 6. 内置应用知识库

MobileAgent 内建了 **超 100 个流行 App 的包名映射**（`packages.py`），覆盖：
- **国内主流**：微信、QQ、微博、淘宝、京东、拼多多、小红书、抖音、快手、B站、美团、饿了么……
- **国际应用**：WhatsApp、Telegram、Reddit、Twitter/X、Duolingo、Booking……
- **系统应用**：Settings、Chrome、Gmail、Google Maps……

这是相比 DroidRun 的显著优势——直接了解国产应用的包名和别名，减少模型推理负担。

## 7. 性能对比

MobileAgent-v3.5（GUI-Owl 1.5-8B）在主要基准上的表现：

| 基准 | 平台 | 成绩 | 备注 |
|------|------|------|------|
| AndroidWorld | Mobile | SOTA | Android 系统任务 |
| Mobile-World | Mobile | SOTA | 工具调用 |
| OSWorld | PC | SOTA | 桌面操作 |
| ScreenSpot-v2 | 跨平台 | SOTA | GUI 元素定位 |
| MemGUI-Bench | 跨平台 | SOTA | 长程记忆 |
| OSWorld-MCP | PC | top | MCP 工具调用 |

**与 DroidRun 的对比**：DroidRun 在 AndroidWorld 上 91.4%（使用 GPT-5 + a11y tree），MobileAgent-v3.5 使用自己的 8B 模型也达到 SOTA。两者方法不同但成绩接近，说明两条路线都是可行的。

## 8. 批判性分析

### 优势
1. **学术顶会认证**：NeurIPS ×2、ICLR Workshop ×2、ACL 2026，学术质量有保障
2. **模型原生能力**：GUI-Owl 是专门训练的 GUI VLM，不是靠 prompt engineering 凑出来的方案
3. **多平台覆盖**：Android + 鸿蒙 + PC + Browser，是国内最全面的方案
4. **中国 App 生态适配**：内置 100+ 国产应用包名映射，开箱即用
5. **阿里云生态**：Bailian API + 无影云手机，商业化路径清晰
6. **端到端简单**：不需安装 Portal App，只需 ADB + ADB Keyboard

### 潜在问题
1. **模型部署门槛高**：需要 GPU 部署 GUI-Owl 模型（8B+ 参数），或用阿里云 API
2. **纯视觉方案局限**：完全依赖截图进行 UI 理解，对复杂页面可能产生误判
3. **不支持 iOS**：在官方文档中明确标注暂不支持
4. **模型依赖阿里生态**：GUI-Owl 基于 Qwen3-VL，API 由阿里云提供
5. **端到端 vs 多 Agent 模糊**：文档同时描述两种模式，但实际代码以端到端为主，多 Agent 模式的成熟度存疑
6. **仓库体积大**：473MB 无法快速 clone（超时），给源码分析带来阻碍

### 对 Hermes 生态的建议
- **MobileAgent vs DroidRun 选型**：
  - 选 MobileAgent：如果需要**纯视觉方案**、想用**开源模型**部署、需要**中国 App 生态**适配
  - 选 DroidRun：如果需要**通用 LLM 灵活性**、需要 **a11y tree 优化**、需要 **iOS 支持**
- **短期**：通过阿里云 Bailian API 快速体验 GUI-Owl 1.5，不需本地 GPU
- **中期**：如果方向验证可行，考虑将 GUI-Owl 1.5 集成到 Hermes 的工具链中（作为视觉 Agent 的底层引擎）

---

> **注意**：由于仓库体积过大（473MB），源码未完整 clone 到本地。以上分析基于 GitHub API 文件树 + 关键源文件（`run_gui_owl_1_5_for_mobile.py`, `packages.py`, README 等）的在线读取。
