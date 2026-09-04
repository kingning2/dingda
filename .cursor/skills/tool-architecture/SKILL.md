---
name: tool-architecture
description: 约束叮答 Tool 契约与实现边界。编写 crawler.search_products、browser.open/click/extract、snapshot.save、MCP 工具、Agent 可调用能力，或改 tool registry 时使用。每个 Tool 必须有名称、输入/输出 Schema、错误模型、timeout 与 cancellation；禁止隐式修改 Agent State。
---

# Tool 架构

唯一正文：`.agents/skills/tool-architecture/SKILL.md`

立即读取并遵守：

1. `.agents/skills/layers.md`
2. `.agents/skills/tool-architecture/SKILL.md`

产品 Agent 与 MCP 共用同一 Tool Executor。不要把 Tool 做成 Tauri command。
