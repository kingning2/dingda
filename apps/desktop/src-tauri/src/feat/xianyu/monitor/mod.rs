//! 闲鱼商品监控 — 调度、Sidecar 搜索、Rust AI 决策。

pub mod ai;
pub mod engine;
pub mod scheduler;
pub mod search;

pub use engine::{MonitorEngine, MonitorRunSummary};
pub use scheduler::MonitorScheduler;
