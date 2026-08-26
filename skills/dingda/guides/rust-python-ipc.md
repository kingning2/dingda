# Rust ↔ Python IPC

仅在 [ADR-0009](../../../docs/managed/decisions/python-runtime/adr-0009-python-only-when-rust-insufficient.md) 允许的生态缺口下使用。默认业务与 AI **不要**走这条路径。

Rust Application Core 与 Python Sidecar 之间的**本机 HTTP** 通讯规范。  
React **禁止**参与此层；流式输出由 Rust 转发为 Tauri Events。

## 通讯模型

```mermaid
sequenceDiagram
    participant R as React
    participant Rust as Rust Core
    participant Py as Python Sidecar

    Note over R,Py: 默认：Rust 直接完成（含 AI）
    R->>Rust: Tauri IPC
    Rust-->>R: IPC / Tauri Event

    Note over R,Py: 例外：仅 Rust 生态不够时才调 sidecar
    R->>Rust: Tauri IPC
    Rust->>Py: HTTP POST /v1/{feature}/{action}
    Py-->>Rust: JSON response
    Rust-->>R: IPC / Tauri Event
```

## 路径约定

| 类型 | 路径 |
|------|------|
| 管理面 | `/health` `/stats` `/tasks/active` `/metrics` `/debug/dump` |
| 业务面 | `/v1/{feature}/{action}` |

OpenAPI 基线：`contracts/openapi/sidecar.v1.yaml`  
业务路径片段：`contracts/openapi/sidecar.paths/<feature>_<action>.yaml`

## 契约

```
contracts/schema/v1/<feature>/sidecar/<action>.request.schema.json
contracts/schema/v1/<feature>/sidecar/<action>.response.schema.json
```

变更顺序：**Contract → Rust runtime client → Python handler**（仅 sidecar 例外能力）

## 代码位置

| 层 | 路径 |
|----|------|
| Rust 生命周期 + 端口 | `crates/infra/` |
| Rust HTTP 客户端 | `crates/infra/src/sidecar/client.rs` |
| Rust 路由绑定 | `crates/infra/src/sidecar/routes/<feature>_<action>.rs` |
| Python 处理器 | `python/packages/gateway/src/gateway/handlers/` |
| Python 路由表 | `python/runtime/ipc.py` |

## 脚手架

```bash
python skills/dingda/scripts/create_rust_python_ipc.py --feature agent --action ping
python skills/dingda/scripts/create_rust_python_ipc.py --feature agent --action run_task --streaming
```

## 禁止

| 禁止 | 原因 |
|------|------|
| React → `http://127.0.0.1:*` | 必须经 Rust |
| Python → Tauri Events | Python 不知道前端 |
| Python → SQLite | 存储归 Rust |
| 无 Contract 的 ad-hoc JSON | Contracts First |

## 相关

- [ipc.md](ipc.md) — React ↔ Rust（Tauri IPC）
- [python.md](python.md)
- [rust.md](rust.md)
- [../recipes/add-rust-python-ipc.md](../recipes/add-rust-python-ipc.md)
- [../examples/rust-python/README.md](../examples/rust-python/README.md)
