//! Sidecar route binding: /v1/agent/ping (POST)

use common::contracts::{AgentSidecarPingRequest, AgentSidecarPingResponse};

use infra::sidecar::client::{SidecarClient, SidecarClientError};

pub async fn call(
    client: &SidecarClient,
    request: AgentSidecarPingRequest,
) -> Result<AgentSidecarPingResponse, SidecarClientError> {
    client.post_json("/v1/agent/ping", &request).await
}
