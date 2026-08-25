//! Runtime 总协调器 — 编排 Python / Agent / Task / Shutdown。
//!
//! 只做 orchestration，具体实现委托给
//! [`python::PythonRuntime`]、[`agent::AgentRuntime`]、[`tasks::TaskManager`]。

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, RwLock};

use crate::runtime::agent::{AgentRuntime, AgentState};
use crate::runtime::app::startup;
use crate::runtime::python::{PythonRuntime, PythonState, SidecarLifecycle};
use crate::runtime::shutdown::{run_shutdown, ShutdownPolicy};
use crate::runtime::state::RuntimeState;
use crate::runtime::tasks::scheduler::TaskScheduler;
use crate::runtime::tasks::TaskManager;
use crate::runtime::RUNTIME_TARGET;

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

    /// 启动 Runtime：确保 Sidecar 运行 → Agent 就绪 → Ready / Failed。
    ///
    /// 保留现有 `rust.sidecar.ensure_running.*` 观测日志（阶段名与格式不变）。
    pub async fn start(&self) {
        self.set_state(RuntimeState::Initializing);
        startup::phase("rust.sidecar.ensure_running.begin");
        match self.python.ensure_running().await {
            Ok(()) => startup::phase("rust.sidecar.ensure_running.ok"),
            Err(error) => {
                error!(%error, "侧车启动失败");
                startup::phase("rust.sidecar.ensure_running.fail");
                self.set_state(RuntimeState::Failed);
                return;
            }
        }
        self.agent.start().await;
        self.scheduler.start();
        self.set_state(RuntimeState::Ready);
    }

    /// 重启 Runtime：先停 Sidecar 再拉起。
    pub async fn restart(&self) {
        match self.python.restart().await {
            Ok(()) => self.set_state(RuntimeState::Ready),
            Err(error) => {
                error!(%error, "侧车重启失败");
                self.set_state(RuntimeState::Failed);
            }
        }
    }

    /// 关闭 Runtime — 幂等：重复调用直接返回。
    pub async fn shutdown(&self) {
        if self.shutdown_started.swap(true, Ordering::SeqCst) {
            return;
        }
        self.set_state(RuntimeState::ShuttingDown);
        self.scheduler.stop();
        run_shutdown(
            &ShutdownPolicy::default(),
            self.tasks.as_ref(),
            &self.agent,
            &self.python,
        )
        .await;
        self.set_state(RuntimeState::Stopped);
    }

    fn set_state(&self, new: RuntimeState) {
        let previous = {
            let mut guard = self.state.write().expect("runtime state lock");
            let previous = *guard;
            *guard = new;
            previous
        };
        if previous != new {
            info!(target: RUNTIME_TARGET, "[runtime] state={}", new.as_str());
        }
    }
}
