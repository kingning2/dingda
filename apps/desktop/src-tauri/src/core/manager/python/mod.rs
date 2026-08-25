//! Python Runtime — 生命周期状态 / 进程 / IPC / 健康检查。

pub mod agent_gateway;
pub mod client;
pub mod health;
pub mod ipc;
pub mod lifecycle;
pub mod log_pipe;
pub mod pipe_ipc;
pub mod process;
pub mod routes;
pub mod shm;
pub mod snapshot;
pub mod wss_bridge;

pub use agent_gateway::RuntimeAgentSidecar;
pub use client::{SidecarClient, SidecarClientError};
pub use lifecycle::PythonState;
pub use process::{
    SidecarConfig, SidecarLifecycle, SidecarLifecycleError, RUNTIME_ERROR_TOPIC,
    SIDECAR_RESTARTED_TOPIC,
};
pub use snapshot::PythonSidecarSnapshot;
pub use wss_bridge::PythonWssBridge;

use std::sync::{Arc, RwLock};

use crate::core::manager::RUNTIME_TARGET;

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
    snapshot: RwLock<Option<PythonSidecarSnapshot>>,
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

        match routes::runtime_status::fetch(self.ipc.client()).await {
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
