//! Sidecar route binding: /v1/channel/search (POST)

use crate::contracts::contracts::{ChannelSidecarSearchRequest, ChannelSidecarSearchResponse};

use super::super::client::{SidecarClient, SidecarClientError};

pub async fn call(
    client: &SidecarClient,
    request: ChannelSidecarSearchRequest,
) -> Result<ChannelSidecarSearchResponse, SidecarClientError> {
    client.post_json("/v1/channel/search", &request).await
}
