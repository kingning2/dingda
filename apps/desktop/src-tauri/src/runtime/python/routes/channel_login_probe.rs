//! Sidecar route binding: /v1/channel/login_probe (POST)

use common::contracts::{ChannelSidecarLoginProbeRequest, ChannelSidecarLoginProbeResponse};

use infra::sidecar::client::{SidecarClient, SidecarClientError};

pub async fn call(
    client: &SidecarClient,
    request: ChannelSidecarLoginProbeRequest,
) -> Result<ChannelSidecarLoginProbeResponse, SidecarClientError> {
    client.post_json("/v1/channel/login_probe", &request).await
}
