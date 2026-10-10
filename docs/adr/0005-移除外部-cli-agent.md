# ADR-0005：移除外部 CLI Agent，AI 能力统一内置 Agent

状态：采纳 · 日期：2026-02-14

## 背景

早期产品把「跑 AI」委托给本机安装的外部 CLI（codex / claude / opencode）：
前端 `/agents` 页做探测 / 登录 / 下载 / 选模型，Python `cli/` 包 spawn 进程并转 SSE，
Rust `runtime` + `agent` crate 做 PATH 探测与托管下载，crawler 的 DOM 修复链也用
外部 CLI 产出补丁。这条链路带来一整层只为「调外部进程」存在的代码：探测缓存、
鉴权视图、偏好存储、模型目录、直播帧投递、以及大量因各 CLI 行为差异打的补丁。

实际使用后裁决（2026-02）：产品只需要一条 AI 链路。外部 CLI 的安装状态、区域可用性、
模型配额都不可控，而内置 Agent（`agent_id="dingda"`，进程内 LLM + Tool 循环）已能
覆盖全部产品场景。

## 决策

1. **AI 能力统一内置 Agent**：唯一 `agent_id="dingda"`；模型由 Server 侧
   `DINGDA_LLM_*` 环境变量决定，客户端不选型。
2. **整链删除**：
   - Python：`packages-py/cli` 包、`/v1/agent/runtimes*` 端点（扫描 / 偏好 / 默认 /
     外部 run / 直播帧 / 取消）、`AgentPing*` 契约；
   - DOM 修复链：`propose_dom_patch` 改内置 LLM（`DINGDA_DOM_REPAIR_MODEL`），
     `crawler/extraction/repair/bridge.py` 删除；
   - 前端：`ui-agent/src/cli/` 与 `agent-catalog.ts`、`/agents` 页整页、Composer
     Agent 选择器、`supportsExternalAgents()` 能力位、`agent-runtime` 契约；
     `run/stream` 改打 `POST /v1/agent/works/{workId}/run`，前端发送链与内置
     Agent 接通；
   - Rust：`packages-rs/agent`、`packages-rs/runtime`、`client` 的
     `agent_runtime` 命令删除，成员包收敛为 `common / camoufox / python / client`。
3. **保留**：`tools/cli.py`（开发者自省命令）与 `internal_only` 字段；
   `test_cli_compress.py`（压缩逻辑单测）；e2e `ai-product-search.spec.ts` 改由
   内置 Agent 驱动。

## 后果

- 删除约 3k 行只为外部进程桥接存在的代码；uv workspace 少一个成员，
  Rust workspace 从 6 包收敛到 4 包。
- `/assets`、`/integrations` 旧书签重定向到 `/accounts`；`/agents` 不再存在。
- 前端取消运行 = AbortController abort：服务端继续跑完并落库，UI 丢弃后续事件。
- 浏览器 Web 端与桌面端能力面一致（都只有产品 HTTP + 对话框 / 窗口），不再需要
  按环境 mock Agent。
- 修复链模型选择从「本机装了什么 CLI」变成一个环境变量，可复现。
