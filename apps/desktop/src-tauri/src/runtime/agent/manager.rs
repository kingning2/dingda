//! Agent Runtime 管理 — 组合生命周期状态机；接入 Python LangGraph agent。
//!
//! `start()` 探活 sidecar 内的 `/v1/agent/ping`（真实 agent 编排在 Python 侧）。

use infra::sidecar::client::SidecarClient;

use crate::runtime::RUNTIME_TARGET;

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
    pub async fn start(&self) {
        self.lifecycle.transition(AgentState::Starting);
        info!(target: RUNTIME_TARGET, "[runtime] agent.start");
        let ping = self
            .client
            .post_json::<serde_json::Value, serde_json::Value>(
                "/v1/agent/ping",
                &serde_json::json!({}),
            )
            .await;
        match ping {
            Ok(_) => {
                self.lifecycle.transition(AgentState::Ready);
                info!(target: RUNTIME_TARGET, "[runtime] agent.ready");
            }
            Err(error) => {
                warn!(target: RUNTIME_TARGET, %error, "[runtime] agent.ping.failed");
                self.lifecycle.transition(AgentState::Failed);
            }
        }
    }

    /// 停止 Agent。
    pub fn stop(&self) {
        self.lifecycle.transition(AgentState::Stopping);
        info!(target: RUNTIME_TARGET, "[runtime] agent.stop");
        self.lifecycle.transition(AgentState::Stopped);
    }

    /// 重启 Agent。
    pub async fn restart(&self) {
        self.stop();
        self.start().await;
    }
}
