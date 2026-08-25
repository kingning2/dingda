//! 闲鱼监控定时调度 — 多任务并发（Semaphore 限流）。
//!
//! 每次到期的监控运行经 Runtime `TaskManager` 创建并执行，
//! 复用通用任务生命周期（`[runtime] task.*` 观测 + 关闭时取消）。

use chrono::Utc;
use platform::domain::monitor::{is_schedule_due, MonitorTaskStore};
use std::collections::HashSet;
use std::sync::Arc;
use tokio::sync::{Mutex, Semaphore};
use tokio::time::{sleep, Duration};

use super::engine::MonitorEngine;
use crate::runtime::tasks::{TaskKind, TaskManager};

const TICK_SECONDS: u64 = 30;
const MAX_CONCURRENT: usize = 2;

pub struct MonitorScheduler {
    engine: Arc<MonitorEngine>,
    owner_id: i64,
    manager: Arc<TaskManager>,
    running: Arc<Mutex<HashSet<String>>>,
    semaphore: Arc<Semaphore>,
}

impl MonitorScheduler {
    pub fn new(engine: Arc<MonitorEngine>, owner_id: i64, manager: Arc<TaskManager>) -> Self {
        Self {
            engine,
            owner_id,
            manager,
            running: Arc::new(Mutex::new(HashSet::new())),
            semaphore: Arc::new(Semaphore::new(MAX_CONCURRENT)),
        }
    }

    pub fn start(self: Arc<Self>) {
        tauri::async_runtime::spawn(async move {
            loop {
                if let Err(error) = self.tick().await {
                    warn!(%error, "监控调度 tick 失败");
                }
                sleep(Duration::from_secs(TICK_SECONDS)).await;
            }
        });
    }

    async fn tick(&self) -> common::DingDaResult<()> {
        let tasks = self.engine.tasks.list_tasks(self.owner_id)?;
        for task in tasks
            .into_iter()
            .filter(|task| task.enabled && !task.schedule_paused)
        {
            if task.is_running {
                continue;
            }
            if !is_schedule_due(&task, Utc::now()) {
                continue;
            }
            if self.running.lock().await.contains(&task.id) {
                continue;
            }
            self.spawn_run(task.id);
        }
        Ok(())
    }

    fn spawn_run(&self, task_id: String) {
        let run_id = self.manager.create(TaskKind::Monitor);
        let monitor_task_id = task_id.clone();
        let engine = self.engine.clone();
        let running = self.running.clone();
        let semaphore = self.semaphore.clone();
        let owner_id = self.owner_id;
        let future = async move {
            running.lock().await.insert(monitor_task_id.clone());
            let _permit = semaphore.acquire().await.ok();
            let result = engine.run_task(owner_id, &monitor_task_id).await;
            running.lock().await.remove(&monitor_task_id);
            result.map(|_| ()).map_err(|error| error.to_string())
        };
        if let Err(error) = self.manager.start(run_id, future) {
            warn!(%error, task_id = %task_id, "监控任务启动失败");
        }
    }
}
