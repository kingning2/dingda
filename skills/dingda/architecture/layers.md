# Layer Architecture

## 分层模型

```
┌──────────────────────────────────────────────────────────┐
│ Layer 1: React（Presentation）                            │
│                                                          │
│  apps/desktop/src/          Feature UI 与路由             │
│  packages/ui/               纯展示组件                    │
│  packages/platform/         IPC 封装（唯一 Tauri 入口）    │
└────────────────────────────┬─────────────────────────────┘
                             │ invoke / listen (platform only)
┌────────────────────────────▼─────────────────────────────┐
│ Layer 2: Rust（Application Core，默认实现含 AI）           │
│                                                          │
│  business/                  应用胶水（日志/配置/渠道存储/事件桥）│
│  apps/desktop/src-tauri/    Tauri 壳：IPC 命令 · 状态 · Builder │
│  crates/agent/              AI 编排（model/knowledge/prompt/intent/reply）│
│  crates/platform/           渠道平台（协议+领域+Provider+SQLite）│
│  crates/infra/              事件总线 · sidecar 运行时 · license │
│  crates/common · ports · macros · adapter    共享叶子          │
└────────────────────────────┬─────────────────────────────┘
                             │ 仅当 Rust 生态不够（ADR-0009）
┌────────────────────────────▼─────────────────────────────┐
│ Layer 3: Python Sidecar（例外，不是 AI Runtime）           │
│                                                          │
│  python/                    单一项目（无 uv workspace）    │
│    sidecar/                 进程入口 · 管理面 API          │
│    channels/                渠道浏览器例外（闲鱼 / 1688 等）│
│    shared/ · contracts/     共享工具 · codegen 类型        │
└──────────────────────────────────────────────────────────┘
```

## 各层职责

### React Layer

| 负责 | 禁止 |
|------|------|
| UI 渲染、交互、主题、动画 | 业务规则、SQL、AI 逻辑 |
| 本地 UI 状态（表单、展开/折叠） | 直接 `invoke()`（Feature UI） |
| 通过 `@desk/platform/ipc` 调 Rust | `import @tauri-apps/api`（Feature UI） |

### Rust Layer

| 负责 | 禁止 |
|------|------|
| 业务编排、权限、缓存 | `unwrap()` / `panic!()` |
| SQLite 读写（经 platform::storage / ports） | Feature 间直接 `use` |
| Agent / LLM（默认） | 把新 AI 能力默认丢给 Python |
| Python sidecar 生命周期 | 阻塞 UI 线程 |
| 结构化日志（tracing） | Python 直连前端事件 |
| Tauri IPC 命令与事件转发 | |

### Python Layer

| 负责 | 禁止 |
|------|------|
| 仅 ADR-0009 论证过的生态缺口 | GUI、Tauri、React |
| 既有 sidecar 探活骨架 | 默认 LLM / RAG / Agent |
| | SQLite、业务状态持久化 |
| | 未评审的 HTTP Server |

## Rust 内部分层（六边形）

```
┌─────────────────────────────────────┐
│  app/（Application / UseCase）       │  ← 编排，无 IO
├─────────────────────────────────────┤
│  domain/（Entity / Value Object）    │  ← 纯领域，无框架依赖
├─────────────────────────────────────┤
│  ports/（trait 定义）                │  ← 接口
├─────────────────────────────────────┤
│  infra/（storage 实现，可选在 crate 内）│  ← SQL / HTTP / FS
└─────────────────────────────────────┘
```

## 层间通信矩阵

| From \ To | React | Rust | Python | SQLite |
|-----------|-------|------|--------|--------|
| React | ✅ | ✅ IPC | ❌ | ❌ |
| Rust | ✅ Events | ✅ | ✅ 仅例外 | ✅ |
| Python | ❌ | ✅ | ✅ | ❌ |

## 相关文档

- [feature-boundary.md](feature-boundary.md)
- [../guides/ipc.md](../guides/ipc.md)
- [dependency.md](dependency.md)
