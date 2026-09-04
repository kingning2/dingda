---
name: tool-architecture
description: 约束叮答 Tool 契约与实现边界。编写 crawler.search_products、browser.open/click/extract、snapshot.save、MCP 工具、Agent 可调用能力，或改 tool registry 时使用。每个 Tool 必须有名称、输入/输出 Schema、错误模型、timeout 与 cancellation；禁止隐式修改 Agent State。
---

# Tool 架构开发规范

先读 [layers.md](../layers.md)（含**核心规则**原文）。Tool 是 Agent 与底层能力之间的边界。Agent 只认识 Tool Contract。

## 核心规则（本层相关）

- Agent / MCP / Tool 不得直接操作 Playwright/Camoufox，统一通过 Tool → Crawler → Browser。
- Crawler 禁止直接依赖 Playwright / Camoufox，必须依赖 Browser Interface。
- 禁止为了该架构新增 Rust Crawler、Rust Browser 或数据库层。

## 何时必须遵守

- 给产品 Agent 加能力
- 写 MCP tool（`server/src/mcp/`、`dingda-mcp`）
- 把 Crawler / Browser / Snapshot 暴露给 Agent 或外部 CLI
- 改工具名、参数、错误码、超时

## 目标目录

```text
server/src/tools/
├── registry.py
├── search.py      # 契约 + run_search
├── product.py     # 契约 + run_product
└── …
```

按现有包习惯放在 `server/src/tools/`，不要新建顶层 `tools/`，也不要在 `agent/tools/` 再写一套实现。

MCP 不是第二套能力模型：新 Tool 先在 `tools/<name>.py` 落地（Schema + `run_*`），再挂 `registry.py`；MCP 与产品 Agent **共用**同一 Executor。

## 契约流

```text
Tool Definition
    ↓
Input Schema
    ↓
Executor
    ↓
Output Schema
```

Tool 必须：

* 有明确名称
* 有输入 Schema
* 有输出 Schema
* 有错误模型
* 支持 timeout
* 支持 cancellation
* 支持结构化事件
* 不允许隐式修改 Agent State

名称示例（当前选品）：

```text
search
product
```

## 单文件 Tool vs registry

| 层 | 放什么 | 谁依赖 |
|----|--------|--------|
| `tools/<name>.py` | 名字、描述、Input/Output、超时、`run_*` | registry、测试 |
| `registry.py` | 按名查找、执行 | Agent Executor、MCP |

Agent Core 只经 `registry.call_tool`。禁止直接 import Crawler Source / Playwright。

## 执行语义

- **timeout**：Executor 必须能在时限结束时停止调用（取消 token 或等价物），并返回明确错误（如 `tool.timeout`），而不是挂死。
- **cancellation**：Agent 取消 run 时向下传；Browser/Crawler 实现要能中止，不要无视。
- **结构化事件**：至少 `tool.started` / `tool.progress` / `tool.completed` / `tool.failed`，payload JSON 可序列化。产品 Agent 经 Python 事件总线/SSE；不要为 Tool 进度新增 Tauri emit。
- **错误模型**：稳定 `code` + `message` + 可选 `details`。不要把 Playwright traceback 当唯一输出。
- **无隐式 State**：Executor 返回 Output Schema；由 Agent loop 写 State。Tool 不要去改 `agent.state`。

## 谁可以调用 Tool

| 调用方 | 路径 |
|--------|------|
| 产品 Agent | `registry.call` |
| 外部 CLI（Codex 等） | MCP stdio → 同一 `registry.call` |
| 前端手动爬虫 | **可以不经 Tool**，HTTP → Crawler 应用服务 → 同一 Crawler Core |

不要为 MCP 单独再写一个 `XianyuSearch` 而产品 Agent 用另一套参数。

## 依赖

```text
Workflow → Agent → Tool Contract → Tool Implementation → Crawler / Browser → Adapter
```

禁止：

```text
❌ Agent → XianyuCrawler
❌ Agent → Playwright
❌ Agent → SQLite
❌ Workflow → Camoufox
❌ MCP handler 里直接 import 平台 vendor 再抄一份业务
```

## 错误 / 正确

```python
# ❌ Tool 偷偷改 Agent，且打开 Playwright
class SearchTool:
    async def run(self, agent, q):
        from playwright.async_api import async_playwright
        agent.state["items"] = []
        browser = await async_playwright().start()
```

```python
# ✅ 纯契约执行
async def run_search(inp: SearchInput) -> SearchOutput:
    return await …  # 经 Crawler → BrowserPort
```

## 新增 Tool 清单

1. 在 `server/src/tools/<name>.py` 写名字 + Input + Output + `run_*`
2. `run_*` 只调 Crawler/Browser Port，不调平台私有包细节之外的捷径
3. 注册到 `registry.py`
4. 需要给 CLI 用时，MCP 用同一 registry 注册
5. 加超时/取消/事件
6. 单测只测 Schema 与假 Port，不启动浏览器
7. 不改 Agent Core（除非 Planner 的允许列表要加名字）

## 检查清单

- [ ] 有名字、输入/输出 Schema、错误码
- [ ] 有 timeout 与 cancellation
- [ ] 不修改 Agent State
- [ ] 实现不 import 平台 Source 或 Playwright 实现类
- [ ] MCP 与产品 Agent 未分叉业务
- [ ] 未把该能力做成 Tauri command
