use serde::{Deserialize, Serialize};
use serde_json::Value;

/// 统一 Agent 事件 — 前端只消费此类型，不解析原始 CLI stdout。
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "camelCase")]
pub enum AgentEvent {
    RunStarted {
        runtime_id: String,
        run_id: String,
    },
    TextDelta {
        text: String,
    },
    Thinking {
        text: String,
    },
    ToolCall {
        id: String,
        name: String,
        input: Value,
    },
    ToolResult {
        id: String,
        output: Value,
    },
    FileChanged {
        path: String,
    },
    /// CLI 会话 id，供下次 `--session` / resume 续聊。
    Session {
        session_id: String,
    },
    Error {
        message: String,
    },
    RunCompleted {
        exit_code: i32,
    },
}

/// Tauri 推送包装 — 前端按 `run_id` 过滤。
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AgentEventEnvelope {
    pub run_id: String,
    #[serde(flatten)]
    pub event: AgentEvent,
}

/// Stream Parser trait — 各 CLI 适配器实现。
pub trait StreamParser: Send {
    fn feed(&mut self, chunk: &str) -> Vec<AgentEvent>;
    fn finish(&mut self) -> Vec<AgentEvent> {
        Vec::new()
    }
}
