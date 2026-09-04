# DingDa

桌面端 Web 产品（React）+ Tauri 壳 + Python Server（`server/`）。不是 `apps/` / `packages/` monorepo。

## Cursor 编码约束（写代码必遵）

| 规则 / Skill | 作用 |
|------|------|
| `.cursor/rules/dingda-coding.mdc` | 全局架构（alwaysApply） |
| `.agents/skills/python-coding/SKILL.md` | Python **示例驱动**（注释 / 插座 / 命名 / 日志） |
| `.agents/skills/rust-coding/SKILL.md` | Rust **示例驱动** |
| `.agents/skills/*-architecture/` | Agent / Crawler / Browser / Tool / 前端 |

写 Python / Rust 时必须按对应 Skill 里的示例 A/B/C 形状编写，不能只看摘要。

Browser / Crawler **核心规则**原文见 `.agents/skills/layers.md` 与 alwaysApply 的 `dingda-coding.mdc`。
