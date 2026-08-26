---
name: market_research
description: >
  闲鱼/1688 选品调研：联网检索 → 分析 → 规划关键词 → 渠道核验 → 成文。
  适用于查行情、比价、找货源；不适用于闲聊。
---

# Market Research Skill

## 做什么

针对闲鱼与 1688 的选品 / 比价调研。先收集公开网页材料，再规划关键词，必要时用渠道搜索核验真实供给与挂价，最后输出结论。

## 入参（AI / 上游）

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `query` | string | 是 | 用户选品、比价或找货源的需求原文 |
| `system` | string | 否 | 补充约束（品类偏好、预算等） |
| `account_id` | string | 否 | 渠道核验用的已登录账号 ID |

对应代码：`skills.market_research.skill.MarketResearchParams`

## 绑定工具（均有 description + 参数 schema，供模型 `bind_tools`）

| 工具 | 作用 | 主要参数 |
|---|---|---|
| `web_fetch` | 公开网页检索，返回标题/链接/摘要 | `query`, `max_results` |
| `web_scrape` | 对 URL 抽取正文（trafilatura） | `url` |
| `alibaba_search` | 1688 货源/报价核验 | `keyword`, `account_id`, `cookies`, `max_results` |
| `xianyu_search` | 闲鱼在售挂价核验 | `keyword`, `account_id`, `cookies`, `max_results` |
| `knowledge_retrieve` | 本地知识库短摘要 | `query` |

注册：`skills.registry.register_skill(SPEC)` → `tools.registry.bind_skill_tools`

AI 目录：`skills.registry.skill_catalog_for_ai()`

## 入口

- `skills.market_research.workflow.run_price_compare`
- `skills.market_research.workflow.run_reply`
- Agent run kind: `price_compare`

## 图节点

`web_research → article_analyze → planner → crawl → normalize → match → analyze → finalize`
