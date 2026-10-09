# 贡献指南

感谢关注叮答（DingDa）！欢迎 Issue 与 PR。本文说明如何把仓库跑起来、门禁是什么、往哪儿改。

## 环境要求

| 工具 | 版本 | 用途 |
|------|------|------|
| Node.js | 22+ | 前端 |
| pnpm | 9+ | 前端工作区 |
| Python | 3.13+ | 服务端（用 `uv` 管理，无需手动建 venv） |
| uv | 最新 | Python 工作区与脚本运行 |
| Rust | stable | 桌面壳（Tauri） |
| RustSLib（Windows） | WebView2 | `pnpm tauri dev` 桌面运行 |

## 本地跑起来

```bash
pnpm install          # 前端依赖
pnpm prepare:python   # uv sync --frozen（Python 工作区）
pnpm tauri dev        # 桌面壳 + 前端 + Python API

pnpm dev              # 仅 Web 联调（API 默认 http://127.0.0.1:8787）
```

> 桌面壳必须经 `pnpm tauri`（根 `scripts/tauri.mjs` 注入路径），不要直接 `pnpm exec tauri`。

## 三套工作区，互不干涉

| 目录 | 工作区 | 成员清单 |
|------|--------|----------|
| `apps/web` + `packages/` | pnpm | `pnpm-workspace.yaml` |
| `packages-rs/` | Cargo | 根 `Cargo.toml` |
| `packages-py/` | uv | 根 `pyproject.toml`（单一 `uv.lock`） |

新增包一律先进对应工作区声明，再写依赖。

## 提交前过门禁（与 CI 一致）

```bash
pnpm build                      # 前端：check:deps + check:unused --strict + tsc + vite build
pnpm test                       # vitest（85 用例）
uv run ruff check packages-py --select E4,E7,E9,F
uv run pytest packages-py/api/tests -m "not integration"   # 集成测试只在本地跑
cargo check --workspace --all-targets
```

CI（`.github/workflows/ci.yml`）在 Linux 上跑同一组命令；`-m integration` 的用例需要本机浏览器与真实会话，不进 CI。

## 改代码前必读

- [`AGENTS.md`](AGENTS.md) —— 编号式开发规范（目录边界、分层规则）
- [`packages/README.md`](packages/README.md) / [`packages-rs/README.md`](packages-rs/README.md) —— 包边界与依赖方向
- Python / Rust 落笔形状见 `.agents/skills/python-coding` 与 `.agents/skills/rust-coding`（示例驱动）

核心红线：

1. **Agent 不直接 import Playwright / Camoufox / SQLite / 电商平台包**（经 Crawler 与 Browser 的插座层）
2. **Crawler 不做 Agent 决策，Browser 不含商品模型**
3. **API 路由一端点一文件**（`packages-py/api/src/api/routes/<域>/<动作>.py`）
4. **每个代码目录必须有 README.md**，说明职责与边界

## 提交规范

- 主题行中文、一句话说清，带类型前缀：`feat: / fix: / refactor: / docs: / style: / ci: / chore:`
- 一个 commit 一件事；重构请保持行为不变并在正文说明验证方式
- PR 描述写清：动机 / 改动点 / 验证方式（跑过哪些门禁）

## 提 Issue

- Bug 报告用 [bug 模板](.github/ISSUE_TEMPLATE/bug_report.yml)：环境（OS / 安装包或源码运行）、复现步骤、期望与实际、日志
- 功能建议用 [feature 模板](.github/ISSUE_TEMPLATE/feature_request.yml)：解决什么问题、期望的交互

## License

提交即表示你同意以 [Apache-2.0](LICENSE) 授权你的贡献。
