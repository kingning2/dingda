# DingDa Agent + Crawler 架构 Skill

本仓库**只有这一套**架构开发规范。不要在 `~/.cursor/skills` 再写平行的目录/依赖规范。

## 先读

1. [layers.md](layers.md) — 真实目录、两个 Agent、**IPC 决策**、依赖方向
2. 再读对应 SKILL：

| Skill | 何时 |
|-------|------|
| [agent-architecture](agent-architecture/SKILL.md) | 产品 Agent、Workflow、planning |
| [crawler-architecture](crawler-architecture/SKILL.md) | 抓取、平台 Source、快照、去重 |
| [browser-architecture](browser-architecture/SKILL.md) | 浏览器生命周期与 adapter |
| [tool-architecture](tool-architecture/SKILL.md) | Tool 契约、MCP、registry |
| [frontend-architecture](frontend-architecture/SKILL.md) | pnpm 工作区结构、桌面能力注入、包依赖方向 |
| [python-coding](python-coding/SKILL.md) | Python **照抄示例**：注释、插座、命名、日志 |
| [rust-coding](rust-coding/SKILL.md) | Rust **照抄示例**：注释、插座、命名、日志 |

## 硬约束（摘要）

- **核心规则**：见 [layers.md](layers.md)「核心规则」原文（Browser / Crawler 职责、禁止跨层、扩展路径、禁止 Rust Crawler/Browser/DB）。
- 产品能力写 Python HTTP/SSE；不要新开 Rust IPC 项目，也不要把搜品做成 `invoke`。
- 壳能力留在现有 `packages-rs/client/src/commands/`（生命周期、对话框、CLI Agent Runtime）。
- 新业务目录：`server/src/{agent,crawler,browser,tools}/`。
- 禁止 Agent → Playwright / SQLite / 闲鱼。
- 前端是 pnpm 工作区：应用装配在 `apps/web`，业务域在 `packages/client/ui-*`（没有仓库根 `src/`）。
- 前端主开发在浏览器；外部 CLI Agent 仅桌面注入（`@v2/runtime/capabilities`）。
- 前端包依赖单向无环，叶子包（`app-state` / `runtime` / `routes` / `contracts`）不许引业务包。
- 写 Python / Rust 时必须按 `python-coding` / `rust-coding` Skill 里的示例形状落笔。
