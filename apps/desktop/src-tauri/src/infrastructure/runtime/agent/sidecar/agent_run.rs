//! Sidecar route: /v1/agent/run/* — 可控 graph run。

use crate::contracts::contracts::{
    AgentSidecarRunCancelRequest, AgentSidecarRunCancelResponse, AgentSidecarRunControlRequest,
    AgentSidecarRunControlResponse, AgentSidecarRunStartRequest, AgentSidecarRunStartResponse,
    AgentSidecarRunStatusRequest, AgentSidecarRunStatusResponse,
};

use crate::infrastructure::runtime::python::client::{SidecarClient, SidecarClientError};

pub async fn start(
    client: &SidecarClient,
    request: &AgentSidecarRunStartRequest,
) -> Result<AgentSidecarRunStartResponse, SidecarClientError> {
    client.post_json("/v1/agent/run/start", request).await
}

pub async fn control(
    client: &SidecarClient,
    request: &AgentSidecarRunControlRequest,
) -> Result<AgentSidecarRunControlResponse, SidecarClientError> {
    client.post_json("/v1/agent/run/control", request).await
}

pub async fn status(
    client: &SidecarClient,
    request: &AgentSidecarRunStatusRequest,
) -> Result<AgentSidecarRunStatusResponse, SidecarClientError> {
    client.post_json("/v1/agent/run/status", request).await
}

pub async fn cancel(
    client: &SidecarClient,
    request: &AgentSidecarRunCancelRequest,
) -> Result<AgentSidecarRunCancelResponse, SidecarClientError> {
    client.post_json("/v1/agent/run/cancel", request).await
}
