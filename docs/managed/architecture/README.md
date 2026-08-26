# DingDa 系统架构与业务

> **本文件是系统业务与架构叙事的唯一入口。**  
> 领域细节见 [`../domains/`](../domains/)；长期决策见 [`../decisions/`](../decisions/)；变更过程见 [`../changes/`](../changes/)。

本地优先的 **AI Agent 智能客服** 桌面应用。React 只负责展示；**Rust 是唯一协调者**（默认实现含 AI）；Python Sidecar 仅补 Rust 生态缺口（[ADR-0009](../decisions/python-runtime/adr-0009-python-only-when-rust-insufficient.md)）。

## 分层

```text
React（展示）  →  Tauri IPC  →  Rust（协调者，默认实现含 AI）
                                  ↓ 仅当 Rust 生态不够
                               Python Sidecar（例外，不是 AI Runtime）
```

## 硬禁令

| 禁止 | 说明 |
|------|------|
| React → Python | 含 localhost HTTP / WebSocket / SSE |
| React → SQLite | 存储由 Rust 负责 |
| Python → SQLite | 存储由 Rust 负责；AI 仅只读 Query Port |
| 把新 AI 能力默认放 Python | 默认用 Rust；Python 只补生态缺口 |
| AI 写库 / 自动发信 | 数据与发送仅 UI 人工操作 |
| Feature 间直接 import | 跨 Feature 只允许 Query Port · Event · Contract |
| 先改实现再改契约 | 跨端变更须先改 `contracts/` |

可执行约束见 [`.cursor/rules/master.md`](../../../.cursor/rules/master.md)。

## 当前领域（事实入口）

| 领域 | 说明 |
|------|------|
| [Agent](../domains/agent/README.md) | AI 编排、模型配置、比价/调研等核心业务 |
| [Python Sidecar](../domains/python-runtime/README.md) | 例外 Sidecar（IPC、渠道缺口能力） |
| [Runtime](../domains/runtime/README.md) | 进程 / Worker / 生命周期 |
| [Channel](../domains/channel/README.md) | 渠道登录与消息桥 |
| [Contracts](../domains/contracts/README.md) | 跨端契约真相源 |
| [Storage](../domains/storage/README.md) | 本地持久化边界 |
| [OCR](../domains/ocr/README.md) | 本地 OCR 插件 |
| [Documentation](../domains/documentation/README.md) | managed docs 治理 |

## 仓库结构（对照）

- `apps/desktop` — Tauri + React
- `packages/` — 前端共享包
- `python/` — 例外 Sidecar
- `contracts/` — 跨端契约
- `tooling/dingda/` — 分支规则与契约 codegen 脚本
- `docs/managed/` — 本架构入口 · Domain · ADR · Change
