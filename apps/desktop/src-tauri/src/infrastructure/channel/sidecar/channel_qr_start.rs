//! Sidecar route binding: /v1/channel/qr_start (POST)

use crate::contracts::contracts::{ChannelSidecarQrStartRequest, ChannelSidecarQrStartResponse};

use crate::infrastructure::runtime::python::client::{SidecarClient, SidecarClientError};

pub async fn call(
    client: &SidecarClient,
    request: ChannelSidecarQrStartRequest,
) -> Result<ChannelSidecarQrStartResponse, SidecarClientError> {
    client.post_json("/v1/channel/qr_start", &request).await
}
