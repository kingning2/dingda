//! Agent 状态定义。

use serde::Serialize;

/// Agent Runtime 状态。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AgentState {
    /// 未启动 / 已停止。
    #[default]
    Stopped,
    /// 启动中。
    Starting,
    /// 就绪。
    Ready,
    /// 运行中。
    Running,
    /// 图运行暂停。
    Paused,
    /// 等待网络恢复。
    WaitingNetwork,
    /// 停止中。
    Stopping,
    /// 失败。
    Failed,
}

impl AgentState {
    /// `[runtime]` 日志用状态名（snake_case）。
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Stopped => "stopped",
            Self::Starting => "starting",
            Self::Ready => "ready",
            Self::Running => "running",
            Self::Paused => "paused",
            Self::WaitingNetwork => "waiting_network",
            Self::Stopping => "stopping",
            Self::Failed => "failed",
        }
    }
}
// Agent 生命周期状态机 — 仅状态；业务管理见 [`super::agent_manager`]。

use std::sync::RwLock;

/// Agent 生命周期状态机。
#[derive(Default)]
pub struct AgentLifecycle {
    state: RwLock<AgentState>,
}

impl AgentLifecycle {
    /// 当前状态。
    pub fn state(&self) -> AgentState {
        *self.state.read().expect("agent state lock")
    }

    /// 转移状态（幂等；仅记录状态，日志由调用方负责）。
    pub fn transition(&self, new: AgentState) {
        let previous = *self.state.read().expect("agent state lock");
        if previous != new {
            *self.state.write().expect("agent state lock") = new;
        }
    }
}
