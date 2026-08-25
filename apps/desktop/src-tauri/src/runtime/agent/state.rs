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
            Self::Stopping => "stopping",
            Self::Failed => "failed",
        }
    }
}
