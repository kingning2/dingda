//! Agent Runtime 管理 — 组合生命周期状态机；接入 Python LangGraph agent。
//!
//! `start()` 探活 sidecar 内的 `/v1/agent/ping`（真实 agent 编排在 Python 侧）。

use crate::core::manager::python::client::SidecarClient;

use crate::core::manager::RUNTIME_TARGET;

use super::lifecycle::AgentLifecycle;
use super::state::AgentState;

/// Agent Runtime 管理器。
pub struct AgentRuntime {
    lifecycle: AgentLifecycle,
    client: SidecarClient,
}

impl AgentRuntime {
    /// 组装管理器；`client` 指向 sidecar（其中运行 LangGraph agent）。
    #[allow(clippy::new_without_default)]
    pub fn new(client: SidecarClient) -> Self {
        Self {
            lifecycle: AgentLifecycle::default(),
            client,
        }
    }

    /// 当前 Agent 状态。
    pub fn state(&self) -> AgentState {
        self.lifecycle.state()
    }

    /// 启动 Agent — 探活 sidecar 内的 LangGraph agent。
    #[macros::runtime(agent, start = Starting, ok = Ready, err = Failed)]
    pub async fn start(&self) -> Result<(), String> {
        match self
            .client
            .post_json::<serde_json::Value, serde_json::Value>(
                "/v1/agent/ping",
                &serde_json::json!({}),
            )
            .await
        {
            Ok(_) => Ok(()),
            Err(error) => {
                warn!(target: RUNTIME_TARGET, %error, "[runtime] agent.ping.failed");
                Err(error.to_string())
            }
        }
    }

    /// 停止 Agent。
    #[macros::runtime(agent, start = Stopping, ok = Stopped)]
    pub fn stop(&self) {}

    /// 重启 Agent。
    pub async fn restart(&self) {
        self.stop();
        let _ = self.start().await;
    }
}
