//! Sidecar: POST /v1/channel/xianyu/item_detail

use serde::{Deserialize, Serialize};

use super::super::client::{SidecarClient, SidecarClientError};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ItemDetailRequest {
    pub cookie: String,
    pub item_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlatformItemDetailDto {
    pub item_id: String,
    pub title: String,
    pub desc: String,
    pub price: f64,
    pub original_price: Option<f64>,
    #[serde(default)]
    pub images: Vec<String>,
    pub want_count: Option<u32>,
    pub browse_count: Option<u32>,
    pub item_url: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ItemDetailResponse {
    pub ok: bool,
    #[serde(default)]
    pub detail: Option<PlatformItemDetailDto>,
    #[serde(default)]
    pub cookie: Option<String>,
    #[serde(default)]
    pub message: Option<String>,
}

pub async fn call(
    client: &SidecarClient,
    request: ItemDetailRequest,
) -> Result<ItemDetailResponse, SidecarClientError> {
    client
        .post_json("/v1/channel/xianyu/item_detail", &request)
        .await
}
