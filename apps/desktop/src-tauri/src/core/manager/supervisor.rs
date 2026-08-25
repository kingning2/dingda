//! Runtime 总协调器 — 编排 Python / Agent / Task / Shutdown。
//!
//! 只做 orchestration，具体实现委托给
//! [`python::PythonRuntime`]、[`agent::AgentRuntime`]、[`tasks::TaskManager`]。

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, RwLock};
use std::time::Duration;

use crate::core::manager::agent::{AgentRuntime, AgentState};
use crate::core::manager::app::startup;
use crate::core::manager::python::{
    PythonRuntime, PythonSidecarSnapshot, PythonState, SidecarLifecycle, SidecarLifecycleError,
};
use crate::core::manager::shutdown::{run_shutdown, ShutdownPolicy};
use crate::core::manager::state::RuntimeState;
use crate::core::manager::tasks::scheduler::TaskScheduler;
use crate::core::manager::tasks::TaskManager;
use crate::core::manager::RUNTIME_TARGET;

/// Runtime 总协调器。
///
/// `lib.rs` 是 Tauri 生命周期入口，仅负责创建本协调器并触发 `start` / `shutdown`；
/// Python / Agent / Task 的启停决策收敛在本模块。
pub struct RuntimeSupervisor {
    state: RwLock<RuntimeState>,
    python: PythonRuntime,
    agent: AgentRuntime,
    tasks: Arc<TaskManager>,
    scheduler: Arc<TaskScheduler>,
    shutdown_started: AtomicBool,
}

impl RuntimeSupervisor {
    /// 组装协调器；复用现有 Sidecar 生命周期实例，行为不变。
    #[allow(clippy::new_without_default)]
    pub fn new(lifecycle: Arc<SidecarLifecycle>) -> Self {
        let tasks = Arc::new(TaskManager::default());
        let scheduler = Arc::new(TaskScheduler::new(tasks.clone()));
        let python = PythonRuntime::new(lifecycle);
        let agent = AgentRuntime::new(python.ipc().client().clone());
        Self {
            state: RwLock::new(RuntimeState::Starting),
            python,
            agent,
            tasks,
            scheduler,
            shutdown_started: AtomicBool::new(false),
        }
    }

    /// 当前 Runtime 状态。
    pub fn state(&self) -> RuntimeState {
        *self.state.read().expect("runtime state lock")
    }

    /// 暴露任务管理器（供业务调度器接入：监控任务经其获得生命周期观测与关闭取消）。
    pub fn tasks(&self) -> &Arc<TaskManager> {
        &self.tasks
    }

    /// Python 生命周期状态。
    pub fn python_state(&self) -> PythonState {
        self.python.state()
    }

    /// Agent 生命周期状态。
    pub fn agent_state(&self) -> AgentState {
        self.agent.state()
    }

    /// Python Sidecar 最近一次快照（缓存）。
    pub fn python_snapshot(&self) -> Option<PythonSidecarSnapshot> {
        self.python.snapshot()
    }

    /// 主动拉取 Sidecar 快照并更新 Python 生命周期状态。
    pub async fn sync_python(&self) -> Option<PythonSidecarSnapshot> {
        self.python.sync_snapshot().await
    }

    /// 后台 watchdog（Rust runtime 控制面）：每 1s 检查子进程退出 / 健康状态，
    /// 异常即触发 `ensure_running` 重启（含崩溃恢复），关闭后退出。
    pub fn spawn_observation_loop(self: &Arc<Self>) {
        let supervisor = Arc::clone(self);
        tauri::async_runtime::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_secs(1));
            loop {
                interval.tick().await;
                let state = supervisor.state();
                if matches!(state, RuntimeState::Stopped | RuntimeState::ShuttingDown) {
                    break;
                }
                match supervisor.python_state() {
                    PythonState::Stopping | PythonState::Stopped | PythonState::Failed => continue,
                    _ => {}
                }
                // reaper：子进程意外退出 → 重启。
                let child_exited = supervisor.python.is_child_exited().await;
                // 健康探活：心跳过期 / ready 清零 → 重启。
                let healthy = supervisor.python.health_check().await.unwrap_or(false);
                if child_exited || !healthy {
                    if let Err(error) = supervisor.python.ensure_running().await {
                        warn!(target: RUNTIME_TARGET, %error, "[runtime] watchdog.restart.failed");
                    }
                } else {
                    let _ = supervisor.sync_python().await;
                }
            }
        });
    }

    /// 启动 Runtime：确保 Sidecar 运行 → Agent 就绪 → Ready / Failed。
    ///
    /// 保留现有 `rust.sidecar.ensure_running.*` 观测日志（阶段名与格式不变）。
    #[macros::runtime(runtime, start = Initializing, ok = Ready, err = Failed)]
    pub async fn start(&self) -> Result<(), SidecarLifecycleError> {
        startup::phase("rust.sidecar.ensure_running.begin");
        match self.python.ensure_running().await {
            Ok(()) => startup::phase("rust.sidecar.ensure_running.ok"),
            Err(error) => {
                error!(%error, "侧车启动失败");
                startup::phase("rust.sidecar.ensure_running.fail");
                return Err(error);
            }
        }
        let _ = self.agent.start().await;
        self.scheduler.start();
        let _ = self.python.sync_snapshot().await;
        Ok(())
    }

    /// 重启 Runtime：先停 Sidecar 再拉起。
    #[macros::runtime(runtime, start = Initializing, ok = Ready, err = Failed)]
    pub async fn restart(&self) -> Result<(), SidecarLifecycleError> {
        self.python.restart().await.map_err(|err| {
            error!(%err, "侧车重启失败");
            err
        })
    }

    /// 关闭 Runtime — 幂等：重复调用直接返回。
    pub async fn shutdown(&self) {
        if self.shutdown_started.swap(true, Ordering::SeqCst) {
            return;
        }
        self.set_state(RuntimeState::ShuttingDown);
        crate::core::manager::mark::phase("runtime", "shutting_down");
        self.scheduler.stop();
        run_shutdown(
            &ShutdownPolicy::default(),
            self.tasks.as_ref(),
            &self.agent,
            &self.python,
        )
        .await;
        self.set_state(RuntimeState::Stopped);
        crate::core::manager::mark::phase("runtime", "stopped");
    }

    fn set_state(&self, new: RuntimeState) {
        let mut guard = self.state.write().expect("runtime state lock");
        if *guard != new {
            *guard = new;
        }
    }
}
