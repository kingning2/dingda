//! Sidecar route binding: /v1/channel/qr_start (POST)

use common::contracts::{ChannelSidecarQrStartRequest, ChannelSidecarQrStartResponse};

use infra::sidecar::client::{SidecarClient, SidecarClientError};

pub async fn call(
    client: &SidecarClient,
    request: ChannelSidecarQrStartRequest,
) -> Result<ChannelSidecarQrStartResponse, SidecarClientError> {
    client.post_json("/v1/channel/qr_start", &request).await
}
