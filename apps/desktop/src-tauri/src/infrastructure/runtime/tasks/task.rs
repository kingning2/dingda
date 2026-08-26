//! 任务数据模型。

use chrono::Utc;
use serde::Serialize;

use super::state::{TaskPhase, TaskState};

/// 任务唯一标识。
pub type TaskId = String;

/// 任务种类。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TaskKind {
    /// Agent 任务。
    Agent,
    /// 爬虫任务。
    Crawler,
    /// 比价任务。
    PriceCompare,
    /// 后台任务。
    Background,
    /// 定时任务（由调度器按周期触发）。
    Scheduled,
    /// Cookie 续期任务（浏览器滑块续期）。
    Renew,
}

impl TaskKind {
    /// `[runtime]` 日志用种类名（snake_case）。
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Agent => "agent",
            Self::Crawler => "crawler",
            Self::PriceCompare => "price_compare",
            Self::Background => "background",
            Self::Scheduled => "scheduled",
            Self::Renew => "renew",
        }
    }
}

/// 任务数据模型。
#[derive(Debug, Clone, Serialize)]
pub struct Task {
    id: TaskId,
    kind: TaskKind,
    state: TaskState,
    phase: TaskPhase,
    created_at: i64,
    started_at: Option<i64>,
    finished_at: Option<i64>,
    error: Option<String>,
}

impl Task {
    /// 新建任务（`Created` / `Planning`）。
    pub fn new(id: TaskId, kind: TaskKind) -> Self {
        Self {
            id,
            kind,
            state: TaskState::Created,
            phase: TaskPhase::default(),
            created_at: Utc::now().timestamp_millis(),
            started_at: None,
            finished_at: None,
            error: None,
        }
    }

    /// 任务 id。
    pub fn id(&self) -> &TaskId {
        &self.id
    }

    /// 任务种类。
    pub fn kind(&self) -> TaskKind {
        self.kind
    }

    /// 任务状态。
    pub fn state(&self) -> TaskState {
        self.state
    }

    /// 任务阶段。
    pub fn phase(&self) -> TaskPhase {
        self.phase
    }

    /// 失败原因。
    pub fn error(&self) -> Option<&str> {
        self.error.as_deref()
    }

    /// 转移状态；`Running` 记录 started_at，终态记录 finished_at。
    pub fn set_state(&mut self, state: TaskState) {
        if self.state == state {
            return;
        }
        self.state = state;
        match state {
            TaskState::Running => {
                self.started_at
                    .get_or_insert_with(|| Utc::now().timestamp_millis());
            }
            TaskState::Completed
            | TaskState::Failed
            | TaskState::Cancelled
            | TaskState::Timeout => {
                self.finished_at = Some(Utc::now().timestamp_millis());
            }
            _ => {}
        }
    }

    /// 转移阶段。
    pub fn set_phase(&mut self, phase: TaskPhase) {
        if self.phase == phase {
            return;
        }
        self.phase = phase;
    }

    /// 记录失败原因。
    pub fn set_error(&mut self, error: String) {
        self.error = Some(error);
    }
}
