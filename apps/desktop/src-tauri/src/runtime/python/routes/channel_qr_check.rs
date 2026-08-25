//! Sidecar route binding: /v1/channel/qr_check (POST)

use common::contracts::{ChannelSidecarQrCheckRequest, ChannelSidecarQrCheckResponse};

use infra::sidecar::client::{SidecarClient, SidecarClientError};

pub async fn call(
    client: &SidecarClient,
    request: ChannelSidecarQrCheckRequest,
) -> Result<ChannelSidecarQrCheckResponse, SidecarClientError> {
    client.post_json("/v1/channel/qr_check", &request).await
}
