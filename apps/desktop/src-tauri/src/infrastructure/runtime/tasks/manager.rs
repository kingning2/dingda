//! 任务管理器 — create / start / cancel / cancel_all / get / list / set_phase。

use uuid::Uuid;

use crate::infrastructure::runtime::RUNTIME_TARGET;

use super::cancellation::TaskCancellation;
use super::executor::{TaskExecutor, TaskStore};
use super::lifecycle::TaskLifecycle;
use super::state::{TaskPhase, TaskState};
use super::task::{Task, TaskId, TaskKind};

/// 任务管理器。
#[derive(Default)]
pub struct TaskManager {
    tasks: TaskStore,
    cancellation: TaskCancellation,
}

impl TaskManager {
    /// 创建任务，返回任务 id。
    pub fn create(&self, kind: TaskKind) -> TaskId {
        let id = Uuid::new_v4().to_string();
        self.tasks
            .write()
            .expect("task store lock")
            .insert(id.clone(), Task::new(id.clone(), kind));
        TaskLifecycle::created(&id, kind);
        id
    }

    /// 开始执行任务（置 `Running` 并交给执行器）。
    pub fn start(
        &self,
        id: TaskId,
        future: impl std::future::Future<Output = Result<(), String>> + Send + 'static,
    ) -> Result<(), String> {
        {
            let mut guard = self.tasks.write().expect("task store lock");
            let task = guard
                .get_mut(&id)
                .ok_or_else(|| format!("任务不存在: {id}"))?;
            TaskLifecycle::transition(task, TaskState::Running);
        }
        let token = self.cancellation.register(id.clone());
        TaskExecutor::spawn(id, token, self.tasks.clone(), future);
        Ok(())
    }

    /// 转移任务阶段（由运行中的任务调用）。
    pub fn set_phase(&self, id: &TaskId, phase: TaskPhase) {
        let mut guard = self.tasks.write().expect("task store lock");
        if let Some(task) = guard.get_mut(id) {
            TaskLifecycle::transition_phase(task, phase);
        }
    }

    /// 取消单个任务。
    pub fn cancel(&self, id: &TaskId) {
        self.cancellation.cancel(id);
        let mut guard = self.tasks.write().expect("task store lock");
        if let Some(task) = guard.get_mut(id) {
            TaskLifecycle::transition(task, TaskState::Cancelled);
        }
    }

    /// 取消全部任务（用于关闭流程；幂等）。
    pub fn cancel_all(&self) {
        self.cancellation.cancel_all();
        {
            let mut guard = self.tasks.write().expect("task store lock");
            for task in guard.values_mut() {
                TaskLifecycle::transition(task, TaskState::Cancelled);
            }
        }
        info!(target: RUNTIME_TARGET, "[runtime] task.cancel_all");
    }

    /// 读取单个任务。
    pub fn get(&self, id: &TaskId) -> Option<Task> {
        self.tasks.read().expect("task store lock").get(id).cloned()
    }

    /// 列出全部任务。
    pub fn list(&self) -> Vec<Task> {
        self.tasks
            .read()
            .expect("task store lock")
            .values()
            .cloned()
            .collect()
    }

    /// 在跑任务数。
    pub fn running_count(&self) -> usize {
        self.tasks
            .read()
            .expect("task store lock")
            .values()
            .filter(|task| task.state() == TaskState::Running)
            .count()
    }
}

#[cfg(test)]
mod tests {
    use super::super::state::{TaskPhase, TaskState};
    use super::{TaskKind, TaskManager};

    #[test]
    fn create_get_list_roundtrip() {
        let manager = TaskManager::default();
        let id = manager.create(TaskKind::Background);
        let task = manager.get(&id).expect("task exists");
        assert_eq!(task.state(), TaskState::Created);
        assert_eq!(task.phase(), TaskPhase::Planning);
        assert_eq!(manager.list().len(), 1);
        assert_eq!(manager.running_count(), 0);
    }

    #[test]
    fn cancel_marks_task_cancelled() {
        let manager = TaskManager::default();
        let id = manager.create(TaskKind::Crawler);
        manager.cancel(&id);
        assert_eq!(manager.get(&id).unwrap().state(), TaskState::Cancelled);
    }

    #[test]
    fn cancel_all_is_noop_when_empty() {
        let manager = TaskManager::default();
        manager.cancel_all();
        assert!(manager.list().is_empty());
    }
}
