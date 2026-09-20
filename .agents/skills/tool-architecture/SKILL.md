---
name: tool-architecture
description: 约束叮答 Agent 节点（工具）契约与实现边界。编写 list/detail/login/live 节点、registry、或把 Crawler 暴露给 Agent 时使用。每个节点必须有名称、输入/输出 Schema、错误模型；禁止隐式修改 Agent State；禁止再建 packages-py/tools/。
---

# Tool / 节点架构开发规范

先读 [layers.md](../layers.md)（含**核心规则**原文）。**节点即工具**：Agent 与底层能力之间的边界在 `agent/nodes/`，经 `core/registry.py` 调用。不要再建 `packages-py/tools/`。

## 核心规则（本层相关）

- Agent / 节点不得直接操作 Playwright/Camoufox，统一通过 Node → Crawler → Browser。
- Crawler 禁止直接依赖 Playwright / Camoufox，必须依赖 Browser Interface。
- 禁止为了该架构新增 Rust Crawler、Rust Browser 或数据库层。

## 何时必须遵守

- 给产品 Agent 加能力（新节点）
- 把 Crawler / Browser / Snapshot 暴露给 Agent
- 改节点名、入参/出参、错误码

## 目标目录

```text
packages-py/agent/src/agent/
├── nodes/           # 每个节点：入参 + 出参 + _execute
│   ├── list/
│   ├── detail/
│   ├── login.py
│   └── live.py
├── core/
│   ├── registry.py  # call_node / list_nodes
│   └── node.py      # Node / NodeContext / NodeOutput
└── engine/
    └── tools.py     # 节点 → OpenAI tools 表
```

不要新建 `packages-py/tools/`，也不要在 `agent/tools/` 再写一套实现。能力就落在 `nodes/`。

## 契约流

```text
Node Definition（name / description / input_model）
    ↓
registry.call_node
    ↓
Node._execute → Crawler
    ↓
NodeOutput
```

节点必须：

* 有明确名称（注册到 `ALL_NODES`）
* 有输入 Schema（pydantic `input_model`）
* 有输出 Schema（`NodeOutput` 子类）
* 失败用 `ok=False` + `error_code`，不抛异常打断发动机
* 不允许隐式修改 Agent State

名称示例（当前）：

```text
login
list_xianyu / list_xiaohongshu / list_ali1688
detail_xianyu / detail_xiaohongshu
live
```

## 单文件节点 vs registry

| 层 | 放什么 | 谁依赖 |
|----|--------|--------|
| `nodes/<…>.py` | 名字、描述、Input/Output、`_execute` | registry、测试 |
| `core/registry.py` | 按名查找、发 toolCall/toolResult | engine |
| `engine/tools.py` | 节点 → 模型 tools 数组 | engine |

发动机只经 `registry.call_node`。禁止直接 import Crawler Source / Playwright。

## 执行语义

- **cancellation**：经 `NodeContext.cancel`；浏览器抓取当前只能在步与步之间停下。
- **结构化事件**：`toolCall` / `toolResult` 由 registry 发；节点可经 `ctx.emit_frame` 推浏览器帧。
- **错误模型**：稳定 `error_code` + `message`。不要把 Playwright traceback 当唯一输出。
- **无隐式 State**：节点返回 `NodeOutput`；由发动机回填消息。节点不要去改「对话状态」。

## 谁可以调用节点

| 调用方 | 路径 |
|--------|------|
| 产品 Agent 发动机 | `registry.call_node` |
| 前端手动爬虫 | **可以不经节点**，HTTP → Crawler 应用服务 → 同一 Crawler Core |

## 依赖

```text
api → agent.engine → registry.call_node → nodes → Crawler → Browser → Adapter
```

禁止：

```text
❌ Agent / Node → Playwright / Camoufox
❌ Agent → SQLite / infrastructure.db
❌ Node → crawler.sources.* 私有细节捷径（走 crawler 公开插座）
❌ 再建 packages-py/tools/ 第二套能力包
```

## 错误 / 正确

```python
# ❌ 节点偷偷改对话状态，且打开 Playwright
class SearchNode:
    async def _execute(self, inp, *, ctx):
        from playwright.async_api import async_playwright
        ctx.meta["items"] = []
        browser = await async_playwright().start()
```

```python
# ✅ 经 crawler 插座取数，失败用 ok=False
async def _execute(self, inp: ListInput, *, ctx: NodeContext) -> ListOutput:
    return await …  # 经 crawler → BrowserPort
```

## 新增节点清单

1. 在 `packages-py/agent/src/agent/nodes/` 写名字 + Input + Output + `_execute`
2. `_execute` 只调 Crawler 插座，不调平台私有包捷径
3. 挂到 `nodes/__init__.py` 的 `ALL_NODES`
4. 需要登录恢复时套 `with_login_recovery`
5. 单测只测 Schema 与假 Port，不启动浏览器
6. 不改发动机核心（除非系统提示要加选型说明）

## 检查清单

- [ ] 有名字、输入/输出 Schema、错误码
- [ ] 失败不抛未捕获异常打断循环
- [ ] 不修改对话 State
- [ ] 实现不 import Playwright / Camoufox
- [ ] 未再建 `packages-py/tools/`
- [ ] 未把该能力做成 Tauri command
