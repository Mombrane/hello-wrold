# 03 — 中优先级：CLI 命令和辅助路径

---

## 1. `src/index-store.js` — 🟡

**已有测试：** `tests/index-store.test.js`
**缺失：** 多个搜索过滤选项和边界路径

| # | 测试项 | 说明 |
|---|--------|------|
| 1.1 | `searchIndex` 按 `projectId` 过滤 | 只返回匹配项目的记忆 |
| 1.2 | `searchIndex` 按 `agentId` 过滤 | 只返回匹配 agent 的记忆 |
| 1.3 | `searchIndex` 按 `veracity` 过滤 | 如只返回 `stated` 类型 |
| 1.4 | `searchIndex` 按 `minImportance` 过滤 | 过滤低重要性记忆 |
| 1.5 | `searchIndex` 多条件组合 | `projectId + kind + minImportance` 等 |
| 1.6 | `searchIndex` 旧字符串签名 | `(cacheDir, query, limit)` 向后兼容 |
| 1.7 | `updateIndex` HEAD 变化 → 全量重建 | 验证 fallback 到 rebuildIndex |
| 1.8 | `updateIndex` 索引不存在 → 回退重建 | 首次运行场景 |
| 1.9 | `rebuildIndex` 使用 `logger` 回调 | 验证诊断日志输出 |
| 1.10 | `findJSONLFilesSync` 递归目录 | 多层子目录中的 JSONL 文件 |
| 1.11 | `getGitHead` 非 Git 仓库 | 返回 `'unknown'` |

---

## 2. `src/redaction-engine.js` — 🟡

**已有测试：** `tests/redaction-engine.test.js`
**缺失：** 自定义规则的错误处理路径

| # | 测试项 | 说明 |
|---|--------|------|
| 2.1 | 自定义规则无效正则表达式 | 应抛出 `Invalid regex in rule` |
| 2.2 | 自定义规则缺少 `name` 字段 | 应抛出 `Invalid custom rule` |
| 2.3 | 自定义规则缺少 `pattern` 字段 | 应抛出 `Invalid custom rule` |
| 2.4 | 配置文件读取非 ENOENT 错误 | 权限不足等 IO 错误应重新抛出 |

---

## 3. `src/cli.js` — 🟡

**已有测试：** `tests/cli-schema-logging.test.js`（仅覆盖 list/export）
**缺失：** CLI 入口分发逻辑和辅助函数

| # | 测试项 | 说明 |
|---|--------|------|
| 3.1 | 无命令时 `printHelp()` 输出 | 验证帮助文本内容 |
| 3.2 | 未知命令退出码 = 1 | `mem-sync foobar` → exitCode 1 |
| 3.3 | `handleIndexCommand` 未知子命令 | `mem-sync index foobar` → exitCode 1 |
| 3.4 | `formatSource` 接收字符串 | 直接返回字符串 |
| 3.5 | `formatSource` 接收对象 | 返回 `source.agent` 或 `source.type` |
| 3.6 | `formatSource` 接收 null/undefined | 返回 `'unknown'` |

---

## 4. `src/repo-store.js` — 🟡

**已有测试：** `tests/repo-store.test.js`
**缺失：** 错误传播路径

| # | 测试项 | 说明 |
|---|--------|------|
| 4.1 | `readJSONL` 非 ENOENT 错误重新抛出 | 如权限不足（EACCES） |
| 4.2 | `readJSONLStream` 非 ENOENT 错误重新抛出 | 同上 |
| 4.3 | `appendJSONL` 写入错误处理 | 磁盘满等场景 |
