//! Python Sidecar 适配层 — 进程托管 / 连接 / 健康 / 日志事件 / 业务 RPC。
//!
//! - 进程与状态机：[`process`] / [`state`]
//! - 通信管道与共享内存：[`connection`]
//! - 客户端与 IPC 面：[`client`]
//! - 健康与快照：[`health`]
//! - 日志事件流：[`events`]
//! - 业务 RPC：[`channel_login`] / [`channel_chat`] / [`channel_product`] /
//!   [`agent_task`] / [`agent_probe`]
//! - Agent 运行时：[`agent_manager`] / [`agent_gateway`] / [`agent_models`] /
//!   [`agent_state`] / [`agent_store`]

pub mod agent_gateway;
pub mod agent_manager;
pub mod agent_models;
pub mod agent_probe;
pub mod agent_state;
pub mod agent_store;
pub mod agent_task;
pub mod channel_chat;
pub mod channel_login;
pub mod channel_product;
pub mod client;
pub mod connection;
pub mod copilot_runtime;
pub mod events;
pub mod health;
pub mod process;
pub mod state;

pub use client::{PythonIpc, SidecarClient, SidecarClientError};
pub use health::{PythonHealth, PythonSidecarSnapshot};
pub use process::{
    SidecarConfig, SidecarLifecycle, SidecarLifecycleError, RUNTIME_ERROR_TOPIC,
    SIDECAR_RESTARTED_TOPIC,
};
pub use state::PythonState;

pub use agent_gateway::RuntimeAgentSidecar;
pub use agent_manager::{observe_run, AgentRuntime};
pub use agent_state::AgentState;
pub use agent_store::{AgentRunRecord, AgentRunStore, AgentStepRecord};

use std::sync::{Arc, RwLock};

use crate::infrastructure::runtime::RUNTIME_TARGET;

/// Python Runtime 门面 — 组合状态 / 进程 / IPC / 健康检查。
pub struct PythonRuntime {
    lifecycle: state::PythonLifecycle,
    process: Arc<SidecarLifecycle>,
    health: PythonHealth,
    ipc: PythonIpc,
    snapshot: RwLock<Option<PythonSidecarSnapshot>>,
}

impl PythonRuntime {
    /// 组装 Python Runtime；复用现有 Sidecar 生命周期实例。
    #[allow(clippy::new_without_default)]
    pub fn new(sidecar: Arc<SidecarLifecycle>) -> Self {
        let ipc = PythonIpc::new(sidecar.client().clone());
        Self {
            lifecycle: state::PythonLifecycle::default(),
            process: sidecar.clone(),
            health: PythonHealth::new(sidecar),
            ipc,
            snapshot: RwLock::new(None),
        }
    }

    /// 当前 Python 生命周期状态。
    pub fn state(&self) -> PythonState {
        self.lifecycle.state()
    }

    /// 确保 Sidecar 运行（未运行则拉起，运行中则健康检查通过即返回）。
    #[macros::runtime(python, start = Starting, ok = Ready, err = Failed)]
    pub async fn ensure_running(&self) -> Result<(), SidecarLifecycleError> {
        self.process.ensure_running().await
    }

    /// 停止 Sidecar（幂等）。
    #[macros::runtime(python, start = Stopping, ok = Stopped)]
    pub async fn stop(&self) -> Result<(), SidecarLifecycleError> {
        self.process.stop().await
    }

    /// 重启 Sidecar（先停后拉）。
    #[macros::runtime(python, start = Restarting, ok = Ready)]
    pub async fn restart(&self) -> Result<(), SidecarLifecycleError> {
        self.process.restart().await
    }

    /// 健康检查。
    pub async fn health_check(&self) -> Result<bool, SidecarLifecycleError> {
        self.health.health_check().await
    }

    /// 子进程是否已退出（供 watchdog 崩溃恢复判定）。
    pub async fn is_child_exited(&self) -> bool {
        self.process.is_child_exited().await
    }

    /// Rust ↔ Python IPC 面。
    pub fn ipc(&self) -> &PythonIpc {
        &self.ipc
    }

    /// 最近一次 Sidecar 快照（由 [`Self::sync_snapshot`] 更新）。
    pub fn snapshot(&self) -> Option<PythonSidecarSnapshot> {
        self.snapshot.read().expect("python snapshot lock").clone()
    }

    /// 从 Sidecar 拉取运行时快照并更新本地缓存 / 生命周期状态。
    pub async fn sync_snapshot(&self) -> Option<PythonSidecarSnapshot> {
        if !self.process.health_check().await.unwrap_or(false) {
            self.lifecycle.set(PythonState::Crashed);
            return None;
        }

        match health::fetch(self.ipc.client()).await {
            Ok(snap) => {
                self.apply_snapshot(&snap);
                *self.snapshot.write().expect("python snapshot lock") = Some(snap.clone());
                Some(snap)
            }
            Err(error) => {
                warn!(target: RUNTIME_TARGET, %error, "[runtime] python.snapshot.failed");
                None
            }
        }
    }

    /// 根据 Sidecar 快照调和 Rust 侧 Python 生命周期状态。
    fn apply_snapshot(&self, snap: &PythonSidecarSnapshot) {
        let current = self.lifecycle.state();
        if matches!(
            current,
            PythonState::Stopping | PythonState::Stopped | PythonState::Restarting
        ) {
            return;
        }

        let next = match snap.state.as_str() {
            "starting" => PythonState::Starting,
            "stopping" => PythonState::Stopping,
            "stopped" => PythonState::Stopped,
            "running" if snap.has_active_work() => PythonState::Running,
            "running" | "ready" => PythonState::Ready,
            other if snap.has_active_work() => {
                warn!(
                    target: RUNTIME_TARGET,
                    sidecar_state = %other,
                    "[runtime] python.active_work unknown_state"
                );
                PythonState::Running
            }
            _ => PythonState::Ready,
        };

        if current != next {
            self.lifecycle.set(next);
            info!(
                target: RUNTIME_TARGET,
                previous = %current.as_str(),
                next = %next.as_str(),
                active_ops = snap.active_ops.len(),
                "[runtime] python.state.sync"
            );
        }
    }
}

/// Python Sidecar 作为受管组件接入 [`crate::core::RuntimeSupervisor`]。
#[async_trait::async_trait]
impl crate::core::lifecycle::Component for PythonRuntime {
    fn id(&self) -> &'static str {
        "python-sidecar"
    }

    fn state(&self) -> crate::core::lifecycle::ComponentState {
        match self.state() {
            PythonState::Stopped => crate::contracts::RuntimeComponentState::Stopped,
            PythonState::Starting | PythonState::Restarting => {
                crate::contracts::RuntimeComponentState::Starting
            }
            PythonState::Ready | PythonState::Running => {
                crate::contracts::RuntimeComponentState::Running
            }
            PythonState::Stopping => crate::contracts::RuntimeComponentState::Stopping,
            PythonState::Failed | PythonState::Crashed => {
                crate::contracts::RuntimeComponentState::Failed
            }
        }
    }

    async fn start(&self) -> Result<(), String> {
        self.ensure_running()
            .await
            .map_err(|error| error.to_string())
    }

    async fn stop(&self) -> Result<(), String> {
        self.stop().await.map_err(|error| error.to_string())
    }

    async fn health(&self) -> crate::core::lifecycle::HealthReport {
        match self.health_check().await {
            Ok(true) => crate::core::lifecycle::HealthReport::ok(),
            Ok(false) => crate::core::lifecycle::HealthReport::failed("health check failed"),
            Err(error) => crate::core::lifecycle::HealthReport::failed(error.to_string()),
        }
    }
}
