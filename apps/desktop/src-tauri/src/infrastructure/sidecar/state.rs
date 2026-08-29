//! Python Runtime 生命周期状态。

use std::sync::RwLock;

use serde::Serialize;

/// Python Runtime 生命周期状态。
///
/// 进程操作本身见 [`super::process`]；本模块只负责状态机。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PythonState {
    /// 未启动。
    #[default]
    Stopped,
    /// 启动中。
    Starting,
    /// 就绪（健康检查通过）。
    Ready,
    /// 业务运行中。
    Running,
    /// 停止中。
    Stopping,
    /// 启动失败。
    Failed,
    /// 运行中异常退出。
    Crashed,
    /// 重启中。
    Restarting,
}

impl PythonState {
    /// `[runtime]` 日志用状态名（snake_case）。
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Stopped => "stopped",
            Self::Starting => "starting",
            Self::Ready => "ready",
            Self::Running => "running",
            Self::Stopping => "stopping",
            Self::Failed => "failed",
            Self::Crashed => "crashed",
            Self::Restarting => "restarting",
        }
    }
}

/// Python 生命周期状态机 — 仅状态持有与转移；进程操作见 [`super::process`]。
#[derive(Default)]
pub struct PythonLifecycle {
    state: RwLock<PythonState>,
}

impl PythonLifecycle {
    /// 当前状态。
    pub fn state(&self) -> PythonState {
        *self.state.read().expect("python state lock")
    }

    /// 转移状态（幂等；仅记录状态，日志由调用方负责）。
    pub fn set(&self, new: PythonState) {
        let previous = *self.state.read().expect("python state lock");
        if previous != new {
            *self.state.write().expect("python state lock") = new;
            crate::infrastructure::runtime::lifecycle_recorder::record_state_change(
                "python",
                previous.as_str(),
                new.as_str(),
                None,
                None,
                None,
            );
        }
    }
}
