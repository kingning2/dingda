//! 异步任务生命周期 — 状态/阶段 / 数据模型 / 管理器 / 执行器 / 取消 / 定时调度。
//!
//! 职责划分：
//! - [`state`] — `TaskState` / `TaskPhase`（两个正交概念）
//! - [`task`] — `Task` 数据模型
//! - [`lifecycle`] — 状态 / 阶段转移 + `[runtime] task.*` 日志
//! - [`cancellation`] — 任务取消令牌与注册表
//! - [`executor`] — 真正执行异步任务并驱动终态
//! - [`manager`] — 任务管理器（create / start / cancel / cancel_all / get / list）
//! - [`scheduler`] — 定时任务调度（周期触发）

pub mod cancellation;
pub mod executor;
pub mod lifecycle;
pub mod manager;
pub mod scheduler;
pub mod state;
pub mod task;

pub use manager::TaskManager;
pub use scheduler::TaskScheduler;
pub use state::{TaskPhase, TaskState};
pub use task::{Task, TaskId, TaskKind};
