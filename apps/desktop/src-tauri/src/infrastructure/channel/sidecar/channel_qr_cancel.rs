//! Sidecar route binding: /v1/channel/qr_cancel (POST)

use crate::contracts::contracts::{ChannelSidecarQrCancelRequest, ChannelSidecarQrCancelResponse};

use crate::infrastructure::runtime::python::client::{SidecarClient, SidecarClientError};

pub async fn call(
    client: &SidecarClient,
    request: ChannelSidecarQrCancelRequest,
) -> Result<ChannelSidecarQrCancelResponse, SidecarClientError> {
    client.post_json("/v1/channel/qr_cancel", &request).await
}
