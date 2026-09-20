---
name: agent-architecture
description: 约束叮答产品 Agent 的目录、职责和依赖。开发或修改 Python Agent、主编排、爬虫/修复/验证子 agent、工具、LangGraph、或把爬虫/浏览器接到 Agent 时使用。禁止 Agent 直接 import Playwright、Camoufox、SQLite 或具体电商平台包。
---

# Agent 架构开发规范

先读 [layers.md](../layers.md)（含**核心规则**原文）。本 Skill 只管**产品 Agent**（`packages-py/agent/src/agent/`），不管 `packages-rs/client` 里的 CLI Agent Runtime。

## 核心规则（本层相关）

- Agent / Tool 不得直接操作 Playwright/Camoufox，统一通过 `crawl_session` → Crawler → Browser。
- Tool 禁止直接依赖平台包（`channels.xianyu*` / `channels.xiaohongshu*`）：只经 `crawler.*`、`core.errors`、`crawler.extraction.*` 抽象层。
- Browser 禁止出现 Xianyu、1688、商品、价格等平台业务逻辑（那在 crawler 包）。
- 禁止为了该架构新增 Rust Crawler、Rust Browser 或数据库层。
- 失败统一 `ok=False` + `error_code` 出参，**不抛异常**：编排循环靠 `error_code` 分流。

## 何时必须遵守

- 实现或修改产品 Agent / 主编排 / 三个子 agent / 工具
- 让 Agent 调用搜索、爬取、DOM 修复、选择器验证、浏览器、快照
- Review 涉及 `packages-py/agent/src/agent/`

## 目标目录（2026-09-17 重构后）

```text
packages-py/agent/src/agent/
├── __init__.py     # 近乎空 docstring，避免 import 环
├── sse.py          # EventBus / EventEmit（SSE 事件总线；别名 SseBus/SseEmit）
├── runs.py         # RunManager / RunRecord：run 生命周期 + 有序投递日志（seq），run 活得比 HTTP 请求长
├── steps.py        # 步骤块文案：platform_label / step_label / step_for_call / step_for_result / result_hint / page_from_live_frame
├── context.py      # RunContext（运行上下文 + 依赖注入）；emit_tool_call / emit_tool_result；AuthSnapshot / LoginPort / EmitFn / CookieResolver / AuthChecker 类型
├── session.py      # crawl_session 异步上下文管理器 / CrawlSession；headless() 切换
├── items.py        # DetailItem / ProductComment / item_from_row / comments_from_raw / raw_text
├── loop.py         # run_react（手写 ReAct 循环）+ ToolSpec / build_tools / tool_of / ReactResult / EXIT_OK|EXIT_FAILED|EXIT_CANCELLED
├── orchestrator.py # 主编排：run_orchestrator + SYSTEM_PROMPT + _specs（工具表）
├── run.py          # run_chat（门禁 → 主编排）+ ensure_logins / _login / AUTH_PLATFORMS
├── compress.py     # headroom_enabled / compress_messages / compress_text / compress_tool_payload
├── llm/            # LangChain ChatOpenAI 门面：client / errors / models / providers（deepseek、doubao）
├── tools/          # login / crawl / select / repair / validate / risk（每个导出 TOOLS: tuple[ToolSpec, ...]）
├── subagents/      # crawler / repair / validator（每个导出 run_* + SYSTEM_PROMPT）
└── tests/          # test_loop.py 等
```

| 模块 | 放什么 |
|------|--------|
| `orchestrator.py` | **主编排**：接用户一句话，工具就是 3 个子 agent + 选品 + 2 个兜底 + `finish`，最后判断够不够 |
| `subagents/*` | 子 agent：只执行不决策，跑 `run_react` 取数/修选择器/验证，结论是作为工具结果回主编排 |
| `tools/*` | 具体动作：搜/详情/导出 DOM/试选择器/热更新/选品打分/单品鉴定/扫码/有头窗口；每个导出 `TOOLS` |
| `loop.py` | 一份共享的「问 → 调工具 → 回填 → 再问」循环，主编排与子 agent 都用它 |
| `context.py` | `RunContext` 携带一切外部依赖（cookie_resolver / auth_checker / login_port / llm / cancel），agent 不 import 底层 |
| `llm/` | 只这一处直连 openai SDK；`ctx.llm.chat_model` 是循环用的模型入口 |
| `sse.py` | 事件总线；`agent/runs.py` 是它**唯一**的消费者，API 层只转发，不生产业务事件 |
| `runs.py` | run 生命周期与投递日志：编 `seq`、按 step 淘汰旧截图帧、重放给接回的订阅者。run 活得比 HTTP 请求长，断开只退订不叫停 |

## 编排模型：一主编排 + 三子 agent

```text
用户消息
  → run.py: ensure_logins（三平台并发查登录态，失效逐个发扫码）
  → orchestrator.run_orchestrator（主编排，stream=True 推正文给用户）
       调 crawl      → subagents.crawler.run_crawler   （取真实数据；撞墙进 issues）
       调 select_products → tools.select（候选品类逐个搜索+抓详情 → crawler.selection 确定性打分）
       调 appraise_item → tools.appraise（本商品详情 + 一批同款 → crawler.appraisal 确定性判词）
       调 repair     → subagents.repair.run_repair      （看 DOM，交候选选择器，不写盘）
       调 validate   → subagents.validator.run_validate（试选择器，通过才热更新）
       调 login      → tools.login（扫码兜底）
       调 open_headed_browser → tools.risk（人工过风控兜底）
       调 finish     → 把总结交给前端
```

**决策只在主编排**：换不换词、修不修、验不验、够不够，都由它判断。子 agent 只执行不决策 —— 让爬虫自己决定去修选择器，全局就没人知道发生过什么。

**`select_products` 是工具不是子 agent**：提候选品类关键词是主编排的活（拿主意的那层），算分是 `crawler.selection` 的纯函数（无 LLM、无网络）。把排名藏进一个 LLM 循环里，只会让「分是怎么来的」不可见。反过来，选品结论里的每个品类都必须能追到候选表里算过分的行 —— `excluded` 里的候选、没抓过的平台，都不许写进结论。

**`appraise_item` 同理，粒度不同**：`crawler.appraisal` 回答「**这一件**值不值得买」，参照系是**同款**（同平台同款的中位价），不是品类。价差是转卖的唯一实质理由，所以它是**硬否决** —— 一个需求爆表但比同款还贵的商品仍判「不值得」，不许被加权的需求分补偿。同款集必须剔掉本商品自己，否则中位价被自己拉平、价差恒 0，症状是「所有人都判不值得」（工具与打分器各剔一次，幂等）。出参与选品侧同一约定：**不带顶层 `platform` + `items`**，否则会被前端 `extractProducts` 当成商品列表吞进商品面板。

**「卖什么」的请求有确定性兜底**：`orchestrator._is_decision_request` 命中决策词表时，在用户那轮话前面钉一条硬指令。实测光靠 SYSTEM_PROMPT 拦不住 —— 模型会自己编个关键词去 `crawl`，再把商品列表包装成结论。

**异常分流全靠 `issues[].error_code`**（子 agent 汇总工具出参里的 `error_code`）：

| error_code | 谁报 | 主编排动作 |
|------------|------|-----------|
| `crawler.needs_repair` | crawler 抽到空/字段缺 | 调 `repair_selectors` 拿候选 → `validate_selectors` 验证热更新 → 重新 `crawl` |
| `channel.risk` | crawl / repair / validate | 先让爬虫换个词/时间再试；还不行 → `open_headed_browser` 让用户手动过 |
| `account.session_expired` / `account.cookie_required` | 任意工具 | 调 `login` 发扫码，扫完继续 |

## 设计原则（2026-09-17 重写时确立）

- **手写循环，不引状态图**：编排只有「问 → 调 → 再问」一条线，没有分支与并行，状态图只多样板。真需要分支时再换图，别提前付成本。
- **子 agent 是一次工具调用**：主编排循环里调 `crawl` 就是跑完整个爬虫子 agent。不嵌套图，否则「谁等谁」变成一团。
- **修复不写盘、验证才写盘**：`repair.submit_patch` 只交候选；`validate.commit_selectors` 调 `write_extract_section`（写 `extract.json` + 热加载）后才生效。改坏了止步于候选，不污染线上选择器。
- **风控优先自动过**：`tools/crawl._retry_on_risk` 撞风控等 8s 换新会话再来一次（2 次）；仍过不了才回报，由主编排决定开有头窗口。
- **正文推前端 vs 不推**：只有主编排 `stream=True`；子 agent `stream=False`，其正文作为工具结果回主编排，直接推下去会同主编排播报混在一起刷屏。
- **取消停在步与步之间**：循环每步入口查 `ctx.cancelled()`，跑了一半的工具不被硬打断（硬断会留「执行中」步骤块，前端永远等不到收尾）。
- **步数用尽进不带工具的收尾轮**：否则最后一轮拿工具结果被截断，用户看不到总结。
- **收尾摘要也要发给用户**：模型偶尔把结论写进 `finish` 的 `summary` 参而不是正文。循环命中 stop tool 时，若该步正文为空就把 `summary` 补发成 `textDelta` —— 不补的话结论只进 `ReactResult`，而 `run_chat` 只取 `exit_code`，用户看到的最后一句会停在「我正在…」。

## 依赖

```text
api/agent_run.py（薄层：读「使用中」凭据 → 建 LlmClient → 注入 RunContext → 交给 RunManager）
  → agent.runs.RunManager（编 seq + 记投递日志 + 扇出；HTTP 只是订阅者之一）
    → agent.run.run_chat(bus, ctx, prompt, ...)
```
    → ensure_logins（并发查 auth_checker）
    → orchestrator.run_orchestrator（调 ctx.llm.chat_model）
      → run_react（loop.py）
        → build_tools(ctx, _specs() | subagent_TOOLS)
          → tools.* / subagents.*  → crawl_session → crawler / browser ports
```

`RunContext` 是唯一的依赖注入点，由 `api/agent_run.py` 装配：

- `emit`：SSE 事件落点（接线方 `bind_emit` 后转成 SSE 帧）
- `llm`：`LlmClient`（只 `agent/llm` 包能建），循环用 `ctx.llm.chat_model`
- `cookie_resolver` / `auth_checker` / `login_port`：平台基础设施，agent 不 import
- `cancel`：`asyncio.Event`，取消标记

允许 import：`agent.*`、`contracts`（agent 相关类型）、`crawler.*` / `core.errors` / `crawler.extraction.*`（抽象层，非平台包）。

禁止 import：`playwright`、`camoufox`、`browser.adapters.*`、`channels.xianyu*`、`channels.xiaohongshu*`、`infrastructure.db*`、`sqlite3`。

## 状态规则

- 工具/子 agent **不允许隐式修改**对话状态。循环根据工具出参显式回填 `ToolMessage`。
- 取消、超时由 `RunContext.cancel` 传递，不要在 agent 里杀浏览器进程。
- 事件用结构化 payload（工具名、参数、结果、错误码），不要把 Page/浏览器对象塞进 Context。
- SSE 帧由接线方（`api/agent_run.py`）发 `runStarted`；agent 只发 `textDelta` / `thinking` / `toolCall` / `toolResult` / `browserFrame` / `error`。`runCompleted` 由 `agent.runs` 在日志末尾保证补上 —— 漏发会让前端永远转圈。
- **不要给 run 记生命周期状态**：在跑与否、取消开关、投递日志都在 `agent.runs`。agent 侧只用 `ctx.cancel`（`asyncio.Event`）读取消标记。

## 错误示例

```python
from playwright.async_api import async_playwright

class Agent:
    async def search(self):
        browser = await async_playwright().start()
```

```python
# ❌ 平台逻辑进 Agent
from channels.xianyu.api import HOME_URL

class Agent:
    async def search(self, q: str):
        ...
```

```python
# ❌ 工具抛异常，主编排没了分流依据
def search_items(ctx, platform, query):
    if bad:
        raise RuntimeError("挂了")
```

## 正确示例

```text
orchestrator.run_orchestrator
 ↓ run_react
   ↓ ToolSpec(crawl) → subagents.crawler.run_crawler
     ↓ run_react
       ↓ ToolSpec(search_items/fetch_detail) → tools.crawl
         ↓ crawl_session
           ↓ CrawlSession.crawler.search/detail
             ↓ crawler / browser ports
```

```python
# ✅ 工具失败走 ok=False + error_code，主编排据 error_code 分流
return _fail(plat, "crawler.needs_repair", "抽不到字段，需修复")
```

```python
# ✅ 新工具：导出 TOOLS，fn 是 async fn(ctx, **kwargs) -> dict
TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(name="search_items", label="搜索商品 · {platform}",
             description="...", args=SearchInput, fn=search_items, browser=True),
)
```

## 新增平台 / 新增浏览器

- 新平台 → 在 `crawler/sources/<platform>/` 加 source + extractor + repair_adapter；在 `tools/*._ADAPTERS` / `_SUPPORTED` 登记。
- 新浏览器 → `browser` 包加 adapter；不要改 `agent/` 契约形状。
- 只有公共抽象真缺能力时，才改 `RunContext` / `ToolSpec` / `EventBus`。

## 检查清单

- [ ] 代码在 `packages-py/agent/src/agent/`，不往 `domains/` 堆 Agent 上帝类
- [ ] 决策在 `orchestrator.py`，子 agent 只执行不决策
- [ ] 工具失败返回 `ok=False` + `error_code`，不抛；子 agent 把 `error_code` 汇进 `issues`
- [ ] 修复只交候选、验证通过才 `write_extract_section`，没写盘
- [ ] `stream=True` 只在主编排；子 agent `stream=False`
- [ ] `RunContext` 是唯一依赖注入点，无 Playwright / Camoufox / sqlite3 / 平台包 import
- [ ] 取消停在步与步之间，不留「执行中」步骤块
- [ ] 未新增 Tauri command 跑产品 Agent（产品 Agent 走 Python HTTP/SSE）
- [ ] 未把代码写进 `packages-rs/client/src/`
