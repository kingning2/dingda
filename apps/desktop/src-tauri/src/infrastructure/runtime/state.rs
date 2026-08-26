//! Runtime 生命周期状态机。

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
