# DingDa 开发规范

桌面端 Web 产品（React）+ Tauri 客户端（Rust workspace）+ Python Server（`packages-py/` uv workspace）。

本文件是**开发规范说明**：写代码前必读，规则按编号引用（如「见规范 1.4」）。

## 1. 仓库形态：三个可运行入口

| 入口 | 目录 | 命令 | 语义 |
|------|------|------|------|
| Web 应用 | `apps/web/` | `pnpm dev`（Vite :1420） | React 装配：路由表 / 页面 / `boot/` 启动编排；浏览器直联 Server 联调 |
| Python Server | `packages-py/api/` | `uv run python -m api`（FastAPI :8787） | 唯一状态持有方；产品能力全部经 HTTP/SSE（SQLite 在 Python） |
| 桌面客户端 | `packages-rs/client/` | `pnpm tauri dev` | 壳 = Web + Server 的打包体 + OS 能力（起停 Server、外部 CLI、对话框） |

1.1 前端是 **pnpm 工作区**，Rust 是 **Cargo 工作区**，Python 是 **uv 工作区**，三套互不干涉。

1.2 前端成员在 `packages/` + `apps/`。`pnpm-workspace.yaml` 的 glob **不要**写成
    `packages*`，否则会把 `packages-rs` 当 JS 包扫。

1.3 **前端已无仓库根 `src/`**，内容拆入 `apps/web` 与 `packages/`。

1.4 桌面壳在 **`packages-rs/client`**（不是 `src-tauri`）。Tauri CLI 默认只认
    `<cwd>/src-tauri`，故 `pnpm tauri` 走 `scripts/tauri.mjs` 注入 `TAURI_APP_PATH`。
    **不要直接 `pnpm exec tauri`**。

1.5 Rust 工作区根在仓库根 `Cargo.toml`，编译产物在 `<repo>/target/`。

1.6 成员包边界与依赖方向见 [`packages/README.md`](packages/README.md) 与
    [`packages-rs/README.md`](packages-rs/README.md)。

## 2. 分层规则（Browser / Crawler，原文必遵）

2.1 八条核心规则的**原文**见 `.agents/skills/layers.md` 与 alwaysApply 的
    `.cursor/rules/project-coding.mdc`。一句话版：能力归 Browser，平台归 Crawler，
    Crawler 只依赖 Browser Interface，登录语义归 channels，Agent/Tool 一律经
    Tool → Crawler → Browser，禁止为此新增 Rust Crawler/Browser/DB。

2.2 Python 分层依赖：`Agent → Tool → Crawler → BrowserPort → Adapter`；跨层 import = 错。

2.3 `api/` 只做 HTTP 校验与调用；`domains/` 承担应用服务；`channels/` 承担登录/账号/IM。

## 3. 语言编码规范（照抄示例）

写 Python / Rust / 前端时必须按对应 Skill 里的示例 A/B/C 形状编写，不能只看摘要。

3.1 Python（`packages-py/**/*.py`）→ [`python-coding`](.agents/skills/python-coding/SKILL.md)

3.2 Rust（`packages-rs/**/*.rs`）→ [`rust-coding`](.agents/skills/rust-coding/SKILL.md)

3.3 前端（`apps/web/**`、`packages/client/**`）→ [`frontend-coding`](.agents/skills/frontend-coding/SKILL.md)（通用模板）；
    项目落点见 `.cursor/rules/frontend-coding.mdc`

## 4. 新增能力落点（写在这里，勿另起炉灶）

4.1 **新增 HTTP 端点**：`packages-py/api/src/api/routes/<域>/<动作>.py`，一端点一文件；
    域 `__init__.py` 挂 `APIRouter(prefix, tags)`，并在 `routes/__init__.py` 聚合。
    详见 [`packages-py/api/src/api/README.md`](packages-py/api/src/api/README.md)。

4.2 **新增 Tool**：`uv run python -m tools.scaffold <name>` 生成
    `packages-py/tools/src/tools/<name>/__init__.py` 骨架；registry 自动发现，
    `tools.cli` 子命令同步出现，无需手工注册。

4.3 **新增平台**：只改 `packages-py/crawler/src/crawler/sources/<platform>/`。

4.4 **新增浏览器**：只改 `packages-py/browser/src/browser/adapters/<browser>/`。

4.5 **新增登录渠道**：只改 `packages-py/channels/src/channels/<platform>/`。

4.6 **改产品 API**：先契约（`packages-py/contracts` ↔ `packages/contracts`），再 Python，再 React；不必改 Rust。

## 5. 禁止清单

5.1 禁止垃圾桶目录：`utils/`、`helpers/`、`services/`、`common/`；包名必须对应一个业务域或一层机制。

5.2 禁止第二套 Skill；产品不用 Rust IPC crate。

5.3 Agent / Tool 不得直接 import Playwright、Camoufox、SQLite 或具体电商平台包。

5.4 禁止 `domains/*/service.py` 上帝类；新代码目录在
    `packages-py/{agent,crawler,browser,tools}/src/<pkg>/`。

5.5 浏览器（Web 端）禁止 mock Codex / Claude；外部 CLI Agent 仅桌面注入，判断用
    `supportsExternalAgents()`（`@v2/runtime/capabilities`）。

## 6. Skill 索引

| 规则 / Skill | 作用 |
|------|------|
| `.cursor/rules/project-coding.mdc` | 全局架构（alwaysApply） |
| `.agents/skills/layers.md` | 分层 / 依赖 / IPC（全 Skill 共享） |
| `.agents/skills/python-coding/SKILL.md` | Python 示例驱动 |
| `.agents/skills/rust-coding/SKILL.md` | Rust 示例驱动 |
| `.agents/skills/frontend-coding/SKILL.md` | 前端示例驱动 |
| `.agents/skills/*-architecture/` | Agent / Crawler / Browser / Tool / 前端 架构边界 |

涉及架构边界时动手前先打开 `layers.md` + 对应 `*-architecture/SKILL.md`。
