//! Agent Sidecar 网关 Port。

use crate::contracts::DingDaResult;
use crate::contracts::{AgentSidecarPingRequest, AgentSidecarPingResponse};
use async_trait::async_trait;

/// Agent Sidecar HTTP 网关（由 Python runtime 适配实现）。
#[async_trait]
pub trait AgentSidecarGateway: Send + Sync {
    async fn ping(
        &self,
        request: AgentSidecarPingRequest,
    ) -> DingDaResult<AgentSidecarPingResponse>;
}
