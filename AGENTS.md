# DingDa

桌面端 Web 产品（React）+ Tauri 客户端（Rust workspace）+ Python Server（`packages-py/` uv workspace）。

## 仓库形态

| 目录 | 内容 |
|------|------|
| `apps/web/` | Web 应用装配（React + Vite 根：路由表 / 页面 / `boot/` 启动编排） |
| `packages/` | 前端 pnpm 工作区（`contracts/` 线协议 + `client/*` 业务域与机制包） |
| `packages-rs/` | Rust Cargo workspace（成员包；Tauri 壳是其中的 `client`） |
| `packages-py/` | Python Server（uv workspace：API / Agent / Crawler / Browser …） |

- 前端是 **pnpm 工作区**，Rust 是 **Cargo 工作区**，Python 是 **uv 工作区**，三套互不干涉：
  前端成员在 `packages/` + `apps/`（见 `pnpm-workspace.yaml`），
  Rust 成员在 `packages-rs/`（见根 `Cargo.toml`），Python 成员在 `packages-py/`
  （见根 `pyproject.toml` 的 `[tool.uv.workspace]`，单一 `uv.lock`）。`pnpm-workspace.yaml`
  的 glob **不要**写成 `packages*`，否则会把 `packages-rs` 当 JS 包扫。
- **前端已无仓库根 `src/`**，内容拆入 `apps/web` 与 `packages/`。
- 桌面壳在 **`packages-rs/client`**（不是 `src-tauri`）。Tauri CLI 默认只认 `<cwd>/src-tauri`，
  故 `pnpm tauri` 走 `scripts/tauri.mjs` 注入 `TAURI_APP_PATH`。**不要直接 `pnpm exec tauri`**。
- 工作区根在仓库根 `Cargo.toml`，编译产物在 `<repo>/target/`。
- 成员包边界与依赖方向见 [`packages-rs/README.md`](packages-rs/README.md) 与
  [`packages/README.md`](packages/README.md)。

## Cursor 编码约束（写代码必遵）

| 规则 / Skill | 作用 |
|------|------|
| `.cursor/rules/project-coding.mdc` | 全局架构（alwaysApply） |
| `.agents/skills/python-coding/SKILL.md` | Python **示例驱动**（注释 / 插座 / 命名 / 日志） |
| `.agents/skills/rust-coding/SKILL.md` | Rust **示例驱动** |
| `.agents/skills/*-architecture/` | Agent / Crawler / Browser / Tool / 前端 |

写 Python / Rust 时必须按对应 Skill 里的示例 A/B/C 形状编写，不能只看摘要。

Browser / Crawler **核心规则**原文见 `.agents/skills/layers.md` 与 alwaysApply 的 `project-coding.mdc`。