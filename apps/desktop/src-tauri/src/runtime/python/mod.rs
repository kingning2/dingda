//! Python Runtime — 生命周期状态 / 进程 / IPC / 健康检查。

pub mod agent_gateway;
pub mod health;
pub mod ipc;
pub mod lifecycle;
pub mod process;
pub mod routes;

pub use agent_gateway::RuntimeAgentSidecar;
pub use lifecycle::PythonState;
pub use process::{
    SidecarConfig, SidecarLifecycle, SidecarLifecycleError, RUNTIME_ERROR_TOPIC,
    SIDECAR_RESTARTED_TOPIC,
};

use std::sync::Arc;

use crate::runtime::RUNTIME_TARGET;

use health::PythonHealth;
use ipc::PythonIpc;
use lifecycle::PythonLifecycle;

/// Python Runtime 门面 — 组合状态 / 进程 / IPC / 健康检查。
///
/// 进程管理本体即 [`SidecarLifecycle`]（已迁入本目录），行为不变；
/// 本模块按职责拆分出状态、进程、IPC、健康四个层面。
pub struct PythonRuntime {
    lifecycle: PythonLifecycle,
    process: Arc<SidecarLifecycle>,
    health: PythonHealth,
    ipc: PythonIpc,
}

impl PythonRuntime {
    /// 组装 Python Runtime；复用现有 Sidecar 生命周期实例。
    #[allow(clippy::new_without_default)]
    pub fn new(sidecar: Arc<SidecarLifecycle>) -> Self {
        let ipc = PythonIpc::new(sidecar.client().clone());
        Self {
            lifecycle: PythonLifecycle::default(),
            process: sidecar.clone(),
            health: PythonHealth::new(sidecar),
            ipc,
        }
    }

    /// 当前 Python 生命周期状态。
    pub fn state(&self) -> PythonState {
        self.lifecycle.state()
    }

    /// 确保 Sidecar 运行（未运行则拉起，运行中则健康检查通过即返回）。
    pub async fn ensure_running(&self) -> Result<(), SidecarLifecycleError> {
        self.lifecycle.set(PythonState::Starting);
        info!(target: RUNTIME_TARGET, "[runtime] python.start");
        let result = self.process.ensure_running().await;
        match &result {
            Ok(()) => {
                self.lifecycle.set(PythonState::Ready);
                info!(target: RUNTIME_TARGET, "[runtime] python.ready");
            }
            Err(_) => {
                self.lifecycle.set(PythonState::Failed);
                info!(target: RUNTIME_TARGET, "[runtime] python.failed");
            }
        }
        result
    }

    /// 停止 Sidecar（幂等）。
    pub async fn stop(&self) -> Result<(), SidecarLifecycleError> {
        self.lifecycle.set(PythonState::Stopping);
        info!(target: RUNTIME_TARGET, "[runtime] python.stop");
        let result = self.process.stop().await;
        if result.is_ok() {
            self.lifecycle.set(PythonState::Stopped);
        }
        result
    }

    /// 重启 Sidecar（先停后拉）。
    pub async fn restart(&self) -> Result<(), SidecarLifecycleError> {
        self.lifecycle.set(PythonState::Restarting);
        info!(target: RUNTIME_TARGET, "[runtime] python.restart");
        let result = self.process.restart().await;
        if result.is_ok() {
            self.lifecycle.set(PythonState::Ready);
            info!(target: RUNTIME_TARGET, "[runtime] python.ready");
        }
        result
    }

    /// 健康检查。
    pub async fn health_check(&self) -> Result<bool, SidecarLifecycleError> {
        self.health.health_check().await
    }

    /// Rust ↔ Python IPC 面。
    pub fn ipc(&self) -> &PythonIpc {
        &self.ipc
    }
}
