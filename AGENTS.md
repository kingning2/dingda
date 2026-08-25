# DingDa

企业 AI 客服桌面平台 — Architecture Skeleton 阶段。

## 当前分支职责

**由分支名自动决定。** 运行 `pnpm branch:sync` 生成 [`.cursor/rules/active-branch.mdc`](.cursor/rules/active-branch.mdc)（允许/禁止路径 + 细则规则）。

```bash
pnpm branch:create frontend feature m5-ui-shell   # → frontend/feature/m5-ui-shell
pnpm branch                                     # 交互式
pnpm branch:sync                                # 切换分支后刷新规则
```

| 分支模式 | 职责 |
|----------|------|
| `frontend/<kind>/<slug>` | React · UI · Tauri · `apps/desktop/src-tauri/**` |
| `python/<kind>/<slug>` | 例外 Sidecar（仅 Rust 生态不够）· `python/**` |
| `contract/<kind>/<slug>` | `contracts/` + codegen（Rust 生成物在 src-tauri `contracts/`） |
| `main` | 集成分支 |

配置源：[`skills/dingda/config/branch_roles.json`](skills/dingda/config/branch_roles.json)

## 架构约束（硬约束）

```
React（展示）  →  Tauri IPC  →  Rust（协调者，默认实现含 AI）
                                    ↓ 仅当 Rust 生态不够
                                 Python Sidecar（例外，不是 AI Runtime）
```

- React **不知道** Python；Python **不知道** React
- 默认用 **Rust** 实现能力（含 LLM / Agent）。仅当 Rust 生态缺少可用实现时才编写 `python/**`（[ADR-0009](docs/managed/decisions/python-runtime/adr-0009-python-only-when-rust-insufficient.md)）
- `contracts/` 是跨端 **唯一真相源**，变更顺序：Contract → Codegen → 受影响端（默认 Rust → React；涉及 sidecar 时才改 Python）
- Feature 完全独立，跨 Feature 只允许 **Query Port**、**Event**、**Contract**

完整约束：[`.cursor/rules/master.md`](.cursor/rules/master.md)

AI 开发知识库：[`skills/dingda/`](skills/dingda/)（架构 · recipes · templates · scripts）

## Managed Docs 变更门禁（所有 Agent 强制）

文档管理入口：[`docs/managed/README.md`](docs/managed/README.md)。详细治理规则以该目录为准，禁止在本文件复制其完整内容。

### 最小上下文读取

处理任何仓库改动时按需渐进读取：

1. `docs/managed/README.md`；
2. `docs/managed/registry/ACTIVE.md`；
3. 与修改路径匹配的一个 Domain 入口；
4. 当前 Change Record；
5. 只有发生冲突或需要追溯设计原因时才读取相关 ADR / 历史 Change。

**禁止**默认递归读取整个 `docs/managed/`。上下文预算遵循 [`docs/managed/CONTEXT_POLICY.md`](docs/managed/CONTEXT_POLICY.md)。

### 先记录，后修改

修改代码、Contract、配置或依赖前，Agent 必须：

1. 从 [`docs/managed/templates/CHANGE.md`](docs/managed/templates/CHANGE.md) 创建独立 Change Record；
2. 将记录加入 [`docs/managed/registry/ACTIVE.md`](docs/managed/registry/ACTIVE.md)；
3. 填写目标、非目标、影响边界和验收标准；
4. 状态至少达到 `approved` 后，才允许开始实现，并切换为 `in_progress`。

紧急修复使用 [`docs/managed/templates/QUICK_FIX.md`](docs/managed/templates/QUICK_FIX.md)，但不得跳过登记。纯只读分析、解释和扫描无需创建 Change Record。

完成修改后必须在同一记录中回填实际结果与验证结论，将状态设为 `completed`，并从 `ACTIVE.md` 移除。若修改稳定领域事实则更新对应 Domain；若形成长期技术决策则创建 ADR。

## 规范入口

- [`.cursor/rules/master.md`](.cursor/rules/master.md) — 全仓库基线
- [`.cursor/rules/branch-workflow.mdc`](.cursor/rules/branch-workflow.mdc) — 分支命令与工作流
- [`.cursor/rules/active-branch.mdc`](.cursor/rules/active-branch.mdc) — **当前分支** scope（生成文件）
- [`.cursor/rules/frontend.md`](.cursor/rules/frontend.md) · [`.cursor/rules/rust.md`](.cursor/rules/rust.md) · [`.cursor/rules/python.md`](.cursor/rules/python.md)
- [`skills/dingda/guides/ui-reference.md`](skills/dingda/guides/ui-reference.md) — **UI 任务首选参考**（Shadcn Admin + Aceternity UI + `@desk/ui` 三层）
- [`docs/shadcn-admin-aceternity-migration-prompt.md`](docs/shadcn-admin-aceternity-migration-prompt.md) — 完整 UI 改造规格与路由清单
- [`.cursor/skills/emil-design-eng/SKILL.md`](.cursor/skills/emil-design-eng/SKILL.md) — 前端 UI / 动效必须遵循（Emil Kowalski）
- `/check-emil-design` — 对照上述 skill 审查当前 UI/动效（见 [`.cursor/commands/check-emil-design.md`](.cursor/commands/check-emil-design.md)）
- [`contracts/`](contracts/) — 三端共享契约，Breaking Change 必须先改契约并提供迁移说明

## Code Review 清单

- [ ] 当前分支 scope 内改动？（见 `active-branch.mdc`）
- [ ] 是否跨层？是否跨 Feature？
- [ ] 是否先改了 Contract？
- [ ] 是否违反六边形架构？
- [ ] `pnpm lint` 是否可通过？
