//! Agent Runtime — 生命周期状态机 / 管理 / 状态定义。
//!
//! 当前为最小抽象，不伪造真实 Agent 进程；未来 Python + LangGraph Runtime 接入 [`manager::AgentRuntime`]。

pub mod lifecycle;
pub mod manager;
pub mod state;

pub use manager::AgentRuntime;
pub use state::AgentState;
