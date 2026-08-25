//! Agent sidecar 网关适配器 — 实现 `crate::core::ports::sidecar::AgentSidecarGateway`。
//!
//! 从 `crates/infra` 迁入：Agent 属于应用域，网关随之归 Python runtime。

use crate::contracts::contracts::{AgentSidecarPingRequest, AgentSidecarPingResponse};
use crate::contracts::DingDaResult;
use crate::core::manager::python::client::SidecarClient;
use crate::core::ports::sidecar::AgentSidecarGateway;
use async_trait::async_trait;

use crate::core::manager::python::routes::agent_ping;

pub struct RuntimeAgentSidecar {
    client: SidecarClient,
}

impl RuntimeAgentSidecar {
    pub fn new(client: SidecarClient) -> Self {
        Self { client }
    }
}

#[async_trait]
impl AgentSidecarGateway for RuntimeAgentSidecar {
    async fn ping(
        &self,
        request: AgentSidecarPingRequest,
    ) -> DingDaResult<AgentSidecarPingResponse> {
        agent_ping::call(&self.client, request)
            .await
            .map_err(|error| crate::contracts::DingDaError::Internal(error.to_string()))
    }
}
