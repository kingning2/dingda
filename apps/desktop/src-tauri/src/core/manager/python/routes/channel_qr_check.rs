//! Sidecar route binding: /v1/channel/qr_check (POST)

use crate::contracts::contracts::{ChannelSidecarQrCheckRequest, ChannelSidecarQrCheckResponse};

use super::super::client::{SidecarClient, SidecarClientError};

pub async fn call(
    client: &SidecarClient,
    request: ChannelSidecarQrCheckRequest,
) -> Result<ChannelSidecarQrCheckResponse, SidecarClientError> {
    client.post_json("/v1/channel/qr_check", &request).await
}
