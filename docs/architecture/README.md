# Architecture

DingDa 架构文档与 ADR 存放目录。

## 分层边界

```
┌─────────────────────────────────────────┐
│  React（展示层）                          │
│  UI · State · Theme · Animation         │
│  禁止：业务逻辑 · AI · SQL · 直连 Python  │
└──────────────────┬──────────────────────┘
                   │ Tauri IPC（@desk/platform/ipc）
┌──────────────────▼──────────────────────┐
│  Rust Application Core（唯一协调者）      │
│  默认实现：Agent · LLM · License · 存储   │
│  禁止：unwrap · Feature 直调 · 阻塞 UI    │
└──────────────────┬──────────────────────┘
                   │ 仅当 Rust 生态不够（ADR-0009）
┌──────────────────▼──────────────────────┐
│  Python Sidecar（例外，不是 AI Runtime）  │
│  补 Rust 缺少的实现（如 Playwright）      │
│  禁止：GUI · SQLite · 写库 · 默认 LLM     │
└─────────────────────────────────────────┘
```

## 代码布局

- `crates/` — 自包含能力包与共享叶子：`agent` · `platform` · `infra`（能力包）+ `common` · `ports` · `macros`（共享叶子）+ `adapter`
- `business/` — 应用胶水 crate：日志 / 配置 / 渠道存储 / 事件桥 / 耗时计时（不依赖 Tauri，领域在 `crates/platform`）
- `apps/desktop/src-tauri/` — Tauri 应用壳：IPC 命令、状态注册、Builder、平台装配
- `apps/desktop/src/` — React 前端（`features/` + `route/` + `i18n/`）
- `packages/` — 前端共享包：`ui` · `platform` · `store` · `contracts` · `utils`
- `python/` — 例外 Sidecar（仅 Rust 生态不够时编写）
- `contracts/` — 跨端契约生成源
- `subscription/` — 独立激活/授权工具，**不属于** workspace

依赖方向：`src-tauri → business → crates/**`；`crates/**` 不依赖 Tauri 与 `business`。
详见 [`package-taxonomy.md`](package-taxonomy.md) 与 [`module-dependency-graph.md`](module-dependency-graph.md)。

## 设计原则

1. Contracts First
2. Feature First
3. Dependency Inward
4. Event Driven
5. Local First / Offline First
6. Testable by Design
7. Composition over Inheritance
8. Explicit over Implicit
9. Rust First — Python 只补生态缺口（[ADR-0009](../managed/decisions/python-runtime/adr-0009-python-only-when-rust-insufficient.md)）

## Feature 列表（互相独立）

`agent` · `chat` · `knowledge` · `platform` · `manage` · `license` · `plugin` · `setting`（另有横切的 `component` / `error`）

跨 Feature 通信只允许：

- **Query Port** — 只读查询
- **Event** — Pub/Sub（`kernel::event`）
- **Contract** — 共享 DTO

## 六边形架构

```
UseCase  →  Ports (trait)  →  Infrastructure
```

UseCase 层禁止直接接触：SQL · HTTP · Filesystem · SQLite · Tauri · Python

## 契约变更流程

```
contracts/  →  codegen  → 受影响实现端
默认：Rust → React
仅当该能力必须走 sidecar：再改 Python
```

禁止跳过 `contracts/` 直接改实现。

## 相关文档

| 文档 | 说明 |
|------|------|
| [`whatsapp-webhook-deployment.md`](whatsapp-webhook-deployment.md) | **WA webhook** 部署手册（**历史参考**，已被 ADR-0006 Baileys 方案取代） |
| [`.cursor/rules/master.md`](../../.cursor/rules/master.md) | 完整约束与 lint 规范 |
| [`contracts/README.md`](../../contracts/README.md) | 契约层说明 |
