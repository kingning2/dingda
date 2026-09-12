---
name: agent-architecture
description: 约束叮答产品 Agent 的目录、职责和依赖。开发或修改 Python Agent、Planner、Executor、LangGraph、Workflow（Research/比价/选品）、或把爬虫/浏览器接到 Agent 时使用。禁止 Agent 直接 import Playwright、Camoufox、SQLite 或具体电商平台。
---

# Agent 架构开发规范

先读 [layers.md](../layers.md)（含**核心规则**原文）。本 Skill 只管**产品 Agent**（`server/src/agent/`），不管 `packages-rs/client` 里的 CLI Agent Runtime。

## 核心规则（本层相关）

- Agent / MCP / Tool 不得直接操作 Playwright/Camoufox，统一通过 Tool → Crawler → Browser。
- Crawler 禁止直接依赖 Playwright / Camoufox，必须依赖 Browser Interface。
- Browser 禁止出现 Xianyu、1688、商品、价格等平台业务逻辑。
- 禁止为了该架构新增 Rust Crawler、Rust Browser 或数据库层。

## 何时必须遵守

- 实现或修改产品 Agent / planning / execution loop
- 新增 Workflow（Research、PriceCompare、ProductDiscovery）
- 让 Agent 调用搜索、爬取、浏览器、快照
- Review 涉及 `domains/agent`、未来的 `server/src/agent/`

## 目标目录

```text
server/src/agent/
├── core/
└── workflows/
server/src/tools/          # 能力边界在这里，不要在 agent/ 下再实现 Playwright/Crawler
```

| 目录 | 放什么 |
|------|--------|
| `core/` | Agent、Context、State、Planner、Executor、execution loop、tool selection |
| `workflows/` | Research、PriceCompare、ProductDiscovery 等业务流程 |
| `server/src/tools/` | Agent 可调用能力的 Definition / Schema / Executor |

不要建 `server/src/agent/tools/` 第二套实现。Agent 只通过 Tool Registry 选工具。

现存空骨架在 ``server/src/agent/``。**新代码写这里**，不要再往 ``domains/`` 堆 Agent。`api/agent.py` 应调用 `src.agent`。

## Agent Core

负责：

* planning
* reasoning
* state
* context
* tool selection
* execution loop

不负责：

* Playwright
* HTTP 请求（平台 API / 页面抓取）
* SQLite
* WSS
* 具体电商平台解析

Core 可以持有 `AgentState` 与 `Context`，可以决定「下一步调哪个 Tool」。Core 不能打开浏览器、不能 `fetch` 闲鱼、不能 `INSERT` 快照。

## Workflow

负责：

```text
Research
PriceCompare
ProductDiscovery
```

等业务流程。

Workflow 可以组合 Agent、Tool，但不能直接绕过 Tool 调用底层 Browser/Crawler。

`server/src/domains/research/` 是未来 Workflow 的候选落点之一；新调研编排放到 `server/src/agent/workflows/research.py`（或同级包），由 API 调用 Workflow，而不是让 ResearchService 自己 import Camoufox。

## 依赖

```text
api/agent.py
  → workflows 或 core.Agent
    → tools.registry  (按名字调用)
      → tools（registry / search / product）
        → crawler / browser ports
```

允许 import：

- `src.agent.core.*`、`src.agent.workflows.*`
- `src.tools` 的 **definition / registry / 结果类型**
- `src.contracts.agent`

禁止 import：

- `playwright`、`camoufox`
- `src.browser.adapters.*`
- `src.crawler.sources.*`
- `src.channels.xianyu*`、`src.channels.xiaohongshu*`
- `src.infrastructure.db*`、`sqlite3`
- `src.browser.adapters.camoufox`

## 状态规则

- Tool **不允许隐式修改** Agent State。Executor 根据 Tool Output Schema 显式写回。
- 取消、超时由 execution loop 传给 Tool（见 tool-architecture），不要在 Core 里杀浏览器进程。
- 事件用结构化 payload（tool 名、参数、结果、错误码），不要把 Playwright Page 塞进 Context。

## 错误示例

```python
from playwright.async_api import async_playwright

class Agent:
    async def search(self):
        browser = await async_playwright().start()
```

```python
# ❌ 平台逻辑进 Agent
from src.channels.xianyu.api import HOME_URL

class Agent:
    async def search(self, q: str):
        ...
```

## 正确示例

```text
Agent
 ↓
CrawlerTool          # 名字如 crawler.search_products
 ↓
Crawler
 ↓
BrowserPort
 ↓
CamoufoxAdapter
```

```python
# ✅ Core 只认 Tool 名与 Schema
result = await tools.call("crawler.search_products", {
    "platform": "xianyu",
    "query": query,
}, timeout_s=30, cancel=cancel)
self.state.apply_tool_result("crawler.search_products", result)
```

## 新增平台 / 新增浏览器

不要改 `agent/core/`。

- 新平台 → crawler Source + 必要时一个 Tool 参数枚举
- 新浏览器 → browser adapter
- 只有公共抽象真缺能力时，才改 Tool Contract（所有实现一起改）

## 检查清单

- [ ] 文件在 `server/src/agent/core` 或 `workflows`，不是 `utils/` / `domains/agent/service.py` 上帝类
- [ ] 无 Playwright / Camoufox / sqlite3 / 平台包 import
- [ ] 外部世界只经 Tool
- [ ] Workflow 未直呼 Crawler/Browser 类
- [ ] 未新增 Tauri command 来跑产品 Agent（产品 Agent 走 Python HTTP/SSE）
- [ ] 未把代码写进 `packages-rs/runtime/src/`
