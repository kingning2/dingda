# Python Guide

适用范围：`python/**`

## 职责

Python 是 **例外 Sidecar**，不是 AI Runtime、不是业务核心。

默认用 **Rust** 实现能力（含 LLM / Agent）。仅当 Change Record 写明「Rust 生态缺少可用实现」时才编写 Python（[ADR-0009](../../../docs/managed/decisions/python-runtime/adr-0009-python-only-when-rust-insufficient.md)）。例如 Playwright。

| 允许（须先论证生态缺口） | 禁止 |
|------|------|
| 该缺口对应的库与适配（如 Playwright） | GUI · Tauri · React |
| 既有 sidecar 探活 / 管理面 | SQLite · 业务状态持久化 |
| | 未论证就把 LLM / RAG / Agent 放到 Python |
| | 未评审的对外 HTTP Server |

## 目录结构

```
python/                 # 单一项目（无 uv workspace 多包）
├── pyproject.toml      # dingda-sidecar
├── application/sidecar/  # 进程入口 + channel handlers
├── runtime/ · runtimes/
├── crawlers/ · agent/ · skills/ · tools/
└── contracts/          # codegen 类型
```

根 `pyproject.toml` 通过 path 依赖安装本项目。新增模块前必须有 Change Record 说明为何 Rust 不够。不要为 LLM / RAG / Agent 预建空包。

## Sidecar 管理面

仅供 Rust 调用，契约：`contracts/openapi/sidecar.v1.yaml`

| 端点 | 用途 |
|------|------|
| `GET /health` | 健康检查 |
| `GET /stats` | 运行时统计 |
| `GET /tasks/active` | 活跃任务 |
| `GET /metrics` | 指标 |
| `GET /debug/dump` | 调试快照 |

## 流式输出路径

若某能力因生态缺口走 sidecar：

```
Python generator  →  Rust 聚合  →  Tauri Events  →  React
```

默认流式 AI 在 Rust 产生，再经 Tauri Events 到 React。禁止 Python 直接向前端推事件。

## 包开发

```bash
# 各包独立 pyproject.toml，Ruff 统一配置于根 pyproject.toml
pnpm lint:python
```

## 相关

- [../architecture/layers.md](../architecture/layers.md)
- [ADR-0009](../../../docs/managed/decisions/python-runtime/adr-0009-python-only-when-rust-insufficient.md)
