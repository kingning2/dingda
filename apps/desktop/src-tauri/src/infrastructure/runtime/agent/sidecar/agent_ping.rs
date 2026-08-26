//! Sidecar route binding: /v1/agent/ping (POST)

use crate::contracts::contracts::{AgentSidecarPingRequest, AgentSidecarPingResponse};
use crate::infrastructure::runtime::python::client::{SidecarClient, SidecarClientError};

pub async fn call(
    client: &SidecarClient,
    request: AgentSidecarPingRequest,
) -> Result<AgentSidecarPingResponse, SidecarClientError> {
    client.post_json("/v1/agent/ping", &request).await
}
