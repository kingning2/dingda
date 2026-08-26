//! Sidecar: POST /v1/channel/xianyu/seller_items

use serde::{Deserialize, Serialize};

use crate::infrastructure::runtime::python::client::{SidecarClient, SidecarClientError};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SellerItemsRequest {
    pub cookie: String,
    pub user_id: String,
    #[serde(default)]
    pub max_pages: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlatformItemDto {
    pub item_id: String,
    pub title: String,
    pub price: f64,
    #[serde(default)]
    pub desc: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SellerItemsResponse {
    pub ok: bool,
    #[serde(default)]
    pub items: Vec<PlatformItemDto>,
    #[serde(default)]
    pub cookie: Option<String>,
    #[serde(default)]
    pub message: Option<String>,
}

pub async fn call(
    client: &SidecarClient,
    request: SellerItemsRequest,
) -> Result<SellerItemsResponse, SidecarClientError> {
    client
        .post_json("/v1/channel/xianyu/seller_items", &request)
        .await
}
