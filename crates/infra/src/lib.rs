//! infra crate — 基础设施（**自包含**）：进程内事件总线 + Python sidecar 运行时 + 基础设施适配器。
//!
//! 结构：
//! - `event` — 进程内 pub/sub 事件总线（`EventBus` / `EventHandler` / `InMemoryEventBus`）
//! - `sidecar` — Python sidecar 客户端 / 日志管道 / 通用管理路由（`manage`）
//! - `license` — license 校验适配器（实现 `ports::license`）
//!
//! 业务路由绑定（channel / llm / agent）与 Agent 网关已迁至桌面端 `runtime::python`；
//! 本 crate 只保留通用基础设施，不依赖业务域。
//!
//! 只依赖 `common` / `ports`（共享叶子）+ 外部 crate，不依赖其它 DingDa crate。

#[macro_use]
extern crate tracing;

pub mod event;
pub mod license;
pub mod sidecar;

pub use event::{EventBus, EventHandler, InMemoryEventBus};
