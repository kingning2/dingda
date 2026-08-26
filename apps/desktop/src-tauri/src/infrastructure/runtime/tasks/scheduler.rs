//! 定时任务生命周期 — 周期注册 / tick 调度 / 停止。
//!
//! 每个到期时刻经 [`TaskManager`] 建一个 `Task`（`TaskKind::Scheduled`）并执行，
//! 使其复用通用任务的状态 / 阶段 / 取消框架。

use std::collections::HashMap;
use std::future::Future;
use std::pin::Pin;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, RwLock};
use std::time::Duration;

use tokio::task::JoinHandle;
use uuid::Uuid;

use crate::infrastructure::runtime::RUNTIME_TARGET;

use super::manager::TaskManager;
use super::task::{TaskId, TaskKind};

/// 定时任务执行体 — 每次到期时返回一个异步任务 future。
pub type ScheduledFn = dyn Fn(TaskId) -> Pin<Box<dyn Future<Output = Result<(), String>> + Send + 'static>>
    + Send
    + Sync;

struct ScheduledEntry {
    kind: TaskKind,
    interval: Duration,
    next_run: tokio::time::Instant,
    spawn: Arc<ScheduledFn>,
}

/// 定时任务调度器。
pub struct TaskScheduler {
    manager: Arc<TaskManager>,
    entries: RwLock<HashMap<TaskId, ScheduledEntry>>,
    tick: Duration,
    handle: Mutex<Option<JoinHandle<()>>>,
    running: AtomicBool,
}

impl TaskScheduler {
    /// 组装调度器；复用任务管理器执行每个周期的运行。
    #[allow(clippy::new_without_default)]
    pub fn new(manager: Arc<TaskManager>) -> Self {
        Self {
            manager,
            entries: RwLock::new(HashMap::new()),
            tick: Duration::from_secs(1),
            handle: Mutex::new(None),
            running: AtomicBool::new(false),
        }
    }

    /// 注册定时任务，返回调度条目 id。
    pub fn register(&self, interval: Duration, spawn: Arc<ScheduledFn>) -> TaskId {
        let id = Uuid::new_v4().to_string();
        let entry = ScheduledEntry {
            kind: TaskKind::Scheduled,
            interval,
            next_run: tokio::time::Instant::now() + interval,
            spawn,
        };
        self.entries
            .write()
            .expect("scheduler entries lock")
            .insert(id.clone(), entry);
        info!(
            target: RUNTIME_TARGET,
            "[runtime] scheduled.register id={id} interval_ms={}",
            interval.as_millis()
        );
        id
    }

    /// 注销定时任务。
    pub fn unregister(&self, id: &TaskId) {
        self.entries
            .write()
            .expect("scheduler entries lock")
            .remove(id);
        info!(target: RUNTIME_TARGET, "[runtime] scheduled.unregister id={id}");
    }

    /// 启动 tick 循环（幂等）。
    pub fn start(self: &Arc<Self>) {
        if self.running.swap(true, Ordering::SeqCst) {
            return;
        }
        let this = self.clone();
        let handle = tokio::spawn(async move {
            let mut interval = tokio::time::interval(this.tick);
            interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
            loop {
                interval.tick().await;
                if !this.running.load(Ordering::SeqCst) {
                    break;
                }
                this.tick_due();
            }
        });
        *self.handle.lock().expect("scheduler handle lock") = Some(handle);
        info!(target: RUNTIME_TARGET, "[runtime] scheduled.start");
    }

    /// 扫描到期条目并各跑一个任务。
    fn tick_due(&self) {
        let due: Vec<(TaskId, TaskKind, Arc<ScheduledFn>)> = {
            let mut entries = self.entries.write().expect("scheduler entries lock");
            let now = tokio::time::Instant::now();
            let mut due = Vec::new();
            for (id, entry) in entries.iter_mut() {
                if entry.next_run <= now {
                    entry.next_run = now + entry.interval;
                    due.push((id.clone(), entry.kind, entry.spawn.clone()));
                }
            }
            due
        };
        for (id, kind, spawn) in due {
            let run_id = self.manager.create(kind);
            let future = spawn(run_id.clone());
            if let Err(error) = self.manager.start(run_id, future) {
                warn!(
                    target: RUNTIME_TARGET,
                    %error,
                    "[runtime] scheduled.run.failed schedule_id={id}"
                );
            }
        }
    }

    /// 停止调度 — 清空条目并中止 tick 循环（幂等）。
    pub fn stop(&self) {
        self.running.store(false, Ordering::SeqCst);
        if let Some(handle) = self.handle.lock().expect("scheduler handle lock").take() {
            handle.abort();
        }
        self.entries
            .write()
            .expect("scheduler entries lock")
            .clear();
        info!(target: RUNTIME_TARGET, "[runtime] scheduled.stop");
    }
}

#[cfg(test)]
mod tests {
    use super::TaskScheduler;
    use crate::infrastructure::runtime::tasks::TaskManager;
    use std::sync::Arc;
    use std::time::Duration;

    fn noop_spawn() -> Arc<super::ScheduledFn> {
        Arc::new(|_task_id| Box::pin(async { Ok::<(), String>(()) }))
    }

    #[test]
    fn register_then_unregister() {
        let scheduler = TaskScheduler::new(Arc::new(TaskManager::default()));
        let id = scheduler.register(Duration::from_secs(60), noop_spawn());
        scheduler.unregister(&id);
        scheduler.stop();
    }

    #[test]
    fn stop_is_safe_when_not_started() {
        let scheduler = TaskScheduler::new(Arc::new(TaskManager::default()));
        scheduler.stop();
    }
}
