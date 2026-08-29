//! Runtime 总协调器 — 编排 Python / Agent / Task / Shutdown。
//!
//! 只做 orchestration，具体实现委托给
//! [`crate::infrastructure::sidecar::PythonRuntime`]、
//! [`crate::infrastructure::sidecar::AgentRuntime`]、
//! [`crate::infrastructure::runtime::tasks::TaskManager`]。
//!
//! 含 `RuntimeState` 全局状态机（原 runtime/state.rs）与统一关闭顺序
//! （原 runtime/shutdown.rs，改为按 [`Component`] 注册序逆序停止）。

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, RwLock};
use std::time::{Duration, Instant};

use crate::bootstrap::startup;
use crate::core::lifecycle::{Component, STOP_TIMEOUT};
use crate::infrastructure::runtime::tasks::scheduler::TaskScheduler;
use crate::infrastructure::runtime::tasks::TaskManager;
use crate::infrastructure::runtime::RUNTIME_TARGET;
use crate::infrastructure::sidecar::{AgentRuntime, AgentState};
use crate::infrastructure::sidecar::{
    PythonRuntime, PythonSidecarSnapshot, PythonState, SidecarLifecycle, SidecarLifecycleError,
};

/// Runtime 总协调器。
///
/// `lib.rs` 是 Tauri 生命周期入口，仅负责创建本协调器并触发 `start` / `shutdown`；
/// Python / Agent / Task 的启停决策收敛在本模块。
pub struct RuntimeSupervisor {
    state: RwLock<RuntimeState>,
    python: Arc<PythonRuntime>,
    agent: Arc<AgentRuntime>,
    tasks: Arc<TaskManager>,
    scheduler: Arc<TaskScheduler>,
    /// 注册的组件；关闭时按注册序的**逆序**停止。
    components: Vec<Arc<dyn Component>>,
    shutdown_started: AtomicBool,
}

impl RuntimeSupervisor {
    /// 组装协调器；复用现有 Sidecar 生命周期实例，行为不变。
    #[allow(clippy::new_without_default)]
    pub fn new(lifecycle: Arc<SidecarLifecycle>) -> Self {
        let tasks = Arc::new(TaskManager::default());
        let scheduler = Arc::new(TaskScheduler::new(tasks.clone()));
        let python = Arc::new(PythonRuntime::new(lifecycle));
        let agent = Arc::new(AgentRuntime::new(python.ipc().client().clone()));
        // 注册序即启动序；关闭按逆序：Agent 先停，Python 最后停。
        let components: Vec<Arc<dyn Component>> = vec![python.clone(), agent.clone()];
        Self {
            state: RwLock::new(RuntimeState::Starting),
            python,
            agent,
            tasks,
            scheduler,
            components,
            shutdown_started: AtomicBool::new(false),
        }
    }

    /// 当前 Runtime 状态。
    pub fn state(&self) -> RuntimeState {
        *self.state.read().expect("runtime state lock")
    }

    /// 暴露任务管理器（供业务调度器接入：获得生命周期观测与关闭取消）。
    pub fn tasks(&self) -> &Arc<TaskManager> {
        &self.tasks
    }

    /// 暴露 Agent Runtime（编排生命周期控制面）。
    pub fn agent(&self) -> &Arc<AgentRuntime> {
        &self.agent
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
    /// Sidecar 运行时快照每 10s 同步一次，避免高频 IPC 刷日志。
    pub fn spawn_observation_loop(self: &Arc<Self>) {
        let supervisor = Arc::clone(self);
        tauri::async_runtime::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_secs(1));
            let mut last_snapshot = Instant::now();
            const SNAPSHOT_INTERVAL: Duration = Duration::from_secs(10);
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
                } else if last_snapshot.elapsed() >= SNAPSHOT_INTERVAL {
                    last_snapshot = Instant::now();
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
    ///
    /// 顺序：取消全部任务 → 按注册序逆序停止组件（每步限时 [`STOP_TIMEOUT`]）。
    pub async fn shutdown(&self) {
        if self.shutdown_started.swap(true, Ordering::SeqCst) {
            return;
        }
        self.set_state(RuntimeState::ShuttingDown);
        crate::infrastructure::runtime::mark::phase("runtime", "shutting_down");
        self.scheduler.stop();
        for component in self.components.iter().rev() {
            match tokio::time::timeout(STOP_TIMEOUT, component.stop()).await {
                Ok(Ok(())) => {}
                Ok(Err(error)) => error!(component = component.id(), %error, "组件停止失败"),
                Err(_elapsed) => {
                    warn!(target: RUNTIME_TARGET, component = component.id(), "[runtime] component.stop.timeout")
                }
            }
        }
        self.set_state(RuntimeState::Stopped);
        crate::infrastructure::runtime::mark::phase("runtime", "stopped");
    }

    fn set_state(&self, new: RuntimeState) {
        let mut guard = self.state.write().expect("runtime state lock");
        if *guard != new {
            *guard = new;
        }
    }
}
// Runtime 生命周期状态机（原 runtime/state.rs）。

use serde::Serialize;

/// 应用 Runtime 全局生命周期状态。
///
/// 由 [`super::supervisor::RuntimeSupervisor`] 持有并驱动；
/// 前端通过未来 IPC 感知 `runtime state`。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RuntimeState {
    /// 进程启动、组件装配中。
    Starting,
    /// 依赖（Sidecar / Agent）初始化中。
    Initializing,
    /// 核心依赖就绪，业务未开始。
    Ready,
    /// 业务运行中（后台任务调度等）。
    Running,
    /// 已进入关闭流程。
    ShuttingDown,
    /// 关闭完成。
    Stopped,
    /// 初始化或运行失败。
    Failed,
}

impl RuntimeState {
    /// `[runtime]` 日志用状态名（snake_case）。
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Starting => "starting",
            Self::Initializing => "initializing",
            Self::Ready => "ready",
            Self::Running => "running",
            Self::ShuttingDown => "shutting_down",
            Self::Stopped => "stopped",
            Self::Failed => "failed",
        }
    }
}

#[cfg(test)]
mod tests {
    use super::RuntimeState;

    #[test]
    fn as_str_uses_snake_case() {
        let cases = [
            (RuntimeState::Starting, "starting"),
            (RuntimeState::Initializing, "initializing"),
            (RuntimeState::Ready, "ready"),
            (RuntimeState::Running, "running"),
            (RuntimeState::ShuttingDown, "shutting_down"),
            (RuntimeState::Stopped, "stopped"),
            (RuntimeState::Failed, "failed"),
        ];
        for (state, expected) in cases {
            assert_eq!(state.as_str(), expected);
        }
    }
}
