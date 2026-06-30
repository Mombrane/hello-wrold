# oh-my-pi (omp) 深度调研报告

> 调研日期：2026-06-30 | 来源：GitHub API、omp.sh、项目 README、源码仓结构
> 仓库：https://github.com/can1357/oh-my-pi

---

## 一、项目概览

**oh-my-pi**（CLI 命令 `omp`，名称致敬 oh-my-zsh）是当前 GitHub 上最强大的终端 AI 编码 agent 之一。

| 指标 | 数值 |
|------|------|
| ⭐ Stars | **15,211** |
| 🍴 Forks | 1,347 |
| 📅 创建时间 | 2025-12-31（仅 6 个月前！） |
| 🔄 最后推送 | 2026-06-30（当天） |
| 🐛 Open Issues | 424 |
| 📝 语言 | TypeScript + Rust |
| ⚡ 运行时 | Bun ≥ 1.3.14 |
| 📄 License | MIT |
| 🏠 官网 | https://omp.sh |
| 💬 Discord | discord.gg/4NMW9cdXZa |

**一句话定位**：A coding agent with the IDE wired in —— 把 IDE 的能力全部内置到终端 agent 中。

**项目渊源**：Fork 自 [Mario Zechner](https://github.com/mariozechner)（libGDX 作者）的 [Pi](https://github.com/badlogic/pi-mono)，由 [Can Bölük](https://github.com/can1357) 大幅扩展为面向编码的全功能 agent。

---

## 二、核心架构

### 2.1 技术栈

```
┌─────────────────────────────────────────────┐
│              TypeScript (Bun)                │
│  ┌──────────┐ ┌────────┐ ┌──────────────┐   │
│  │ pi-agent │ │ pi-tui │ │ pi-coding    │   │
│  │ -core    │ │        │ │ -agent (CLI) │   │
│  └──────────┘ └────────┘ └──────────────┘   │
│                     │                        │
│              N-API Bindings                  │
│                     │                        │
│  ┌─────────────────────────────────────┐     │
│  │     Rust (~55,000 lines)            │     │
│  │  ┌────────┐ ┌───────┐ ┌──────────┐ │     │
│  │  │pi-shell│ │pi-ast │ │pi-natives│ │     │
│  │  │(brush) │ │(tree- │ │(grep,    │ │     │
│  │  │        │ │sitter)│ │highlight)│ │     │
│  │  └────────┘ └───────┘ └──────────┘ │     │
│  │  ┌────────┐                        │     │
│  │  │pi-iso  │ (workspace isolation)  │     │
│  │  └────────┘                        │     │
│  └─────────────────────────────────────┘     │
└─────────────────────────────────────────────┘
```

**关键设计决策**：所有传统 agent 需要 fork/exec 外部命令的操作（grep、find、shell、语法高亮等），omp 全部在进程内通过 Rust 原生完成。Windows 原生支持，无需 WSL。

### 2.2 Monorepo 结构

| 包名 | 功能 |
|------|------|
| `@oh-my-pi/pi-coding-agent` | CLI 入口 + SDK |
| `@oh-my-pi/pi-agent-core` | Agent 运行时、工具调用、状态管理 |
| `@oh-my-pi/pi-ai` | 多供应商 LLM 客户端 |
| `@oh-my-pi/pi-catalog` | 模型目录数据库 |
| `@oh-my-pi/pi-tui` | 终端 UI 库（差分渲染） |
| `@oh-my-pi/pi-natives` | N-API 原生绑定 |
| `@oh-my-pi/hashline` | Hash 锚定补丁语言 |
| `@oh-my-pi/pi-mnemopi` | SQLite 记忆引擎 |
| `@oh-my-pi/snapcompact` | 上下文压缩引擎 |
| `@oh-my-pi/swarm-extension` | Swarm 集群扩展 |
| `@oh-my-pi/collab-web` | 协作浏览器客户端 |

---

## 三、核心特性（20 大亮点）

### 01 · 双内核代码执行（eval）
持久化 Python（子进程）+ Bun Worker 双执行环境。两个内核可以**通过 loopback bridge 回调 agent 工具**（read、search、task）。Agent 在 Python 里加载 CSV、在 JS 里画图，全程不出一个 cell。

### 02 · LSP 深度集成
14 种 LSP 操作，53 种语言。重命名走 `workspace/willRenameFiles`，re-export 和 barrel 文件自动更新。IDE 知道的一切，agent 全知道。

### 03 · 真实调试器（DAP）
28 种 DAP 操作，14 个适配器（lldb-dap、dlv、debugpy 等）。C 程序 segfault？lldb 附加、单步到野指针、读栈帧。Go 服务卡死？dlv 遍历 goroutine。Python 卡住？debugpy 暂停、检查、求值。

### 04 · 时间旅行流规则（TTSR）
规则在模型「越界」时才触发——正则匹配到流中的内容后**中断流、注入系统提醒、从断点重试**。零上下文开销，注入在压缩后存活。

### 05 · 一流子代理（subagents）
`task` 工具扇出到隔离 worktree 的子代理，8 种隔离后端（APFS clone、btrfs/zfs reflink、overlayfs 等）。子代理通过 IRC 通道通信，返回 schema 校验的结构化结果。

### 06 · 顾问模式（Advisor）
第二个模型以 advisor 角色**监视主 agent 的每一步**，注入旁注（aside/concern/blocker）。主 agent 看到后自行纠偏，或向用户解释为什么不改。

### 07 · 协作会话（Collab）
`/collab` 生成链接 + QR 码。队友 `omp join` 接入或浏览器打开。读写/只读两种模式，AES-256-GCM 端到端加密，中继看不到密钥。

### 08 · 网络搜索 + 智能提取
18 个搜索后端（自动链式 fallback）。arXiv PDF、GitHub 页面、Stack Overflow 全部转为带锚点的结构化 markdown。

### 09 · 全 Rust 原生
ripgrep、glob、find、bash（brush-shell）、语法高亮、图片解码——全部进进程，零 fork/exec。macOS/Linux/Windows 同二进制。

### 10 · 代码审查（/review）
P0–P3 优先级 + 置信度打分。专用审查子代理并行扫描分支、commit 或未提交变更。

### 11 · Hashline 编辑格式
基于内容 hash 锚定的编辑，替代传统的字符串替换。Grok 4 Fast **输出 token 减少 61%**，Grok Code Fast 编辑准确率从 **6.7% → 68.3%**。

### 12 · GitHub 作为文件系统
PR 是路径（`pr://1428`），Issue 是路径。`read`、`search` 统一接口操作，无需专用 gh 工具。

### 13 · Hindsight 记忆系统
Agent 跨会话记忆代码库。`retain` 写入、`recall` 检索、`reflect` 综合回答。项目级隔离。

### 14 · ACP 编辑器协议
Zed 等编辑器通过 ACP over JSON-RPC 驱动 omp。工具 I/O 走编辑器，写操作由 `session/request_permission` 门控。

### 15 · 原生兼容其他 agent 配置
自动继承 `.claude`、`.cursor`、`.windsurf`、`.gemini`、`.codex`、`.cline`、`.github/copilot`、`.vscode` 的 rules/skills/MCP 服务器配置。零迁移。

### 16 · omp commit：原子拆分
读取工作树变更，按依赖关系拆分为原子 commit。源码 > 测试 > 文档的优先级排序，锁文件自动排除。

### 17 · 内部 URI 方案
12 种内部 scheme（`pr://`、`issue://`、`agent://`、`skill://`、`rule://`）在任何 FS 工具中透明解析。`agent://<id>/findings.0.path` 直接提取子代理输出。

### 18 · 冲突解决
合并冲突变成 URL。`conflict://N` 写入 `@theirs`/`@ours`/`@base`。批量：`conflict://*`。

### 19 · AST 编辑 + 预览-确认
`ast_edit` 通过 ast-grep（50+ tree-sitter 语法）做结构化重写。先预览（卡片显示替换数），`resolve` 确认后原子提交。

### 20 · 真实浏览器（或 Slack）
Puppeteer over headless Chromium。Stealth 默认开启。同一 API 可驱动任何 Electron 应用——指向 Slack 就能读 DM。

---

## 四、工具矩阵（32 个内置工具）

### 文件 & 搜索
| 工具 | 能力 |
|------|------|
| `read` | 文件/目录/归档/SQLite/PDF/Notebook/URL/内部 `://` scheme |
| `write` | 创建或覆盖 |
| `edit` | Hashline 补丁，hash 锚定 + 过期恢复 |
| `ast_edit` | ast-grep 结构化重写 |
| `ast_grep` | 50+ 语法结构查询 |
| `search` | 正则搜索 |
| `find` | Glob 路径查找 |

### 运行时
| 工具 | 能力 |
|------|------|
| `bash` | 工作区 shell（PTY/后台可选） |
| `eval` | 持久化 Python/JS cell + 共享 prelude + 工具回调 |
| `ssh` | 远程命令 |

### 代码智能
| 工具 | 能力 |
|------|------|
| `lsp` | 诊断/导航/符号/重命名/代码操作 |
| `debug` | DAP 驱动调试 |

### 协调
| 工具 | 能力 |
|------|------|
| `task` | 并行子代理扇出 |
| `irc` | 代理间短消息 |
| `todo` | 有序 todo 列表 + 阶段追踪 |
| `job` | 等待/取消后台任务 |
| `ask` | 结构化交互提问 |

### 外部
| 工具 | 能力 |
|------|------|
| `browser` | Puppeteer/Chromium/CDP |
| `web_search` | 18 后端链式搜索 |
| `github` | 仓库/PR/Issue/Actions |
| `generate_image` | Gemini/GPT/Grok 生图 |
| `inspect_image` | 视觉模型分析 |
| `tts` | Grok Voice TTS |

### 记忆 & 状态
| 工具 | 能力 |
|------|------|
| `checkpoint` | 标记会话状态 |
| `rewind` | 裁剪探索上下文 |
| `retain` | 写入 Hindsight 记忆 |
| `recall` | 检索记忆 |
| `reflect` | 综合记忆回答 |

---

## 五、供应商 & 模型生态（40+ 供应商）

### 一级 API
Anthropic (OAuth) · OpenAI · OpenAI Codex (OAuth) · Google Gemini · Google Antigravity (OAuth) · xAI · Mistral · Groq · Cerebras · Fireworks · Together · Hugging Face · NVIDIA · OpenRouter · Synthetic · Vercel AI Gateway · Cloudflare AI Gateway · Wafer Serverless · Perplexity (OAuth)

### Coding Plans（订阅路由）
Cursor (OAuth) · GitHub Copilot (OAuth) · GitLab Duo · Kimi Code · Moonshot · MiniMax Coding Plan · MiniMax CN · Alibaba Coding Plan · Qwen Portal · Z.AI/GLM Coding Plan · Xiaomi MiMo · Qianfan · NanoGPT · Venice · Kilo · ZenMux · OpenCode Go · OpenCode Zen

### 本地
Ollama · Ollama Cloud · LM Studio · llama.cpp · vLLM · LiteLLM

### 路由特性
- **自定义供应商**：声明任何 OpenAI/Anthropic/Google/Vertex 兼容 API
- **Fallback 链**：429/quota 耗尽自动切换下一个供应商
- **路径范围模型**：按 repo 路径绑定不同模型
- **轮询凭证**：多 API key 轮转 + session affinity + 独立退避

---

## 六、与同类工具对比

| 维度 | omp | Claude Code | Codex CLI | Hermes Agent |
|------|-----|-------------|-----------|--------------|
| 语言 | TS + Rust | TS | Rust | Python |
| Shell | 进程内 brush-shell | fork bash | fork bash | fork bash |
| 搜索 | 进程内 ripgrep | fork rg | fork rg | fork rg |
| LSP | ✅ 14 操作 | ❌ | ❌ | ❌ |
| DAP 调试 | ✅ 28 操作 | ❌ | ❌ | ❌ |
| 子代理隔离 | ✅ 8 后端 | ❌ (无隔离) | ❌ | ✅ (subprocess) |
| Advisor 模式 | ✅ 第二模型监视 | ❌ | ❌ | ❌ |
| 协作会话 | ✅ E2EE | ❌ | ❌ | ❌ (Discord 多用户) |
| TTSR 流规则 | ✅ | ❌ | ❌ | ❌ (skills) |
| Hashline 编辑 | ✅ | ❌ | ❌ | ❌ |
| AST 编辑 | ✅ ast-grep | ❌ | ❌ | ❌ |
| 供应商数量 | 40+ | ~5 | ~5 | ~10 |
| Windows 原生 | ✅ | ❌ (WSL) | ❌ | ❌ |
| ACP 协议 | ✅ | ❌ | ❌ | ❌ |
| npm 包体积 | - | - | - | - |

**结论**：omp 在技术深度上超越当前所有主流终端编码 agent。尤其在 LSP/DAP 集成、进程内原生工具、子代理隔离、编辑器协议方面遥遥领先。

---

## 七、批判性分析

### 优势
1. **性能极致**：Rust 原生的 grep/shell/parser 消除了 fork/exec 瓶颈
2. **IDE 级代码理解**：LSP + DAP 让 agent 不再是「盲写代码」，而是真正理解代码库
3. **编辑可靠性**：Hashline 解决传统字符串替换的脆弱性问题，这是所有 agent 的核心痛点
4. **跨平台一致**：Windows 原生支持（无 WSL），这是 Claude Code / Codex CLI 都做不到的
5. **开放深度**：MIT 协议，全开源，可以读到所有实现细节
6. **记忆系统**：项目级 Hindsight，比 Claude Code 的 CLAUDE.md 更智能

### 风险 & 不足
1. **年轻**：仅 6 个月历史，API 可能不稳定，生态还未成熟
2. **Bun 依赖**：运行时锁定 Bun（非 Node），对某些环境有门槛
3. **社区控制严格**：PR 需要 vouch 机制，外部贡献者门槛高
4. **424 Open Issues**：快速迭代中的技术债务
5. **Vouch 争议**：已有 [社区讨论](https://news.ycombinator.com/item?id=...) 质疑这种机制可能阻碍社区发展
6. **文档深度不均衡**：README 极其详尽，但内部 API 文档可能滞后于代码

### 对 Hermes 的启示
omp 的几个设计对 Hermes 有参考价值：
- **Hashline 编辑**：可以研究并适配到 Hermes 的 `patch` 工具
- **TTSR 流规则**：skills 的触发机制可以借鉴「匹配中断 + 注入 + 重试」模式
- **进程内工具**：如果 Hermes 也把 grep/find 做进程内化，性能会大幅提升
- **Advisor 模式**：第二模型审查 + 旁注，可以集成到 Hermes 的 delegation 流程

---

## 八、安装与使用

### 安装
```bash
# macOS / Linux
curl -fsSL https://omp.sh/install | sh

# Homebrew
brew install can1357/tap/omp

# Bun (推荐)
bun install -g @oh-my-pi/pi-coding-agent

# Windows (PowerShell)
irm https://omp.sh/install.ps1 | iex

# mise 版本锁定
mise use -g github:can1357/oh-my-pi
```

### 基本用法
```bash
# 交互模式
omp

# 单次问答
omp -p "给这个项目添加 TypeScript 严格模式"

# 指定模型
omp --model anthropic/claude-sonnet-4.5

# 角色路由
omp --smol   # 便宜模型做子代理
omp --slow   # 深度推理模型
omp --plan   # 规划模式
```

### shell 补全
```bash
eval "$(omp completions zsh)"   # zsh
eval "$(omp completions bash)"  # bash
omp completions fish > ~/.config/fish/completions/omp.fish
```

---

## 九、来源

- GitHub 仓库：https://github.com/can1357/oh-my-pi
- 官网：https://omp.sh
- 博客文章（编辑格式）：https://blog.can.ac/2026/02/12/the-harness-problem/
- npm：https://www.npmjs.com/package/@oh-my-pi/pi-coding-agent
- Discord：https://discord.gg/4NMW9cdXZa
- 上游项目 Pi：https://github.com/badlogic/pi-mono
