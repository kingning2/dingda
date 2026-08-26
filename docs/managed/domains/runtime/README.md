# Runtime / Worker Domain

## 职责

桌面端 **进程编排** 与 **Python Sidecar 生命周期**（Sidecar 为 ADR-0009 例外运行时，不是默认 AI 层）：

- `SidecarLifecycle`：启动、监控、退出 Python sidecar（产品仅 `--ipc`）
- `SidecarClient`：业务经 pipe `sidecar.invoke`；Event 同管道推送；SHM 预留大文件
- 渠道 / Agent 路径绑定：`infrastructure/channel/sidecar`、`infrastructure/runtime/agent/sidecar`（仍 `post_json`）
- 日志管道：`log_pipe.rs`
- 配置：`SidecarConfig::from_env()`（`DINGDA_SIDECAR_IPC` 可覆盖；`DINGDA_SIDECAR_SHM` 预留）

**重任务 Worker（dingda-worker）已随采集/客户/邮箱板块移除**，如后续需要按新 Change 重新引入。

## 非职责

- OCR 业务规则细节（OCR 领域；规划中）
- Python Sidecar 内部实现（[python-runtime](../python-runtime/README.md) 领域；仅生态缺口）
- 领域业务规则（业务代码在 `apps/desktop/src-tauri`）

## 稳定边界

```text
Tauri 主进程（src-tauri）
  → SidecarLifecycle（spawn --ipc）
  → SidecarClient（pipe sidecar.invoke + Event 订阅）
  → Python ipc_server（线程池 dispatch_post）
  → Event → React
```

产品通讯 **不** 使用本机 HTTP；`runtime.server` 仅可手工 `--port` 调试。`--shm`+`--ipc` hybrid 为预留，非产品默认。

## 入口

| 类型 | 路径 |
|------|------|
| Lifecycle / Client | `apps/desktop/src-tauri/src/infrastructure/runtime/python/` |
| Pipe RPC / Event | `.../python/pipe_ipc/` |
| SHM（预留） | `.../python/shm/` |
| ADR | [ADR-0002](../../decisions/runtime/adr-0002-heavy-work-worker-process.md) · [ADR-0009](../../decisions/python-runtime/adr-0009-python-only-when-rust-insufficient.md) |

## 当前状态

Sidecar 生命周期已接入；产品通讯为 pipe RPC（`sidecar.invoke`）+ Event 推送。

## 当前约束

- 重 CPU/IO 任务 **不得** 在 Tauri 主进程执行（ADR-0002）
- Sidecar 进程由 Rust 唯一编排，UI 不直连 Python
- 新能力默认在 Rust；不得因为已有 sidecar 就把 AI 放到 Python（[ADR-0009](../../decisions/python-runtime/adr-0009-python-only-when-rust-insufficient.md)）
- 桌面主进程 **单实例**（`tauri-plugin-single-instance`，Win / macOS / Linux）：二次启动聚焦已有窗口，避免争用 SQLite / Named Pipe / 配置目录
