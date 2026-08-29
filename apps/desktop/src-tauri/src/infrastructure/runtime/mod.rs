//! Runtime 控制层 — Task / 生命周期记录 / 通用标记。
//!
//! Python Sidecar 与 Agent 运行时已迁至 [`crate::infrastructure::sidecar`]；
//! 本模块保留任务运行时与通用观测设施。

pub mod lifecycle_recorder;
pub mod mark;
pub mod tasks;

/// `[runtime]` 日志 target — 与观测层 `[startup]`（`dingda.lifecycle`）区分。
pub const RUNTIME_TARGET: &str = "dingda.runtime";
