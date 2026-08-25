//! infra crate — 基础设施（**自包含**）：进程内事件总线 + 基础设施适配器。
//!
//! 结构：
//! - `event` — 进程内 pub/sub 事件总线（`EventBus` / `EventHandler` / `InMemoryEventBus`）
//! - `license` — license 校验适配器（实现 `crate::ports::license`）
//!
//! Python Sidecar 客户端 / 生命周期 / 路由绑定已迁至桌面端 `runtime::python`。
//!
//! 只依赖 `common` / `ports`（共享叶子）+ 外部 crate，不依赖其它 DingDa crate。

pub mod event;
pub mod license;

pub use event::{EventBus, EventHandler, InMemoryEventBus};
