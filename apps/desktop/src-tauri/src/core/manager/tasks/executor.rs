//! 任务执行器 — 真正执行异步任务并驱动终态。

use std::collections::HashMap;
use std::sync::{Arc, RwLock};

use super::cancellation::CancellationToken;
use super::lifecycle::TaskLifecycle;
use super::state::TaskState;
use super::task::{Task, TaskId};

/// 任务存储句柄（同步短临界区，不跨 await 持有）。
pub type TaskStore = Arc<RwLock<HashMap<TaskId, Task>>>;

/// 异步任务执行器。
pub struct TaskExecutor;

impl TaskExecutor {
    /// 执行一个异步任务；经 `select!` 在完成 / 取消间竞争，并驱动终态。
    ///
    /// # 参数
    ///
    /// * `task_id` — 任务 id
    /// * `token` — 取消令牌（`cancel` 后本任务被取消）
    /// * `store` — 任务存储
    /// * `future` — 实际任务，返回 `Ok(())` 或 `Err(描述)`
    pub fn spawn(
        task_id: TaskId,
        token: CancellationToken,
        store: TaskStore,
        future: impl std::future::Future<Output = Result<(), String>> + Send + 'static,
    ) {
        tokio::spawn(async move {
            tokio::select! {
                result = future => {
                    let mut guard = store.write().expect("task store lock");
                    let Some(task) = guard.get_mut(&task_id) else {
                        return;
                    };
                    match result {
                        Ok(()) => TaskLifecycle::transition(task, TaskState::Completed),
                        Err(error) => {
                            task.set_error(error);
                            TaskLifecycle::transition(task, TaskState::Failed);
                        }
                    }
                }
                _ = token.cancelled() => {
                    let mut guard = store.write().expect("task store lock");
                    let Some(task) = guard.get_mut(&task_id) else {
                        return;
                    };
                    TaskLifecycle::transition(task, TaskState::Cancelled);
                }
            }
        });
    }
}
