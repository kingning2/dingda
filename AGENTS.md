# DingDa

桌面端 Web 产品（React）+ Tauri 客户端（Rust workspace）+ Python Server（`server/`）。

## 仓库形态

| 目录 | 内容 |
|------|------|
| `src/` | Web UI（React + Vite） |
| `server/` | Python Server（API / Agent / Crawler / Browser / MCP） |
| `packages-rs/` | Rust Cargo workspace（成员包；Tauri 壳是其中的 `client`） |

- Rust 侧是 `packages-rs/`，**不是** `apps/` / `packages/` 的 JS monorepo。
- 桌面壳在 **`packages-rs/client`**（不是 `src-tauri`）。Tauri CLI 默认只认 `<cwd>/src-tauri`，
  故 `pnpm tauri` 走 `scripts/tauri.mjs` 注入 `TAURI_APP_PATH`。**不要直接 `pnpm exec tauri`**。
- 工作区根在仓库根 `Cargo.toml`，编译产物在 `<repo>/target/`。
- 成员包边界与依赖方向见 [`packages-rs/README.md`](packages-rs/README.md)。

## Cursor 编码约束（写代码必遵）

| 规则 / Skill | 作用 |
|------|------|
| `.cursor/rules/project-coding.mdc` | 全局架构（alwaysApply） |
| `.agents/skills/python-coding/SKILL.md` | Python **示例驱动**（注释 / 插座 / 命名 / 日志） |
| `.agents/skills/rust-coding/SKILL.md` | Rust **示例驱动** |
| `.agents/skills/*-architecture/` | Agent / Crawler / Browser / Tool / 前端 |

写 Python / Rust 时必须按对应 Skill 里的示例 A/B/C 形状编写，不能只看摘要。

Browser / Crawler **核心规则**原文见 `.agents/skills/layers.md` 与 alwaysApply 的 `project-coding.mdc`。