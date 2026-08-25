# DingDa

本地优先的 **AI Agent 智能客服** 桌面应用。

> **当前阶段：** Architecture Skeleton + 基础切片（UI Shell、Rust Agent 组装、Python Sidecar ping）。Python 不是 AI Runtime；仅 Rust 生态不够时才编写。

## 架构约束（必读）

```
React  →  Rust（默认实现，含 AI）
            ↓ 仅当 Rust 生态不够
         Python Sidecar
```

| 禁止 | 说明 |
|------|------|
| React → Python | 含 localhost HTTP / WebSocket / SSE |
| React → SQLite | 存储由 Rust 负责 |
| Python → SQLite | 存储由 Rust 负责；AI 仅只读 Query Port |
| 把新 AI 能力默认放 Python | 默认用 Rust；Python 只补生态缺口（ADR-0009） |
| AI 写库 / 自动发信 | 数据与发送仅 UI 人工操作 |
| Feature 间直接 import | 跨 Feature 只允许 Query Port · Event · Contract |
| 先改实现再改契约 | 跨端变更须先改 `contracts/` |

完整规则见 [`.cursor/rules/master.md`](.cursor/rules/master.md)。

## 结构

- `apps/desktop` — Tauri + React 桌面应用
- `packages` — 前端共享包（ui · platform · store · contracts · utils）
- `crates` — Rust Workspace 自包含能力包（`agent` · `platform` · `infra`）与共享叶子（`common` / `ports` / `macros`）+ `adapter`
- `business` — 应用胶水 crate（日志 / 配置 / 渠道存储 / 事件桥，不依赖 Tauri）
- `python` — 例外 Sidecar（仅 Rust 生态不够时扩展）
- `contracts` — 跨端共享契约（**唯一真相源**）
- `subscription` — 独立激活/授权工具（不属于 workspace）
- `docs/managed/` — 领域文档、Change Record、ADR

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

## 文档

- [`skills/dingda/`](skills/dingda/) — AI 开发知识库
- [`.cursor/skills/dingda/SKILL.md`](.cursor/skills/dingda/SKILL.md) — Cursor Skill 入口
- [`.cursor/rules/master.md`](.cursor/rules/master.md) — 全局架构约束

### 架构检查

```bash
python skills/dingda/scripts/check_architecture.py
```
