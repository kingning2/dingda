//! Sidecar route binding: /v1/channel/login_probe (POST)

use crate::contracts::contracts::{
    ChannelSidecarLoginProbeRequest, ChannelSidecarLoginProbeResponse,
};

use super::super::client::{SidecarClient, SidecarClientError};

pub async fn call(
    client: &SidecarClient,
    request: ChannelSidecarLoginProbeRequest,
) -> Result<ChannelSidecarLoginProbeResponse, SidecarClientError> {
    client.post_json("/v1/channel/login_probe", &request).await
}
