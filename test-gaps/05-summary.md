# 05 — 汇总表

## 按优先级统计

| 优先级 | 缺失用例数 | 涉及模块 |
|--------|-----------|----------|
| 🔴 高 | ~30 | `git.js`, `schema.js`, `memory-store.js` |
| 🟡 中 | ~25 | `commands/compact.js`, `commands/summarize.js`, `index-store.js`, `redaction-engine.js`, `cli.js`, `repo-store.js` |
| 🟢 低 | ~6 | `argparse.js`, `compact-engine.js`, `project-resolver.js` |
| **合计** | **~61** | **12 个模块** |

## 按模块统计

| 模块 | 有测试 | 缺失用例 | 优先级 |
|------|--------|----------|--------|
| `src/commands/compact.js` | ❌ | 8 | 🔴 |
| `src/commands/summarize.js` | ❌ | 5 | 🔴 |
| `src/file-store.js` | ❌ | 0（re-export，跳过） | 🟢 |
| `src/git.js` | ⚠️ | 8 | 🔴 |
| `src/schema.js` | ⚠️ | 15 | 🔴 |
| `src/memory-store.js` | ⚠️ | 7 | 🔴 |
| `src/index-store.js` | ⚠️ | 11 | 🟡 |
| `src/redaction-engine.js` | ⚠️ | 4 | 🟡 |
| `src/cli.js` | ⚠️ | 6 | 🟡 |
| `src/repo-store.js` | ⚠️ | 3 | 🟡 |
| `src/argparse.js` | ⚠️ | 2 | 🟢 |
| `src/compact-engine.js` | ⚠️ | 3 | 🟢 |
| `src/project-resolver.js` | ⚠️ | 1 | 🟢 |

## 覆盖良好的模块（无需补充）

以下模块测试覆盖良好，无需额外测试：

- `src/lock.js` ✅
- `src/merge.js` ✅
- `src/retain-engine.js` ✅
- `src/summarize-engine.js` ✅
- `src/commands/remember.js` ✅
- `src/commands/recall.js` ✅
- `src/commands/prepare.js` ✅
- `src/commands/context.js` ✅
- `src/commands/retain.js` ✅
- `src/commands/flush.js` ✅
- `src/commands/doctor.js` ✅
- `src/commands/redact.js` ✅
- `src/commands/review.js` ✅
- `src/commands/index.js` ✅

## 推荐执行顺序

1. **Phase 1**（核心补全）：`git.js` + `schema.js` + `memory-store.js` — 补全 Git 操作、Schema 兼容性、脱敏路径
2. **Phase 2**（CLI 补全）：`commands/compact.js` + `commands/summarize.js` — 新增测试文件
3. **Phase 3**（搜索增强）：`index-store.js` — 补全过滤选项测试
4. **Phase 4**（边缘收尾）：`cli.js` + `repo-store.js` + `redaction-engine.js` + 低优先级模块
