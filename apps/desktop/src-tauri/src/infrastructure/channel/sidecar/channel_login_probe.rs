//! Sidecar route binding: /v1/channel/login_probe (POST)

use crate::contracts::contracts::{
    ChannelSidecarLoginProbeRequest, ChannelSidecarLoginProbeResponse,
};

use crate::infrastructure::runtime::python::client::{SidecarClient, SidecarClientError};

pub async fn call(
    client: &SidecarClient,
    request: ChannelSidecarLoginProbeRequest,
) -> Result<ChannelSidecarLoginProbeResponse, SidecarClientError> {
    client.post_json("/v1/channel/login_probe", &request).await
}
