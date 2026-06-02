# 02 — 高优先级：已有测试但覆盖不完整

---

## 1. `src/git.js` — 🔴

**已有测试：** `tests/git.test.js`
**缺失函数/路径：** `stageFile`、`commit`、`push` 完全未测试；`pullRebase` 冲突路径未覆盖

| # | 测试项 | 说明 |
|---|--------|------|
| 1.1 | `stageFile(cwd, filePath)` 暂存文件 | 将指定文件加入 git 暂存区 |
| 1.2 | `stageFile()` 文件不存在时的行为 | 是否抛出错误或静默处理 |
| 1.3 | `commit(cwd, message)` 提交变更 | 验证提交消息和 commit 内容 |
| 1.4 | `commit()` 无暂存变更时的行为 | 空提交处理 |
| 1.5 | `push(cwd)` 推送到 origin main | 验证远程仓库收到提交 |
| 1.6 | `push()` 无 remote 时返回 false | 错误路径 |
| 1.7 | `push()` 远程拒绝时的行为 | 权限不足等场景 |
| 1.8 | `pullRebase` 冲突时抛出 `RebaseConflictError` | 模拟冲突场景 |

---

## 2. `src/schema.js` — 🔴

**已有测试：** `tests/schema.test.js`
**缺失函数/路径：** 兼容性路径和部分导出函数未测试

| # | 测试项 | 说明 |
|---|--------|------|
| 2.1 | `normalizeMemoryInput` 使用 `text` 字段 | `input.text` 作为 `content` 的回退（旧格式兼容） |
| 2.2 | `normalizeSource` 接收字符串 | `--source codex` → `{ type: 'manual', agent: 'codex' }` |
| 2.3 | `normalizeSource` 接收 null | 返回 `{ type: 'manual' }` |
| 2.4 | `normalizeSource` 接收 undefined | 返回 `{ type: 'manual' }` |
| 2.5 | `normalizeMemoryInput` 使用显式 `id` | 覆盖自动生成的 ID |
| 2.6 | `createMemoryIdFromCanonicalKey()` | 从 canonicalKey 生成 `mem_` 前缀 ID |
| 2.7 | `createCanonicalKey` 不同 projectId/agentId 组合 | 验证不同上下文不产生相同 key |
| 2.8 | `validateMemory` 接收 null | 应抛出 TypeError |
| 2.9 | `validateMemory` 接收数组 | 应抛出 TypeError |
| 2.10 | `validateMemory` 错误的 schemaVersion（如 2） | 应抛出错误 |
| 2.11 | `validateMemory` 缺少必需字段 | 每个字段缺失都应抛出对应错误 |
| 2.12 | `defaultConfidence` 非 manual 来源 | `tool`/`inferred`/`imported` → 0.5 |
| 2.13 | `defaultVeracity` 非 manual 来源 | `tool`/`inferred`/`imported` → `'unknown'` |
| 2.14 | `normalizeSummary` 显式 summary | 走 `normalizeContent(summary)` 路径 |
| 2.15 | 无效时间戳的错误路径 | 非 ISO 格式字符串 |

---

## 3. `src/memory-store.js` — 🔴

**已有测试：** `tests/memory-store.test.js`
**缺失函数/路径：** redaction 相关路径和兼容性映射

| # | 测试项 | 说明 |
|---|--------|------|
| 3.1 | `store.add()` 内容被 redaction 阻止 | 返回 blocked 错误 |
| 3.2 | `store.add()` 使用 `skipRedaction: true` | 跳过脱敏直接写入 |
| 3.3 | `normalizeLegacyScope('assistant')` | 映射为 `'agent'` |
| 3.4 | `normalizeLegacyScope` 其他旧值 | 确保所有旧 scope 正确映射 |
| 3.5 | `legacySourceName` 接收 string | 返回字符串 |
| 3.6 | `legacySourceName` 接收 object | 返回 `source.agent` 或 `source.type` |
| 3.7 | `legacySourceName` 接收 null/undefined | 返回 `'unknown'` |
