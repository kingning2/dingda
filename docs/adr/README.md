# 架构决策记录（ADR）

一个决策一个文件，编号递增不改名。已推翻的决策标 `状态: 已废弃（被 ADR-XXX 取代）`，
不删除 —— ADR 记录的是"当时的理由"，历史被删掉就无法解释现状。

| # | 决策 | 状态 |
|---|------|------|
| [0001](0001-三入口仓库形态.md) | 三入口仓库形态：pnpm / Cargo / uv 三工作区互不干涉 | 采纳 |
| [0002](0002-python-server-拆分为-uv-工作区.md) | 单体 server 拆为 packages-py uv 工作区 | 采纳 |
| [0003](0003-能力归-browser-平台归-crawler.md) | 能力归 Browser、平台归 Crawler 的分层铁律 | 采纳 |
| [0004](0004-质量约束棘轮.md) | 质量约束写进 CONSTRAINTS.md 并以守卫棘轮化 | 采纳 |
| [0005](0005-移除外部-cli-agent.md) | 移除外部 CLI Agent，AI 能力统一内置 Agent | 采纳 |

新写 ADR 拷贝 [模板](template.md)。
