# ADR-0002：单体 server 拆分为 packages-py uv 工作区

状态：采纳 · 日期：2026-02（b19fe541）

## 背景

早期后端是单个 `server/` 目录（LangChain 版 Agent、工具、爬虫、浏览器、渠道全在一个
包里）。问题：任何一个模块的依赖变更都会触发整包重装；Agent 直接 import Playwright
和 SQLite，分层只靠约定没有依赖方向约束；测试集中在 api 一层，跨层改动无法单测。

## 决策

按分层把单体拆成 uv 工作区的 11 个成员包，依赖方向单向：

```
Agent → Tool → Crawler → BrowserPort → Adapter
```

- 成员：`agent` `tools` `crawler` `browser` `channels` `domains` `api` `core`
  `contracts` `cli` `infrastructure`，单一 `uv.lock`。
- 每包一个 `src/<pkg>/README.md` 写职责与禁区；跨层 import 视为违规
  （机械检查见 ADR-0003 的 layers-guard）。
- LangChain 版 Agent 在同一次拆分中被重写为 `AgentService`（OpenAI-compatible
  直连 + `tools.registry` 选型），快照里的旧测试不随迁 —— 旧架构的测试不测新架构。

## 后果

- 依赖图可审计：`uv tree` 一眼看出谁越层。
- 新增平台/浏览器/渠道分别只改 `crawler/sources/<platform>`、
  `browser/adapters/<browser>`、`channels/<platform>`，不再碰别的包。
- 代价：新增一个后端包要同时登记 `pyproject.toml` 工作区成员与 README。
