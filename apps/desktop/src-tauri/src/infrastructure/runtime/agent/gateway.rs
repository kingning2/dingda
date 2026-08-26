//! Agent sidecar 网关适配器 — 实现 `crate::ports::sidecar::AgentSidecarGateway`。
//!
//! Agent 网关：经 SidecarClient 调用 sidecar `/v1/agent/*`。

use crate::contracts::contracts::{AgentSidecarPingRequest, AgentSidecarPingResponse};
use crate::contracts::DingDaResult;
use crate::infrastructure::runtime::python::client::SidecarClient;
use crate::ports::sidecar::AgentSidecarGateway;
use async_trait::async_trait;

use crate::infrastructure::runtime::agent::sidecar::agent_ping;

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
