# 更新日志

本项目的所有重要变更记录于此。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本遵循 [语义化版本](https://semver.org/lang/zh-CN/)；版本号只在
`desktop-release.yml` 打 tag 时递增，日常变更进 Unreleased。

## [Unreleased]

### 移除

- **LLM 配置面收敛**：删除 `OPENAI_API_KEY` 兜底别名（只认 `DINGDA_LLM_API_KEY`）与外部 CLI 时代死变量（`DINGDA_SKILL_DIRS`、`DINGDA_E2E_AGENT_ID`、`DINGDA_E2E_MODEL_ID`）；`.env.example` 补火山方舟 Coding Plan 配置示例（`/api/coding/v3` + `ark-code-latest`），全表由 54 项收敛至 50 项。

- **外部 CLI Agent 整链删除**（ADR-0005）：Python `packages-py/cli` 包与
  `/v1/agent/runtimes*` 端点（扫描 / 偏好 / 默认 / 外部 run / 直播帧 / 取消）、
  Rust `packages-rs/agent` + `packages-rs/runtime` crate 与 `client` 的
  `agent_runtime` 命令、前端 `/agents` 页与 Composer Agent 选择器、
  `supportsExternalAgents()` 能力位与 `agent-runtime` 契约。
  AI 能力统一内置 Agent（`agent_id="dingda"`，模型由 `DINGDA_LLM_*` 决定）：
  前端发送链接通 `POST /v1/agent/works/{workId}/run`，Composer 隐藏选择器，
  取消 = AbortController abort（服务端继续跑完落库）；`/assets` `/integrations`
  重定向 `/accounts`；DOM 修复链 `propose_dom_patch` 改内置 LLM
  （`DINGDA_DOM_REPAIR_MODEL`）。

### 新增

- **工作流技能包**：引入 agent-skills（MIT）25 个生命周期技能至 `.agents/skills/`，
  共享检查清单至 `.agents/references/`，9 个 slash 命令至 `.pi/prompts/`
  （`/spec` `/plan` `/build` `/test` `/constraints` `/review` `/webperf` `/code-simplify` `/ship`）
- **质量约束体系**：新增 `CONSTRAINTS.md`（地板规则 + 棘轮基线 + 例外表）、
  `pnpm check:fast`（floor-guard + layers-guard）、CI `floor` 阻断 job 与
  `observe` 观察期 job（分层 / gitleaks / pnpm audit）；rust job 追加 `cargo test --workspace`
- **架构决策记录**：`docs/adr/`（仓库形态、uv 工作区拆分、分层铁律、约束棘轮）
- **Agent 单测**：`AgentService` 工具循环 10 项单测（api/tests/agent）
- **日志落盘轮转**：Python Server 业务日志写 `~/.dingda/v2/logs/server.log`（5MB×5 轮转，文件无 ANSI 色码），壳日志写 `logs/shell.log`（超 1MB 改名 .old）——stderr 日志不再随窗口消失
- **观测性埋点**：SSE `runId` 绑定为日志 trace id（同链路日志行尾自动带 `trace=<id>`，前端报 runId 即可对上服务端日志）；启动 / 崩溃恢复 / uv sync 耗时以 `elapsed=` 进日志；壳清理外部 CLI 删除后的死枚举

- **`.env` 加载器补回**：外部 CLI 删除后 Server 侧没人读 `.env`——`core.config.load_dotenv_file()` 在入口读 `DINGDA_SERVER_DIR`（缺省 CWD）下的 `.env`，真实环境变量优先不覆盖，异常编码容错不崩启动。

### 修复

- Agent：未配置 LLM key 时 SSE 流不再裸抛异常，改为发 `error` + `runCompleted(1)` 兜底事件
- **Python Server 崩溃自愈（watchdog）**：Rust 壳常驻监督循环——启动成功后每 15s 探活
  `/health`，连续失败 2 次（≈30s 不可用）判定崩溃，带退避（2s→4s→8s）自动重启最多 3 次；
  成功重发 `server-ready`（前端状态机原样接住），耗尽发 `server-error` 终态并停手，
  随 `stop()`（用户退出）结束
- **SQLite 并发加固**：`session.connect` 成为全项目连接唯一出口——WAL（读写不互斥）+
  busy_timeout 5s（锁冲突等待而非立即抛 database is locked）+ synchronous=NORMAL；
  四个 repo 的连接/事务代码收敛到共享 `connection()` 上下文
- **LLM 显式超时**：Agent 循环与 DOM 修复链的 OpenAI 客户端不再吃 SDK 默认 600s——
  connect 10s / read 默认 120s（`DINGDA_LLM_TIMEOUT` 可覆盖）/ 重试收敛到 1 次

- **依赖安全清欠**：`pnpm audit --prod` 24 项（1 critical / 9 high / 11 moderate / 3 low）→ 0。
  根因是 shadcn CLI 被声明为主题包生产依赖，把 express/undici/MCP SDK 等服务端链拖进
  prod 图；现将 base-nova 主题 CSS vendor 进 `@v2/ui-theme`（MIT，带溯源头）并移除该依赖，
  另以 pnpm.overrides 收口 `source-map-js`

### 工具链

- pi 扩展：移植 agent-skills hooks 为 `.pi/extensions/sdd-cache.ts`（HTTP 缓存 304 复用）
  与 `simplify-ignore.ts`（代码块折叠/恢复，`/simplify-restore`），37 项 bun 单测

## 历史

版本发布记录见 GitHub Releases（tag 由 `desktop-release.yml` 自动生成）。
