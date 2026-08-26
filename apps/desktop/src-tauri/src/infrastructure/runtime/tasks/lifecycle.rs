//! 任务生命周期事件 — 状态 / 阶段转移 + `[runtime] task.*` 日志。
//!
//! `manager` / `executor` 统一经本模块驱动任务状态，保证所有 `task.*` 日志只此一处。

use crate::infrastructure::runtime::RUNTIME_TARGET;

use super::state::{TaskPhase, TaskState};
use super::task::{Task, TaskId, TaskKind};

/// 任务生命周期事件。
pub struct TaskLifecycle;

impl TaskLifecycle {
    /// 创建日志。
    pub fn created(id: &TaskId, kind: TaskKind) {
        info!(target: RUNTIME_TARGET, "[runtime] task.created id={id} kind={}", kind.as_str());
    }

    /// 转移任务状态并打日志（幂等：状态未变不打日志）。
    pub fn transition(task: &mut Task, state: TaskState) {
        let previous = task.state();
        if previous == state {
            return;
        }
        task.set_state(state);
        let id = task.id().clone();
        match state {
            TaskState::Running => info!(target: RUNTIME_TARGET, "[runtime] task.running id={id}"),
            TaskState::Queued => info!(target: RUNTIME_TARGET, "[runtime] task.queued id={id}"),
            TaskState::Completed => {
                info!(target: RUNTIME_TARGET, "[runtime] task.completed id={id}")
            }
            TaskState::Failed => {
                let error = task.error().unwrap_or("").to_string();
                info!(target: RUNTIME_TARGET, "[runtime] task.failed id={id} error={error}");
            }
            TaskState::Cancelled => {
                info!(target: RUNTIME_TARGET, "[runtime] task.cancelled id={id}")
            }
            TaskState::Timeout => info!(target: RUNTIME_TARGET, "[runtime] task.timeout id={id}"),
            // Created 为初始状态，不单独打日志。
            TaskState::Created => {}
        }
    }

    /// 转移任务阶段并打日志（幂等：阶段未变不打日志）。
    pub fn transition_phase(task: &mut Task, phase: TaskPhase) {
        let previous = task.phase();
        if previous == phase {
            return;
        }
        task.set_phase(phase);
        info!(
            target: RUNTIME_TARGET,
            "[runtime] task.phase id={} phase={}",
            task.id(),
            phase.as_str()
        );
    }
}
