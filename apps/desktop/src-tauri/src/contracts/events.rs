//! 应用级事件模型与统一 emit 入口。
//!
//! 负责：
//! - [`AppEvent`]：消息 / 账号 / 任务状态变更
//! - [`EventSink`]：事件下发 Port（由 `kernel::InMemoryEventBus` 等在壳层实现）
//! - [`emit`]：序列化并发布到对应 topic
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

use crate::contracts::errors::DingDaError;
use crate::contracts::ChannelMessage;
use crate::contracts::DingDaResult;
use serde::{Deserialize, Serialize};

/// 应用事件 topic 前缀。
pub const TOPIC_MESSAGE: &str = "app/message";
/// 账号变更 topic。
pub const TOPIC_ACCOUNT: &str = "app/account";
/// 任务状态 topic。
pub const TOPIC_TASK: &str = "app/task";
/// 渠道消息 topic（入站/出站消息 + 建议）。
pub const TOPIC_CHANNEL_MESSAGE: &str = "channel/message";
/// 渠道连接状态 topic。
pub const TOPIC_CHANNEL_STATUS: &str = "channel/status";
/// Agent graph 运行进度 topic。
pub const TOPIC_AGENT_PROGRESS: &str = "app/agent/progress";

/// 应用级事件 — 涵盖消息、账号、后台任务状态。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "category", rename_all = "snake_case")]
pub enum AppEvent {
    /// 渠道消息相关。
    Message(MessageEvent),
    /// 账号 CRUD / 状态变更。
    Account(AccountEvent),
    /// 后台任务生命周期。
    Task(TaskEvent),
    /// 渠道消息推送（入站/出站 + 建议回复）。
    ChannelMessage(ChannelMessageEvent),
    /// 渠道连接状态变更。
    ChannelStatus(ChannelStatusEvent),
    /// Agent / LangGraph 运行逐步进度。
    AgentProgress(AgentProgressEvent),
}

/// 消息类事件载荷。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MessageEvent {
    /// 所属账号 ID。
    pub account_id: String,
    /// 会话 ID。
    pub conversation_id: String,
    /// 消息体（与 IPC 契约一致）。
    pub message: ChannelMessage,
    /// 变更动作。
    pub action: MessageAction,
}

/// 消息事件动作。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum MessageAction {
    /// 收到入站消息。
    Received,
    /// 出站消息已发送。
    Sent,
    /// 消息内容或状态更新。
    Updated,
}

/// 账号类事件载荷。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccountEvent {
    /// 租户 / 用户 ID。
    pub owner_id: i64,
    /// 账号 ID。
    pub account_id: String,
    /// 展示名（可选，便于 UI 订阅方直接展示）。
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub display_name: String,
    /// 变更动作。
    pub action: AccountAction,
}

/// 账号事件动作。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum AccountAction {
    /// 新建账号。
    Created,
    /// 字段更新。
    Updated,
    /// 启用 / 禁用等状态切换。
    StatusChanged {
        /// 旧状态（如 `active`）。
        from: String,
        /// 新状态（如 `disabled`）。
        to: String,
    },
    /// 删除账号。
    Deleted,
}

/// 任务类事件载荷。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskEvent {
    /// 任务 ID（调度器分配）。
    pub task_id: u64,
    /// 任务名称（如 `batch_publish`）。
    pub name: String,
    /// 关联账号（可选）。
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub account_id: Option<String>,
    /// 变更动作。
    pub action: TaskAction,
}

/// 任务事件动作。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum TaskAction {
    /// 任务已开始执行。
    Started,
    /// 进度更新（0–100）。
    Progress {
        /// 完成百分比。
        percent: u8,
    },
    /// 任务成功结束。
    Completed,
    /// 任务失败。
    Failed {
        /// 失败原因。
        reason: String,
    },
    /// 任务被取消。
    Cancelled,
}

/// 渠道消息推送载荷 — 替代原 `ChannelEventMessage` 契约。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChannelMessageEvent {
    /// 所属账号 ID。
    pub account_id: String,
    /// 消息体。
    pub message: ChannelMessage,
    /// AI 建议回复（仅提示，不自动发送）。
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub suggestion: Option<String>,
}

/// 渠道连接状态变更载荷。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChannelStatusEvent {
    /// 账号 ID。
    pub account_id: String,
    /// 连接状态（`connected` / `disconnected` / `connecting` / `error`）。
    pub state: String,
    /// 补充信息（错误详情等）。
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub detail: Option<String>,
}

/// Agent graph 运行逐步进度。
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AgentProgressEvent {
    pub run_id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub step_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub node: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub index: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub total: Option<i64>,
    pub status: String,
    pub message: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub detail: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error_kind: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub account_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub content: Option<String>,
}

impl AppEvent {
    /// 返回事件应发布到的 topic。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    pub fn topic(&self) -> &'static str {
        match self {
            AppEvent::Message(_) => TOPIC_MESSAGE,
            AppEvent::Account(_) => TOPIC_ACCOUNT,
            AppEvent::Task(_) => TOPIC_TASK,
            AppEvent::ChannelMessage(_) => TOPIC_CHANNEL_MESSAGE,
            AppEvent::ChannelStatus(_) => TOPIC_CHANNEL_STATUS,
            AppEvent::AgentProgress(_) => TOPIC_AGENT_PROGRESS,
        }
    }
}

/// 事件下发 Port — 由进程内 EventBus 等实现。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
pub trait EventSink: Send + Sync {
    /// 向指定 topic 发布原始 JSON 载荷。
    ///
    /// # 参数
    /// - `topic` — 订阅主题
    /// - `payload` — 已序列化的 JSON 字节
    fn publish(&self, topic: &str, payload: &[u8]) -> DingDaResult<()>;
}

/// 统一 emit：序列化 [`AppEvent`] 并发布到对应 topic。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
///
/// # 参数
/// - `sink` — 事件总线或 Tauri Emitter 适配器
/// - `event` — 待广播的应用事件
///
/// # 返回值
/// 成功返回 `()`；序列化或发布失败返回 [`DingDaError`]。
///
/// # 示例
/// ```ignore
/// use crate::contracts::events::{emit, AppEvent, MessageAction, MessageEvent};
/// emit(&event_bus, &AppEvent::Message(MessageEvent { /* ... */ }))?;
/// ```
pub fn emit(sink: &dyn EventSink, event: &AppEvent) -> DingDaResult<()> {
    let payload = serde_json::to_vec(event).map_err(|error| {
        DingDaError::Serialization(format!("AppEvent serialize failed: {error}"))
    })?;
    sink.publish(event.topic(), &payload)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Arc, Mutex};

    type Records = Arc<Mutex<Vec<(String, Vec<u8>)>>>;

    struct RecordingSink {
        records: Records,
    }

    impl EventSink for RecordingSink {
        fn publish(&self, topic: &str, payload: &[u8]) -> DingDaResult<()> {
            self.records
                .lock()
                .map_err(|error| DingDaError::Internal(error.to_string()))?
                .push((topic.to_string(), payload.to_vec()));
            Ok(())
        }
    }

    #[test]
    fn emit_routes_message_topic() {
        let records = Arc::new(Mutex::new(Vec::new()));
        let sink = RecordingSink {
            records: records.clone(),
        };
        let event = AppEvent::Account(AccountEvent {
            owner_id: 1,
            account_id: "acc-1".to_string(),
            display_name: String::new(),
            action: AccountAction::Created,
        });
        emit(&sink, &event).expect("emit");
        let stored = records.lock().expect("lock");
        assert_eq!(stored[0].0, TOPIC_ACCOUNT);
    }
}
