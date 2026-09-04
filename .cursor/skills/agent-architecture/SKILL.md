---
name: agent-architecture
description: 约束叮答产品 Agent 的目录、职责和依赖。开发或修改 Python Agent、Planner、Executor、LangGraph、Workflow（Research/比价/选品）、或把爬虫/浏览器接到 Agent 时使用。禁止 Agent 直接 import Playwright、Camoufox、SQLite 或具体电商平台。
---

# Agent 架构

唯一正文：`.agents/skills/agent-architecture/SKILL.md`

立即读取并遵守：

1. `.agents/skills/layers.md`
2. `.agents/skills/agent-architecture/SKILL.md`

未读完不要写产品 Agent 代码。不要把实现放进 `src-tauri/src/runtime/`，不要为产品 Agent 新增 Tauri command。
