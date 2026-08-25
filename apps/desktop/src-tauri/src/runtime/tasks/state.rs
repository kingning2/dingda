//! 任务状态与阶段定义 — `TaskState` 与 `TaskPhase` 是两个不同概念。
//!
//! 例如：`state = RUNNING`、`phase = SEARCHING_XIANYU`。

use serde::Serialize;

/// 任务生命周期状态。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TaskState {
    /// 已创建，未入队。
    #[default]
    Created,
    /// 已入队，等待执行。
    Queued,
    /// 执行中。
    Running,
    /// 成功完成。
    Completed,
    /// 失败。
    Failed,
    /// 已取消。
    Cancelled,
    /// 超时。
    Timeout,
}

impl TaskState {
    /// `[runtime]` 日志用状态名（snake_case）。
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Created => "created",
            Self::Queued => "queued",
            Self::Running => "running",
            Self::Completed => "completed",
            Self::Failed => "failed",
            Self::Cancelled => "cancelled",
            Self::Timeout => "timeout",
        }
    }
}

/// 任务执行阶段（业务进度；与 `TaskState` 正交）。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TaskPhase {
    /// 规划中。
    #[default]
    Planning,
    /// 搜索闲鱼。
    SearchingXianyu,
    /// 搜索 1688。
    SearchingAlibaba,
    /// 归一化。
    Normalizing,
    /// 匹配。
    Matching,
    /// 分析。
    Analyzing,
    /// 收尾。
    Finalizing,
}

impl TaskPhase {
    /// `[runtime]` 日志用阶段名（snake_case）。
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Planning => "planning",
            Self::SearchingXianyu => "searching_xianyu",
            Self::SearchingAlibaba => "searching_alibaba",
            Self::Normalizing => "normalizing",
            Self::Matching => "matching",
            Self::Analyzing => "analyzing",
            Self::Finalizing => "finalizing",
        }
    }
}
