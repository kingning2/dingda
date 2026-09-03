# Developer B（Rust）规则

适用范围：`apps/desktop/src-tauri/**`（含内联的 `contracts` / `ports` / `infrastructure`；proc-macro 在 `apps/desktop/src-tauri/macros`）

## 职责边界

- Rust 是桌面端 **Application Core / 协调中枢**
- React 只能通过 Tauri IPC 调 Rust；Python 只能通过 Rust runtime 访问
- SQLite / 存储层由 Rust 独占（Python 不直连 DB）

## 目录归类（六边形 + Tauri）

| 模块 | 职责 |
|------|------|
| `commands/` | Tauri IPC 薄适配层（禁止业务/SQL） |
| `domain/` | 纯领域：实体、规则、渠道协议 |
| `application/` | UseCase 编排（bootstrap、渠道协调等） |
| `ports/` | Port traits（license / sidecar 等） |
| `infrastructure/` | Driven 适配器：storage / event / license / embedding / runtime / channel / plugins |
| `app/` | 壳层：AppState、生命周期观测、平台装配、日志/计时 |
| `config/` · `contracts/` | 应用配置 · 共享 DTO / 错误 / 事件 |

依赖方向：`commands` → `application` → `domain` / `ports` ← `infrastructure`；`lib.rs` 为组装根。

## 分层与依赖（必须）

- `domain/` 禁止 IO（无 SQL/HTTP/文件/tauri）以外的壳层依赖；IO 在 `infrastructure/`
- `infrastructure` 实现 `ports` trait，不反向依赖 `commands`
- 横切能力（event/config/logger）走对应模块，禁止在 UI IPC 里直接拼协议

## 通信模式

- 跨模块：优先 `infrastructure::event` Pub/Sub，禁止 UI 直连深层实现
- 后台任务：必须通过 `infrastructure::runtime::tasks` 注册/调度，禁止私开长循环线程

## 日志

- `lib.rs` / `main.rs` 已 `#[macro_use] extern crate tracing;`，模块内直接写 `info!` / `debug!` / `warn!` / `error!`，勿写 `tracing::info!`，勿重复 `use tracing::…` 导入宏。
- IPC / 业务函数**默认不加** `#[timed]`；需要观测耗时时显式标注 `#[timed("中文调用名")]`（禁止用函数英文名）。
- 生命周期状态用 `#[runtime(...)]`（展开到 `crate::infrastructure::runtime::mark`）。

## 契约变更

- 所有跨端 DTO/事件/错误码：必须来源 `contracts/`
- Rust 生成物目录：`apps/desktop/src-tauri/src/contracts/contracts/`
- Breaking Change：新 `schema/v2` 或新文件 + 迁移说明
