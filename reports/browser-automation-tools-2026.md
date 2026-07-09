# 浏览器操作插件/工具生态调研报告

> 调研日期：2026-07-08 | 覆盖范围：传统框架、AI-Native 工具、MCP/CLI、浏览器扩展、隐身浏览器、数据抓取、云平台

---

## 一、全景概览

浏览器操作工具正在经历从「脚本驱动」到「AI 驱动」的代际转换。2025-2026 年涌现了大量 AI-Native 工具，核心趋势是：**让 LLM 直接控制浏览器，用自然语言替代 CSS/XPath 选择器**。

整个生态可以分为 7 个层次：

| 层次 | 代表工具 | 核心能力 |
|------|---------|---------|
| 底层驱动 | Selenium / Puppeteer / Playwright | CDP/WebDriver 协议封装 |
| AI 操作 | Browser Use / Stagehand / Skyvern | LLM 直接操控浏览器 |
| Agent 协议 | Playwright MCP / Browser Use CLI | 为 AI Agent 提供的标准化接口 |
| 浏览器扩展 | Nanobrowser | Chrome 插件，对标 OpenAI Operator |
| 隐身反检测 | Camoufox | 绕过 Cloudflare / 反爬 |
| 数据抓取 | Crawl4AI / AgentQL | LLM 友好的网页转结构化数据 |
| 云托管 | Browserbase / Browser Use Cloud | 隐身浏览器+代理+验证码 |

**我的判断**：2026 年这个领域处于快速整合期。传统框架（Playwright/Selenium）是基石不会消失，但 AI-Native 层（Browser Use/Stagehand）正在成为开发者首选的抽象层。MCP/CLI 工具解决了「Agent 如何标准化调用浏览器」的问题，是生态的关键胶水。

---

## 二、传统浏览器自动化框架

### 2.1 三巨头对比

| 特性 | Selenium | Puppeteer | Playwright |
|------|----------|-----------|------------|
| 维护方 | SeleniumHQ | Google | Microsoft |
| GitHub Stars | 31k+ | 90k+ | 72k+ |
| 语言支持 | Java/Python/JS/C#/Ruby | JS/TS | JS/Python/Java/.NET |
| 浏览器 | Chrome/Firefox/Edge/Safari | Chrome/Chromium | Chromium/Firefox/WebKit |
| 协议 | WebDriver (W3C) | CDP | CDP |
| 自动等待 | ❌ 需手动 | ❌ 需手动 | ✅ 内置 |
| 测试隔离 | 弱 | 中 | 强 (Browser Context) |
| AI 集成 | 无 | 无 | MCP + CLI + SKILL |

**我的判断**：Playwright 已成事实标准。它的多浏览器支持、自动等待、Browser Context 隔离、以及微软近期大力投入的 MCP/CLI/SKILL 生态，让它从「测试框架」进化为「AI Agent 浏览器平台」。Selenium 仍然大量用于存量企业项目，但在新项目中份额持续下降。Puppeteer 被 Playwright 挤压严重，主要靠 Google 生态留存。

---

## 三、AI-Native 浏览器操作工具

这是目前最活跃的领域，让 LLM 直接理解网页并执行操作。

### 3.1 Browser Use ⭐ 最热门

| 项目 | 详情 |
|------|------|
| 仓库 | [browser-use/browser-use](https://github.com/browser-use/browser-use) |
| 语言 | Python |
| 协议 | MIT 开源 |
| 核心思路 | Playwright 之上包装 Agent 层，LLM 输出结构化操作指令 |

**关键特性**：
- `Agent(task="...", llm=...)` 一行代码启动
- 支持 OpenAI/Anthropic/Google/自有优化模型 `bu-*`
- CLI 3.0：命令式 Python 接口，Agent 直接写代码操控浏览器
- Cloud：隐身浏览器 + 代理轮换 + 验证码破解
- 自有 benchmark：100 个真实任务评估

**我的评价**：Python 生态的首选。CLI 3.0 的「命令式 Python」理念值得注意——他们认为最新的模型不需要过度抽象，直接给 Agent 自由写代码比限定一套 tool schema 更高效。这跟微软 Playwright CLI 的思路一致（见后文）。Cloud 版的准确率显著高于开源版（模型优化 + 反检测）。

### 3.2 Stagehand — 代码与 AI 的混合

| 项目 | 详情 |
|------|------|
| 仓库 | [browserbase/stagehand](https://github.com/browserbase/stagehand) |
| 语言 | TypeScript（有 Python 移植版） |
| 维护方 | Browserbase |
| 核心思路 | 可选：用代码做确定性操作，用 AI 做不确定性探索 |

**关键特性**：
- `stagehand.act("click on the login button")` — 自然语言操作
- `stagehand.extract("...", zodSchema)` — 结构化提取
- `stagehand.agent().execute("...")` — 多步任务
- **自愈缓存**：AI 执行过一次的路径自动缓存，下次不跑 LLM
- 网站变化时自动重新推理

**我的评价**：JS/TS 生态的最佳选择。自愈缓存是一个聪明的设计——解决了「AI 很贵且慢」的核心痛点。让开发者在「确定性代码」和「AI 灵活性」之间自由切换，而不是二选一。Browserbase 云平台提供隐身浏览器 + 代理。

### 3.3 Skyvern — 计算机视觉路线

| 项目 | 详情 |
|------|------|
| 仓库 | [Skyvern-AI/skyvern](https://github.com/Skyvern-AI/skyvern) |
| 语言 | Python |
| 核心思路 | 用 Vision LLM 理解页面截图，不依赖 DOM |

**关键特性**：
- Playwright 扩展：`page.act("...")` / `page.extract("...")` 直接在 page 对象上
- 纯视觉路线：不被 DOM 结构变化影响
- WebVoyager benchmark 达到 85.8%
- 支持 no-code 工作流构建器

**我的评价**：视觉路线的最大优势是**抗 DOM 变化**——网站改版不会让脚本崩溃。但代价是慢（每步都要 LLM 推理图片）和贵（视觉 tokens 消耗大）。适合「对稳定性要求极高、操作步骤少」的场景（如表单填写、保险理赔）。

### 3.4 其他值得关注的

| 工具 | Stars | 特色 |
|------|-------|------|
| AgentQL | 1.4k | AI 查询语言 + Playwright，声明式提取 |
| Notte | 2.0k | 无服务器部署，浏览器函数 |
| Magnitude Browser Agent | 4.1k | Vision-first，开源 |

---

## 四、MCP/CLI — AI Agent 的标准化接口

### 4.1 Playwright MCP (Microsoft)

| 项目 | 详情 |
|------|------|
| 仓库 | [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) |
| 协议 | MCP (Model Context Protocol) |
| 核心思路 | 用 Accessibility Tree 而非截图，让 LLM 高效理解页面 |

**关键设计决策**：
- **不用视觉模型**：通过结构化 accessibility snapshot，不需要昂贵的视觉 tokens
- 工具是确定性的（click/fill/navigate），避免截图方式的歧义
- 支持所有主流 Agent：Claude Code、Codex、Cursor、Copilot、Gemini CLI...

**微软同时推出了 Playwright CLI + SKILL**，理由是：MCP 加载大量 tool schema 和 accessibility tree 进入 context 太耗 token；CLI 命令更紧凑，通过 SKILL 文件告诉 Agent 如何调用。微软明确建议 coding agent 用 CLI，exploratory agent 用 MCP。

### 4.2 agent-browser (Vercel)

| 项目 | 详情 |
|------|------|
| 仓库 | [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser) |
| 语言 | Rust 原生 CLI |
| Stars | 38k ⭐ |

Rust 编译的极速 CLI，<1ms 启动。用法类似 Playwright CLI 但更轻量：
```bash
agent-browser open example.com
agent-browser snapshot          # accessibility tree
agent-browser click @e2         # 按 ref 点击
agent-browser fill @e3 "text"
```

**我的评价**：Vercel 出品，38k stars 反映了社区对这个方向的热情。纯 CLI 模式避免了 MCP 的 token 开销，跟微软 Playwright CLI 思路一致。Rust 二进制意味着极快的冷启动。

### 4.3 Browser Use CLI 3.0

命令式 Python 接口。Agent 直接写 Python 代码控制浏览器：
```python
browser-use <<'PY'
new_tab("https://example.com")
print(page_info())
PY
```
内置 Claude Code / Codex skill 安装指引。

---

## 五、浏览器扩展（Chrome 插件）

### 5.1 Nanobrowser ⭐ 最符合「插件」定义

| 项目 | 详情 |
|------|------|
| 仓库 | [nanobrowser/nanobrowser](https://github.com/nanobrowser/nanobrowser) |
| Stars | 13.4k |
| 安装 | [Chrome Web Store](https://chromewebstore.google.com/detail/nanobrowser/imbddededgmcgfhfpcjmijokokekbkal) |

**这是最字面意义上的「浏览器操作插件」**——一个 Chrome/Edge 扩展，安装后在侧边栏提供 AI 操作界面：

- **多 Agent 系统**：Planner（规划）+ Navigator（执行）两个 LLM 分工
- **100% 本地**：不经过任何云服务，隐私安全
- **免费**：只需要你自己的 LLM API key
- **对标 OpenAI Operator**：功能类似但完全开源免费
- **支持多种 LLM**：OpenAI, Anthropic, Gemini, Ollama, Groq 等

**使用场景**：在浏览器里直接给 AI 下指令——「帮我在淘宝搜索 XX 并比价」「自动填这个表单」「从这 10 个页面提取摘要」。

**我的评价**：如果你的需求是「在浏览器里有个 AI 助手帮你操作网页」，这是最直接的方案。安装即用，不需要写代码。但灵活性受限于浏览器扩展的沙盒。

---

## 六、隐身/反检测浏览器

### 6.1 Camoufox

| 项目 | 详情 |
|------|------|
| 仓库 | [daijro/camoufox](https://github.com/daijro/camoufox) |
| 语言 | Python |
| 核心 | Firefox 魔改，反指纹+绕过 Cloudflare |

**关键能力**：
- 模拟真实浏览器的几十个指纹维度（WebGL、canvas、字体、时区...）
- Playwright 兼容 API：`from camoufox import Camoufox`
- 自带上千个真实浏览器指纹库
- 支持代理轮换

**我的评价**：如果你需要爬取被严格反爬的网站（Cloudflare 盾、DataDome 等），这是开源最佳选择。但注意它是 Firefox 魔改，不是 Chromium——某些只兼容 Chrome 的网站会有问题。项目声明「仍在开发中，不适合稳定生产」。

---

## 七、数据抓取工具

### 7.1 Crawl4AI

| 项目 | 详情 |
|------|------|
| 仓库 | [unclecode/crawl4ai](https://github.com/unclecode/crawl4ai) |
| Stars | 50k+ |
| 核心 | 网页 → 干净 Markdown，为 LLM 优化 |

**关键特性**：
- 输出 LLM 友好的 Markdown（含标题、表格、引用）
- 异步浏览器池，支持深度爬取（BFS/DFS）
- BM25 算法过滤无关内容
- LLM 驱动的结构化提取
- CLI：`crwl https://example.com -o markdown`

**我的评价**：如果你不关心浏览器操作本身、只关心「把网页内容喂给 LLM」，Crawl4AI 是最佳选择。50k stars，社区活跃。但它是一个 crawler，不是 browser agent——它不能登录、填表、点击。

---

## 八、云平台

### 8.1 Browserbase

Stagehand 背后的基础设施。提供：
- 隐身 Chromium 浏览器实例
- 代理轮换
- 验证码绕过
- 按 Browser Session 计价

### 8.2 Browser Use Cloud

提供托管 Agent + 隐身浏览器，比开源版准确率高（模型优化 + 反检测）。

**我的评价**：这类云平台解决的是「自己部署隐身浏览器的运维噩梦」。如果项目需要规模化运行，云平台比自建更划算——一个隐身浏览器池的维护成本远超云服务费。

---

## 九、核心对比矩阵

| 维度 | Browser Use | Stagehand | Skyvern | Playwright MCP | Nanobrowser | Camoufox |
|------|------------|-----------|---------|---------------|-------------|----------|
| 类型 | AI Agent | AI 混合 | Vision Agent | Agent 协议 | 浏览器扩展 | 隐身浏览器 |
| 语言 | Python | TS | Python | 协议无关 | JS | Python |
| 依赖 | Playwright | Playwright | Playwright | Playwright | 浏览器扩展API | Firefox |
| 视觉/结构 | 结构 | 结构 | 视觉 | 结构 | 结构 | 结构 |
| 反检测 | Cloud 版有 | Browserbase 有 | Cloud 版有 | 无 | 浏览器自身 | ✅ 核心功能 |
| 开源 | ✅ MIT | ✅ MIT | ✅ AGPL | ✅ Apache 2 | ✅ | ✅ |
| 适合场景 | Python项目AI自动化 | TS项目混合编程 | 抗DOM变化的稳定操作 | Agent标准化接口 | 个人日常浏览器AI助手 | 反爬场景 |
| 学习曲线 | 低 | 中 | 低 | 低 | 极低 | 中 |

---

## 十、场景推荐

### 按使用场景推荐

| 场景 | 推荐工具 | 理由 |
|------|---------|------|
| **给 Claude Code 加浏览器能力** | Playwright MCP 或 Browser Use CLI | 标准化接口，Claude Code 原生支持 |
| **个人日常浏览器自动化** | Nanobrowser | 安装即用，不需要写代码 |
| **Python 项目集成** | Browser Use | 生态最好，文档完善 |
| **TS/JS 项目集成** | Stagehand | 自愈缓存省 token |
| **爬取反爬严格的网站** | Camoufox + Crawl4AI | 隐身 + 提取 |
| **批量抓取转 Markdown** | Crawl4AI | 专为此场景优化 |
| **表单填写/保险理赔等稳定操作** | Skyvern | 视觉路线抗 DOM 变化 |
| **不想管基础设施** | Browser Use Cloud 或 Browserbase | 隐身浏览器+代理全托管 |

### 按技术栈推荐

| 技术栈 | 首选 |
|--------|------|
| Python + AI | Browser Use |
| TypeScript + AI | Stagehand |
| 纯前端/Chrome 扩展 | Nanobrowser |
| AGENT SDK 集成 | Playwright MCP |
| 极致性能 CLI | agent-browser (Vercel) |

---

## 十一、趋势判断与批判性分析

### 11.1 我认为正在发生的关键转变

1. **从「选择器」到「意图」**：不再写 `.class > div:nth-child(3)`，而是说「点击登录按钮」。这是质变。

2. **CLI > MCP**：微软和 Vercel 都选择了 CLI 路线而非 MCP 路线（给 coding agent 用）。原因很简单——MCP 的 tool schema 和 accessibility snapshot 太大了，对于需要管理大量代码上下文的 coding agent 来说 token 太贵。CLI 是紧凑命令，Agent 在需要时才调用。

3. **命令式 > 声明式**：Browser Use CLI 3.0 的核心理念——让 Agent 直接写 Python 代码操控浏览器，而不是通过预定义的 tool。这跟 Anthropic 的「模型能力越强、抽象越少」理念一致。

### 11.2 我不太看好的方向

- **纯视觉路线（Skyvern）** 作为通用方案的局限性：每步推理一张截图成本太高。只在「DOM 极度不稳定」的场景（如老旧政府网站、企业内部系统）有价值。
- **Selenium 的 AI 化**：Selenium 社区太大太慢，AI 集成需要框架级重构。Playwright 已先发制人。

### 11.3 值得关注的新趋势

- **Agent Skill 标准化**：Browser Use 和 Playwright 都提供了「把浏览器能力打包成 skill 给 coding agent」的机制。这可能是下一个标准化方向。
- **自愈自动化**：Stagehand 的缓存+自愈模式——跑过一次的操作用缓存，网站变了自动重新推理。这解决了 AI 自动化「又贵又慢」的致命弱点。

---

## 十二、给 Hermes 用户的具体建议

如果你想让 Hermes（或 Claude Code）获得浏览器操作能力：

### 方案 A：Playwright MCP（推荐起步）
```bash
# Claude Code
claude mcp add playwright npx @playwright/mcp@latest

# Hermes
# 在 config.yaml 中添加 MCP server 配置
```

### 方案 B：Browser Use CLI（更灵活）
```bash
pip install browser-use
# 然后 Agent 可以直接写 Python 操控浏览器
```

### 方案 C：Nanobrowser（个人日常用）
直接从 [Chrome Web Store](https://chromewebstore.google.com/detail/nanobrowser/imbddededgmcgfhfpcjmijokokekbkal) 安装，在浏览器里直接使用。

---

*报告完成。如有具体场景需要深入调研，可以进一步展开。*
