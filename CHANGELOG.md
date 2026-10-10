# 更新日志

本项目的所有重要变更记录于此。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本遵循 [语义化版本](https://semver.org/lang/zh-CN/)；版本号只在
`desktop-release.yml` 打 tag 时递增，日常变更进 Unreleased。

## [Unreleased]

### 新增

- **工作流技能包**：引入 agent-skills（MIT）25 个生命周期技能至 `.agents/skills/`，
  共享检查清单至 `.agents/references/`，9 个 slash 命令至 `.pi/prompts/`
  （`/spec` `/plan` `/build` `/test` `/constraints` `/review` `/webperf` `/code-simplify` `/ship`）
- **质量约束体系**：新增 `CONSTRAINTS.md`（地板规则 + 棘轮基线 + 例外表）、
  `pnpm check:fast`（floor-guard + layers-guard）、CI `floor` 阻断 job 与
  `observe` 观察期 job（分层 / gitleaks / pnpm audit）
- **架构决策记录**：`docs/adr/`（仓库形态、uv 工作区拆分、分层铁律、约束棘轮）
- **Agent 单测**：`AgentService` 工具循环 10 项单测（api/tests/agent）

### 修复

- Agent：未配置 LLM key 时 SSE 流不再裸抛异常，改为发 `error` + `runCompleted(1)` 兜底事件

### 工具链

- pi 扩展：移植 agent-skills hooks 为 `.pi/extensions/sdd-cache.ts`（HTTP 缓存 304 复用）
  与 `simplify-ignore.ts`（代码块折叠/恢复，`/simplify-restore`），37 项 bun 单测

## 历史

版本发布记录见 GitHub Releases（tag 由 `desktop-release.yml` 自动生成）。
