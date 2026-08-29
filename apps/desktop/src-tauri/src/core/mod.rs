//! 核心抽象 — 组件生命周期与运行时协调（全仓库唯一定义处）。

pub mod lifecycle;
pub mod supervisor;

pub use lifecycle::{Component, ComponentState, HealthReport};
pub use supervisor::RuntimeSupervisor;
