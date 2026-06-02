# 04 — 低优先级：边缘情况

---

## 1. `src/argparse.js` — 🟢

**已有测试：** `tests/argparse.test.js`

| # | 测试项 | 说明 |
|---|--------|------|
| 1.1 | `validateRange` 接收 NaN | 应抛出非数字错误 |
| 1.2 | `validateRange` 接收字符串 | 应抛出非数字错误 |

---

## 2. `src/compact-engine.js` — 🟢

**已有测试：** `tests/compact-engine.test.js`

| # | 测试项 | 说明 |
|---|--------|------|
| 2.1 | storePath 文件不存在时备份失败 | `copyFileSync` 的 ENOENT 错误路径 |

---

## 3. `src/project-resolver.js` — 🟢

**已有测试：** `tests/project-resolver.test.js`

| # | 测试项 | 说明 |
|---|--------|------|
| 3.1 | `package.json` 存在但无 `name` 字段 | 应 fallback 到目录名 |

---

## 4. `src/compact-engine.js` — 🟢

**已有测试：** `tests/compact-engine.test.js`

| # | 测试项 | 说明 |
|---|--------|------|
| 4.1 | 空 JSONL 文件的压缩行为 | 无记忆可压缩时的输出 |
| 4.2 | 所有记忆都已过期 | `validUntil` 全部过期后的压缩结果 |
