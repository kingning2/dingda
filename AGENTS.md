# DingDa

企业 AI 客服桌面平台。

## 系统业务与架构（唯一入口）

[`docs/managed/architecture/README.md`](docs/managed/architecture/README.md)

## 当前分支职责

**由分支名自动决定。** 运行 `pnpm branch:sync` 生成 [`.cursor/rules/active-branch.mdc`](.cursor/rules/active-branch.mdc)。

```bash
pnpm branch:create frontend feature m5-ui-shell   # → frontend/feature/m5-ui-shell
pnpm branch                                     # 交互式
pnpm branch:sync                                # 切换分支后刷新规则
```

| 分支模式 | 职责 |
|----------|------|
| `frontend/<kind>/<slug>` | React · UI · Tauri · `apps/desktop/src-tauri/**` |
| `python/<kind>/<slug>` | 例外 Sidecar（仅 Rust 生态不够）· `python/**` |
| `contract/<kind>/<slug>` | `contracts/` + codegen |
| `main` | 集成分支 |

配置源：[`tooling/dingda/config/branch_roles.json`](tooling/dingda/config/branch_roles.json)

## 硬约束（摘要）

```
React（展示）  →  Tauri IPC  →  Rust（协调者，默认实现含 AI）
                                    ↓ 仅当 Rust 生态不够
                                 Python Sidecar（例外）
```

完整说明见架构入口；可执行规则见 [`.cursor/rules/master.md`](.cursor/rules/master.md)。

## Managed Docs 变更门禁（所有 Agent 强制）

文档管理入口：[`docs/managed/README.md`](docs/managed/README.md)。详细治理规则以该目录为准，禁止在本文件复制其完整内容。

### 最小上下文读取

1. `docs/managed/architecture/README.md`（业务/架构）或 `docs/managed/README.md`（治理）；
2. `docs/managed/registry/ACTIVE.md`；
3. 与修改路径匹配的一个 Domain 入口；
4. 当前 Change Record；
5. 只有发生冲突时才读取相关 ADR / 历史 Change。

**禁止**默认递归读取整个 `docs/managed/`。上下文预算遵循 [`docs/managed/CONTEXT_POLICY.md`](docs/managed/CONTEXT_POLICY.md)。

### 先记录，后修改

修改代码、Contract、配置或依赖前，Agent 必须：

1. 从 [`docs/managed/templates/CHANGE.md`](docs/managed/templates/CHANGE.md) 创建独立 Change Record；
2. 将记录加入 [`docs/managed/registry/ACTIVE.md`](docs/managed/registry/ACTIVE.md)；
3. 填写目标、非目标、影响边界和验收标准；
4. 状态至少达到 `approved` 后，才允许开始实现，并切换为 `in_progress`。

紧急修复使用 [`docs/managed/templates/QUICK_FIX.md`](docs/managed/templates/QUICK_FIX.md)，但不得跳过登记。纯只读分析无需 Change Record。

完成修改后必须在同一记录中回填实际结果，将状态设为 `completed`，并从 `ACTIVE.md` 移除。

## 规范入口

- [`docs/managed/architecture/README.md`](docs/managed/architecture/README.md) — **业务与架构**
- [`.cursor/rules/master.md`](.cursor/rules/master.md) — 全仓库基线
- [`.cursor/rules/active-branch.mdc`](.cursor/rules/active-branch.mdc) — 当前分支 scope
- [`.cursor/rules/frontend.md`](.cursor/rules/frontend.md) · [`.cursor/rules/rust.md`](.cursor/rules/rust.md) · [`.cursor/rules/python.md`](.cursor/rules/python.md)
- [`.agents/skills/emil-design-eng/SKILL.md`](.agents/skills/emil-design-eng/SKILL.md) — 前端 UI / 动效
- [`contracts/`](contracts/) — 三端共享契约

## Code Review 清单

- [ ] 当前分支 scope 内改动？（见 `active-branch.mdc`）
- [ ] 是否跨层？是否跨 Feature？
- [ ] 是否先改了 Contract？
- [ ] 是否违反六边形架构？
- [ ] `pnpm lint` 是否可通过？
