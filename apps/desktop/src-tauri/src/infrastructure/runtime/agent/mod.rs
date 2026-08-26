//! Agent Runtime — 生命周期状态机 / 管理 / 状态定义 / 落库。

pub mod gateway;
pub mod lifecycle;
pub mod manager;
pub mod models;
pub mod sidecar;
pub mod state;
pub mod store;

pub use gateway::RuntimeAgentSidecar;
pub use manager::{observe_run, AgentRuntime};
pub use state::AgentState;
pub use store::{AgentRunRecord, AgentRunStore, AgentStepRecord};
