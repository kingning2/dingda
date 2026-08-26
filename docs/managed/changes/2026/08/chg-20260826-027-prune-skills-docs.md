---
id: CHG-20260826-027-prune-skills-docs
title: 删除 skills/dingda，业务叙事收敛到 architecture
type: change
status: completed
priority: P2
owner: auto
domain: documentation
parent: none
depends_on: []
blocks: []
milestone: none
created: 2026-08-26
updated: 2026-08-26
contracts: none
related: []
---

# 删除 skills/dingda，业务叙事收敛到 architecture

## 目标

仓库只保留一处系统业务/架构叙事（`docs/managed/architecture/README.md`）；删除 `skills/dingda`；分支与契约脚本迁至 `tooling/dingda/` 并保持 `pnpm branch*` / `contracts:sync` 可用。

## 非目标

- 不搬迁脚手架 templates / create_feature 等未接线脚本
- 不重写全部 ADR / Change 历史
- 不改产品运行时行为

## 背景

`skills/dingda` 混有叙事与活工具，与 `AGENTS.md`、根 README、`docs/managed` 三重重复。planned 空壳 domain 增加噪音。

## 影响与边界

- 修改范围：`skills/dingda`（删除）、`tooling/dingda/`（新建）、`package.json`、`.husky/post-checkout`、`tooling/scripts/sync-contracts.mjs`、入口文档与 domains 索引、`.cursor/rules` 外链
- 不修改范围：业务代码、契约 schema
- Contract：无
- 跨层：否
- 跨 Feature：否
- 风险：路径未改全会导致 branch:sync / contracts:sync 失败

## 依赖关系

- 父任务：无
- 前置任务：无
- 阻塞任务：无

## 实施方案

1. 迁 branch/contracts 相关脚本与 `branch_roles.json` 到 `tooling/dingda/`
2. 更新 package.json / husky / sync-contracts 引用
3. 新建 architecture README；删 planned domains；瘦身 AGENTS/README
4. 删除 `skills/dingda/`；全仓检索验收

## 验收

- [x] `rg skills/dingda` 无业务引用（仅本 Change 可提及）
- [x] `pnpm branch:sync` 可跑
- [x] `contracts:sync` 指向 `tooling/dingda/scripts/sync_contracts.py` 且可执行
- [x] 业务叙事从 `docs/managed/architecture/README.md` 起读
- [x] 实际结果已回填

## 实际结果

- 脚本迁至 `tooling/dingda/{scripts,config}/`；`package.json` / husky / `sync-contracts.mjs` 已改路径
- 新建 `docs/managed/architecture/README.md` 为唯一业务叙事入口
- 删除 planned 空壳 domains：kol / alert / analytics / pricing / schedule / workflow
- 瘦身 `AGENTS.md`、根 `README.md`；清理 `.cursor/rules` 中 `skills/dingda` 与过时 `skills/opendesk` 链接
- 整目录删除 `skills/dingda/`；`pnpm branch:sync`、`pnpm contracts:sync` 验证通过

## 后续项

- 无
