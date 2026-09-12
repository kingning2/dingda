---
name: crawler-architecture
description: 约束叮答 Crawler 模块目录与平台扩展方式。开发或修改爬虫、闲鱼/1688/淘宝/Amazon/小红书抓取、解析、snapshot、去重、CrawlTask 时使用。禁止把平台特例写入 crawler/core 或 agent，禁止 Crawler 包含 Agent 决策，禁止 crawler 直接当 Playwright 入口。
---

# Crawler 架构

唯一正文：`.agents/skills/crawler-architecture/SKILL.md`

立即读取并遵守：

1. `.agents/skills/layers.md`
2. `.agents/skills/crawler-architecture/SKILL.md`

新平台只加 `packages-py/crawler/src/crawler/sources/<id>/`。不要改 Agent Core / Browser。
