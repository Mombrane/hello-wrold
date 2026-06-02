# 01 — 完全缺失测试的模块

以下 3 个源码模块完全没有对应的测试文件。

---

## 1. `src/commands/compact.js` — 🔴 优先级：中

**功能：** 压缩旧记忆，合并同 canonicalKey 的重复记录。

### 缺失的测试项

| # | 测试项 | 说明 |
|---|--------|------|
| 1.1 | `parseCompactArgs()` 解析 `--older-than` | 正常传入天数（如 `30`） |
| 1.2 | `parseCompactArgs()` 解析 `--dry-run` | 标志位，无值 |
| 1.3 | `parseCompactArgs()` 解析 `--repo` | 指定仓库路径 |
| 1.4 | `parseCompactArgs()` 缺少 `--older-than` 值 | 应抛出错误 |
| 1.5 | `parseCompactArgs()` `--older-than` 非数字 | 应抛出错误 |
| 1.6 | `parseCompactArgs()` 未知标志 | 应抛出 `unknown option` |
| 1.7 | `compactCommand()` 端到端 dry-run | 输出 JSON 到 stdout，不实际修改文件 |
| 1.8 | `compactCommand()` 端到端实际压缩 | 修改文件并输出 JSON 结果 |

---

## 2. `src/commands/summarize.js` — 🔴 优先级：中

**功能：** 基于项目记忆生成摘要文件（`summary.md`、`projects/<id>/summary.md`）。

### 缺失的测试项

| # | 测试项 | 说明 |
|---|--------|------|
| 2.1 | `parseSummarizeArgs()` 解析 `--project` | 指定项目路径 |
| 2.2 | `parseSummarizeArgs()` 解析 `--force` | 强制重新生成 |
| 2.3 | `parseSummarizeArgs()` 解析 `--repo` | 指定仓库路径 |
| 2.4 | `parseSummarizeArgs()` 未知标志 | 应抛出 `unknown option` |
| 2.5 | `summarizeCommand()` 端到端 | 调用 summarizeMemories 并输出 JSON |

---

## 3. `src/file-store.js` — 🟢 优先级：低（可跳过）

**说明：** 纯 re-export 层，所有函数（`resolveStorePath`, `readMemories`, `readJSONLStream` 等）均从 `repo-store.js` 导出。底层已在 `repo-store.test.js` 中覆盖，无需独立测试。
