//! Runtime 控制层 — Python / Agent / Task / Supervisor。
//!
//! App 生命周期观测在 [`crate::app`]；本模块只负责 sidecar 与任务运行时。

pub mod agent;
pub mod lifecycle_recorder;
pub mod mark;
pub mod python;
pub mod shutdown;
pub mod state;
pub mod supervisor;
pub mod tasks;

pub use state::RuntimeState;
pub use supervisor::RuntimeSupervisor;

/// `[runtime]` 日志 target — 与观测层 `[startup]`（`dingda.lifecycle`）区分。
pub const RUNTIME_TARGET: &str = "dingda.runtime";
