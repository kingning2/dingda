---
name: browser-architecture
description: 约束叮答 Browser 基础设施与适配器。开发或修改浏览器生命周期、Context、Page、Cookie、导航、DOM、Playwright、Camoufox、CDP 时使用。禁止 Browser 包含商品模型或 Agent 推理；禁止 Agent/Crawler 直接 import Playwright 或 Camoufox。
---

# Browser 架构

唯一正文：`.agents/skills/browser-architecture/SKILL.md`

立即读取并遵守：

1. `.agents/skills/layers.md`
2. `.agents/skills/browser-architecture/SKILL.md`

新浏览器只加 `server/src/browser/adapters/`。不要让 Agent 直接 import Playwright。
