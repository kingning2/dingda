# DingDa

本地优先的 **AI Agent 智能客服** 桌面应用。

**系统业务与架构（唯一入口）：** [`docs/managed/architecture/README.md`](docs/managed/architecture/README.md)

```
React  →  Rust（默认实现，含 AI）
            ↓ 仅当 Rust 生态不够
         Python Sidecar
```

可执行约束见 [`.cursor/rules/master.md`](.cursor/rules/master.md)。

## 结构

- `apps/desktop` — Tauri + React 桌面应用
- `packages` — 前端共享包（ui · platform · store · contracts · utils）
- `python` — 例外 Sidecar（仅 Rust 生态不够时扩展）
- `contracts` — 跨端共享契约（**唯一真相源**）
- `tooling/dingda` — 分支规则与契约 codegen
- `subscription` — 独立激活/授权工具
- `docs/managed/` — 架构 · Domain · Change · ADR

## 开发

```bash
pnpm install
pnpm tauri dev
```

## 代码校验

```bash
pnpm lint              # 三端全量检查（含 TypeScript 类型检查）
pnpm lint:frontend     # ESLint + tsc
pnpm lint:types        # TypeScript 类型检查
pnpm lint:rust         # rustfmt + clippy
pnpm lint:python       # ruff check + format
pnpm lint:fix          # 自动修复（前端 + rust fmt + python）
```

提交前 Husky 会自动对 staged 文件跑对应语言的 lint（`pnpm install` 后生效）。
